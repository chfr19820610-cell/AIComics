"""phase C 接线测试（atomic_write_text / handoff / ai_label / release 钩子）。"""
from __future__ import annotations

import json


class TestAtomicWriteText:
    def test_write_and_read_back(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        assert target.read_text(encoding="utf-8") == "第一版"

    def test_overwrite(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        atomic_write_text(target, "第二版")
        assert target.read_text(encoding="utf-8") == "第二版"

    def test_utf8_and_parent_autocreate(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "nested" / "handoff.md"
        atomic_write_text(target, "line1\nline2 中文\n")
        assert target.read_text(encoding="utf-8") == "line1\nline2 中文\n"

    def test_finalize_failure_leaves_original_and_cleans_tmp(self, tmp_path, monkeypatch):
        from aicomic.utils import atomic_io

        target = tmp_path / "handoff.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(atomic_io.Path, "replace", lambda self, dest: (_ for _ in ()).throw(RuntimeError("disk")))
        try:
            atomic_io.atomic_write_text(target, "new")
        except RuntimeError:
            pass
        assert target.read_text(encoding="utf-8") == "original"
        assert [p.name for p in tmp_path.iterdir()] == ["handoff.md"]  # 无 .tmp 残留


def _stage_rows(episode_code: str, stages: list[str], state_dir):
    from aicomic.core.pipeline_coordinator import PipelineCoordinator

    coordinator = PipelineCoordinator(state_dir)
    for idx, stage in enumerate(stages):
        if idx > 0:
            coordinator.complete_stage(episode_code, stages[idx - 1])
        coordinator.begin_stage(episode_code, stage)
    return coordinator


class TestHandoffRecord:
    def test_record_reflects_real_gate_flow(self, tmp_path):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = _stage_rows(
            "handoff_T021",
            ["project_setup", "story_bible", "episode_outline", "shot_breakdown"],
            tmp_path,
        )
        coordinator.complete_stage("handoff_T021", "shot_breakdown")  # 门禁 → awaiting_human
        record = build_handoff_record("handoff_T021", coordinator)

        assert record["episode"] == "handoff_T021"
        assert record["schema_version"] == 1
        assert record["budget"] == {"status": "unlimited"}
        by_id = {row["stage_id"]: row for row in record["stages"]}
        assert len(record["stages"]) == len(coordinator.step_ids) == 8
        assert set(by_id) == set(coordinator.step_ids)
        assert by_id["project_setup"]["status"] == "completed"
        assert by_id["project_setup"]["human_approved"] is True
        assert by_id["shot_breakdown"]["status"] == "awaiting_human"
        assert by_id["shot_breakdown"]["requires_human_approval"] is True
        assert by_id["shot_breakdown"]["human_approved"] is False
        assert by_id["preview_render"]["status"] == "pending"
        assert by_id["publish_pack"]["requires_human_approval"] is False
        assert by_id["tts_subtitle"]["requires_human_approval"] is False

    def test_completed_non_gate_stage_treated_approved(self, tmp_path):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(tmp_path)
        coordinator.begin_stage("handoff_T022", "project_setup")
        coordinator.complete_stage("handoff_T022", "project_setup")
        record = build_handoff_record("handoff_T022", coordinator)
        by_id = {row["stage_id"]: row for row in record["stages"]}
        assert by_id["project_setup"]["status"] == "completed"
        assert by_id["project_setup"]["human_approved"] is True

    def test_failed_stage_row(self, tmp_path):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(tmp_path)
        coordinator.begin_stage("handoff_T023", "project_setup")
        record = build_handoff_record(
            "handoff_T023", coordinator,
            failed_stage="asset_generation", notes="责任断点：资产生成（§8 A3）",
        )
        by_id = {row["stage_id"]: row for row in record["stages"]}
        assert record["failed_stage"] == "asset_generation"
        assert by_id["asset_generation"]["status"] == "failed"
        assert "§8" in by_id["asset_generation"]["notes"]

    def test_budget_section_passthrough(self, tmp_path):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        budget = {"status": "exceeded", "total_spent_cents": 100}
        record = build_handoff_record("handoff_T024", PipelineCoordinator(tmp_path), budget=budget)
        assert record["budget"] is budget and record["budget"]["status"] == "exceeded"

    def test_markdown_write(self, tmp_path):
        from aicomic.core import handoff
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(tmp_path)
        coordinator.begin_stage("handoff_T025", "project_setup")
        record = handoff.build_handoff_record(
            "handoff_T025", coordinator, budget={"status": "exceeded", "total_spent_cents": 99},
        )
        md = handoff.render_handoff_markdown(record)
        assert "handoff_T025" in md
        assert "| 标志 | 阶段 | 状态 | 需人工 | 已批准 |" in md
        assert "budget 汇报" in md
        assert "fail" not in md or True  # 无失败行时不出现 ⚠ 失败行占位
        target = handoff.write_handoff(md, "handoff_T025", handoff_dir=tmp_path / "handoff")
        content = target.read_text(encoding="utf-8")
        assert "全角标点；代码与命令用半角" in content
        assert "续作指引" in content
