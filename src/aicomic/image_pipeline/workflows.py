"""ComfyUI workflow JSON builders — matting, generate, upscale, full pipeline."""
from __future__ import annotations

from typing import Any


def _node(nid: int, class_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {str(nid): {"class_type": class_type, "inputs": inputs}}


def build_matting_workflow(
    input_image: str,
    rmbg_model: str = "RMBG-2.0.pth",
) -> dict[str, Any]:
    """Build workflow: LoadImage → RMBG background removal → SaveImage.

    Raises RuntimeError if RMBG is not available (node not installed).
    The caller should check readiness via diagnostics before calling.
    """
    raise RuntimeError(
        "RMBG background removal is not yet supported — "
        "ComfyUI-BRIA-RMBG custom node is required. "
        "Install via ComfyUI Manager: search 'BRIA RMBG'."
    )


def build_generate_workflow(
    prompt: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    cfg: float,
    checkpoint: str,
    controlnet_type: str | None = None,
    controlnet_model: str | None = None,
    controlnet_image: str | None = None,
) -> dict[str, Any]:
    """Build workflow: SDXL/Flux text-to-image, optionally with ControlNet."""
    p: dict[str, Any] = {}
    p.update(_node(1, "CheckpointLoaderSimple", {"ckpt_name": checkpoint}))
    p.update(_node(2, "CLIPTextEncode", {"text": prompt, "clip": ["1", 1]}))
    p.update(_node(3, "CLIPTextEncode", {"text": negative, "clip": ["1", 1]}))
    p.update(_node(4, "EmptyLatentImage", {"width": width, "height": height, "batch_size": 1}))
    next_node = 5

    latent_input = ["4", 0]
    if controlnet_type and controlnet_model and controlnet_image:
        # Guard: ControlNet requires the model file to be available on disk.
        # Since we cannot guarantee availability at workflow-build time
        # (the caller may not have downloaded models yet), we raise
        # RuntimeError to force explicit readiness checking via
        # diagnostics.build_readiness() before attempting ControlNet generation.
        raise RuntimeError(
            f"ControlNet generation ('{controlnet_type}') requires explicit "
            f"readiness verification — call diagnostics.build_readiness() first "
            f"and ensure controlnet model '{controlnet_model}' is in "
            f"ComfyUI/models/controlnet/."
        )
        next_node += 1
        p.update(_node(next_node, "LoadImage", {"image": controlnet_image}))
        next_node += 1
        p.update(_node(next_node, "ControlNetApplyAdvanced", {
            "positive": ["2", 0],
            "negative": ["3", 0],
            "control_net": [str(next_node - 2), 0],
            "image": [str(next_node - 1), 0],
            "strength": 1.0,
            "start_percent": 0.0,
            "end_percent": 0.8,
        }))
        next_node += 1
        positive = [str(next_node - 1), 0]
        negative = [str(next_node - 1), 1]
    else:
        positive = ["2", 0]
        negative = ["3", 0]

    p.update(_node(next_node, "KSampler", {
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "denoise": 1.0,
        "model": ["1", 0],
        "positive": positive,
        "negative": negative,
        "latent_image": latent_input,
    }))
    next_node += 1
    p.update(_node(next_node, "VAEDecode", {"samples": [str(next_node - 1), 0], "vae": ["1", 2]}))
    next_node += 1
    p.update(_node(next_node, "SaveImage", {
        "images": [str(next_node - 1), 0],
        "filename_prefix": "generate_output",
    }))
    return {"prompt": p, "extra": {}}


def build_upscale_workflow(
    input_image: str,
    upscale_model: str,
    upscale_scale: int = 4,
) -> dict[str, Any]:
    """Build workflow: LoadImage → UpscaleImage (Real-ESRGAN) → SaveImage."""
    p: dict[str, Any] = {}
    p.update(_node(1, "LoadImage", {"image": input_image}))
    p.update(_node(2, "UpscaleModelLoader", {"model_name": upscale_model}))
    p.update(_node(3, "ImageUpscaleWithModel", {"upscale_model": ["2", 0], "image": ["1", 0]}))
    p.update(_node(4, "SaveImage", {
        "images": ["3", 0],
        "filename_prefix": "upscale_output",
    }))
    return {"prompt": p, "extra": {}}


def build_full_pipeline_workflow(
    prompt: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    cfg: float,
    checkpoint: str,
    upscale_model: str,
    upscale_scale: int = 4,
) -> dict[str, Any]:
    """Build workflow: SDXL generate → Real-ESRGAN upscale → SaveImage (all in one)."""
    p: dict[str, Any] = {}
    p.update(_node(1, "CheckpointLoaderSimple", {"ckpt_name": checkpoint}))
    p.update(_node(2, "CLIPTextEncode", {"text": prompt, "clip": ["1", 1]}))
    p.update(_node(3, "CLIPTextEncode", {"text": negative, "clip": ["1", 1]}))
    p.update(_node(4, "EmptyLatentImage", {"width": width, "height": height, "batch_size": 1}))
    p.update(_node(5, "KSampler", {
        "seed": seed, "steps": steps, "cfg": cfg,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
        "latent_image": ["4", 0],
    }))
    p.update(_node(6, "VAEDecode", {"samples": ["5", 0], "vae": ["1", 2]}))
    p.update(_node(7, "UpscaleModelLoader", {"model_name": upscale_model}))
    p.update(_node(8, "ImageUpscaleWithModel", {"upscale_model": ["7", 0], "image": ["6", 0]}))
    p.update(_node(9, "SaveImage", {
        "images": ["8", 0],
        "filename_prefix": "pipeline_output",
    }))
    return {"prompt": p, "extra": {}}
