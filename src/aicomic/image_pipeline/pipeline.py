"""Image pipeline orchestrator — matting → generate → upscale → composite → output."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from aicomic.image_pipeline.matting import MattingService
from aicomic.image_pipeline.generation import GenerationService
from aicomic.image_pipeline.upscaling import UpscalingService
from aicomic.image_pipeline.composite import CompositeService
from aicomic.image_consistency.triple_lock import build_triple_lock_workflow, build_triple_lock_metadata


class ImagePipeline:
    """5-stage pipeline: matting → generate → upscale → composite → output."""

    def _try_post_comfyui(self, workflow: dict[str, Any], output_path: Path) -> bool:
        """Try to post a ComfyUI workflow. Returns True if posted, False if ComfyUI not available."""
        import logging
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                "http://127.0.0.1:8188/prompt",
                data=_json.dumps({"prompt": workflow}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            logging.debug("ComfyUI not available, falling back to standard generate")
            return False

    def __init__(
        self,
        comfyui_client: Any,
        output_dir: Path = Path("output"),
    ) -> None:
        self.client = comfyui_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.matting = MattingService(comfyui_client)
        self.generation = GenerationService(comfyui_client)
        self.upscaling = UpscalingService(comfyui_client)
        self.composite_svc = CompositeService()

    def run(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int = -1,
        steps: int = 20,
        cfg: float = 7.0,
        checkpoint: str = "sd_xl_base_1.0.safetensors",
        controlnet_type: str | None = None,
        controlnet_model: str | None = None,
        controlnet_image: Path | None = None,
        reference_image: Path | None = None,
        rmbg_model: str = "RMBG-2.0.pth",
        upscale: bool = False,
        upscale_model: str = "RealESRGAN_x4plus.pth",
        upscale_scale: int = 4,
        composite_bg: Path | None = None,
    ) -> dict[str, Any]:
        """Execute the full pipeline. Returns dict with output_path, stages, metadata."""
        if seed < 0:
            import random
            seed = random.randint(1, 2**32 - 1)

        stages: list[str] = []
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        work_dir = self.output_dir / f"run_{timestamp}_{seed}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # ① Matting (optional — only if reference image provided)
        foreground: Path | None = None
        triple_lock_used = False
        if reference_image and controlnet_image:
            # Triple-Lock: IPAdapter FaceID + ControlNet + FaceDetailer
            triple_lock_used = True
            stages.append("triple_lock")
            tl_workflow = build_triple_lock_workflow(
                prompt=prompt,
                negative=negative,
                width=width,
                height=height,
                seed=seed,
                steps=steps,
                cfg=cfg,
                checkpoint=checkpoint,
                reference_image=str(reference_image),
                controlnet_type=controlnet_type or "openpose",
                controlnet_image=str(controlnet_image),
            )
            # Post to ComfyUI when available; for now build plan only
            tl_metadata = build_triple_lock_metadata(
                prompt=prompt,
                reference_image=str(reference_image),
                controlnet_type=controlnet_type or "openpose",
                seed=seed,
            )
            tl_plan_path = work_dir / "triple_lock_plan.json"
            tl_plan_path.write_text(
                json.dumps(tl_workflow, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            gen_output = work_dir / "generated.png"
            # If ComfyUI is running, post the workflow; else fall through to standard generate
            if not self._try_post_comfyui(tl_workflow, gen_output):
                # ComfyUI offline — produce plan only, no actual generation
                gen_output = work_dir / "triple_lock_plan.json"
                stages.append("triple_lock_plan_only")
            stages.append("generate")
        elif reference_image:
            foreground = work_dir / "foreground.png"
            self.matting.remove_background(reference_image, foreground, rmbg_model)
            stages.append("matting")

            # ② Generate
            gen_output = work_dir / "generated.png"
            self.generation.generate(
                prompt=prompt, negative=negative,
                width=width, height=height, seed=seed,
                steps=steps, cfg=cfg, checkpoint=checkpoint,
                controlnet_type=controlnet_type,
                controlnet_model=controlnet_model,
                controlnet_image=controlnet_image,
                output_path=gen_output,
            )
            stages.append("generate")
        else:
            # ② Generate (no reference image)
            gen_output = work_dir / "generated.png"
            self.generation.generate(
                prompt=prompt, negative=negative,
                width=width, height=height, seed=seed,
                steps=steps, cfg=cfg, checkpoint=checkpoint,
                controlnet_type=controlnet_type,
                controlnet_model=controlnet_model,
                controlnet_image=controlnet_image,
                output_path=gen_output,
            )
            stages.append("generate")
        current = gen_output

        # ③ Upscale (optional — skip if plan-only mode)
        if upscale and "triple_lock_plan_only" not in stages:
            upscaled = work_dir / "upscaled.png"
            self.upscaling.upscale(current, upscale_model, upscale_scale, upscaled)
            stages.append("upscale")
            current = upscaled

        # ④ Composite (optional — needs foreground from matting, skip if plan-only)
        if composite_bg and "triple_lock_plan_only" not in stages:
            composite_out = work_dir / "composite.png"
            self.composite_svc.composite(
                foreground or current,
                composite_bg,
                x=0, y=0,
                output_path=composite_out,
            )
            stages.append("composite")
            current = composite_out

        # ⑤ Output — save metadata
        metadata = {
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "checkpoint": checkpoint,
            "controlnet_type": controlnet_type,
            "upscale": upscale,
            "upscale_model": upscale_model if upscale else None,
            "timestamp": timestamp,
            "triple_lock_used": triple_lock_used,
        }
        manifest_path = work_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "output_path": str(current),
            "work_dir": str(work_dir),
            "stages_executed": stages,
            "metadata": metadata,
        }
