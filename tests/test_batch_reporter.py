from __future__ import annotations

import json
from pathlib import Path

from aicomic.batch.reporter import build_batch_summary, write_batch_summary


class TestBuildBatchSummary:
    def test_empty_steps(self) -> None:
        report = {"batch_id": "B001", "status": "completed", "scope_type": "season", "scope_value": "S01", "step_results": []}
        summary = build_batch_summary(report)
        assert summary["batch_id"] == "B001"
        assert summary["status"] == "completed"
        assert summary["step_count"] == 0

    def test_counts_completed_steps(self) -> None:
        report = {
            "batch_id": "B001",
            "status": "running",
            "scope_type": "episode",
            "scope_value": "E01-E03",
            "step_results": [
                {"step_name": "scan", "status": "completed"},
                {"step_name": "render", "status": "simulated"},
                {"step_name": "publish", "status": "failed"},
            ],
        }
        summary = build_batch_summary(report)
        assert summary["step_count"] == 3
        assert summary["real_step_count"] == 1  # only 'completed'
        assert summary["failed_step_count"] == 1
        assert summary["completed_step_count"] == 2  # completed + simulated

    def test_all_failed(self) -> None:
        report = {
            "batch_id": "B001",
            "status": "failed",
            "scope_type": "episode",
            "scope_value": "E01",
            "step_results": [
                {"step_name": "scan", "status": "failed"},
                {"step_name": "render", "status": "failed"},
            ],
        }
        summary = build_batch_summary(report)
        assert summary["failed_step_count"] == 2
        assert summary["real_step_count"] == 0
        assert summary["completed_step_count"] == 0

    def test_with_next_actions(self) -> None:
        report = {
            "batch_id": "B001",
            "status": "completed",
            "scope_type": "season",
            "scope_value": "S01",
            "step_results": [],
        }
        summary = build_batch_summary(report)
        assert isinstance(summary["next_actions"], list)


class TestWriteBatchSummary:
    def test_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        payload = {"batch_id": "B001", "status": "completed", "step_count": 0, "next_actions": []}
        write_batch_summary(path, payload)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["batch_id"] == "B001"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "summary.json"
        write_batch_summary(path, {"status": "done"})
        assert path.exists()
