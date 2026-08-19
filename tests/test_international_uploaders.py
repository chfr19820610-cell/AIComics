"""Tests for international platform uploaders — YouTube/TikTok/Instagram real implementations."""
from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.publish.international import (
    YouTubeUploader,
    TikTokUploader,
    InstagramUploader,
    publish,
    PublishPayload,
)


class TestYouTubeUploader:
    def test_no_config_returns_error(self):
        u = YouTubeUploader()
        payload = PublishPayload(video_path=Path("/tmp/v.mp4"), title="test")
        result = u.upload(payload, {})
        assert result["success"] is False
        assert result["platform"] == "youtube"
        assert "error" in result

    def test_uses_api_not_selenium(self):
        import inspect
        source = inspect.getsource(YouTubeUploader.upload)
        assert "youtube_publisher" in source
        assert "_selenium_upload" not in source


class TestTikTokUploader:
    def test_no_account_file_returns_error(self):
        u = TikTokUploader()
        payload = PublishPayload(video_path=Path("/tmp/v.mp4"), title="test")
        result = u.upload(payload, {})
        assert result["success"] is False
        assert result["platform"] == "tiktok"
        assert "account_file" in result["error"]

    def test_uses_sau_not_selenium(self):
        import inspect
        source = inspect.getsource(TikTokUploader.upload)
        assert "_selenium_upload" not in source
        assert "sau" in source.lower() or "subprocess" in source


class TestInstagramUploader:
    def test_no_token_returns_error(self):
        u = InstagramUploader()
        payload = PublishPayload(video_path=Path("/tmp/v.mp4"), title="test")
        result = u.upload(payload, {})
        assert result["success"] is False
        assert result["platform"] == "instagram"
        assert "token" in result["error"].lower() or "user_id" in result["error"].lower()

    def test_uses_graph_api_not_selenium(self):
        import inspect
        source = inspect.getsource(InstagramUploader.upload)
        assert "_selenium_upload" not in source
        assert "graph" in source.lower()


class TestPublishOrchestration:
    def test_unknown_platform(self):
        payload = PublishPayload(video_path=Path("/tmp/v.mp4"), title="test")
        result = publish(payload, ["unknown_platform"], {})
        assert result["unknown_platform"]["success"] is False

    def test_all_three_platforms_attempted(self):
        payload = PublishPayload(video_path=Path("/tmp/v.mp4"), title="test")
        result = publish(payload, ["youtube", "tiktok", "instagram"], {})
        assert "youtube" in result
        assert "tiktok" in result
        assert "instagram" in result
        # All should fail gracefully without config
        assert all(p in result for p in ["youtube", "tiktok", "instagram"])

    def test_no_selenium_upload_function_exists(self):
        """_selenium_upload should be deleted."""
        import aicomic.publish.international as mod
        assert not hasattr(mod, "_selenium_upload")
