from __future__ import annotations

import json
from pathlib import Path

import pytest

from aicomic.batch.coordinator import (
    BatchStepError,
    _build_season_jobs,
    apply_batch_preflight_gate,
    build_batch_payload,
    build_batch_record,
    build_run_output_path,
    load_batch_payload,
    parse_steps,
    run_batch_payload,
    write_batch_payload,
)
from aicomic.core.models import BatchRecord


class TestParseSteps:
    def test_default_steps(self) -> None:
        steps = parse_steps("")
        assert len(steps) >= 6

    def test_custom_steps(self) -> None:
        steps = parse_steps("scan, render, publish")
        assert steps == ["scan", "render", "publish"]

    def test_whitespace_handling(self) -> None:
        steps = parse_steps("  scan  ,  render  ")
        assert steps == ["scan", "render"]

    def test_single_step(self) -> None:
        steps = parse_steps("scan")
        assert steps == ["scan"]


class TestBuildBatchRecord:
    def test_builds_record(self) -> None:
        record = build_batch_record(
            batch_id="B001", batch_type="full", scope_type="episode",
            scope_value="E01-E03", steps=["scan", "render"], provider_filter="",
            summary_path=Path("/tmp/summary.json"),
        )
        assert isinstance(record, BatchRecord)
        assert record.batch_id == "B001"
        assert record.target_steps == "scan,render"
        assert record.status == "planned"

    def test_empty_steps(self) -> None:
        record = build_batch_record(
            batch_id="B002", batch_type="full", scope_type="episode",
            scope_value="E01", steps=[], provider_filter="local",
            summary_path=Path("/tmp/s.json"),
        )
        assert record.target_steps == ""


class TestBuildBatchPayload:
    def test_builds_payload(self) -> None:
        record = BatchRecord(
            batch_id="B001", batch_type="full", scope_type="episode", scope_value="E01",
            target_steps="scan,render", provider_filter="", status="planned",
            summary_path="/tmp/s.json",
        )
        payload = build_batch_payload(record)
        assert "batch" in payload
        assert "steps" in payload
        assert len(payload["steps"]) == 2
        assert payload["steps"][0]["step_name"] == "scan"

    def test_empty_steps(self) -> None:
        record = BatchRecord(
            batch_id="B001", batch_type="full", scope_type="episode", scope_value="E01",
            target_steps="", provider_filter="", status="planned", summary_path="/tmp/s.json",
        )
        payload = build_batch_payload(record)
        assert payload["steps"] == []


class TestWriteAndLoadBatchPayload:
    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "payload.json"
        payload = {"batch": {"batch_id": "B001"}, "steps": []}
        write_batch_payload(path, payload)
        assert path.exists()
        loaded = load_batch_payload(path)
        assert loaded["batch"]["batch_id"] == "B001"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "payload.json"
        write_batch_payload(path, {"test": True})
        assert path.exists()


class TestBuildRunOutputPath:
    def test_builds_path(self) -> None:
        path = build_run_output_path(Path("/reports"), "B001", "scan")
        assert str(path).endswith("B001_scan.json")
        assert str(path).startswith("/reports")

    def test_with_nested_dir(self) -> None:
        path = build_run_output_path(Path("/base/reports"), "B001", "render")
        assert path.parent == Path("/base/reports")


class TestBatchStepError:
    def test_error_message(self) -> None:
        err = BatchStepError("scan", ValueError("file not found"))
        assert err.step_name == "scan"
        assert "scan" in str(err)
        assert "file not found" in str(err)

    def test_original_error(self) -> None:
        original = RuntimeError("something broke")
        err = BatchStepError("render", original)
        assert err.original_error is original


class TestApplyBatchPreflightGate:
    def test_applies_gate(self) -> None:
        payload = {"batch": {"batch_id": "B001", "provider_filter": ""}}
        result = apply_batch_preflight_gate(payload, enabled=False)
        assert "preflight_gate" in result

    def test_non_dict_batch(self) -> None:
        payload = {"batch": None}
        result = apply_batch_preflight_gate(payload)
        assert result == payload


class TestRunBatchPayload:
    def test_simulated_mode(self, tmp_path: Path) -> None:
        record = BatchRecord(
            batch_id="B001", batch_type="full", scope_type="episode", scope_value="E01",
            target_steps="scan,render", provider_filter="", status="planned", summary_path="",
        )
        payload = build_batch_payload(record)
        report, run_records = run_batch_payload(payload, tmp_path, mode="simulated")
        assert report["status"] == "completed"
        assert report["simulated_step_count"] == 2
        assert len(run_records) == 2

    def test_unknown_mode_raises(self, tmp_path: Path) -> None:
        payload = {"batch": {"batch_id": "B001"}, "steps": []}
        with pytest.raises(ValueError, match="Unknown batch execution mode"):
            run_batch_payload(payload, tmp_path, mode="invalid")

    def test_preflight_blocked(self, tmp_path: Path) -> None:
        record = BatchRecord(
            batch_id="B001", batch_type="full", scope_type="episode", scope_value="E01",
            target_steps="scan", provider_filter="", status="planned", summary_path="",
        )
        payload = build_batch_payload(record)
        payload["preflight_gate"] = {"enabled": True, "auto_run": False, "report_path": str(tmp_path / "missing.json")}
        report, run_records = run_batch_payload(payload, tmp_path, mode="simulated")
        assert report["status"] == "blocked_preflight_failed"

    def test_simulated_with_no_steps(self, tmp_path: Path) -> None:
        record = BatchRecord(
            batch_id="B002", batch_type="full", scope_type="episode", scope_value="E01",
            target_steps="", provider_filter="", status="planned", summary_path="",
        )
        payload = build_batch_payload(record)
        report, run_records = run_batch_payload(payload, tmp_path, mode="simulated")
        assert report["step_count"] == 0


class TestBuildSeasonJobs:
    def test_builds_jobs_bundle(self) -> None:
        season_manifest = {
            "project_id": "P001",
            "season": {"season_id": "S1"},
            "season_title": "第一季",
            "episodes": [
                {
                    "episode_code": "E01",
                    "shots": [{"shot_id": "S001", "dialogue": "hello", "ai_video": True}],
                }
            ],
        }
        episode_manifest = {
            "episodes": [
                {
                    "episode_code": "E01",
                    "shots": [{"shot_id": "S001", "dialogue": "hello", "ai_video": True}],
                }
            ]
        }
        result = _build_season_jobs(season_manifest, episode_manifest)
        assert "jobs" in result
