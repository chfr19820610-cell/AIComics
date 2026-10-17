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

    def _post_and_fetch_comfyui(self, workflow: dict[str, Any], work_dir: Path) -> Path | None:
        """POST /prompt → poll /history → download outputs.

        Returns the path of the first downloaded image, or None when ComfyUI
        is unavailable / produced nothing (caller must treat as plan-only).
        """
        import json as _json
        import time as _time
        import urllib.request

        base = "http://127.0.0.1:8188"
        try:
            req = urllib.request.Request(
                f"{base}/prompt",
                data=_json.dumps({"prompt": workflow}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                prompt_id = _json.loads(resp.read()).get("prompt_id")
            if not prompt_id:
                return None
            for _ in range(20):  # 20 × 2s = 40s generation budget
                _time.sleep(2)
                with urllib.request.urlopen(f"{base}/history/{prompt_id}", timeout=5) as resp:
                    entry = _json.loads(resp.read()).get(prompt_id)
                if not entry:
                    continue
                for node_out in entry.get("outputs", {}).values():
                    for idx, img in enumerate(node_out.get("images", [])):
                        view_url = (
                            f"{base}/view?filename={img.get('filename', '')}"
                            f"&subfolder={img.get('subfolder', '')}"
                            f"&type={img.get('type', 'output')}"
                        )
                        dest = work_dir / f"triple_lock_{idx}.png"
                        with urllib.request.urlopen(view_url, timeout=30) as resp, open(dest, "wb") as f:
                            f.write(resp.read())
                        return dest
            return None
        except Exception:
            return None

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
            build_triple_lock_metadata(
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
            fetched = self._post_and_fetch_comfyui(tl_workflow, work_dir)
            if fetched is not None:
                gen_output = fetched
                stages.append("generate")
            else:
                # ComfyUI unavailable or produced nothing — plan only, honestly labeled
                gen_output = work_dir / "triple_lock_plan.json"
                stages.append("triple_lock_plan_only")
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
