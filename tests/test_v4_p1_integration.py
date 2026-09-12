"""v4.0 P1 integration tests — cross-episode consistency, publish integration, template system.

Tests that the v4.0 P1 upgrades are properly wired:
  - P1-5: Workflow-First — execute_publish_pack wires into publish pipeline
  - P1-6: Cross-episode consistency — ConsistencyService.check_cross_episode_consistency
  - P1-7: Publish platform integration — domestic + international publishers
  - P1-8: Template system — load genre templates into pipeline config
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── P1-5: Workflow-First publish integration ──────────────────────────────


class TestPublishPackIntegration:
    """P1-5: execute_publish_pack should produce publish-ready output."""

    def test_publish_pack_in_pipeline(self):
        """PipelineCoordinator should have execute_publish_pack method."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(
            state_dir=Path("/tmp/test_v4_p1"), manifest={}
        )
        assert hasattr(coordinator, "execute_publish_pack")

    def test_publish_pack_returns_required_fields(self):
        """execute_publish_pack should return pack with metadata."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(
            state_dir=Path("/tmp/test_v4_p1"), manifest={}
        )
        manifest = {
            "episode_code": "EP001",
            "title": "测试剧集",
            "shots": [
                {"shot_id": "S001", "dialogue": "你好", "tts_prompt": "你好"}
            ],
            "episodes": [
                {
                    "episode_code": "EP001",
                    "title": "测试剧集",
                    "publish_title": "测试剧集 EP001",
                    "cover_text": "她回来了",
                    "shots": [
                        {"shot_id": "S001", "dialogue": "你好", "tts_prompt": "你好"}
                    ],
                }
            ],
        }
        result = coordinator.execute_publish_pack(
            episode_code="EP001", episode_manifest=manifest
        )
        assert "publish_pack" in result or "pack" in result
        assert "episode_code" in result


# ── P1-6: Cross-episode consistency ────────────────────────────────────────


class TestCrossEpisodeConsistency:
    """P1-6: ConsistencyService should check consistency across episodes."""

    def test_cross_episode_method_exists(self):
        """ConsistencyService should have check_cross_episode_consistency."""
        from aicomic.characters.consistency_service import ConsistencyService
        import sqlite3

        conn = sqlite3.connect(":memory:")
        svc = ConsistencyService(connection=conn)
        assert hasattr(svc, "check_cross_episode_consistency")

    def test_cross_episode_detects_drift(self):
        """Cross-episode check should detect character attribute drift."""
        from aicomic.characters.consistency_service import (
            ConsistencyService,
            ShotCharacterState,
            AttributeEntry,
        )
        import sqlite3

        conn = sqlite3.connect(":memory:")
        svc = ConsistencyService(connection=conn)

        # Episode 1: character has black hair
        ep1_states = [
            ShotCharacterState(
                character_name="主角",
                shot_id="S001",
                attributes=[
                    AttributeEntry(category="hair", attribute="黑色长发"),
                    AttributeEntry(category="eyes", attribute="棕色眼睛"),
                ],
            )
        ]
        # Episode 2: same character but hair changed (drift!)
        ep2_states = [
            ShotCharacterState(
                character_name="主角",
                shot_id="S101",
                attributes=[
                    AttributeEntry(category="hair", attribute="金色短发"),
                    AttributeEntry(category="eyes", attribute="棕色眼睛"),
                ],
            )
        ]

        issues = svc.check_cross_episode_consistency(
            episode_a_states=ep1_states,
            episode_b_states=ep2_states,
        )
        assert len(issues) > 0
        # Should detect hair drift
        categories = [i.attribute_category for i in issues]
        assert "hair" in categories

    def test_cross_episode_no_drift_returns_empty(self):
        """Cross-episode check should return empty list when consistent."""
        from aicomic.characters.consistency_service import (
            ConsistencyService,
            ShotCharacterState,
            AttributeEntry,
        )
        import sqlite3

        conn = sqlite3.connect(":memory:")
        svc = ConsistencyService(connection=conn)

        states_a = [
            ShotCharacterState(
                character_name="主角",
                shot_id="S001",
                attributes=[AttributeEntry(category="hair", attribute="黑色长发")],
            )
        ]
        states_b = [
            ShotCharacterState(
                character_name="主角",
                shot_id="S101",
                attributes=[AttributeEntry(category="hair", attribute="黑色长发")],
            )
        ]
        issues = svc.check_cross_episode_consistency(
            episode_a_states=states_a,
            episode_b_states=states_b,
        )
        assert len(issues) == 0


# ── P1-7: Publish platform integration ────────────────────────────────────


class TestPublishPlatformIntegration:
    """P1-7: Publish modules should be importable and have key functions."""

    def test_domestic_publisher_importable(self):
        """domestic_publisher should be importable with publish_to_platforms."""
        from aicomic.publish.domestic_publisher import publish_to_platforms

        assert callable(publish_to_platforms)

    def test_international_publisher_importable(self):
        """international publisher should be importable."""
        from aicomic.publish.international import publish, YouTubeUploader

        assert callable(publish)
        assert YouTubeUploader is not None

    def test_publish_pack_module_exists(self):
        """publish_pack module should exist and have build function."""
        from aicomic.publish.publish_pack import build_publish_pack

        assert callable(build_publish_pack)

    def test_publish_dashboard_exists(self):
        """Dashboard should be buildable from validation report."""
        from aicomic.publish.dashboard import build_dashboard_payload

        assert callable(build_dashboard_payload)


# ── P1-8: Template system ──────────────────────────────────────────────────


class TestTemplateSystem:
    """P1-8: Genre templates should be loadable and usable in pipeline."""

    def test_template_directory_exists(self):
        """config/templates/ should exist with genre YAML files."""
        template_dir = Path(__file__).parent.parent / "config" / "templates"
        assert template_dir.exists()
        yaml_files = list(template_dir.glob("*.yaml"))
        assert len(yaml_files) >= 6  # cultivation, horror, mystery, romance, sweetpet, workplace

    def test_load_genre_template(self):
        """Should be able to load a genre template by name."""
        from aicomic.core.template_loader import load_genre_template

        template = load_genre_template("cultivation")
        assert template is not None
        assert "name" in template or "genre" in template
        assert "visual_motifs" in template or "visual_rules" in template

    def test_template_includes_prompt_overrides(self):
        """Template should include prompt overrides for character/style."""
        from aicomic.core.template_loader import load_genre_template

        template = load_genre_template("romance")
        has_prompts = (
            "visual_templates" in template
            or "dialogue_templates" in template
            or "visual_motifs" in template
            or "camera_map" in template
            or "emotion_map" in template
        )
        assert has_prompts, f"Template missing prompt/style keys: {list(template.keys())}"

    def test_template_list_all_genres(self):
        """Should be able to list all available genre templates."""
        from aicomic.core.template_loader import list_genre_templates

        genres = list_genre_templates()
        assert len(genres) >= 6
        assert "cultivation" in genres
        assert "romance" in genres
