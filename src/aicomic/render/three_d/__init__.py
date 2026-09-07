"""3D render line — Tripo image-to-3D → Mixamo rig → Blender cel-shader.

Migrated from company/projects/aicomics/acom-0.9.0/ (gate 5/5 PASS).
Full chain: character image → Tripo 3D model → auto-rig (Mixamo) →
Blender cel-shader render with freestyle outline.

Requires: Blender 4.4+ + Tripo API key + (optional) Mixamo action library.
"""
from aicomic.render.three_d.pipeline import ThreeDPipeline

__all__ = ["ThreeDPipeline"]
