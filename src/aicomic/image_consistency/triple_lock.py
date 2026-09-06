"""Triple-Lock character consistency — IPAdapter FaceID + ControlNet + FaceDetailer.

2026 standard for character consistency in ComfyUI:
  Layer 1: IPAdapter FaceID (weight 0.75) — locks facial identity
  Layer 2: ControlNet OpenPose/Depth (strength 0.8) — locks pose/composition
  Layer 3: FaceDetailer (denoise 0.4) — post-processes face region

Replaces the old pHash-only approach (2024) with the industry-standard
triple-lock workflow confirmed by multiple 2026 sources.
"""
from __future__ import annotations

from typing import Any


def _node(nid: int, class_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {str(nid): {"class_type": class_type, "inputs": inputs}}


# ── Default weights (tuned from 2026 best practices) ─────────────────────

IPADAPTER_WEIGHT = 0.75
CONTROLNET_STRENGTH = 0.8
FACEDETAILER_DENOISE = 0.4
FACEDETAILER_STEPS = 20


def build_triple_lock_workflow(
    prompt: str,
    negative: str,
    width: int = 1024,
    height: int = 1536,
    seed: int = -1,
    steps: int = 25,
    cfg: float = 7.0,
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    reference_image: str = "reference_face.png",
    ipadapter_model: str = "ip-adapter-faceid-plusv2_sdxl.bin",
    ipadapter_lora: str = "ip-adapter-faceid-plusv2_sdxl_lora.safetensors",
    controlnet_type: str = "openpose",
    controlnet_model: str = "controlnet-openpose-sdxl.safetensors",
    controlnet_image: str = "pose_reference.png",
    facedetailer_model: str = "face_yolov8n.pt",
) -> dict[str, Any]:
    """Build a Triple-Lock character consistency workflow for ComfyUI.

    Structure:
        LoadImage(ref) → IPAdapter FaceID Apply (weight 0.75)
        LoadImage(pose) → ControlNet OpenPose (strength 0.8)
        → KSampler → VAEDecode → FaceDetailer (denoise 0.4) → SaveImage

    Returns ComfyUI prompt dict. Does NOT call ComfyUI — caller posts it.
    """
    if seed < 0:
        import random
        seed = random.randint(1, 2**32 - 1)

    p: dict[str, Any] = {}

    # 1. Load checkpoint
    p.update(_node(1, "CheckpointLoaderSimple", {"ckpt_name": checkpoint}))

    # 2. CLIP text encode (positive + negative)
    p.update(_node(2, "CLIPTextEncode", {"text": prompt, "clip": ["1", 1]}))
    p.update(_node(3, "CLIPTextEncode", {"text": negative, "clip": ["1", 1]}))

    # 3. Empty latent
    p.update(_node(4, "EmptyLatentImage", {"width": width, "height": height, "batch_size": 1}))

    # 4. IPAdapter FaceID (Layer 1 — identity lock)
    p.update(_node(5, "LoadImage", {"image": reference_image}))
    p.update(_node(6, "IPAdapterUnifiedLoader", {
        "model": ["1", 0],
        "preset": "faceid",
        "ipadapter_file": ipadapter_model,
        "lora_file": ipadapter_lora,
    }))
    p.update(_node(7, "IPAdapterFaceID", {
        "model": ["6", 0],
        "image": ["5", 0],
        "weight": IPADAPTER_WEIGHT,
        "weight_type": "linear",
        "start_at": 0.0,
        "end_at": 0.9,
    }))

    # 5. ControlNet (Layer 2 — pose lock)
    p.update(_node(8, "LoadImage", {"image": controlnet_image}))
    p.update(_node(9, "ControlNetLoader", {"control_net_name": controlnet_model}))
    cn_preprocessor = "OpenposePreprocessor" if controlnet_type == "openpose" else "DepthPreprocessor"
    p.update(_node(10, cn_preprocessor, {"image": ["8", 0]}))
    p.update(_node(11, "ControlNetApplyAdvanced", {
        "positive": ["2", 0],
        "negative": ["3", 0],
        "control_net": ["9", 0],
        "image": ["10", 0],
        "strength": CONTROLNET_STRENGTH,
        "start_percent": 0.0,
        "end_percent": 0.8,
    }))

    # 6. KSampler
    p.update(_node(12, "KSampler", {
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "denoise": 1.0,
        "model": ["7", 0],
        "positive": ["11", 0],
        "negative": ["11", 1],
        "latent_image": ["4", 0],
    }))

    # 7. VAE Decode
    p.update(_node(13, "VAEDecode", {"samples": ["12", 0], "vae": ["1", 2]}))

    # 8. FaceDetailer (Layer 3 — face post-processing)
    p.update(_node(14, "FaceDetailer", {
        "model": ["7", 0],
        "image": ["13", 0],
        "clip": ["1", 1],
        "vae": ["1", 2],
        "positive": ["2", 0],
        "negative": ["3", 0],
        "detector": facedetailer_model,
        "guide_size": 512,
        "denoise": FACEDETAILER_DENOISE,
        "steps": FACEDETAILER_STEPS,
        "seed": seed,
    }))

    # 9. Save
    p.update(_node(15, "SaveImage", {
        "images": ["14", 0],
        "filename_prefix": "triple_lock_output",
    }))

    return {"prompt": p, "extra": {}}


def build_triple_lock_metadata(
    prompt: str,
    reference_image: str,
    controlnet_type: str,
    seed: int,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build metadata manifest for a Triple-Lock generation run."""
    return {
        "pipeline": "triple_lock",
        "prompt": prompt,
        "reference_image": reference_image,
        "controlnet_type": controlnet_type,
        "ipadapter_weight": IPADAPTER_WEIGHT,
        "controlnet_strength": CONTROLNET_STRENGTH,
        "facedetailer_denoise": FACEDETAILER_DENOISE,
        "seed": seed,
        "layers": [
            {"name": "IPAdapter FaceID", "weight": IPADAPTER_WEIGHT, "purpose": "identity_lock"},
            {"name": "ControlNet", "type": controlnet_type, "strength": CONTROLNET_STRENGTH, "purpose": "pose_lock"},
            {"name": "FaceDetailer", "denoise": FACEDETAILER_DENOISE, "purpose": "face_refinement"},
        ],
        **kwargs,
    }
