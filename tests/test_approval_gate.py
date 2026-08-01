"""人类审核门硬门禁测试 — ACOM-0.6.0 P0-2."""
from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.core.approval_gate import (
    HumanApprovalRequiredError,
    approve_stage,
    complete_stage,
    is_stage_approved,
    mark_awaiting_human,
    require_stage_approved,
)
from aicomic.core.checkpoint_store import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    read_checkpoint,
)
from aicomic.core.pipeline_manifest import load_pipeline_manifest


@pytest.fixture()
def manifest():
    return load_pipeline_manifest()


class TestApprovalGate:
    def test_gate_stage_locks_awaiting_on_complete(self, tmp_path: Path, manifest) -> None:
        with pytest.raises(HumanApprovalRequiredError):
            complete_stage(tmp_path, "E01", "shot_breakdown", manifest=manifest)
        cp = read_checkpoint(tmp_path, "E01", "shot_breakdown")
        assert cp is not None
        assert cp["status"] == CHECKPOINT_AWAITING_HUMAN
        assert not is_stage_approved(tmp_path, "E01", "shot_breakdown")

    def test_non_gate_stage_completes(self, tmp_path: Path, manifest) -> None:
        complete_stage(tmp_path, "E01", "project_setup", manifest=manifest)
        cp = read_checkpoint(tmp_path, "E01", "project_setup")
        assert cp is not None
        assert cp["status"] == CHECKPOINT_COMPLETED

    def test_require_approved_blocks_unapproved_gate(self, tmp_path: Path, manifest) -> None:
        mark_awaiting_human(tmp_path, "E01", "asset_generation", manifest=manifest)
        with pytest.raises(HumanApprovalRequiredError):
            require_stage_approved(tmp_path, "E01", "asset_generation", manifest)

    def test_require_approved_passes_after_approval(self, tmp_path: Path, manifest) -> None:
        approve_stage(tmp_path, "E01", "asset_generation", reviewer="峰哥", notes="素材OK")
        require_stage_approved(tmp_path, "E01", "asset_generation", manifest)  # no raise
        cp = read_checkpoint(tmp_path, "E01", "asset_generation")
        assert cp is not None
        assert cp["status"] == CHECKPOINT_COMPLETED
        assert is_stage_approved(tmp_path, "E01", "asset_generation")

    def test_non_gate_stage_require_approval_noop(self, tmp_path: Path, manifest) -> None:
        require_stage_approved(tmp_path, "E01", "tts_subtitle", manifest)  # no raise

    def test_approval_is_independent_per_gate(self, tmp_path: Path, manifest) -> None:
        """批准分镜门不影响素材门（每门独立批准）。"""
        approve_stage(tmp_path, "E01", "shot_breakdown", reviewer="峰哥")
        assert is_stage_approved(tmp_path, "E01", "shot_breakdown")
        # asset_generation 尚未批准
        assert not is_stage_approved(tmp_path, "E01", "asset_generation")
        with pytest.raises(HumanApprovalRequiredError):
            require_stage_approved(tmp_path, "E01", "asset_generation", manifest)

    def test_approval_record_fields(self, tmp_path: Path, manifest) -> None:
        approve_stage(tmp_path, "E01", "shot_breakdown", reviewer="产品体验官", notes="分镜符合三拍法")
        cp = read_checkpoint(tmp_path, "E01", "shot_breakdown")
        assert cp is not None
        assert cp["self_review"]["reviewer"] == "产品体验官"
        assert cp["self_review"]["human_approved"] is True
        assert cp["self_review"]["approval_notes"] == "分镜符合三拍法"
