"""AI图像生成Pipeline — 抠图→生图→放大→合成→输出."""
from aicomic.image_pipeline.models import ModelManager
from aicomic.image_pipeline.workflows import (
    build_matting_workflow,
    build_generate_workflow,
    build_upscale_workflow,
    build_full_pipeline_workflow,
)
from aicomic.image_pipeline.matting import MattingService
from aicomic.image_pipeline.generation import GenerationService
from aicomic.image_pipeline.upscaling import UpscalingService
from aicomic.image_pipeline.composite import CompositeService
from aicomic.image_pipeline.pipeline import ImagePipeline

__all__ = [
    "ModelManager",
    "build_matting_workflow",
    "build_generate_workflow",
    "build_upscale_workflow",
    "build_full_pipeline_workflow",
    "MattingService",
    "GenerationService",
    "UpscalingService",
    "CompositeService",
    "ImagePipeline",
]
