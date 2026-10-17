"""ShowAgent 编排测试（SOP 第 6 章 Transformer 闭环 → agent 编排落地）。"""
from __future__ import annotations

from pathlib import Path


def _manifest(episode_code: str = "E_SHOWAGENT") -> dict:
    return {
        "series_title": "测试剧集",
        "episode_code": episode_code,
        "logline": "测试",
        "characters": [],
        "scene_count": 1,
        "shots": [],
    }


_BLUEPRINT = {"blueprint_version": "horror_v1", "episodes": [{"episode_code": "E01"}]}


def _agent(tmp_path, **kw):
    from aicomic.core.show_agent import ShowAgent

    agent = ShowAgent(state_dir=tmp_path, **kw)
    return agent


def _stub_asset(coordinator, monkeypatch, *, manifest=None):
    monkeypatch.setattr(
        coordinator, "execute_asset_generation",
        lambda *a, **k: {"provider_requests": {"requests": []}, "status": "generated", "shot_manifest": manifest or _manifest()},
    )


def _stub_downstream(coordinator, monkeypatch):
    monkeypatch.setattr(coordinator, "execute_tts_subtitle", lambda *a, **k: {"subtitles": [], "status": "generated"})
    monkeypatch.setattr(
        coordinator, "execute_preview_render",
        lambda ep, render_plan, output_path, report_path: {"render_result": {}, "status": "rendered"},
    )
    monkeypatch.setattr(coordinator, "execute_publish_pack", lambda *a, **k: {"publish_pack": {}, "status": "generated"})


class TestRunnerSharedBlueprint:
    BLUEPRINT = _BLUEPRINT


class TestNeedsInput:
    def test_missing_blueprint_needs_input(self, tmp_path):
        agent = _agent(tmp_path)
        result = agent.run_until_human("needs_input_T033", {})
        assert result.stop_reason == "needs_input"
        assert result.current_stage == "shot_breakdown"

    def test_missing_render_plan_needs_input(self, tmp_path, monkeypatch):
        agent = _agent(tmp_path)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        _stub_asset(agent.coordinator, monkeypatch, manifest=_manifest())
        _stub_downstream(agent.coordinator, monkeypatch)
        # 首轮停在 shot_breakdown 门（inputs 需带 blueprint，stub 不免校验）
        first = agent.run_until_human("needs_input_T033b", {"shot_breakdown": {"blueprint": _BLUEPRINT, "template_name": "horror"}})
        assert first.stop_reason == "awaiting_human"
        agent.coordinator.approve_stage("needs_input_T033b", "shot_breakdown", reviewer="T")
        second = agent.run_until_human("needs_input_T033b", {})
        assert second.stop_reason == "awaiting_human"
        agent.coordinator.approve_stage("needs_input_T033b", "asset_generation", reviewer="T")
        third = agent.run_until_human("needs_input_T033b", {})
        assert third.stop_reason == "needs_input"
        assert third.current_stage == "preview_render"


