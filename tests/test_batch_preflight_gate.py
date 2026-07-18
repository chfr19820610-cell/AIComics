from __future__ import annotations

import json
from pathlib import Path

from aicomic.batch.preflight_gate import (
    build_batch_preflight_gate,
    ensure_batch_preflight_gate,
    evaluate_existing_preflight_report,
    load_optional_json,
    parse_provider_filter,
    parse_run_time,
    should_require_local_provider_preflight,
)


class TestParseProviderFilter:
    def test_single_provider(self) -> None:
        assert parse_provider_filter("local_comfyui_image") == {"local_comfyui_image"}

    def test_multiple_providers(self) -> None:
        result = parse_provider_filter("local_comfyui_image, windows_tts")
        assert result == {"local_comfyui_image", "windows_tts"}

    def test_empty_string(self) -> None:
        assert parse_provider_filter("") == set()

    def test_whitespace_handling(self) -> None:
        result = parse_provider_filter("  local_comfyui_image  ,  windows_tts  ")
        assert result == {"local_comfyui_image", "windows_tts"}


class TestShouldRequirePreflight:
    def test_disabled_returns_false(self) -> None:
        assert should_require_local_provider_preflight("local_comfyui_image", False) is False

    def test_empty_filter_with_enabled_returns_true(self) -> None:
        assert should_require_local_provider_preflight("", True) is True

    def test_non_local_provider_returns_false(self) -> None:
        assert should_require_local_provider_preflight("openai_image", True) is False

    def test_local_comfyui_image_returns_true(self) -> None:
        assert should_require_local_provider_preflight("local_comfyui_image", True) is True

    def test_windows_tts_returns_true(self) -> None:
        # windows_tts is manual, not a local provider that needs preflight
        assert should_require_local_provider_preflight("windows_tts", True) is False


class TestBuildBatchPreflightGate:
    def test_builds_gate_with_defaults(self) -> None:
        gate = build_batch_preflight_gate(batch_id="B001", provider_filter="local_comfyui_image")
        assert gate["enabled"] is True
        assert gate["auto_run"] is True
        assert "providers" in gate
        assert gate["max_age_minutes"] >= 1
        assert gate["report_path"]

    def test_disabled_gate(self) -> None:
        gate = build_batch_preflight_gate(batch_id="B001", provider_filter="", enabled=False)
        assert gate["enabled"] is False

    def test_auto_run_false(self) -> None:
        gate = build_batch_preflight_gate(batch_id="B001", provider_filter="local_comfyui_image", auto_run=False)
        assert gate["auto_run"] is False

    def test_min_max_age_clamped(self) -> None:
        gate = build_batch_preflight_gate(batch_id="B001", provider_filter="local_comfyui_image", max_age_minutes=0)
        assert gate["max_age_minutes"] >= 1


class TestLoadOptionalJson:
    def test_missing_file_returns_empty(self) -> None:
        assert load_optional_json(Path("/nonexistent/file.json")) == {}

    def test_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        assert load_optional_json(p) == {"key": "value"}


class TestParseRunTime:
    def test_valid_iso(self) -> None:
        dt = parse_run_time("2025-01-15T10:30:00+00:00")
        assert dt is not None
        assert dt.year == 2025

    def test_empty_string(self) -> None:
        assert parse_run_time("") is None

    def test_invalid_string(self) -> None:
        assert parse_run_time("not-a-date") is None


class TestEvaluateExistingPreflightReport:
    def test_missing_report(self, tmp_path: Path) -> None:
        result = evaluate_existing_preflight_report({
            "enabled": True,
            "report_path": str(tmp_path / "nonexistent.json"),
            "max_age_minutes": 240,
            "providers": ["local_comfyui_image"],
        })
        assert result["status"] == "missing"

    def test_failed_report(self, tmp_path: Path) -> None:
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
        result = evaluate_existing_preflight_report({
            "enabled": True,
            "report_path": str(report_path),
            "max_age_minutes": 240,
            "providers": ["local_comfyui_image"],
        })
        assert result["status"] == "failed"

    def test_passed_report(self, tmp_path: Path) -> None:
        report_path = tmp_path / "report.json"
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        report_path.write_text(json.dumps({
            "status": "passed",
            "run_at": now,
            "selected_providers": ["local_comfyui_image"],
            "image_workflow_mode": "smoke",
        }), encoding="utf-8")
        result = evaluate_existing_preflight_report({
            "enabled": True,
            "report_path": str(report_path),
            "max_age_minutes": 99999,
            "providers": ["local_comfyui_image"],
            "image_workflow_mode": "smoke",
        })
        assert result["status"] == "passed"


class TestEnsureBatchPreflightGate:
    def test_disabled_gate(self) -> None:
        gate = {"enabled": False, "report_path": ""}
        result = ensure_batch_preflight_gate(gate)
        assert result["status"] == "disabled"

    def test_enabled_no_auto_run_returns_blocked(self, tmp_path: Path) -> None:
        gate = {
            "enabled": True,
            "auto_run": False,
            "report_path": str(tmp_path / "missing.json"),
            "max_age_minutes": 240,
            "providers": ["local_comfyui_image"],
        }
        result = ensure_batch_preflight_gate(gate)
        assert result["status"] == "blocked"
