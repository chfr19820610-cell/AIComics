"""2.5D render line — cel-shaded plane + Blender Cycles orbit camera.

Migrated from company/projects/aicomics/acom-0.8.0/ (design review 100/100).
Uses Blender Cycles with cel-shader material on a standing character plane,
orbit camera ±12° for pseudo-3D turn effect.

Requires: Blender 4.4+ (Cycles engine, no Eevee Next -b issues).
"""
from aicomic.render.two_half_d.pipeline import TwoHalfDPipeline

__all__ = ["TwoHalfDPipeline"]
