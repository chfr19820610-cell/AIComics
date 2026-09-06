"""Generation service — SDXL/Flux text-to-image with optional ControlNet."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.image_pipeline.workflows import build_generate_workflow


class GenerationService:
    """Generate images via ComfyUI (SDXL or Flux)."""

    def __init__(self, comfyui_client: Any) -> None:
        self.client = comfyui_client

    def generate(
        self,
        prompt: str,
        negative: str,
        width: int,
        height: int,
        seed: int,
        steps: int,
        cfg: float,
        checkpoint: str,
        output_path: Path,
        controlnet_type: str | None = None,
        controlnet_model: str | None = None,
        controlnet_image: Path | None = None,
    ) -> Path:
        """Generate an image and save to output_path."""
        workflow = build_generate_workflow(
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            checkpoint=checkpoint,
            controlnet_type=controlnet_type,
            controlnet_model=controlnet_model,
            controlnet_image=str(controlnet_image) if controlnet_image else None,
        )
        result = self.client.submit_and_wait(workflow, output_path=str(output_path))
        output_path = Path(result.get("output_path", output_path))
        return output_path
