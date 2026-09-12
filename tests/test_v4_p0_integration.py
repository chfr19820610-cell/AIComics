"""v4.0 P0 integration tests — four-view, video router, drift gate, i18n pipeline.

Tests that the v4.0 upgrades are properly wired into the SOP pipeline:
  - P0-1: Character four-view generation in asset_generation stage
  - P0-2: VideoRouter mandatory in request_builder
  - P0-3: Drift gate consistency checking
  - P0-4: Multi-language subtitle/TTS in tts_subtitle stage
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── P0-1: Four-view integration ───────────────────────────────────────────


class TestFourViewIntegration:
    """P0-1: Character four-view generation wired into SOP stage ⑤."""

    def test_asset_generation_includes_four_view_prompts(self):
        """execute_asset_generation should produce four-view prompts for each character."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(state_dir=Path("/tmp/test_v4"), manifest={})
        manifest = {
            "episode_code": "EP001",
            "characters": [
                {"character_id": "char_001", "name": "主角", "description": "黑发少年"}
            ],
            "shots": [],
        }
        result = coordinator.execute_asset_generation(
            episode_code="EP001",
            episode_manifest=manifest,
            providers_config_path="providers.yaml",
            output_root="/tmp/test_v4_output",
        )
        assert "four_view_prompts" in result
        assert len(result["four_view_prompts"]) > 0
        first = result["four_view_prompts"][0]
        assert "character_id" in first
        assert "views" in first
        # Should have at least front view
        assert any(v["angle"] == "front" for v in first["views"])

    def test_four_view_prompts_have_all_four_angles(self):
        """Each character should get prompts for front, three_quarter, side, back."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(state_dir=Path("/tmp/test_v4"), manifest={})
        manifest = {
            "episode_code": "EP001",
            "characters": [
                {"character_id": "char_001", "name": "主角", "description": "黑发少年"}
            ],
            "shots": [],
        }
        result = coordinator.execute_asset_generation(
            episode_code="EP001",
            episode_manifest=manifest,
            providers_config_path="providers.yaml",
            output_root="/tmp/test_v4_output",
        )
        views = result["four_view_prompts"][0]["views"]
        angles = {v["angle"] for v in views}
        assert "front" in angles
        assert "three_quarter" in angles
        assert "side" in angles
        assert "back" in angles

    def test_four_view_skipped_when_no_characters(self):
        """No characters in manifest → empty four_view_prompts, not crash."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(state_dir=Path("/tmp/test_v4"), manifest={})
        result = coordinator.execute_asset_generation(
            episode_code="EP001",
            episode_manifest={"episode_code": "EP001", "characters": [], "shots": []},
            providers_config_path="providers.yaml",
            output_root="/tmp/test_v4_output",
        )
        assert result["four_view_prompts"] == []


# ── P0-2: Video router mandatory ──────────────────────────────────────────


class TestVideoRouterIntegration:
    """P0-2: VideoRouter mandatory in request_builder for all video requests."""

    def test_video_request_uses_router(self):
        """build_provider_requests should route video shots through VideoRouter."""
        from aicomic.providers.request_builder import build_provider_requests

        manifest = {
            "episode_code": "EP001",
            "episodes": [
                {
                    "episode_code": "EP001",
                    "shots": [
                        {
                            "shot_id": "S001",
                            "dialogue": "你好",
                            "tts_prompt": "你好",
                        }
                    ],
                }
            ],
            "shots": [
                {
                    "shot_id": "S001",
                    "dialogue": "你好",
                    "tts_prompt": "你好",
                }
            ],
        }
        with patch("aicomic.providers.request_builder.VideoRouter") as MockRouter:
            mock_instance = MockRouter.from_config.return_value
            mock_instance.route_shot.return_value = MagicMock(
                provider_name="kling",
                shot_type="action",
                reason="routed",
            )
            result = build_provider_requests(
                manifest=manifest,
                jobs=[],
                providers_config_path=Path("providers.yaml"),
                output_root=Path("/tmp/test_v4_output"),
            )
            # VideoRouter.from_config should have been called
            MockRouter.from_config.assert_called()

    def test_video_router_fallback_chain(self):
        """When primary provider fails, router should provide fallback."""
        from aicomic.providers.video_router import VideoRouter, ShotType

        router = VideoRouter()
        # Router should have a fallback for every shot type
        for shot_type in ShotType.ALL:
            decision = router.route(shot_type)
            assert decision is not None
            assert decision.provider_name  # non-empty


