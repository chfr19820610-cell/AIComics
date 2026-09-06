"""Tests for video router and FLF interpolator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── VideoRouter ───────────────────────────────────────────────────────────

class TestVideoRouter:
    def test_route_action_to_kling(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        decision = router.route(ShotType.ACTION)
        assert decision.provider_name == "kling"
        assert decision.shot_type == "action"

    def test_route_dialogue_to_seedance(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        decision = router.route(ShotType.DIALOGUE)
        assert decision.provider_name == "seedance"

    def test_route_wide_to_wan(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        decision = router.route(ShotType.WIDE)
        assert decision.provider_name == "wan"
        # Wan provider is not yet implemented — provider should be None
        assert decision.provider is None

    def test_route_unknown_shot_falls_back_to_dialogue(self):
        from aicomic.providers.video_router import VideoRouter
        router = VideoRouter()
        decision = router.route("nonexistent_type")
        assert decision.shot_type == "dialogue"

    def test_route_with_flf_flag(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        decision = router.route(ShotType.ACTION, flf=True)
        assert decision.flf_enabled is True

    def test_route_batch(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        shots = [
            {"shot_type": "action", "flf": True},
            {"shot_type": "dialogue", "flf": False},
            {"shot_type": "wide"},
        ]
        decisions = router.route_batch(shots)
        assert len(decisions) == 3
        assert decisions[0].provider_name == "kling"
        assert decisions[1].provider_name == "seedance"
        assert decisions[2].provider_name == "wan"

    def test_update_routing(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        router.update_routing(ShotType.ACTION, "seedance")
        decision = router.route(ShotType.ACTION)
        assert decision.provider_name == "seedance"

    def test_get_routing_table(self):
        from aicomic.providers.video_router import VideoRouter
        router = VideoRouter()
        table = router.get_routing_table()
        assert "action" in table
        assert "dialogue" in table
        assert "wide" in table
        # Ensure it's a copy
        table["action"] = "modified"
        assert router.get_routing_table()["action"] != "modified"

    def test_routing_decision_has_reason(self):
        from aicomic.providers.video_router import VideoRouter, ShotType
        router = VideoRouter()
        decision = router.route(ShotType.ACTION)
        assert len(decision.reason) > 0
        assert "Kling" in decision.reason or "kling" in decision.reason.lower()


# ── FLF Interpolator ──────────────────────────────────────────────────────

class TestFLFRequest:
    def test_to_provider_payload(self):
        from aicomic.providers.flf_interpolator import FLFRequest
        req = FLFRequest(
            first_frame="start.png",
            last_frame="end.png",
            duration=3.0,
            motion_hint="character walks",
        )
        payload = req.to_provider_payload()
        assert payload["mode"] == "flf"
        assert payload["first_frame"] == "start.png"
        assert payload["last_frame"] == "end.png"
        assert payload["duration"] == 3.0
        assert payload["motion_hint"] == "character walks"

    def test_seed_negative_becomes_none_in_payload(self):
        from aicomic.providers.flf_interpolator import FLFRequest
        req = FLFRequest(first_frame="a", last_frame="b", seed=-1)
        payload = req.to_provider_payload()
        assert payload["seed"] is None


class TestFLFInterpolator:
    def test_interpolate_without_provider_returns_error(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        interp = FLFInterpolator(provider=None)
        result = interp.interpolate("start.png", "end.png")
        assert result.success is False
        assert "No video provider" in result.error

    def test_interpolate_missing_first_frame(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        interp = FLFInterpolator()
        result = interp.interpolate("", "end.png")
        assert result.success is False
        assert "first_frame" in result.error

    def test_interpolate_missing_last_frame(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        interp = FLFInterpolator()
        result = interp.interpolate("start.png", "")
        assert result.success is False
        assert "last_frame" in result.error

    def test_interpolate_negative_duration(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        interp = FLFInterpolator()
        result = interp.interpolate("a.png", "b.png", duration=-1)
        assert result.success is False
        assert "duration" in result.error

    def test_interpolate_with_mock_provider_success(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        mock_provider = MagicMock()
        mock_provider.execute_request.return_value = {"output_path": "/tmp/out.mp4"}
        interp = FLFInterpolator(provider=mock_provider)
        result = interp.interpolate("start.png", "end.png", duration=3.0)
        assert result.success is True
        assert result.video_path == "/tmp/out.mp4"
        mock_provider.execute_request.assert_called_once()

    def test_interpolate_with_mock_provider_error(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        mock_provider = MagicMock()
        mock_provider.execute_request.return_value = {"error": "API timeout"}
        interp = FLFInterpolator(provider=mock_provider)
        result = interp.interpolate("start.png", "end.png")
        assert result.success is False
        assert result.error == "API timeout"

    def test_interpolate_with_provider_exception(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        mock_provider = MagicMock()
        mock_provider.execute_request.side_effect = RuntimeError("network error")
        interp = FLFInterpolator(provider=mock_provider)
        result = interp.interpolate("a.png", "b.png")
        assert result.success is False
        assert "network error" in result.error

    def test_interpolate_batch(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        mock_provider = MagicMock()
        mock_provider.execute_request.return_value = {"output_path": "/tmp/out.mp4"}
        interp = FLFInterpolator(provider=mock_provider)
        pairs = [
            {"first_frame": "k1.png", "last_frame": "k2.png"},
            {"first_frame": "k2.png", "last_frame": "k3.png"},
        ]
        results = interp.interpolate_batch(pairs)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_build_motion_continuity_chain(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator, FLFRequest
        interp = FLFInterpolator()
        keyframes = ["k1.png", "k2.png", "k3.png", "k4.png"]
        chain = interp.build_motion_continuity_chain(keyframes, duration_per_shot=2.0)
        assert len(chain) == 3
        assert chain[0].first_frame == "k1.png"
        assert chain[0].last_frame == "k2.png"
        assert chain[1].first_frame == "k2.png"
        assert chain[1].last_frame == "k3.png"
        assert chain[2].first_frame == "k3.png"
        assert chain[2].last_frame == "k4.png"
        assert all(r.duration == 2.0 for r in chain)

    def test_build_motion_continuity_chain_too_short(self):
        from aicomic.providers.flf_interpolator import FLFInterpolator
        interp = FLFInterpolator()
        chain = interp.build_motion_continuity_chain(["only_one.png"])
        assert chain == []
