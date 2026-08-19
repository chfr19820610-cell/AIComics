"""Novel pipeline Phase 2 — blueprint → shot breakdown → asset generation plan."""
from __future__ import annotations

import pytest

from aicomic.core.novel_pipeline import (
    generate_episode_plan,
    build_season_production_plan,
)


class TestGenerateEpisodePlan:
    def test_returns_dict_with_required_keys(self):
        blueprint = {
            "acts": [{"act_id": "A1", "title": "开场", "beat": "open", "shot_count": 5}],
            "characters": [{"name": "主角", "role": "主视角", "visual_rule": "x"}],
            "locations": ["场景A", "场景B"],
            "visual_motifs": ["道具A"],
            "emotion_map": {"open": "悬念"},
        }
        plan = generate_episode_plan(blueprint, template_name="mystery", shots_per_episode=10)
        assert "shot_plan" in plan
        assert "asset_plan" in plan
        assert "total_shots" in plan
        assert plan["total_shots"] == 10

    def test_shot_plan_has_per_shot_details(self):
        blueprint = {
            "acts": [{"act_id": "A1", "title": "开场", "beat": "open", "shot_count": 3}],
            "characters": [{"name": "主角", "role": "主视角", "visual_rule": "x"}],
            "locations": ["场景A"],
            "visual_motifs": ["道具A"],
            "emotion_map": {"open": "悬念"},
        }
        plan = generate_episode_plan(blueprint, template_name="mystery", shots_per_episode=6)
        assert len(plan["shot_plan"]) == 6
        for shot in plan["shot_plan"]:
            assert "shot_id" in shot
            assert "act_id" in shot
            assert "location" in shot
            assert "emotion" in shot
            assert "narration" in shot

    def test_asset_plan_lists_characters(self):
        blueprint = {
            "acts": [{"act_id": "A1", "title": "x", "beat": "x", "shot_count": 2}],
            "characters": [
                {"name": "主角", "role": "主视角", "visual_rule": "x"},
                {"name": "配角", "role": "辅助", "visual_rule": "y"},
            ],
            "locations": ["场景A"],
            "visual_motifs": ["道具A"],
            "emotion_map": {"x": "x"},
        }
        plan = generate_episode_plan(blueprint, template_name="mystery", shots_per_episode=4)
        assert len(plan["asset_plan"]["characters"]) == 2
        assert len(plan["asset_plan"]["locations"]) >= 1

    def test_zero_shots_raises(self):
        blueprint = {"acts": [{"act_id": "A1", "title": "x", "beat": "x", "shot_count": 0}]}
        with pytest.raises(ValueError):
            generate_episode_plan(blueprint, template_name="mystery", shots_per_episode=0)


class TestBuildSeasonProductionPlan:
    def test_returns_plan_with_episodes(self):
        episodes = [
            {"episode_code": "E01", "shot_count": 10, "blueprint": {"acts": [], "characters": [], "locations": [], "visual_motifs": [], "emotion_map": {}}},
            {"episode_code": "E02", "shot_count": 10, "blueprint": {"acts": [], "characters": [], "locations": [], "visual_motifs": [], "emotion_map": {}}},
        ]
        plan = build_season_production_plan(episodes, template_name="mystery")
        assert plan["episode_count"] == 2
        assert len(plan["episode_plans"]) == 2
        assert plan["total_shots"] == 20

    def test_empty_episodes(self):
        plan = build_season_production_plan([], template_name="mystery")
        assert plan["episode_count"] == 0
        assert plan["total_shots"] == 0
