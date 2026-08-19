"""Cloud mode — lightweight API-only provider selection.

When AICOMIC_CLOUD=1, all local_* providers are skipped in favor of API providers.
This enables a < 500MB Docker image without ComfyUI/models.
"""
from __future__ import annotations

import os
from typing import Any


def is_cloud_mode() -> bool:
    """Check if cloud mode is enabled via AICOMIC_CLOUD env var."""
    val = os.environ.get("AICOMIC_CLOUD", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def filter_cloud_providers(available: list[str]) -> list[str]:
    """Remove local_* providers from a list."""
    return [p for p in available if not p.startswith("local_")]


def get_cloud_defaults() -> dict[str, str]:
    """Return default API providers for cloud mode."""
    return {
        "image": "openai_image",
        "video": "seedance",
        "tts": "openai_tts",
    }


def apply_cloud_mode(config: dict[str, Any]) -> dict[str, Any]:
    """Transform a providers config dict for cloud mode.

    Replaces local_* defaults with API providers and filters available lists.
    Preserves all non-provider keys (api configs, etc).
    """
    cloud = get_cloud_defaults()

    # Image providers
    if "image_providers" in config:
        img = config["image_providers"]
        img["available"] = filter_cloud_providers(img.get("available", []))
        if img.get("default", "").startswith("local_"):
            img["default"] = cloud["image"]

    # Video providers
    if "video_providers" in config:
        vid = config["video_providers"]
        vid["available"] = filter_cloud_providers(vid.get("available", []))
        if vid.get("default", "").startswith("local_"):
            vid["default"] = cloud["video"]

    # TTS providers
    if "tts_providers" in config:
        tts = config["tts_providers"]
        tts["available"] = filter_cloud_providers(tts.get("available", []))
        if tts.get("default", "").startswith("local_"):
            tts["default"] = cloud["tts"]

    return config


# Round-robin counter for multi-GPU dispatch
_rr_counter = 0


def remote_gpu_dispatch(
    prompt: str,
    comfyui_urls: list[str],
) -> dict[str, Any]:
    """Dispatch an image generation request to a remote ComfyUI GPU.

    Uses round-robin to distribute load across multiple GPUs.

    Args:
        prompt: Image generation prompt.
        comfyui_urls: List of remote ComfyUI server URLs.

    Returns:
        {assigned_url, prompt, dispatch_mode}
    """
    global _rr_counter
    if not comfyui_urls:
        raise ValueError("No ComfyUI URLs provided")

    assigned = comfyui_urls[_rr_counter % len(comfyui_urls)]
    _rr_counter += 1

    return {
        "assigned_url": assigned,
        "prompt": prompt,
        "dispatch_mode": "round_robin",
        "gpu_index": (_rr_counter - 1) % len(comfyui_urls),
    }
