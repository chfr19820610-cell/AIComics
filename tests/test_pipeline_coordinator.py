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


class TestStageExecutors:
    """SOP 阶段执行器接入测试 — 8阶段管线从空壳到真实产出。"""

    def test_execute_shot_breakdown(self, coord: PipelineCoordinator) -> None:
        """shot_breakdown 执行器：blueprint → shot manifest。"""
        blueprint = {
            "blueprint_version": "horror_v1",
            "episode_title": "Test",
            "episode_count": 1,
            "episodes": [{"episode_code": "E01", "title": "Test", "act": 1, "beats": ["intro"]}],
        }
        result = coord.execute_shot_breakdown("E01", blueprint, template_name="horror")
        assert result["status"] == "generated"
        assert result["episode_code"] == "E01"
        assert "shot_manifest" in result

    def test_execute_asset_generation(self, coord: PipelineCoordinator, tmp_path: Path) -> None:
        """asset_generation 执行器：episode_manifest → provider requests。"""
        import yaml

        providers_yaml = tmp_path / "providers.yaml"
        providers_yaml.write_text(yaml.dump({"providers": []}), encoding="utf-8")
        manifest = {"episode_code": "E01", "shots": []}
        result = coord.execute_asset_generation("E01", manifest, str(providers_yaml), str(tmp_path))
        assert result["status"] == "generated"
        assert "provider_requests" in result

    def test_execute_tts_subtitle(self, coord: PipelineCoordinator) -> None:
        """tts_subtitle 执行器：episode_manifest → subtitles + tts prompts。"""
        manifest = {
            "episode_code": "E01",
            "episodes": [
                {
                    "episode_code": "E01",
                    "shots": [
                        {"shot_id": "E01_S001", "dialogue": "你好", "duration": 2, "tts_provider": "edge"},
                    ],
                }
            ],
            "shots": [
                {"shot_id": "E01_S001", "dialogue": "你好", "duration": 2, "tts_provider": "edge"},
            ],
        }
        result = coord.execute_tts_subtitle("E01", manifest)
        assert result["status"] == "generated"
        assert "subtitles" in result
        assert "tts_prompts" in result

    def test_execute_preview_render(self, coord: PipelineCoordinator, tmp_path: Path) -> None:
        """preview_render 执行器：render_plan → 预览视频。"""
        render_plan = {
            "episode_code": "E01",
            "shot_count": 1,
            "shots": [
                {
                    "shot_id": "E01_S001",
                    "duration": 1,
                    "image_path": "",
                    "has_image": False,
                    "visual": "test scene",
                    "narration": "test",
                },
            ],
        }
        out = tmp_path / "preview.mp4"
        report = tmp_path / "report.json"
        result = coord.execute_preview_render("E01", render_plan, str(out), str(report))
        assert result["status"] == "rendered"
        assert "render_result" in result

    def test_execute_publish_pack(self, coord: PipelineCoordinator) -> None:
        """publish_pack 执行器：episode_manifest → publish pack。"""
        manifest = {
            "episode_code": "E01",
            "episodes": [
                {
                    "episode_code": "E01",
                    "title": "Test Episode",
                    "publish_title": "测试标题",
                    "cover_text": "测试封面",
                    "shots": [{"shot_id": "E01_S001", "scene": "intro", "dialogue": "hi", "duration": 2}],
                }
            ],
        }
        result = coord.execute_publish_pack("E01", manifest)
        assert result["status"] == "generated"
        assert "publish_pack" in result
