"""Tests for v5.0 P2 MLLM intelligence modules."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# ── MLLM Storyboard Engine ────────────────────────────────────────────────


class TestMLLMStoryboard:
    def test_engine_no_key(self):
        """Engine without API key should report unavailable."""
        from aicomic.core.mllm_storyboard import MLLMStoryboardEngine
        engine = MLLMStoryboardEngine(api_key="")
        assert engine.is_available is False

    def test_engine_with_key(self):
        from aicomic.core.mllm_storyboard import MLLMStoryboardEngine
        engine = MLLMStoryboardEngine(api_key="test_key")
        assert engine.is_available is True

    def test_fallback_no_key(self):
        """Without API key, should fall back to template engine."""
        from aicomic.core.mllm_storyboard import MLLMStoryboardEngine
        engine = MLLMStoryboardEngine(api_key="")
        result = engine.generate_storyboard("测试故事", genre="horror")
        assert result["source"] == "fallback"

    def test_storyboard_shot_dataclass(self):
        from aicomic.core.mllm_storyboard import StoryboardShot
        shot = StoryboardShot(
            shot_index=1,
            scene_description="少年站在悬崖边",
            characters=["主角"],
            emotion="tense",
            camera_movement="wide",
            duration_seconds=5.0,
        )
        d = shot.to_dict()
        assert d["shot_index"] == 1
        assert d["emotion"] == "tense"


# ── Content Anchor ────────────────────────────────────────────────────────


class TestContentAnchor:
    def test_create_anchor(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001", "李明")
        assert anchor.character_id == "char_001"
        assert anchor.character_name == "李明"
        assert len(anchor.frames) == 0

    def test_add_reference(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        anchor.add_reference("front", "/refs/front.png")
        assert "front" in anchor.frames
        assert anchor.get_reference("front").image_path == "/refs/front.png"

    def test_completeness_empty(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        assert anchor.get_completeness_score() == 0.0

    def test_completeness_full(self):
        from aicomic.image_consistency.content_anchor import (
            ContentAnchor, STANDARD_VIEWS, STANDARD_EXPRESSIONS,
        )
        anchor = ContentAnchor("char_001")
        for view in STANDARD_VIEWS + STANDARD_EXPRESSIONS:
            anchor.add_reference(view, f"/refs/{view}.png")
        assert anchor.get_completeness_score() == 1.0

    def test_missing_views(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        anchor.add_reference("front", "/front.png")
        missing = anchor.get_missing_views()
        assert "front" not in missing
        assert "side_left" in missing

    def test_check_consistency_pass(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        anchor.add_reference("front", "/front.png", features={"hair": "black", "eyes": "blue"})
        result = anchor.check_consistency({"hair": "black", "eyes": "blue"}, "front")
        assert result["status"] == "PASS"
        assert result["score"] == 1.0

    def test_check_consistency_fail(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        anchor.add_reference("front", "/front.png", features={"hair": "black"})
        result = anchor.check_consistency({"hair": "blonde"}, "front")
        assert result["status"] == "FAIL"

    def test_check_consistency_no_ref(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        result = anchor.check_consistency({}, "nonexistent")
        assert result["status"] == "WARN"

    def test_episode_history(self):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001")
        anchor.record_episode_usage("E01", [1, 3, 5], [0.9, 0.85, 0.8])
        anchor.record_episode_usage("E02", [2, 4], [0.8, 0.75])
        trend = anchor.get_drift_trend()
        assert trend["episodes"] == 2
        assert trend["trend"] in ("stable", "degrading", "improving")

    def test_save_and_load(self, tmp_path):
        from aicomic.image_consistency.content_anchor import ContentAnchor
        anchor = ContentAnchor("char_001", "李明")
        anchor.add_reference("front", "/front.png", features={"hair": "black"})
        path = tmp_path / "anchor.json"
        anchor.save(path)
        loaded = ContentAnchor.load(path)
        assert loaded.character_id == "char_001"
        assert loaded.character_name == "李明"
        assert "front" in loaded.frames
        assert loaded.frames["front"].features["hair"] == "black"


# ── Smart Provider Router ─────────────────────────────────────────────────


class TestSmartRouter:
    def test_default_providers(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        assert "kling" in router.providers
        assert "seedance" in router.providers
        assert "wan" in router.providers

    def test_route_returns_decision(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        decision = router.route("action")
        assert decision.provider_name in ("kling", "seedance", "wan")
        assert decision.score > 0
        assert len(decision.fallback_chain) >= 1

    def test_shot_preference(self):
        """Action shots should prefer Kling (higher quality)."""
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        decision = router.route("action")
        # Kling has highest quality (90) + preference bonus → should win
        assert decision.provider_name == "kling"

    def test_record_success(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        original_rate = router.providers["wan"].success_rate
        router.record_success("wan")
        assert router.providers["wan"].success_rate > original_rate

    def test_record_failure(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        original_rate = router.providers["kling"].success_rate
        router.record_failure("kling")
        assert router.providers["kling"].success_rate < original_rate

    def test_consecutive_failures_reduce_availability(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        original_avail = router.providers["seedance"].availability
        for _ in range(3):
            router.record_failure("seedance")
        assert router.providers["seedance"].availability < original_avail

    def test_get_rankings(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        rankings = router.get_rankings()
        assert len(rankings) == 3
        # Rankings should be sorted by score descending
        assert rankings[0]["score"] >= rankings[1]["score"] >= rankings[2]["score"]

    def test_get_provider_status(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        status = router.get_provider_status("kling")
        assert status["provider"] == "kling"
        assert "score" in status
        assert "metrics" in status

    def test_update_metric(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        router.update_metric("kling", "quality", 100)
        assert router.providers["kling"].quality == 100

    def test_empty_router(self):
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter(providers={})
        decision = router.route()
        assert decision.provider_name == ""
        assert decision.score == 0

    def test_fallback_chain(self):
        """Fallback chain should have all providers except the chosen one."""
        from aicomic.providers.smart_router import SmartProviderRouter
        router = SmartProviderRouter()
        decision = router.route("action")
        assert decision.provider_name not in decision.fallback_chain
        assert len(decision.fallback_chain) == 2
