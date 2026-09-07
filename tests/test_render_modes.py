"""Tests for three-line render architecture (2D / 2.5D / 3D)."""
from __future__ import annotations

import pytest


class TestRenderModeRouter:
    def test_route_2d(self):
        from aicomic.render.mode_router import RenderModeRouter, RenderMode
        router = RenderModeRouter()
        plan = router.route(mode="2d")
        assert plan.mode == "2d"
        assert plan.engine == "ffmpeg"
        assert plan.requires_blender is False
        assert plan.requires_tripo is False

    def test_route_2_5d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route(mode="2.5d")
        assert plan.mode == "2.5d"
        assert plan.engine == "blender_cycles"
        assert plan.requires_blender is True
        assert plan.requires_tripo is False

    def test_route_3d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route(mode="3d")
        assert plan.mode == "3d"
        assert plan.engine == "blender_cycles"
        assert plan.requires_blender is True
        assert plan.requires_tripo is True

    def test_route_unknown_raises(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        with pytest.raises(ValueError, match="Unknown"):
            router.route(mode="4d")

    def test_route_auto_dialogue_to_2d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route_auto(shot_type="dialogue")
        assert plan.mode == "2d"
        assert plan.auto_routed is True

    def test_route_auto_action_to_2_5d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route_auto(shot_type="action")
        assert plan.mode == "2.5d"

    def test_route_auto_key_moment_to_3d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route_auto(shot_type="key_moment")
        assert plan.mode == "3d"

    def test_route_auto_unknown_defaults_2d(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        plan = router.route_auto(shot_type="whatever")
        assert plan.mode == "2d"

    def test_route_batch(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        shots = [
            {"shot_type": "dialogue"},
            {"shot_type": "action"},
            {"shot_type": "key_moment"},
            {"mode": "3d", "shot_type": "closeup"},
        ]
        plans = router.route_batch(shots)
        assert len(plans) == 4
        assert plans[0].mode == "2d"
        assert plans[1].mode == "2.5d"
        assert plans[2].mode == "3d"
        assert plans[3].mode == "3d"  # explicit override

    def test_check_readiness_2d_always_ready(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        r = router.check_readiness("2d")
        assert r["ready"] is True

    def test_check_readiness_2_5d_needs_blender(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        r = router.check_readiness("2.5d", blender_available=False)
        assert r["ready"] is False
        assert "Blender" in r["blockers"][0]

    def test_check_readiness_3d_needs_both(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        r = router.check_readiness("3d", blender_available=False, tripo_key_configured=False)
        assert r["ready"] is False
        assert len(r["blockers"]) == 2

    def test_check_readiness_3d_with_blender_no_key(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        r = router.check_readiness("3d", blender_available=True, tripo_key_configured=False)
        assert r["ready"] is False
        assert "Tripo" in r["blockers"][0]

    def test_check_readiness_3d_all_present(self):
        from aicomic.render.mode_router import RenderModeRouter
        router = RenderModeRouter()
        r = router.check_readiness("3d", blender_available=True, tripo_key_configured=True)
        assert r["ready"] is True
