"""Checkpoint 存储与自检状态测试 — ACOM-0.6.0 P0-3."""
from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.core.checkpoint_store import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    CHECKPOINT_FAILED,
    CHECKPOINT_IN_PROGRESS,
    build_checkpoint,
    checkpoint_status,
    read_checkpoint,
    resume_from,
    stage_is_completed,
    write_checkpoint,
)
from aicomic.core.pipeline_manifest import PipelineManifestError

STEPS = ["project_setup", "shot_breakdown", "asset_generation", "tts_subtitle"]


class TestCheckpointStore:
    def test_write_and_read(self, tmp_path: Path) -> None:
        path = write_checkpoint(
            tmp_path, "E01", "shot_breakdown", CHECKPOINT_COMPLETED,
            review_focus=["三拍法"],
            self_review={"human_approved": True},
            success_criteria_met=True,
        )
        assert path.is_file()
        cp = read_checkpoint(tmp_path, "E01", "shot_breakdown")
        assert cp is not None
        assert cp["status"] == CHECKPOINT_COMPLETED
        assert cp["self_review"]["human_approved"] is True
        assert cp["review_focus"] == ["三拍法"]
        assert cp["episode_code"] == "E01"

    def test_missing_checkpoint_is_none(self, tmp_path: Path) -> None:
        assert read_checkpoint(tmp_path, "E01", "nope") is None
        assert checkpoint_status(tmp_path, "E01", "nope") is None

    def test_invalid_status_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PipelineManifestError):
            build_checkpoint("E01", "shot_breakdown", "bogus")

    def test_stage_is_completed(self, tmp_path: Path) -> None:
        write_checkpoint(tmp_path, "E01", "project_setup", CHECKPOINT_COMPLETED)
        write_checkpoint(tmp_path, "E01", "shot_breakdown", CHECKPOINT_AWAITING_HUMAN)
        assert stage_is_completed(tmp_path, "E01", "project_setup")
        assert not stage_is_completed(tmp_path, "E01", "shot_breakdown")

    def test_resume_from_first_incomplete(self, tmp_path: Path) -> None:
        write_checkpoint(tmp_path, "E01", "project_setup", CHECKPOINT_COMPLETED)
        write_checkpoint(tmp_path, "E01", "shot_breakdown", CHECKPOINT_COMPLETED)
        # asset_generation not started
        assert resume_from(tmp_path, "E01", STEPS) == "asset_generation"

    def test_resume_blocks_at_awaiting_human(self, tmp_path: Path) -> None:
        write_checkpoint(tmp_path, "E01", "project_setup", CHECKPOINT_COMPLETED)
        write_checkpoint(tmp_path, "E01", "shot_breakdown", CHECKPOINT_AWAITING_HUMAN)
        assert resume_from(tmp_path, "E01", STEPS) == "shot_breakdown"

    def test_resume_all_completed_returns_none(self, tmp_path: Path) -> None:
        for s in STEPS:
            write_checkpoint(tmp_path, "E01", s, CHECKPOINT_COMPLETED)
        assert resume_from(tmp_path, "E01", STEPS) is None

    def test_resume_after_failed(self, tmp_path: Path) -> None:
        write_checkpoint(tmp_path, "E01", "project_setup", CHECKPOINT_COMPLETED)
        write_checkpoint(tmp_path, "E01", "shot_breakdown", CHECKPOINT_FAILED)
        assert resume_from(tmp_path, "E01", STEPS) == "shot_breakdown"

    def test_all_statuses_allowed(self, tmp_path: Path) -> None:
        for status in [CHECKPOINT_IN_PROGRESS, CHECKPOINT_AWAITING_HUMAN, CHECKPOINT_COMPLETED, CHECKPOINT_FAILED]:
            cp = build_checkpoint("E01", "s", status)
            assert cp["status"] == status
