from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.providers.executor import (
    SUPPORTED_EXECUTION_PROVIDERS,
    build_provider_request_preview,
    execute_provider_requests,
    resolve_provider_ready,
    should_include_provider,
    write_provider_execution_report,
)

_PAYLOAD_BASE = {"job_id": "J1", "provider": "openai_image", "job_type": "image", "prompt": "test"}


class TestShouldIncludeProvider:
    def test_no_filter_includes_all(self) -> None:
        assert should_include_provider("anything", None) is True

    def test_in_filter(self) -> None:
        assert should_include_provider("openai_image", {"openai_image"}) is True

    def test_not_in_filter(self) -> None:
        assert should_include_provider("windows_tts", {"openai_image"}) is False


class TestSupportedExecutionProviders:
    def test_contains_expected(self) -> None:
        assert "openai_image" in SUPPORTED_EXECUTION_PROVIDERS
        assert "openai_tts" in SUPPORTED_EXECUTION_PROVIDERS


class TestBuildProviderRequestPreview:
    def test_unsupported_provider(self, tmp_path: Path) -> None:
        item = {"payload": {"provider": "unknown_provider"}}
        preview = build_provider_request_preview(item, tmp_path)
        assert preview["preflight"]["ready"] is False

    def test_missing_payload(self, tmp_path: Path) -> None:
        item: dict = {}
        preview = build_provider_request_preview(item, tmp_path)
        assert preview["preflight"]["ready"] is False


class TestResolveProviderReady:
    def test_openai_needs_api_key(self) -> None:
        assert resolve_provider_ready("openai_image", {}, True) is True
        assert resolve_provider_ready("openai_image", {}, False) is False

    def test_local_depends_on_preflight(self) -> None:
        preview = {"preflight": {"ready": True}}
        assert resolve_provider_ready("windows_tts", preview, False) is True

    def test_local_preflight_not_ready(self) -> None:
        preview = {"preflight": {"ready": False}}
        assert resolve_provider_ready("windows_tts", preview, False) is False


class TestExecuteProviderRequests:

    def test_empty_requests(self, providers_config_path: Path) -> None:
        result = execute_provider_requests({"requests": []}, providers_config_path)
        assert result["request_count"] == 0

    def test_unsupported_provider_skipped(self, providers_config_path: Path) -> None:
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "provider": "fake_provider",
                        "output_path": "/tmp/out.png",
                    },
                }
            ]
        }
        result = execute_provider_requests(payload, providers_config_path)
        assert result["skipped_count"] == 1
        assert result["results"][0]["status"] == "skipped_unsupported_provider"

    def test_skip_existing(self, tmp_path: Path, providers_config_path: Path) -> None:
        output_path = tmp_path / "out.png"
        output_path.write_text("fake image data")
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "output_path": str(output_path),
                    },
                }
            ]
        }
        result = execute_provider_requests(payload, providers_config_path, skip_existing=True)
        assert result["results"][0]["status"] == "cached_existing_output"

    def test_skip_existing_empty_file(self, tmp_path: Path, providers_config_path: Path) -> None:
        output_path = tmp_path / "empty.png"
        output_path.write_text("")
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "output_path": str(output_path),
                    },
                }
            ]
        }
        result = execute_provider_requests(payload, providers_config_path, skip_existing=True)
        assert result["results"][0]["status"] != "cached_existing_output"

    def test_dry_run(self, tmp_path: Path, providers_config_path: Path) -> None:
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "output_path": str(tmp_path / "out.png"),
                    },
                }
            ]
        }
        result = execute_provider_requests(payload, providers_config_path, dry_run=True)
        assert result["dry_run_count"] == 1
        assert result["results"][0]["status"] == "dry_run"

    def test_blocked_live_not_confirmed(self, tmp_path: Path, providers_config_path: Path) -> None:
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "output_path": str(tmp_path / "out.png"),
                    },
                }
            ]
        }
        result = execute_provider_requests(payload, providers_config_path, confirm_live=False)
        assert result["results"][0]["status"] == "blocked_live_confirmation_required"

    def test_selected_providers_filter(self, tmp_path: Path, providers_config_path: Path) -> None:
        payload = {
            "requests": [
                {
                    "request_id": "R1",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "output_path": str(tmp_path / "out.png"),
                    },
                },
                {
                    "request_id": "R2",
                    "payload": {
                        **_PAYLOAD_BASE,
                        "provider": "openai_tts",
                        "job_type": "tts",
                        "output_path": str(tmp_path / "out.wav"),
                    },
                },
            ]
        }
        result = execute_provider_requests(payload, providers_config_path, selected_providers={"openai_image"})
        assert result["request_count"] == 1
        assert result["results"][0]["provider"] == "openai_image"


class TestWriteProviderExecutionReport:
    def test_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "report.json"
        payload = {"request_count": 1, "results": []}
        write_provider_execution_report(path, payload)
        assert path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "report.json"
        write_provider_execution_report(path, {"request_count": 0})
        assert path.exists()