class TestRunsAndStops:
    BLUEPRINT = _BLUEPRINT
    BLUEPRINT = {"blueprint_version": "horror_v1", "episodes": [{"episode_code": "E01"}]}

    def test_runs_to_gate_and_requests_approval(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        agent = _agent(tmp_path)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        inputs = {
            "shot_breakdown": {"blueprint": self.BLUEPRINT, "template_name": "horror"},
        }
        result = agent.run_until_human("showagent_T034", inputs)
        assert result.stop_reason == "awaiting_human"
        assert result.current_stage == "shot_breakdown"
        from aicomic.core.checkpoint_store import read_checkpoint

        checkpoint = read_checkpoint(tmp_path, "showagent_T034", "shot_breakdown")
        assert checkpoint["stage_id"] == "shot_breakdown"
        assert checkpoint["status"] == "awaiting_human"

    def test_gate_not_replayed(self, tmp_path, monkeypatch):
        agent = _agent(tmp_path)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        inputs = {"shot_breakdown": {"blueprint": self.BLUEPRINT, "template_name": "horror"}}
        first = agent.run_until_human("gate_T036", inputs)
        assert first.stop_reason == "awaiting_human" and first.current_stage == "shot_breakdown"

        witnessed: list[str] = []
        real_begin = agent.coordinator.begin_stage

        def spy_begin(episode_code, stage_id):
            witnessed.append(stage_id)
            return real_begin(episode_code, stage_id)

        monkeypatch.setattr(agent.coordinator, "begin_stage", spy_begin)
        second = agent.run_until_human("gate_T036", inputs)
        assert second.stop_reason == "awaiting_human" and second.current_stage == "shot_breakdown"
        assert "shot_breakdown" not in witnessed  # gate 防重放：停在审批点的阶段不得再 begin_stage

    def test_resumes_after_approval(self, tmp_path, monkeypatch):
        agent = _agent(tmp_path)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        _stub_asset(agent.coordinator, monkeypatch, manifest=_manifest())
        _stub_downstream(agent.coordinator, monkeypatch)
        inputs = {
            "shot_breakdown": {"blueprint": self.BLUEPRINT, "template_name": "horror"},
            "preview_render": {"render_plan": {"scene_count": 0, "render_plan": []}, "output_path": str(tmp_path / "preview.mp4"), "report_path": str(tmp_path / "preview.json")},
        }
        first = agent.run_until_human("gate_T035", inputs)
        assert first.stop_reason == "awaiting_human"
        agent.coordinator.approve_stage("gate_T035", "shot_breakdown", reviewer="USER")
        second = agent.run_until_human("gate_T035", inputs)
        # asset_generation 是第二道门禁
        assert second.stop_reason == "awaiting_human"
        assert second.current_stage == "asset_generation"
        _stub_asset_gate = agent.coordinator
        _stub_asset_gate.approve_stage("gate_T035", "asset_generation", reviewer="USER")
        third = agent.run_until_human("gate_T035", inputs)
        assert third.stop_reason == "all_completed"

    def test_stage_failure_writes_failed_checkpoint(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        def boom(*a, **k):
            raise RuntimeError("kaboom")

        agent = _agent(tmp_path)
        _stub_asset(agent.coordinator, monkeypatch, manifest=_manifest())
        _stub_downstream(agent.coordinator, monkeypatch)
        inputs = {
            "shot_breakdown": {"blueprint": self.BLUEPRINT, "template_name": "horror"},
            "tts_subtitle": {"episode_manifest": _manifest()},
        }
        first = agent.run_until_human("failed_T041", inputs)
        assert first.stop_reason == "awaiting_human"
        agent.coordinator.approve_stage("failed_T041", "shot_breakdown", reviewer="USER")
        second = agent.run_until_human("failed_T041", inputs)
        assert second.stop_reason == "awaiting_human"
        agent.coordinator.approve_stage("failed_T041", "asset_generation", reviewer="USER")
        monkeypatch.setattr(agent.coordinator, "execute_tts_subtitle", boom)
        third = agent.run_until_human("failed_T041", inputs)
        assert third.stop_reason == "failed"
        assert third.current_stage == "tts_subtitle"
        from aicomic.core.checkpoint_store import read_checkpoint

        checkpoint = read_checkpoint(tmp_path, "failed_T041", "tts_subtitle")
        assert checkpoint["status"] == "failed"


class TestExecuteLive:
    def test_budget_stopped(self, tmp_path, monkeypatch):
        import aicomic.core.show_agent as sa

        agent = _agent(tmp_path)
        _stub_asset(agent.coordinator, monkeypatch, manifest=_manifest())
        _stub_downstream(agent.coordinator, monkeypatch)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        monkeypatch.setattr(
            sa, "execute_provider_requests",
            lambda *a, **k: {"stopped_by_budget_guard": True},
        )
        inputs = {
            "shot_breakdown": {"blueprint": _BLUEPRINT, "template_name": "horror"},
            "asset_generation": {"providers_config_path": "tmp/providers.yaml", "output_root": str(tmp_path)},
        }
        first = agent.run_until_human("budget_T043", inputs, live=True)
        assert first.stop_reason == "awaiting_human"  # 首轮停在 shot_breakdown 门
        agent.coordinator.approve_stage("budget_T043", "shot_breakdown", reviewer="USER")
        second = agent.run_until_human("budget_T043", inputs, live=True)
        assert second.stop_reason == "budget_stopped"
        assert second.current_stage == "asset_generation"
        from aicomic.core.checkpoint_store import read_checkpoint

        checkpoint = read_checkpoint(tmp_path, "budget_T043", "asset_generation")
        assert checkpoint["status"] == "failed"

    def test_live_success_chain(self, tmp_path, monkeypatch):
        import aicomic.core.show_agent as sa

        agent = _agent(tmp_path)
        _stub_asset(agent.coordinator, monkeypatch, manifest=_manifest())
        _stub_downstream(agent.coordinator, monkeypatch)
        monkeypatch.setattr(
            agent.coordinator, "execute_shot_breakdown",
            lambda ep, blueprint, template_name="", project_id="": {"shot_manifest": _manifest(), "status": "generated"},
        )
        monkeypatch.setattr(
            sa, "execute_provider_requests", lambda *a, **k: {"stopped_by_budget_guard": False},
        )
        inputs = {
            "shot_breakdown": {"blueprint": _BLUEPRINT, "template_name": "horror"},
            "asset_generation": {"providers_config_path": "tmp/providers.yaml", "output_root": str(tmp_path)},
            "preview_render": {"render_plan": {"scene_count": 0, "render_plan": []}, "output_path": str(tmp_path / "preview.mp4"), "report_path": str(tmp_path / "preview.json")},
        }
        first = agent.run_until_human("liveok_T043", inputs, live=True)
        assert first.stop_reason == "awaiting_human"  # 首轮停在 shot_breakdown 门
        agent.coordinator.approve_stage("liveok_T043", "shot_breakdown", reviewer="USER")
        second = agent.run_until_human("liveok_T043", inputs, live=True)
        assert second.stop_reason == "awaiting_human"  # asset_generation 门禁完成即停
        assert second.current_stage == "asset_generation"
        agent.coordinator.approve_stage("liveok_T043", "asset_generation", reviewer="USER")
        final = agent.run_until_human("liveok_T043", inputs, live=True)
        assert final.stop_reason == "all_completed"
