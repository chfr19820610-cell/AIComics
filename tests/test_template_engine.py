"""Template registry tests.

Tests the template engine that replaces hardcoded horror_pipeline/romance_pipeline
with a YAML-driven generic blueprint+manifest generator.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aicomic.core.template_engine import (
    list_templates,
    load_template,
    build_blueprint_from_template,
    build_manifest_from_template,
)


# ── Template discovery ──────────────────────────────────────────────────

class TestTemplateDiscovery:
    def test_list_templates_returns_builtins(self):
        names = list_templates()
        assert "horror" in names
        assert "romance" in names

    def test_list_templates_excludes_non_yaml(self):
        names = list_templates()
        # Should not include README or non-yaml files
        for n in names:
            assert not n.endswith(".md")

    def test_load_template_horror_has_required_fields(self):
        t = load_template("horror")
        assert t["template_id"] == "horror"
        assert t["genre"]
        assert len(t["acts"]) == 5
        assert t["acts"][0]["act_id"] == "A1"
        assert t["default_hook"]
        assert t["locations"]
        assert t["characters"]
        assert t["visual_motifs"]

    def test_load_template_romance_has_required_fields(self):
        t = load_template("romance")
        assert t["template_id"] == "romance"
        assert len(t["acts"]) == 5
        assert t["default_hook"]

    def test_load_template_unknown_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_template")

    def test_load_template_invalid_yaml_raises(self, tmp_path: Path):
        # Write a bad yaml file into the templates dir
        from aicomic.core.template_engine import _templates_dir
        bad = _templates_dir() / "bad.yaml"
        bad.write_text(":\n  invalid: [unclosed", encoding="utf-8")
        try:
            with pytest.raises(Exception):
                load_template("bad")
        finally:
            bad.unlink(missing_ok=True)


# ── Blueprint generation ────────────────────────────────────────────────

class TestBlueprintGeneration:
    def test_horror_blueprint_has_5_acts(self):
        bp = build_blueprint_from_template("horror", hook="测试钩子")
        assert len(bp["acts"]) == 5
        assert bp["acts"][0]["act_id"] == "A1"
        assert bp["acts"][-1]["act_id"] == "A5"

    def test_blueprint_hook_used_when_provided(self):
        bp = build_blueprint_from_template("horror", hook="村里老人说不能回头")
        assert bp["hook"] == "村里老人说不能回头"

    def test_blueprint_default_hook_when_empty(self):
        bp = build_blueprint_from_template("horror", hook="")
        assert bp["hook"]  # non-empty default

    def test_blueprint_shots_distribute_across_acts(self):
        bp = build_blueprint_from_template("horror", hook="test", max_shots=50)
        total = sum(a["shot_count"] for a in bp["acts"])
        assert total == bp["shot_count"]

    def test_blueprint_episode_code(self):
        bp = build_blueprint_from_template("horror", hook="test", episode_code="E03")
        assert bp["episode_code"] == "E03"

    def test_romance_blueprint_acts(self):
        bp = build_blueprint_from_template("romance", hook="雨夜偶遇")
        assert len(bp["acts"]) == 5
        assert bp["acts"][0]["act_id"] == "A1"


# ── Manifest generation ─────────────────────────────────────────────────

class TestManifestGeneration:
    def test_horror_manifest_shots_match_blueprint(self):
        bp = build_blueprint_from_template("horror", hook="测试", max_shots=45)
        manifest = build_manifest_from_template(bp, project_id="test", season=1)
        ep = manifest["episodes"][0]
        assert len(ep["shots"]) == bp["shot_count"]

    def test_manifest_shots_have_required_fields(self):
        bp = build_blueprint_from_template("horror", hook="测试", max_shots=45)
        manifest = build_manifest_from_template(bp, project_id="test", season=1)
        shot = manifest["episodes"][0]["shots"][0]
        for field in ["shot_id", "duration", "scene", "characters", "visual",
                       "action", "dialogue", "emotion", "camera", "act_id"]:
            assert field in shot, f"missing field: {field}"

    def test_manifest_episode_code(self):
        bp = build_blueprint_from_template("horror", hook="test", episode_code="E07")
        manifest = build_manifest_from_template(bp, project_id="test", season=2)
        assert manifest["episodes"][0]["episode_code"] == "E07"
        assert manifest["season"] == 2

    def test_romance_manifest_shots(self):
        bp = build_blueprint_from_template("romance", hook="雨夜", max_shots=6)
        manifest = build_manifest_from_template(bp, project_id="test", season=1)
        assert len(manifest["episodes"][0]["shots"]) == bp["shot_count"]


# ── Horror backward compatibility ────────────────────────────────────────

class TestHorrorBackwardCompat:
    """The template engine must produce output compatible with existing
    horror_pipeline consumers (CLI horror-blueprint command)."""

    def test_template_horror_same_genre(self):
        bp = build_blueprint_from_template("horror", hook="测试")
        assert "恐怖" in bp["genre"] or "玄学" in bp["genre"]

    def test_template_horror_has_taboos(self):
        bp = build_blueprint_from_template("horror", hook="测试")
        assert "taboos" in bp
        assert len(bp["taboos"]) >= 1

    def test_template_horror_has_twist(self):
        bp = build_blueprint_from_template("horror", hook="测试")
        assert "twist" in bp
        assert bp["twist"]

    def test_template_horror_has_visual_rules(self):
        bp = build_blueprint_from_template("horror", hook="测试")
        assert "visual_rules" in bp
        assert len(bp["visual_rules"]) >= 1

    def test_template_horror_continuity_anchors(self):
        bp = build_blueprint_from_template("horror", hook="测试")
        assert "continuity_anchors" in bp
        assert len(bp["continuity_anchors"]) >= 1
