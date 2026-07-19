from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aicomic.providers.readiness import (
    JOB_TYPE_BY_PROVIDER,
    build_env_readiness,
    build_manual_readiness,
    build_provider_item,
    build_provider_next_actions,
    build_report_next_actions,
    build_sample_request,
    count_requests_by_provider,
    item_ready,
    load_optional_json,
)


class TestLoadOptionalJson:
    def test_file_exists(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_text(json.dumps({"key": "val"}), encoding="utf-8")
        assert load_optional_json(path) == {"key": "val"}

    def test_not_exists(self, tmp_path: Path) -> None:
        assert load_optional_json(tmp_path / "missing.json") == {}


class TestCountRequestsByProvider:
    def test_counts(self) -> None:
        reqs = {"requests": [
            {"payload": {"provider": "openai_image"}},
            {"payload": {"provider": "openai_image"}},
            {"payload": {"provider": "sora"}},
            {},  # no payload
        ]}
        assert count_requests_by_provider(reqs) == {"openai_image": 2, "sora": 1}

    def test_empty(self) -> None:
        assert count_requests_by_provider({}) == {}


class TestBuildSampleRequest:
    @pytest.mark.parametrize("provider,job_type,suffix", [
        ("openai_image", "image", "png"),
        ("sora", "video", "mp4"),
        ("openai_tts", "tts", "wav"),
    ])
    def test_suffix(self, provider: str, job_type: str, suffix: str) -> None:
        req = build_sample_request(provider, job_type)
        assert req["request_id"] == f"REQ_READINESS_{provider}"
        assert req["payload"]["output_path"].endswith(f".{suffix}")

    def test_default_suffix(self) -> None:
        req = build_sample_request("unknown", "text")
        assert req["payload"]["output_path"].endswith(".png")


class TestBuildEnvReadiness:
    def test_env_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        result = build_env_readiness("openai_image")
        assert result["ready"] is True
        assert all(item["configured"] for item in result["required_env_status"])

    def test_env_missing(self) -> None:
        os.environ.pop("OPENAI_API_KEY", None)
        result = build_env_readiness("openai_image")
        assert result["ready"] is False

    def test_no_env_required(self) -> None:
        result = build_env_readiness("manual_web")
        assert result["ready"] is True


class TestBuildManualReadiness:
    @pytest.mark.parametrize("provider,expected_ready", [
        ("manual_web", True),
        ("windows_tts", True),
        ("unknown_provider", False),
    ])
    def test_readiness(self, provider: str, expected_ready: bool) -> None:
        assert build_manual_readiness(provider)["ready"] is expected_ready


class TestBuildProviderItem:
    def test_manual_provider(self, tmp_path: Path) -> None:
        result = build_provider_item("manual_web", tmp_path / "providers.yaml", {})
        assert result["provider"] == "manual_web"
        assert result["ready"] is True
        assert result["readiness_status"] == "ready"

    def test_env_provider_no_key(self, tmp_path: Path) -> None:
        os.environ.pop("OPENAI_API_KEY", None)
        result = build_provider_item("openai_image", tmp_path / "providers.yaml", {})
        assert result["ready"] is False
        assert result["readiness_status"] == "setup_required"

    def test_env_provider_with_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        result = build_provider_item("openai_image", tmp_path / "providers.yaml", {})
        assert result["ready"] is True

    def test_local_provider(self, tmp_path: Path) -> None:
        result = build_provider_item("local_comfyui_image", tmp_path / "providers.yaml", {})
        assert result["provider"] == "local_comfyui_image"
        assert result["readiness_status"] == "setup_required"

    def test_with_request_counts(self, tmp_path: Path) -> None:
        result = build_provider_item("manual_web", tmp_path / "providers.yaml", {"manual_web": 3})
        assert result["configured_request_count"] == 3

    def test_windows_tts(self, tmp_path: Path) -> None:
        result = build_provider_item("windows_tts", tmp_path / "providers.yaml", {})
        assert result["provider"] == "windows_tts"
        assert result["ready"] is True


class TestBuildProviderNextActions:
    def test_ready_local(self) -> None:
        actions = build_provider_next_actions("local_comfyui_image", {"ready": True})
        assert any("--confirm-live" in a for a in actions)

    def test_ready_api(self) -> None:
        actions = build_provider_next_actions("openai_image", {"ready": True})
        assert any("--confirm-live" in a for a in actions)

    def test_openai_not_ready(self) -> None:
        actions = build_provider_next_actions("openai_image", {"ready": False})
        assert any("OPENAI_API_KEY" in a for a in actions)

    def test_comfyui_image_workflow(self) -> None:
        actions = build_provider_next_actions("local_comfyui_image", {"ready": False})
        assert any("workflow" in a for a in actions)

    def test_comfyui_video_workflow(self) -> None:
        actions = build_provider_next_actions("local_comfyui_video", {"ready": False})
        assert any("video workflow" in a for a in actions)

    def test_comfyui_models(self) -> None:
        actions = build_provider_next_actions("local_comfyui_image", {"ready": False, "required_models_ready": False})
        assert any("model" in a for a in actions)

    def test_comfyui_server(self) -> None:
        actions = build_provider_next_actions("local_comfyui_image", {"ready": False, "comfyui_server_available": False})
        assert any("Start ComfyUI" in a for a in actions)

    def test_piper_not_ready(self) -> None:
        actions = build_provider_next_actions("local_piper_tts", {"ready": False})
        assert any("Piper" in a for a in actions)

    def test_piper_license_not_known(self) -> None:
        actions = build_provider_next_actions("local_piper_tts", {"ready": False, "license_status": "review_required"})
        assert any("MODEL_CARD" in a for a in actions)

    def test_piper_ready(self) -> None:
        actions = build_provider_next_actions("local_piper_tts", {"ready": True, "license_status": "known"})
        assert any("--confirm-live" in a for a in actions)

    def test_unknown_provider(self) -> None:
        actions = build_provider_next_actions("unknown_provider", {"ready": False})
        assert any("Review" in a for a in actions)

    def test_comfyui_image_fully_ready(self) -> None:
        actions = build_provider_next_actions("local_comfyui_image", {"ready": True, "workflow_api_format": True, "required_models_ready": True, "comfyui_server_available": True})
        assert any("--confirm-live" in a for a in actions)

    def test_comfyui_video_fully_ready(self) -> None:
        actions = build_provider_next_actions("local_comfyui_video", {"ready": True, "workflow_api_format": True, "required_models_ready": True, "comfyui_server_available": True})
        assert any("--confirm-live" in a for a in actions)


class TestItemReady:
    def test_ready(self) -> None:
        assert item_ready({"p1": {"ready": True}}, "p1") is True

    def test_not_ready(self) -> None:
        assert item_ready({"p1": {"ready": False}}, "p1") is False

    def test_missing(self) -> None:
        assert item_ready({"p1": {"ready": True}}, "p2") is False


class TestBuildReportNextActions:
    def test_all_not_ready(self) -> None:
        actions = build_report_next_actions(False, False, False)
        assert len(actions) == 3
        assert any("OpenAI" in a for a in actions)
        assert any("Local core" in a for a in actions)
        assert any("Local video" in a for a in actions)

    def test_all_ready(self) -> None:
        actions = build_report_next_actions(True, True, True)
        assert len(actions) == 1
        assert "All configured" in actions[0]

    def test_core_ready_video_not(self) -> None:
        actions = build_report_next_actions(True, True, False)
        assert len(actions) == 1
        assert "video" in actions[0]
