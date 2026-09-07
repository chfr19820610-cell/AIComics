"""2.5D pipeline — Blender Cycles cel-shaded plane + orbit camera.

Migrated from ACOM-0.8.0 (design review 100/100, red-blue 300 rounds 0 breaches).
Original files:
  - breathing_2d5.py  (breathing animation: subtle scale/opacity oscillation)
  - tri2d_render.py   (cel-shader material + Cycles orbit camera ±12°)
  - compose_final.py  (breathing → cross-dissolve → tri2d → dissolve → breathing)

This module provides a clean Python interface for the 2.5D render line.
The actual Blender scripts remain in company/projects/ for direct `blender -b`
invocation; this wrapper builds render plans and coordinates file flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TwoHalfDRenderConfig:
    """Configuration for 2.5D rendering."""
    orbit_degrees: float = 12.0       # camera orbit range ±N degrees
    frame_count: int = 90             # tri2d frames
    breathing_frames: int = 105       # breathing frames per segment
    cross_dissolve_frames: int = 8    # transition between segments
    cycles_samples: int = 16          # Cycles render samples
    resolution: tuple[int, int] = (1080, 1920)  # vertical 9:16
    blender_bin: str = "/Applications/Blender.app/Contents/MacOS/Blender"
    # Scripts (relative to company/projects/aicomics/acom-0.8.0/src/)
    breathing_script: str = "breathing_2d5.py"
    tri2d_script: str = "tri2d_render.py"
    compose_script: str = "compose_final.py"


class TwoHalfDPipeline:
    """2.5D render pipeline: breathing → tri2d cel-shade → compose.

    Usage:
        pipe = TwoHalfDPipeline()
        plan = pipe.build_plan(
            episode="E01",
            master_image="character_master.png",
            config=TwoHalfDRenderConfig(),
        )
    """

    # Path to ACOM-0.8.0 source scripts
    SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "company" / "projects" / "aicomics" / "acom-0.8.0" / "src"

    def build_plan(
        self,
        episode: str,
        master_image: str,
        config: TwoHalfDRenderConfig | None = None,
    ) -> dict[str, Any]:
        """Build a 2.5D render plan.

        Args:
            episode: Episode code.
            master_image: Path to character master sheet PNG.
            config: Render configuration.

        Returns:
            Render plan with Blender script invocations and frame counts.
        """
        cfg = config or TwoHalfDRenderConfig()
        total_frames = (
            cfg.breathing_frames * 2     # two breathing segments
            + cfg.frame_count            # tri2d segment
            + cfg.cross_dissolve_frames * 2  # two dissolves
        )
        return {
            "mode": "2.5d",
            "episode": episode,
            "engine": "blender_cycles",
            "master_image": master_image,
            "resolution": cfg.resolution,
            "total_frames": total_frames,
            "segments": [
                {
                    "name": "breathing_1",
                    "script": cfg.breathing_script,
                    "frames": cfg.breathing_frames,
                },
                {
                    "name": "cross_dissolve_1",
                    "frames": cfg.cross_dissolve_frames,
                },
                {
                    "name": "tri2d_cel",
                    "script": cfg.tri2d_script,
                    "frames": cfg.frame_count,
                    "orbit_degrees": cfg.orbit_degrees,
                    "cycles_samples": cfg.cycles_samples,
                },
                {
                    "name": "cross_dissolve_2",
                    "frames": cfg.cross_dissolve_frames,
                },
                {
                    "name": "breathing_2",
                    "script": cfg.breathing_script,
                    "frames": cfg.breathing_frames,
                },
            ],
            "compose_script": cfg.compose_script,
            "scripts_dir": str(self.SCRIPTS_DIR),
            "requires_blender": True,
            "requires_tripo": False,
            "blender_bin": cfg.blender_bin,
        }

    def get_capabilities(self) -> dict[str, Any]:
        """Return 2.5D pipeline capabilities."""
        return {
            "engine": "blender_cycles",
            "requires_blender": True,
            "requires_tripo": False,
            "frame_time": "~1.2s/frame (Cycles 16 samples)",
            "description": "Cel-shaded plane + Blender Cycles orbit camera (±12°)",
            "mature": True,
            "test_coverage": "red-blue 300 rounds, design review 100/100",
        }
