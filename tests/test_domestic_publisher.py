"""Publish platform integration tests.

Tests the domestic platform publisher that delegates to social-auto-upload.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aicomic.publish.domestic_publisher import (
    PublishPayload,
    check_platform_ready,
    load_publish_config,
    publish_to_platforms,
)


class TestPublishConfig:
    def test_load_config_returns_dict(self):
        cfg = load_publish_config()
        assert isinstance(cfg, dict)
        assert "platforms" in cfg

    def test_config_has_three_platforms(self):
        cfg = load_publish_config()
        platforms = cfg["platforms"]
        assert "douyin" in platforms
        assert "xiaohongshu" in platforms
        assert "bilibili" in platforms

    def test_platform_config_has_required_fields(self):
        cfg = load_publish_config()
        for name in ("douyin", "xiaohongshu", "bilibili"):
            p = cfg["platforms"][name]
            assert "cookie_path" in p
            assert "headless" in p


class TestPlatformReadiness:
    def test_disabled_platform_not_ready(self):
        cfg = {"platforms": {"douyin": {"enabled": False, "cookie_path": "/nonexist"}}}
        ready = check_platform_ready("douyin", cfg)
        assert ready["ready"] is False
        assert "disabled" in ready["reason"]

    def test_missing_cookie_not_ready(self):
        cfg = {"platforms": {"douyin": {"enabled": True, "cookie_path": "/nonexist/path.json"}}}
        ready = check_platform_ready("douyin", cfg)
        assert ready["ready"] is False
        assert "cookie" in ready["reason"].lower()

    def test_enabled_with_cookie_ready(self, tmp_path):
        cookie = tmp_path / "cookie.json"
        cookie.write_text('{"cookies": []}')
        cfg = {"platforms": {"douyin": {"enabled": True, "cookie_path": str(cookie)}}}
        ready = check_platform_ready("douyin", cfg)
        assert ready["ready"] is True

    def test_unknown_platform_not_ready(self):
        cfg = {"platforms": {}}
        ready = check_platform_ready("unknown", cfg)
        assert ready["ready"] is False


class TestPublishPayload:
    def test_payload_creation(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        p = PublishPayload(
            video_path=video,
            title="测试标题",
            description="测试描述",
            tags=["#测试"],
        )
        assert p.title == "测试标题"
        assert p.video_path.exists()

    def test_payload_from_publish_pack(self, tmp_path):
        """PublishPayload can be built from a publish_pack dict."""
        video = tmp_path / "ep01.mp4"
        video.write_bytes(b"fake")
        pack = {
            "publish_title": "测试发布标题",
            "description": "测试描述",
            "hashtags": ["#AI漫剧", "#短剧"],
            "platform_copy": {
                "douyin": "抖音文案",
                "xiaohongshu": "小红书文案",
                "bilibili": "B站文案",
            },
        }
        p = PublishPayload.from_publish_pack(pack, video)
        assert p.title == "测试发布标题"
        assert p.tags == ["#AI漫剧", "#短剧"]
        assert p.platform_copy["douyin"] == "抖音文案"


class TestPublishToPlatforms:
    def test_unknown_platform_returns_error(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        payload = PublishPayload(video_path=video, title="test")
        cfg = {"platforms": {}, "social_auto_upload_path": "/nonexist"}
        results = publish_to_platforms(payload, ["unknown"], cfg)
        assert results["unknown"]["success"] is False
        assert "unsupported" in results["unknown"]["error"].lower()

    def test_disabled_platform_skipped(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        payload = PublishPayload(video_path=video, title="test")
        cfg = {"platforms": {"douyin": {"enabled": False, "cookie_path": "/x"}}, "social_auto_upload_path": "/nonexist"}
        results = publish_to_platforms(payload, ["douyin"], cfg)
        assert results["douyin"]["success"] is False
        assert "disabled" in results["douyin"]["error"].lower()

    @patch("aicomic.publish.domestic_publisher._run_sau_upload")
    def test_mock_douyin_upload_success(self, mock_upload, tmp_path):
        """Mock the actual upload — test orchestration logic only."""
        mock_upload.return_value = {"success": True, "platform": "douyin", "url": "https://douyin.com/xxx"}
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        cookie = tmp_path / "cookie.json"
        cookie.write_text('{"cookies": []}')
        payload = PublishPayload(video_path=video, title="test")
        cfg = {"platforms": {"douyin": {"enabled": True, "cookie_path": str(cookie), "headless": True}}, "social_auto_upload_path": "/fake"}
        results = publish_to_platforms(payload, ["douyin"], cfg)
        assert results["douyin"]["success"] is True

    @patch("aicomic.publish.domestic_publisher._run_sau_upload")
    def test_multi_platform_publish(self, mock_upload, tmp_path):
        mock_upload.return_value = {"success": True, "platform": "test", "url": "test"}
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        cookie = tmp_path / "cookie.json"
        cookie.write_text('{"cookies": []}')
        payload = PublishPayload(video_path=video, title="test")
        cfg = {
            "platforms": {
                p: {"enabled": True, "cookie_path": str(cookie), "headless": True}
                for p in ("douyin", "xiaohongshu", "bilibili")
            },
            "social_auto_upload_path": "/fake",
        }
        results = publish_to_platforms(payload, ["douyin", "xiaohongshu", "bilibili"], cfg)
        assert all(results[p]["success"] for p in ("douyin", "xiaohongshu", "bilibili"))

    @patch("aicomic.publish.domestic_publisher._run_sau_upload")
    def test_partial_failure_continues(self, mock_upload, tmp_path):
        """If one platform fails, others should still be attempted."""
        mock_upload.side_effect = [
            {"success": False, "error": "network"},
            {"success": True, "platform": "xiaohongshu"},
        ]
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        cookie = tmp_path / "cookie.json"
        cookie.write_text('{"cookies": []}')
        payload = PublishPayload(video_path=video, title="test")
        cfg = {
            "platforms": {p: {"enabled": True, "cookie_path": str(cookie)} for p in ("douyin", "xiaohongshu")},
            "social_auto_upload_path": "/fake",
        }
        results = publish_to_platforms(payload, ["douyin", "xiaohongshu"], cfg)
        assert results["douyin"]["success"] is False
        assert results["xiaohongshu"]["success"] is True
