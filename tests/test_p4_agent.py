"""Tests for v5.0 P4 — Director Agent + API Key Manager."""
from __future__ import annotations

import time
from pathlib import Path

import pytest


# ── Director Agent ─────────────────────────────────────────────────────────


class TestDirectorAgent:
    def test_pipeline_definition(self):
        from aicomic.core.director_agent import DirectorAgent
        director = DirectorAgent()
        assert "script" in DirectorAgent.AGENT_PIPELINE
        assert "storyboard" in DirectorAgent.AGENT_PIPELINE
        assert "video" in DirectorAgent.AGENT_PIPELINE
        assert "quality" in DirectorAgent.AGENT_PIPELINE
        assert "publish" in DirectorAgent.AGENT_PIPELINE

    def test_register_agent(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult
        director = DirectorAgent()

        def mock_script(context, **kwargs):
            return AgentResult(agent_name="script", status="success", output={"script": "test"})

        director.register_agent("script", mock_script)
        assert "script" in director._agents

    def test_execute_unregistered_agent(self):
        from aicomic.core.director_agent import DirectorAgent
        director = DirectorAgent()
        result = director.execute_agent("nonexistent", {})
        assert result.status == "skipped"

    def test_execute_success(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult
        director = DirectorAgent()

        def mock_agent(context, **kwargs):
            return AgentResult(agent_name="script", status="success", output={"result": "ok"})

        director.register_agent("script", mock_agent)
        result = director.execute_agent("script", {"story": "test"})
        assert result.status == "success"
        assert result.output["result"] == "ok"

    def test_execute_retry_on_failure(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult
        director = DirectorAgent(max_retries=2)
        call_count = [0]

        def flaky_agent(context, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                return AgentResult(agent_name="video", status="failed", error="transient")
            return AgentResult(agent_name="video", status="success", output={})

        director.register_agent("video", flaky_agent)
        result = director.execute_agent("video", {})
        assert result.status == "success"
        assert call_count[0] == 2

    def test_execute_max_retries(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult
        director = DirectorAgent(max_retries=1)

        def always_fail(context, **kwargs):
            return AgentResult(agent_name="script", status="failed", error="permanent")

        director.register_agent("script", always_fail)
        result = director.execute_agent("script", {})
        assert result.status == "failed"

    def test_produce_episode_success(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult

        def make_agent(name):
            def agent_fn(context, **kwargs):
                return AgentResult(agent_name=name, status="success", output={f"{name}_done": True})
            return agent_fn

        director = DirectorAgent(max_retries=0)
        for name in DirectorAgent.AGENT_PIPELINE:
            director.register_agent(name, make_agent(name))

        result = director.produce_episode(story="test story", episode_code="E01")
        assert result.success is True
        assert result.episode_code == "E01"
        assert len(result.agent_results) == 7

    def test_produce_episode_halts_on_critical_failure(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult

        def success_agent(name):
            def fn(context, **kwargs):
                return AgentResult(agent_name=name, status="success", output={})
            return fn

        def fail_agent(context, **kwargs):
            return AgentResult(agent_name="storyboard", status="failed", error="no storyboard")

        director = DirectorAgent(max_retries=0)
        director.register_agent("script", success_agent("script"))
        director.register_agent("storyboard", fail_agent)
        # Rest not registered → should be skipped

        result = director.produce_episode(story="test")
        assert result.success is False
        # Should have script (success) + storyboard (failed) and stopped
        assert len(result.agent_results) <= 3  # script + storyboard + maybe one more

    def test_get_pipeline_status(self):
        from aicomic.core.director_agent import DirectorAgent, AgentResult
        director = DirectorAgent()
        director.register_agent("script", lambda **kw: AgentResult(agent_name="script", status="success"))
        status = director.get_pipeline_status()
        assert "script" in status["registered_agents"]
        assert "storyboard" in status["missing_agents"]

    def test_agent_result_to_dict(self):
        from aicomic.core.director_agent import AgentResult
        r = AgentResult(agent_name="test", status="success", output={"x": 1})
        d = r.to_dict()
        assert d["agent_name"] == "test"
        assert d["status"] == "success"
        assert d["output"]["x"] == 1

    def test_episode_result_to_dict(self):
        from aicomic.core.director_agent import EpisodeProductionResult, AgentResult
        r = EpisodeProductionResult(
            episode_code="E01",
            success=True,
            agent_results=[AgentResult(agent_name="script", status="success")],
            quality_score=85,
        )
        d = r.to_dict()
        assert d["episode_code"] == "E01"
        assert d["success"] is True
        assert d["quality_score"] == 85
        assert len(d["agent_results"]) == 1


# ── API Key Manager ───────────────────────────────────────────────────────


class TestAPIKeyManager:
    def test_set_and_get_key(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-test-123")
        assert mgr.get_key("kling") == "sk-test-123"

    def test_get_nonexistent_key(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        assert mgr.get_key("nonexistent") == ""

    def test_is_configured(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        assert mgr.is_configured("kling") is False
        mgr.set_key("kling", "sk-test")
        assert mgr.is_configured("kling") is True

    def test_disable_enable(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-test")
        mgr.disable("kling")
        assert mgr.is_configured("kling") is False
        mgr.enable("kling")
        assert mgr.is_configured("kling") is True

    def test_record_usage(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-test", quota_limit=1000)
        mgr.record_usage("kling", tokens=50)
        status = mgr.get_key_status("kling")
        assert status["quota_used"] == 50
        assert status["quota_remaining"] == 950

    def test_record_failure_auto_disable(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-test")
        for _ in range(10):
            mgr.record_failure("kling")
        assert mgr.is_configured("kling") is False  # auto-disabled

    def test_record_success_resets_failures(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-test")
        mgr.record_failure("kling")
        mgr.record_failure("kling")
        mgr.record_success("kling")
        status = mgr.get_key_status("kling")
        assert status["failure_count"] == 0

    def test_rotate_key(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "old-key")
        mgr.rotate_key("kling", "new-key")
        assert mgr.get_key("kling") == "new-key"
        status = mgr.get_key_status("kling")
        assert status["failure_count"] == 0

    def test_key_status_not_configured(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        status = mgr.get_key_status("kling")
        assert status["status"] == "not_configured"

    def test_get_all_status(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-1")
        mgr.set_key("openai", "sk-2")
        all_status = mgr.get_all_status()
        assert len(all_status) == 2

    def test_get_unconfigured(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "sk-1")
        unconfigured = mgr.get_unconfigured()
        assert "kling" not in unconfigured
        assert "openai" in unconfigured

    def test_export_config_no_keys(self, tmp_path):
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=str(tmp_path / "keys.json"))
        mgr.set_key("kling", "secret-key-value")
        config = mgr.export_config()
        assert "key_value" not in config["kling"]

    def test_persistence(self, tmp_path):
        """Keys should persist across manager instances."""
        from aicomic.providers.api_key_manager import APIKeyManager
        path = str(tmp_path / "keys.json")
        mgr1 = APIKeyManager(storage_path=path)
        mgr1.set_key("kling", "persistent-key")
        mgr2 = APIKeyManager(storage_path=path)
        assert mgr2.get_key("kling") == "persistent-key"
