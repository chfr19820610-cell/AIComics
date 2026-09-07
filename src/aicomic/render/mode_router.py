"""Render mode router — 2D / 2.5D / 3D three-line selection.

AIComics v3.0 three-line architecture (peak's directive):
  - 2D:     Static keyframe + Ken Burns zoom/pan + ffmpeg interpolation
  - 2.5D:   Cel-shaded plane + Blender Cycles orbit camera (±12° pseudo-3D)
  - 3D:     Tripo image-to-3D → Mixamo rig → Blender cel-shader render

The router selects a render mode and delegates to the corresponding
pipeline. It does NOT execute Blender/ComfyUI — it returns a render
plan that the caller executes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class RenderMode:
    """Supported render modes."""
    TWO_D = "2d"
    TWO_HALF_D = "2.5d"
    THREE_D = "3d"

    ALL: tuple[str, ...] = (TWO_D, TWO_HALF_D, THREE_D)


# ── Auto-routing: shot type → render mode ─────────────────────────────────

SHOT_TYPE_TO_MODE: dict[str, str] = {
    "dialogue": RenderMode.TWO_D,       # talking heads, cheap and fast
    "action": RenderMode.TWO_HALF_D,    # motion needs pseudo-3D depth
    "establishing": RenderMode.TWO_D,   # static wide shots
    "closeup": RenderMode.TWO_D,        # emotion close-ups
    "key_moment": RenderMode.THREE_D,   # hero shots need real 3D
    "transition": RenderMode.TWO_D,     # transitions are cheap
    "flashback": RenderMode.TWO_HALF_D, # dreamy pseudo-3D feel
}

# ── Mode capabilities ─────────────────────────────────────────────────────

MODE_CAPABILITIES: dict[str, dict[str, Any]] = {
    RenderMode.TWO_D: {
        "engine": "ffmpeg",
        "requires_blender": False,
        "requires_tripo": False,
        "frame_time": "seconds",
        "description": "Static keyframe + Ken Burns zoom/pan + ffmpeg interpolation",
    },
    RenderMode.TWO_HALF_D: {
        "engine": "blender_cycles",
        "requires_blender": True,
        "requires_tripo": False,
        "frame_time": "~1.2s/frame (Cycles 16 samples)",
        "description": "Cel-shaded plane + Blender Cycles orbit camera (±12°)",
    },
    RenderMode.THREE_D: {
        "engine": "blender_cycles",
        "requires_blender": True,
        "requires_tripo": True,
        "frame_time": "~2-5s/frame (3D model + cel shader)",
        "description": "Tripo image-to-3D → Mixamo rig → Blender cel-shader render",
    },
}


@dataclass
class RenderPlan:
    """A render plan produced by the mode router."""
    mode: str
    engine: str
    description: str
    requires_blender: bool
    requires_tripo: bool
    shot_type: str = ""
    auto_routed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class RenderModeRouter:
    """Routes render requests to the appropriate pipeline (2D/2.5D/3D).

    Usage:
        router = RenderModeRouter()
        plan = router.route(mode="2d", episode="E01")
        plan = router.route_auto(shot_type="action")
    """

    def route(
        self,
        mode: str,
        episode: str = "",
        shot_type: str = "",
        **kwargs: Any,
    ) -> RenderPlan:
        """Select a render mode explicitly."""
        normalized = mode.lower().strip()
        if normalized not in RenderMode.ALL:
            raise ValueError(
                f"Unknown render mode '{mode}'. Supported: {RenderMode.ALL}"
            )
        caps = MODE_CAPABILITIES[normalized]
        return RenderPlan(
            mode=normalized,
            engine=caps["engine"],
            description=caps["description"],
            requires_blender=caps["requires_blender"],
            requires_tripo=caps["requires_tripo"],
            shot_type=shot_type,
            auto_routed=False,
            extra=kwargs,
        )

    def route_auto(
        self,
        shot_type: str,
        episode: str = "",
        **kwargs: Any,
    ) -> RenderPlan:
        """Auto-select render mode based on shot type."""
        normalized = shot_type.lower().strip()
        mode = SHOT_TYPE_TO_MODE.get(normalized, RenderMode.TWO_D)
        caps = MODE_CAPABILITIES[mode]
        return RenderPlan(
            mode=mode,
            engine=caps["engine"],
            description=caps["description"],
            requires_blender=caps["requires_blender"],
            requires_tripo=caps["requires_tripo"],
            shot_type=normalized,
            auto_routed=True,
            extra=kwargs,
        )

    def route_batch(
        self,
        shots: list[dict[str, Any]],
    ) -> list[RenderPlan]:
        """Route a batch of shots. Each shot dict must have 'shot_type'.
        If 'mode' is present in the shot dict, it overrides auto-routing.
        """
        plans: list[RenderPlan] = []
        for shot in shots:
            explicit_mode = shot.get("mode")
            st = shot.get("shot_type", "dialogue")
            if explicit_mode:
                plans.append(self.route(mode=explicit_mode, shot_type=st))
            else:
                plans.append(self.route_auto(shot_type=st))
        return plans

    def get_capabilities(self, mode: str) -> dict[str, Any]:
        """Return capability info for a render mode."""
        normalized = mode.lower().strip()
        return MODE_CAPABILITIES.get(normalized, {})

    def check_readiness(
        self,
        mode: str,
        blender_available: bool = False,
        tripo_key_configured: bool = False,
    ) -> dict[str, Any]:
        """Check if the environment can run a given render mode."""
        normalized = mode.lower().strip()
        caps = MODE_CAPABILITIES.get(normalized, {})
        if not caps:
            return {"ready": False, "reason": f"Unknown mode '{mode}'"}

        blockers: list[str] = []
        if caps["requires_blender"] and not blender_available:
            blockers.append("Blender not available")
        if caps["requires_tripo"] and not tripo_key_configured:
            blockers.append("Tripo API key not configured")

        return {
            "ready": len(blockers) == 0,
            "mode": normalized,
            "engine": caps["engine"],
            "blockers": blockers,
        }
