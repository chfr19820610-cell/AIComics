"""2D render line — keyframe + Ken Burns + ffmpeg interpolation.

This is the most mature pipeline (v1.0 baseline). It uses:
  - keyframe_engine for first/last frame prompt generation
  - Ken Burns zoom/pan via ffmpeg zoompan filter
  - ffmpeg morph/zoom/pan interpolation between keyframes

No Blender or Tripo required — just ffmpeg.
"""
from aicomic.render.two_d.pipeline import TwoDPipeline

__all__ = ["TwoDPipeline"]
