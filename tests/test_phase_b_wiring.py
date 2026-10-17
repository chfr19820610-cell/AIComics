"""Phase B 接线回归 — 云 Provider 进执行链、cascade 路由、Web mount。"""

from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_CFG = ROOT / "config" / "providers.yaml"

from aicomic.providers.executor import (
    build_provider_request_preview,
    execute_provider_requests,
    perform_provider_request,
)


def _vid_item(provider: str = "kling") -> dict:
    return {
        "request_id": "REQ_j1",
        "request_status": "ready",
        "payload": {
            "job_id": "E01_S01_VID",
            "episode_code": "E01",
            "shot_id": "S01",
            "job_type": "video",
            "provider": provider,
            "prompt": "test",
            "output_path": "state/local_provider_output/E01/video/E01_S01.mp4",
            "duration": 5,
        },
    }


class TestKlingExecutionPath:
    def test_kling_not_skipped_as_unsupported(self, monkeypatch):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        monkeypatch.delenv("KLING_SECRET_KEY", raising=False)
        out = execute_provider_requests(
            {"requests": [_vid_item("kling")]},
            PROVIDERS_CFG,
            dry_run=False,
            confirm_live=False,
        )
        assert out["request_count"] == 1
        assert out["results"][0]["status"] == "blocked_live_confirmation_required"

    def test_kling_dry_run(self, monkeypatch):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        out = execute_provider_requests(
            {"requests": [_vid_item("kling")]}, PROVIDERS_CFG, dry_run=True
        )
        result = out["results"][0]
        assert result["status"] == "dry_run"
        assert result["provider_ready"] is False

    def test_kling_preview_has_preflight(self, monkeypatch):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        preview = build_provider_request_preview(_vid_item("kling"), PROVIDERS_CFG)
        assert "body" in preview
        assert isinstance(preview.get("preflight", {}).get("ready"), bool)

    def test_unknown_provider_still_skipped(self):
        out = execute_provider_requests({"requests": [_vid_item("human")]}, PROVIDERS_CFG)
        assert out["results"][0]["status"] == "skipped_unsupported_provider"

    def test_perform_dispatches_to_iexec(self, monkeypatch):
        monkeypatch.setenv("KLING_ACCESS_KEY", "ak-test")
        monkeypatch.setenv("KLING_SECRET_KEY", "sk-test")
        with patch(
            "aicomic.providers.kling_provider.KlingProvider.execute_request",
            return_value={"status": "succeeded"},
        ):
            out = perform_provider_request(_vid_item("kling"), PROVIDERS_CFG)
        assert out == {"status": "succeeded"}
