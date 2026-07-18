from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aicomic.providers.local_adapter import LOCAL_EXECUTION_PROVIDERS, build_local_request_preview
from aicomic.providers.provider_planner import collect_available_providers, load_provider_settings, resolve_provider_profile


JOB_TYPE_BY_PROVIDER = {
    "manual_web": "image",
    "openai_image": "image",
    "local_comfyui_image": "image",
    "sora": "video",
    "local_comfyui_video": "video",
    "windows_tts": "tts",
    "local_piper_tts": "tts",
    "openai_tts": "tts",
}


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def count_requests_by_provider(provider_requests: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for request in provider_requests.get("requests", []):
        payload = request.get("payload", {}) if isinstance(request, dict) else {}
        provider = str(payload.get("provider", ""))
        if provider:
            counts[provider] = counts.get(provider, 0) + 1
    return counts


def build_sample_request(provider: str, job_type: str) -> dict[str, Any]:
    suffix = "png"
    if job_type == "video":
        suffix = "mp4"
    elif job_type == "tts":
        suffix = "wav"
    return {
        "request_id": f"REQ_READINESS_{provider}",
        "payload": {
            "job_id": f"JOB_READINESS_{provider}",
            "episode_code": "E00",
            "shot_id": "S00",
            "job_type": job_type,
            "provider": provider,
            "prompt": "AIComics provider readiness probe",
            "output_path": f"state/provider_readiness/E00_S00_{provider}.{suffix}",
        },
    }


def build_env_readiness(provider: str) -> dict[str, Any]:
    profile = resolve_provider_profile(provider)
    env_status = [
        {
            "name": env_name,
            "configured": bool(os.environ.get(env_name)),
        }
        for env_name in profile.required_env
    ]
    ready = all(item["configured"] for item in env_status)
    return {
        "ready": ready,
        "required_env_status": env_status,
        "notes": "Environment variables are required before live API execution." if env_status else "",
    }


def build_manual_readiness(provider: str) -> dict[str, Any]:
    if provider == "manual_web":
        return {
            "ready": True,
            "notes": "Manual web fallback is always available when output import naming is followed.",
        }
    if provider == "windows_tts":
        return {
            "ready": True,
            "notes": "Windows TTS placeholder route is treated as available for fallback planning.",
        }
    return {
        "ready": False,
        "notes": f"No readiness adapter registered for provider: {provider}",
    }


def build_provider_item(
    provider: str,
    providers_config_path: Path,
    request_counts: dict[str, int],
) -> dict[str, Any]:
    profile = resolve_provider_profile(provider)
    job_type = JOB_TYPE_BY_PROVIDER.get(provider)
    readiness: dict[str, Any]
    if provider in LOCAL_EXECUTION_PROVIDERS and job_type is not None:
        preview = build_local_request_preview(build_sample_request(provider, job_type), providers_config_path)
        readiness = dict(preview.get("preflight", {}))
        readiness["runtime_checked"] = False
        readiness["runtime_check_note"] = "Run a limited --confirm-live execution after configuration to verify server/process runtime."
    elif profile.required_env:
        readiness = build_env_readiness(provider)
    else:
        readiness = build_manual_readiness(provider)

    ready = bool(readiness.get("ready", False))
    return {
        "provider": provider,
        "job_type": job_type or "",
        "dispatch_channel": profile.dispatch_channel,
        "queue_name": profile.queue_name,
        "run_mode": profile.run_mode,
        "configured_request_count": int(request_counts.get(provider, 0)),
        "ready": ready,
        "readiness_status": "ready" if ready else "setup_required",
        "readiness": readiness,
        "next_actions": build_provider_next_actions(provider, readiness),
    }


def build_provider_next_actions(provider: str, readiness: dict[str, Any]) -> list[str]:
    if bool(readiness.get("ready", False)):
        if provider in LOCAL_EXECUTION_PROVIDERS:
            return ["Run execute-provider-requests with --confirm-live --limit 1 to verify real local output writeback."]
        return ["Run a small live provider batch with --confirm-live --limit 1 before scaling up."]
    if provider in {"openai_image", "openai_tts", "sora"}:
        return ["Set OPENAI_API_KEY and run a dry-run followed by --confirm-live --limit 1."]
    if provider == "local_comfyui_image":
        actions: list[str] = []
        if not bool(readiness.get("workflow_api_format", False)):
            actions.append("Place an API-format image workflow JSON at local_providers/comfyui/workflows/image_workflow.json.")
        if not bool(readiness.get("required_models_ready", False)):
            actions.append("Place required image model weights under local_providers/comfyui/models according to model_requirements.json.")
        if not bool(readiness.get("comfyui_server_available", False)):
            actions.append("Start ComfyUI at the configured base_url, then validate one image shot.")
        return actions or ["Validate one image shot with --confirm-live --limit 1."]
    if provider == "local_comfyui_video":
        actions = []
        if not bool(readiness.get("workflow_api_format", False)):
            actions.append("Place an API-format video workflow JSON at local_providers/comfyui/workflows/video_workflow.json.")
        if not bool(readiness.get("required_models_ready", False)):
            actions.append("Place required video model weights under local_providers/comfyui/models according to model_requirements.json.")
        if not bool(readiness.get("comfyui_server_available", False)):
            actions.append("Start ComfyUI at the configured base_url, then validate one low-resolution video shot.")
        return actions or ["Validate one low-resolution video shot with --confirm-live --limit 1."]
    if provider == "local_piper_tts":
        actions = []
        if not bool(readiness.get("ready", False)):
            actions.append("Install Piper, place a local voice .onnx model under local_providers/piper/models, then validate one TTS request.")
        if readiness.get("license_status") != "known":
            actions.append("Review or replace the Piper voice MODEL_CARD before commercial production release.")
        return actions or ["Run a one-shot Piper --confirm-live validation before scaling."]
    return ["Review provider configuration and adapter support."]


def item_ready(items_by_provider: dict[str, dict[str, Any]], provider: str) -> bool:
    return bool(items_by_provider.get(provider, {}).get("ready", False))


def build_provider_readiness_report(
    providers_config_path: Path,
    provider_requests_path: Path | None = None,
) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    configured_providers = sorted(collect_available_providers(settings))
    provider_requests = load_optional_json(provider_requests_path) if provider_requests_path is not None else {}
    request_counts = count_requests_by_provider(provider_requests)
    items = [build_provider_item(provider, providers_config_path, request_counts) for provider in configured_providers]
    items_by_provider = {str(item["provider"]): item for item in items}

    openai_core_ready = item_ready(items_by_provider, "openai_image") and item_ready(items_by_provider, "openai_tts")
    openai_video_ready = item_ready(items_by_provider, "sora")
    local_core_ready = item_ready(items_by_provider, "local_comfyui_image") and item_ready(items_by_provider, "local_piper_tts")
    local_video_ready = item_ready(items_by_provider, "local_comfyui_video")
    manual_fallback_ready = item_ready(items_by_provider, "manual_web") and item_ready(items_by_provider, "windows_tts")

    if local_core_ready and local_video_ready:
        status = "ready_with_full_local_provider"
    elif local_core_ready:
        status = "ready_with_core_local_provider"
    elif openai_core_ready:
        status = "ready_with_openai_core_provider"
    elif manual_fallback_ready:
        status = "ready_with_manual_fallback"
    else:
        status = "setup_required"

    return {
        "providers_config_path": str(providers_config_path),
        "provider_requests_path": str(provider_requests_path) if provider_requests_path else "",
        "provider_count": len(items),
        "status": status,
        "manual_fallback_ready": manual_fallback_ready,
        "openai_core_ready": openai_core_ready,
        "openai_video_ready": openai_video_ready,
        "local_core_ready": local_core_ready,
        "local_video_ready": local_video_ready,
        "full_local_ready": local_core_ready and local_video_ready,
        "items": items,
        "blocking_reasons": [
            f"{item['provider']}: {item['readiness_status']}"
            for item in items
            if not bool(item["ready"]) and item["provider"] in {"openai_image", "openai_tts", "sora", "local_comfyui_image", "local_comfyui_video", "local_piper_tts"}
        ],
        "next_actions": build_report_next_actions(openai_core_ready, local_core_ready, local_video_ready),
    }


def build_report_next_actions(openai_core_ready: bool, local_core_ready: bool, local_video_ready: bool) -> list[str]:
    actions: list[str] = []
    if not openai_core_ready:
        actions.append("OpenAI live route: set OPENAI_API_KEY, then run execute-provider-requests --confirm-live --limit 1.")
    if not local_core_ready:
        actions.append("Local core route: validate ComfyUI image workflow/model weights and Piper model/license, then run --confirm-live --limit 1.")
    if not local_video_ready:
        actions.append("Local video route: validate ComfyUI video workflow/model weights and one low-resolution shot before batch scale-up.")
    if not actions:
        actions.append("All configured live/local routes are ready for limited production verification.")
    return actions


def write_provider_readiness_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
