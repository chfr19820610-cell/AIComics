"""3D pipeline — Tripo → Mixamo → Blender cel-shader full chain.

Migrated from ACOM-0.9.0 (gate 5/5 PASS, fallback mode verified).
Original files in company/projects/aicomics/acom-0.9.0/src/:
  - tripo_pipeline.py   (image → Tripo 3D → rig → FBX export)
  - auto_animate.py     (Blender: import FBX + Mixamo animation → export)
  - cel_shader_setup.py (Blender: cel material + freestyle outline render)

Requires: TRIPO_API_KEY environment variable for real 3D generation.
Without key, falls back to placeholder mode (gate tests still pass).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ThreeDRenderConfig:
    """Configuration for 3D rendering."""
    tripo_model: str = "v3.1-20260211"     # Tripo model version
    tripo_preset: str = "mixamo"            # Rig preset for Mixamo compatibility
    cel_outline: bool = True                # Freestyle outline
    cycles_samples: int = 16
    resolution: tuple[int, int] = (1080, 1920)
    frame_count: int = 90
    blender_bin: str = "/Applications/Blender.app/Contents/MacOS/Blender"
    # Scripts (relative to company/projects/aicomics/acom-0.9.0/src/)
    tripo_script: str = "tripo_pipeline.py"
    animate_script: str = "auto_animate.py"
    cel_shader_script: str = "cel_shader_setup.py"


class ThreeDPipeline:
    """3D render pipeline: Tripo → Mixamo → cel-shader.

    Usage:
        pipe = ThreeDPipeline()
        plan = pipe.build_plan(
            episode="E01",
            character_image="character.png",
            config=ThreeDRenderConfig(),
        )
    """

    # Path to ACOM-0.9.0 source scripts
    SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "company" / "projects" / "aicomics" / "acom-0.9.0" / "src"

    def build_plan(
        self,
        episode: str,
        character_image: str,
        config: ThreeDRenderConfig | None = None,
    ) -> dict[str, Any]:
        """Build a 3D render plan.

        Args:
            episode: Episode code.
            character_image: Path to character reference image for Tripo.
            config: Render configuration.

        Returns:
            Render plan with Tripo + Blender invocations.
        """
        cfg = config or ThreeDRenderConfig()
        tripo_key = os.environ.get("TRIPO_API_KEY", "")
        has_key = bool(tripo_key)

        return {
            "mode": "3d",
            "episode": episode,
            "engine": "blender_cycles",
            "character_image": character_image,
            "resolution": cfg.resolution,
            "frame_count": cfg.frame_count,
            "tripo_available": has_key,
            "phases": [
                {
                    "name": "phase1_generate_3d",
                    "script": cfg.tripo_script,
                    "description": "Image → Tripo 3D model → rig → FBX export",
                    "requires_api_key": True,
                    "fallback": "placeholder_local" if not has_key else None,
                    "model": cfg.tripo_model,
                    "preset": cfg.tripo_preset,
                },
                {
                    "name": "phase2_auto_animate",
                    "script": cfg.animate_script,
                    "description": "Blender: import FBX + Mixamo animation → export animated FBX",
                    "requires_api_key": False,
                },
                {
                    "name": "phase3_cel_render",
                    "script": cfg.cel_shader_script,
                    "description": "Blender: cel material + freestyle outline → 1080×1920 frames",
                    "requires_api_key": False,
                    "cycles_samples": cfg.cycles_samples,
                    "outline": cfg.cel_outline,
                },
            ],
            "scripts_dir": str(self.SCRIPTS_DIR),
            "requires_blender": True,
            "requires_tripo": True,
            "tripo_key_configured": has_key,
            "blender_bin": cfg.blender_bin,
        }

    def get_capabilities(self) -> dict[str, Any]:
        """Return 3D pipeline capabilities."""
        return {
            "engine": "blender_cycles",
            "requires_blender": True,
            "requires_tripo": True,
            "frame_time": "~2-5s/frame (3D model + cel shader)",
            "description": "Tripo image-to-3D → Mixamo rig → Blender cel-shader render",
            "mature": False,
            "test_coverage": "gate 5/5 PASS (fallback mode, real 3D pending API key)",
        }