# ── P0-3: Drift gate ──────────────────────────────────────────────────────


class TestDriftGate:
    """P0-3: Drift gate consistency checking after image generation."""

    def test_drift_gate_exists(self):
        """DriftGate class should be importable."""
        from aicomic.image_consistency.drift_gate import DriftGate

        assert DriftGate is not None

    def test_drift_gate_pass(self):
        """High similarity → PASS."""
        from aicomic.image_consistency.drift_gate import DriftGate

        gate = DriftGate(threshold=60)
        result = gate.check(
            reference_features={"hair_color": "black", "eye_color": "brown"},
            generated_features={"hair_color": "black", "eye_color": "brown"},
            score=95,
        )
        assert result["status"] == "PASS"
        assert result["score"] == 95

    def test_drift_gate_fail(self):
        """Low similarity → FAIL."""
        from aicomic.image_consistency.drift_gate import DriftGate

        gate = DriftGate(threshold=60)
        result = gate.check(
            reference_features={"hair_color": "black", "eye_color": "brown"},
            generated_features={"hair_color": "blonde", "eye_color": "blue"},
            score=30,
        )
        assert result["status"] == "FAIL"
        assert result["score"] < 60

    def test_drift_gate_warn(self):
        """Borderline → WARN."""
        from aicomic.image_consistency.drift_gate import DriftGate

        gate = DriftGate(threshold=60)
        result = gate.check(
            reference_features={"hair_color": "black"},
            generated_features={"hair_color": "dark_brown"},
            score=65,
        )
        assert result["status"] == "WARN"

    def test_drift_gate_returns_details(self):
        """DriftGate should return detailed diff info."""
        from aicomic.image_consistency.drift_gate import DriftGate

        gate = DriftGate()
        result = gate.check(
            reference_features={"a": "1"},
            generated_features={"a": "2"},
            score=50,
        )
        assert "diffs" in result
        assert len(result["diffs"]) > 0


# ── P0-4: Multi-language pipeline ─────────────────────────────────────────


class TestI18nPipelineIntegration:
    """P0-4: Multi-language subtitle + TTS in tts_subtitle stage."""

    def test_tts_subtitle_includes_multilang(self):
        """execute_tts_subtitle should produce multi-language subtitles when configured."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(state_dir=Path("/tmp/test_v4"), manifest={})
        manifest = {
            "episode_code": "EP001",
            "output_languages": ["zh", "en"],
            "episodes": [
                {
                    "episode_code": "EP001",
                    "shots": [
                        {
                            "shot_id": "S001",
                            "dialogue": "你好世界",
                            "tts_prompt": "你好世界",
                        }
                    ],
                }
            ],
            "shots": [
                {
                    "shot_id": "S001",
                    "dialogue": "你好世界",
                    "tts_prompt": "你好世界",
                }
            ],
        }
        result = coordinator.execute_tts_subtitle(
            episode_code="EP001", episode_manifest=manifest
        )
        assert "multilang_subtitles" in result
        assert "zh" in result["multilang_subtitles"]
        assert "en" in result["multilang_subtitles"]

    def test_tts_subtitle_default_single_lang(self):
        """Without output_languages config, default to zh only."""
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(state_dir=Path("/tmp/test_v4"), manifest={})
        manifest = {
            "episode_code": "EP001",
            "episodes": [
                {
                    "episode_code": "EP001",
                    "shots": [
                        {"shot_id": "S001", "dialogue": "你好", "tts_prompt": "你好"}
                    ],
                }
            ],
            "shots": [
                {"shot_id": "S001", "dialogue": "你好", "tts_prompt": "你好"}
            ],
        }
        result = coordinator.execute_tts_subtitle(
            episode_code="EP001", episode_manifest=manifest
        )
        assert "multilang_subtitles" in result
        assert "zh" in result["multilang_subtitles"]

    def test_multilang_tts_voice_routing(self):
        """Each language should get appropriate TTS voice."""
        from aicomic.video_synthesis.i18n import get_voice_for_language

        voice_zh = get_voice_for_language("zh", "female")
        voice_en = get_voice_for_language("en", "female")
        voice_ja = get_voice_for_language("ja", "female")
        assert "zh-CN" in voice_zh
        assert "en-US" in voice_en
        assert "ja-JP" in voice_ja
