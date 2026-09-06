"""Matting service — RMBG-2.0 background removal via ComfyUI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.image_pipeline.workflows import build_matting_workflow


class MattingService:
    """Remove image background using RMBG-2.0 via ComfyUI."""

    def __init__(self, comfyui_client: Any) -> None:
        self.client = comfyui_client

    def remove_background(
        self,
        input_image: Path,
        output_path: Path,
        rmbg_model: str = "RMBG-2.0.pth",
    ) -> Path:
        """Remove background from input_image, save to output_path."""
        if not Path(input_image).exists():
            raise FileNotFoundError(f"Input image not found: {input_image}")
        workflow = build_matting_workflow(str(input_image), rmbg_model)
        self.client.submit_and_wait(workflow, output_path=str(output_path))
        return output_path
