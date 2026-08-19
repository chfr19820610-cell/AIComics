"""Coverage gap tests — get_expired_platforms, publish_to_youtube, write_blueprint."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from web.backend.app import app
    return TestClient(app)


class TestGetExpiredPlatforms:
    def test_returns_empty_when_all_valid(self, tmp_path):
        from aicomic.publish.cookie_manager import get_expired_platforms
        import json
        cookie = tmp_path / "douyin.json"
        cookie.write_text(json.dumps([{"name": "sid", "value": "x", "expires": 9999999999}]))
        result = get_expired_platforms({"douyin": cookie})
        assert result == []

    def test_returns_expired_platforms(self, tmp_path):
        from aicomic.publish.cookie_manager import get_expired_platforms
        import json
        expired = tmp_path / "expired.json"
        expired.write_text(json.dumps([{"name": "sid", "value": "x", "expires": 1}]))
        missing = tmp_path / "missing.json"
        result = get_expired_platforms({"douyin": expired, "xhs": missing})
        assert "douyin" in result
        assert "xhs" in result
        assert len(result) == 2


class TestPublishToYouTube:
    def test_no_config_returns_error(self):
        from aicomic.publish.youtube_publisher import publish_to_youtube, YouTubePayload
        payload = YouTubePayload(
            video_path="/tmp/test.mp4",
            title="test",
            description="",
            tags=[],
            privacy="public",
        )
        result = publish_to_youtube(payload, cfg={})
        assert result["success"] is False
        assert result["error"]  # non-empty


class TestWriteBlueprint:
    def test_writes_json_file(self, tmp_path):
        from aicomic.core.template_engine import write_blueprint
        bp = {"hook": "test", "shots": [], "total_shots": 0}
        out = tmp_path / "blueprint.json"
        write_blueprint(out, bp)
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert data["hook"] == "test"


class TestAPIPreviewEndpoint:
    """Ensure /api/templates/{id}/preview has TestClient coverage."""
    def test_preview_endpoint_works(self, client):
        r = client.get("/api/templates/horror/preview")
        assert r.status_code == 200
        data = r.json()
        assert "genre" in data
        assert "acts" in data

    def test_preview_not_found(self, client):
        r = client.get("/api/templates/nonexistent/preview")
        assert r.status_code == 404
