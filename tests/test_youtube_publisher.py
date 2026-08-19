"""YouTube Data API v3 publisher tests."""
from __future__ import annotations

import pytest

from aicomic.publish.youtube_publisher import (
    YouTubePayload,
    build_youtube_upload_command,
    check_youtube_ready,
)


class TestYouTubePayload:
    def test_creation(self):
        p = YouTubePayload(
            video_path="/tmp/test.mp4",
            title="测试视频",
            description="描述",
            tags=["tag1", "tag2"],
            privacy="public",
            category_id=22,
        )
        assert p.title == "测试视频"
        assert p.privacy == "public"

    def test_from_publish_pack(self):
        pack = {
            "platform_copy": {
                "youtube": {"title": "YT标题", "description": "YT描述", "tags": ["yt_tag"]}
            }
        }
        p = YouTubePayload.from_publish_pack(pack, video_path="/tmp/v.mp4")
        assert p.title == "YT标题"
        assert p.description == "YT描述"
        assert "yt_tag" in p.tags

    def test_from_pack_fallback_to_generic(self):
        pack = {"titles": {"main": "通用标题"}, "description": "通用描述", "tags": ["t"]}
        p = YouTubePayload.from_publish_pack(pack, video_path="/tmp/v.mp4")
        assert p.title == "通用标题"


class TestCheckYouTubeReady:
    def test_no_credentials_not_ready(self):
        result = check_youtube_ready({})
        assert result["ready"] is False
        assert result["reason"]  # non-empty reason

    def test_with_credentials_ready(self):
        cfg = {"client_secret_path": "/tmp/secret.json", "credentials_path": "/tmp/creds.json"}
        # Mock file existence
        from unittest.mock import patch
        with patch("pathlib.Path.exists", return_value=True):
            result = check_youtube_ready(cfg)
        assert result["ready"] is True


class TestBuildUploadCommand:
    def test_builds_cli_command(self):
        p = YouTubePayload(
            video_path="/tmp/test.mp4",
            title="标题",
            description="描述",
            tags=["t1", "t2"],
            privacy="unlisted",
            category_id=22,
        )
        cmd = build_youtube_upload_command(p, script_path="/tmp/yt_upload.py")
        assert "python" in cmd[0] or "python3" in cmd[0]
        assert "/tmp/yt_upload.py" in cmd[1]
        assert "--title" in cmd
        assert "标题" in cmd
        assert "--privacy" in cmd
        assert "unlisted" in cmd
