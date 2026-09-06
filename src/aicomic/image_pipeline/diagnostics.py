"""Diagnostics — build readiness report for image pipeline without posting prompts.

Checks ComfyUI node availability, model files, and reports which pipeline
stages are ready vs blocked. In dry_run mode, never posts to ComfyUI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_readiness(
    client: Any,
    comfyui_root: Path,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Build a readiness report for the image pipeline.

    Args:
        client: ComfyUI client with get_json / post_json / submit_and_wait methods.
        comfyui_root: Path to ComfyUI root directory (containing models/).
        dry_run: If True, never post prompts to ComfyUI.

    Returns:
        Dict with keys:
            dry_run: bool
            prompt_posted: bool  (always False in dry_run)
            nodes: dict[str, bool]  — which ComfyUI nodes are available
            models: dict[str, list[str]]  — which model files exist
            missing: list[str]  — missing components (e.g. "RMBG")
            stages: dict[str, dict]  — per-stage readiness status
    """
    # 1. Query ComfyUI for available nodes
    system_info: dict = {}
    object_info: dict = {}
    try:
        system_info = client.get_json("/system_stats") or {}
    except Exception:
        pass
    try:
        object_info = client.get_json("/object_info") or {}
    except Exception:
        pass

    available_nodes: set[str] = set(object_info.keys()) if isinstance(object_info, dict) else set()

    # 2. Check model files on disk
    root = Path(comfyui_root)
    models_dir = root / "models"

    def _scan(subdir: str) -> list[str]:
        d = models_dir / subdir
        if not d.exists():
            return []
        return [f.name for f in d.iterdir() if f.is_file() and not f.name.startswith("put_")]

    checkpoints = _scan("checkpoints")
    controlnet = _scan("controlnet")
    upscale = _scan("upscale_models")
    ipadapter = _scan("ipadapter")

    # 3. Node availability
    nodes: dict[str, bool] = {}
    for node_name in (
        "CheckpointLoaderSimple", "KSampler", "CLIPTextEncode",
        "EmptyLatentImage", "VAEDecode", "SaveImage", "LoadImage",
        "ControlNetLoader", "ControlNetApplyAdvanced",
        "UpscaleModelLoader", "ImageUpscaleWithModel",
        "UNETLoader", "DualCLIPLoader", "ModelSamplingFlux",
        "BRIA_RMBG_ModelLoader", "BRIA_RMBG_RemoveBackground",
    ):
        nodes[node_name] = node_name in available_nodes

    # 4. Missing components
    missing: list[str] = []
    has_rmbg_node = nodes.get("BRIA_RMBG_ModelLoader", False) or nodes.get("BRIA_RMBG_RemoveBackground", False)
    if not has_rmbg_node:
        missing.append("RMBG")
    if not controlnet:
        missing.append("ControlNet")
    if not ipadapter:
        missing.append("IPAdapter")
    if not upscale:
        missing.append("UpscaleModel")

    # 4b. Upscale readiness — model file present is sufficient;
    # UpscaleModelLoader and ImageUpscaleWithModel are core ComfyUI nodes.
    has_upscale = len(upscale) > 0

    # 5. Stage readiness
    has_checkpoint = len(checkpoints) > 0
    # Generate is ready if we have a checkpoint file — core nodes
    # (KSampler, CLIPTextEncode, etc.) are assumed available in a
    # working ComfyUI installation. The diagnostics check focuses on
    # model files and optional custom nodes (RMBG, ControlNet).
    stages: dict[str, dict[str, Any]] = {
        "generate": {
            "status": "ready" if has_checkpoint else "blocked",
            "reason": "" if has_checkpoint else "missing checkpoint model",
        },
        "matting": {
            "status": "ready" if has_rmbg_node else "blocked",
            "reason": "" if has_rmbg_node else "RMBG node not installed",
        },
        "upscale": {
            "status": "ready" if has_upscale else "blocked",
            "reason": "" if has_upscale else "missing upscale model or nodes",
        },
    }

    return {
        "dry_run": dry_run,
        "prompt_posted": False,  # Never post in diagnostics
        "system_info": system_info,
        "nodes": nodes,
        "models": {
            "checkpoints": checkpoints,
            "controlnet": controlnet,
            "upscale": upscale,
            "ipadapter": ipadapter,
        },
        "missing": missing,
        "stages": stages,
    }
