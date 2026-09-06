"""Upscaling service — Real-ESRGAN via ComfyUI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.image_pipeline.workflows import build_upscale_workflow


class UpscalingService:
    """Upscale images using Real-ESRGAN via ComfyUI."""

    def __init__(self, comfyui_client: Any) -> None:
        self.client = comfyui_client

    def upscale(
        self,
        input_image: Path,
        model: str,
        scale: int,
        output_path: Path,
    ) -> Path:
        """Upscale input_image by `scale`x using given model."""
        if not Path(input_image).exists():
            raise FileNotFoundError(f"Input image not found: {input_image}")
        workflow = build_upscale_workflow(str(input_image), model, scale)
        result = self.client.submit_and_wait(workflow, output_path=str(output_path))
        output_path = Path(result.get("output_path", output_path))
        return output_path
