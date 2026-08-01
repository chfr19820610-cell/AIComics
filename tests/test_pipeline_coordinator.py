"""管线协调器端到端测试 — ACOM-0.6.0 P0-1/2/3."""
from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.core.approval_gate import HumanApprovalRequiredError
from aicomic.core.checkpoint_store import CHECKPOINT_COMPLETED
from aicomic.core.pipeline_coordinator import PipelineCoordinator
from aicomic.core.resume import checkpoint_summary, resume_stage_from_checkpoints


@pytest.fixture()
def coord(tmp_path: Path) -> PipelineCoordinator:
    return PipelineCoordinator(tmp_path)


class TestPipelineCoordinator:
    def test_steps_order_from_manifest(self, coord: PipelineCoordinator) -> None:
        assert coord.step_ids == [
            "project_setup", "story_bible", "episode_outline", "shot_breakdown",
            "asset_generation", "tts_subtitle", "preview_render", "publish_pack",
        ]

    def test_full_flow_with_two_gates(self, coord: PipelineCoordinator) -> None:
        # 非门禁阶段直接完成
        for st in ["project_setup", "story_bible", "episode_outline"]:
            coord.begin_stage("E01", st)
            r = coord.complete_stage("E01", st)
            assert r.status == CHECKPOINT_COMPLETED
        # 分镜门：完成即锁 awaiting_human
        coord.begin_stage("E01", "shot_breakdown")
        r = coord.complete_stage("E01", "shot_breakdown")
        assert r.required_human_approval is True
        assert r.status == "awaiting_human"
        # 未批准无法推进
        with pytest.raises(HumanApprovalRequiredError):
            coord.advance("E01")
        # 批准后推进到素材门
        coord.approve_stage("E01", "shot_breakdown", reviewer="峰哥")
        a = coord.advance("E01")
        assert a.current_stage == "asset_generation"
        # 素材门：完成即锁 awaiting_human
        coord.begin_stage("E01", "asset_generation")
        r = coord.complete_stage("E01", "asset_generation")
        assert r.status == "awaiting_human"
        with pytest.raises(HumanApprovalRequiredError):
            coord.advance("E01")
        # 批准素材门
        coord.approve_stage("E01", "asset_generation", reviewer="峰哥")
        a = coord.advance("E01")
        assert a.current_stage == "tts_subtitle"

    def test_unapproved_cannot_reach_next_stage(self, coord: PipelineCoordinator) -> None:
        for st in ["project_setup", "story_bible", "episode_outline"]:
            coord.begin_stage("E01", st)
            coord.complete_stage("E01", st)
        coord.begin_stage("E01", "shot_breakdown")
        coord.complete_stage("E01", "shot_breakdown")
        # 任何路径（advance 硬门禁）都被拦截
        with pytest.raises(HumanApprovalRequiredError):
            coord.advance("E01")
        # resume 也停在 shot_breakdown
        assert resume_stage_from_checkpoints(coord.state_dir, "E01") == "shot_breakdown"

    def test_resume_based_on_checkpoint(self, coord: PipelineCoordinator) -> None:
        for st in ["project_setup", "story_bible", "episode_outline", "shot_breakdown"]:
            coord.begin_stage("E01", st)
            coord.complete_stage("E01", st)
        # shot_breakdown 是门禁，未批准前 resume 卡在它
        assert resume_stage_from_checkpoints(coord.state_dir, "E01") == "shot_breakdown"
        coord.approve_stage("E01", "shot_breakdown", reviewer="峰哥")
        assert resume_stage_from_checkpoints(coord.state_dir, "E01") == "asset_generation"

    def test_checkpoint_summary(self, coord: PipelineCoordinator) -> None:
        coord.begin_stage("E01", "project_setup")
        coord.complete_stage("E01", "project_setup")
        summary = checkpoint_summary(coord.state_dir, "E01")
        assert summary["project_setup"] == "completed"
        assert summary["shot_breakdown"] == "not_started"

    def test_approve_independent_gates(self, coord: PipelineCoordinator) -> None:
        for st in ["project_setup", "story_bible", "episode_outline"]:
            coord.begin_stage("E01", st)
            coord.complete_stage("E01", st)
        coord.begin_stage("E01", "shot_breakdown")
        coord.complete_stage("E01", "shot_breakdown")
        coord.approve_stage("E01", "shot_breakdown", reviewer="峰哥")
        # 只批准分镜门，素材门仍未批准
        assert coord.stage_approved("E01", "shot_breakdown")
        assert not coord.stage_approved("E01", "asset_generation")

    def test_require_ready_to_proceed_enforces_gate(self, coord: PipelineCoordinator) -> None:
        with pytest.raises(HumanApprovalRequiredError):
            coord.require_ready_to_proceed("E01", "shot_breakdown")

    def test_advance_blocks_tampered_completed_gate(self, coord: PipelineCoordinator) -> None:
        """B3 回归：门禁阶段被直写 completed 但未批准 → advance 必须拦截（不依赖 status 值）。"""
        for st in ["project_setup", "story_bible", "episode_outline"]:
            coord.begin_stage("E01", st)
            coord.complete_stage("E01", st)
        # 绕过 approve_stage，直接写 completed（模拟状态篡改/误用 write_checkpoint）
        from aicomic.core.checkpoint_store import write_checkpoint

        write_checkpoint(coord.state_dir, "E01", "shot_breakdown", CHECKPOINT_COMPLETED)
        assert coord.stage_status("E01", "shot_breakdown") == CHECKPOINT_COMPLETED
        assert not coord.stage_approved("E01", "shot_breakdown")
        with pytest.raises(HumanApprovalRequiredError):
            coord.advance("E01")
        # 批准后才放行
        coord.approve_stage("E01", "shot_breakdown", reviewer="峰哥")
        assert coord.advance("E01").current_stage == "asset_generation"

    def test_resume_blocks_tampered_completed_gate(self, coord: PipelineCoordinator) -> None:
        """R2 回归：门禁阶段 completed 但未批准 → resume 必须停在它（防直写绕过）。"""
        from aicomic.core.checkpoint_store import write_checkpoint

        for st in ["project_setup", "story_bible", "episode_outline"]:
            coord.begin_stage("E01", st)
            coord.complete_stage("E01", st)
        write_checkpoint(coord.state_dir, "E01", "shot_breakdown", CHECKPOINT_COMPLETED)
        assert resume_stage_from_checkpoints(coord.state_dir, "E01") == "shot_breakdown"
        coord.approve_stage("E01", "shot_breakdown", reviewer="峰哥")
        assert resume_stage_from_checkpoints(coord.state_dir, "E01") == "asset_generation"
