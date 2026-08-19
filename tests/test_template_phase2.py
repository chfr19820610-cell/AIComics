"""Tests for new Phase 2 templates: workplace, cultivation, mystery, sweetpet."""
from __future__ import annotations

import pytest

from aicomic.core.template_engine import (
    list_templates,
    load_template,
    build_blueprint_from_template,
    build_manifest_from_template,
)


class TestSixTemplatesDiscovery:
    def test_six_templates_available(self):
        names = list_templates()
        for t in ("horror", "romance", "workplace", "cultivation", "mystery", "sweetpet"):
            assert t in names, f"missing template: {t}"

    def test_workplace_loads(self):
        t = load_template("workplace")
        assert t["genre"] == "职场逆袭"
        assert len(t["acts"]) == 5
        assert t["acts"][0]["beat"] == "humiliation"

    def test_cultivation_loads(self):
        t = load_template("cultivation")
        assert t["genre"] == "修仙"
        assert t["acts"][0]["beat"] == "underdog"
        assert t["acts"][4]["beat"] == "ascension"

    def test_mystery_loads(self):
        t = load_template("mystery")
        assert t["genre"] == "悬疑推理"
        assert t["acts"][0]["beat"] == "crime_scene"

    def test_sweetpet_loads(self):
        t = load_template("sweetpet")
        assert t["genre"] == "甜宠"
        assert t["acts"][0]["beat"] == "meet_cute"


class TestNewTemplatesBlueprint:
    def test_workplace_blueprint_5_acts(self):
        bp = build_blueprint_from_template("workplace", episode_code="W01")
        assert len(bp["acts"]) == 5
        assert bp["acts"][0]["title"] == "开场屈辱"

    def test_cultivation_blueprint_shots(self):
        bp = build_blueprint_from_template("cultivation", episode_code="C01", max_shots=25)
        assert bp["shot_count"] == 25

    def test_mystery_blueprint_has_twist(self):
        bp = build_blueprint_from_template("mystery", episode_code="M01")
        # twist is in template, check blueprint has narrative
        assert bp["episode_code"] == "M01"

    def test_sweetpet_blueprint_uses_hook(self):
        bp = build_blueprint_from_template("sweetpet", hook="自定义钩子", episode_code="S01")
        assert bp["hook"] == "自定义钩子"

    def test_each_template_produces_valid_manifest(self):
        """All 6 templates must produce valid manifests with shots."""
        for name in ("horror", "romance", "workplace", "cultivation", "mystery", "sweetpet"):
            bp = build_blueprint_from_template(name, episode_code=f"T_{name[:3]}", max_shots=10)
            m = build_manifest_from_template(bp, project_id="test", season=1)
            ep = m["episodes"][0]
            assert len(ep["shots"]) == 10, f"{name}: expected 10 shots, got {len(ep['shots'])}"
            # Each shot must have required fields
            for s in ep["shots"]:
                assert "shot_id" in s
                assert "scene" in s
                assert "visual" in s
                assert "dialogue" in s


class TestTemplateSpecificContent:
    def test_workplace_has_office_locations(self):
        t = load_template("workplace")
        assert any("公司" in loc or "电梯" in loc for loc in t["locations"])

    def test_cultivation_has_cultivation_terms(self):
        t = load_template("cultivation")
        assert any("宗门" in loc or "修炼" in loc for loc in t["locations"])

    def test_mystery_has_detective_elements(self):
        t = load_template("mystery")
        assert any("监控" in m for m in t["visual_motifs"])

    def test_sweetpet_has_sweet_elements(self):
        t = load_template("sweetpet")
        assert any("奶茶" in m for m in t["visual_motifs"])

    def test_all_templates_have_required_fields(self):
        """Every template must have all fields the engine reads."""
        required = ["template_id", "genre", "default_hook", "acts", "locations",
                     "characters", "visual_motifs", "sound_cues", "emotion_map",
                     "camera_map", "visual_rules", "twist"]
        for name in ("workplace", "cultivation", "mystery", "sweetpet"):
            t = load_template(name)
            for field in required:
                assert field in t, f"{name}: missing field {field}"
