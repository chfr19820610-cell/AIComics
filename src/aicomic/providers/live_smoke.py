from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Iterator

from aicomic.utils.atomic_io import atomic_write_json

from aicomic.core.config import ProjectPaths
from aicomic.providers.comfyui_service import inspect_comfyui_service, resolve_comfyui_service_config, run_comfyui_service_action
from aicomic.providers.executor import build_provider_request_preview, execute_provider_requests
from aicomic.providers.local_adapter import (
    LOCAL_COMFYUI_PROVIDER,
    LOCAL_COMFYUI_PROVIDERS,
    LOCAL_COMFYUI_VIDEO_PROVIDER,
    LOCAL_PIPER_PROVIDER,
)


SUPPORTED_LIVE_SMOKE_PROVIDERS = (
    LOCAL_COMFYUI_PROVIDER,
    LOCAL_COMFYUI_VIDEO_PROVIDER,
    LOCAL_PIPER_PROVIDER,
)
WORKFLOW_MODES = {"configured", "smoke", "full"}
IMAGE_WORKFLOW_MODES = WORKFLOW_MODES
VIDEO_WORKFLOW_MODES = WORKFLOW_MODES


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def validate_selected_providers(providers: set[str] | None) -> list[str]:
    if not providers:
        return list(SUPPORTED_LIVE_SMOKE_PROVIDERS)
    invalid = sorted(provider for provider in providers if provider not in SUPPORTED_LIVE_SMOKE_PROVIDERS)
    if invalid:
        raise ValueError(f"Unsupported live smoke providers: {invalid}")
    return [provider for provider in SUPPORTED_LIVE_SMOKE_PROVIDERS if provider in providers]


def build_live_smoke_request(provider: str, output_root: Path) -> dict[str, Any]:
    if provider == LOCAL_COMFYUI_PROVIDER:
        output_path = output_root / provider / "E01_S01_image.png"
        return {
            "request_id": "REQ_LIVE_SMOKE_LOCAL_COMFYUI_IMAGE",
            "request_status": "ready",
            "endpoint": "/local/comfyui/prompt",
            "run_mode": "local_live",
            "payload": {
                "job_id": "JOB_LIVE_SMOKE_LOCAL_COMFYUI_IMAGE",
                "episode_code": "E01",
                "shot_id": "S01",
                "job_type": "image",
                "provider": provider,
                "prompt": "动漫插画风，都市职场会议室内，女主站在会议桌前抬头看向众人，逆光，情绪克制但坚定，中近景缓慢推进。",
                "output_path": str(output_path),
                "priority": "high",
                "duration": 4,
                "scene": "会议室",
                "camera": "中近景缓慢推进",
            },
        }
    if provider == LOCAL_COMFYUI_VIDEO_PROVIDER:
        output_path = output_root / provider / "E01_S02_video.mp4"
        return {
            "request_id": "REQ_LIVE_SMOKE_LOCAL_COMFYUI_VIDEO",
            "request_status": "ready",
            "endpoint": "/local/comfyui/video",
            "run_mode": "local_live",
            "payload": {
                "job_id": "JOB_LIVE_SMOKE_LOCAL_COMFYUI_VIDEO",
                "episode_code": "E01",
                "shot_id": "S02",
                "job_type": "video",
                "provider": provider,
                "prompt": "动漫动态镜头，都市职场走廊里女主快步前行后短暂停步回头，情绪压抑后反击，镜头稳定推进，时长控制在 3 到 4 秒。",
                "output_path": str(output_path),
                "priority": "high",
                "duration": 4,
                "scene": "办公走廊",
                "camera": "稳定推进后短暂停留",
            },
        }
    if provider == LOCAL_PIPER_PROVIDER:
        output_path = output_root / provider / "E01_S01_tts.wav"
        return {
            "request_id": "REQ_LIVE_SMOKE_LOCAL_PIPER_TTS",
            "request_status": "ready",
            "endpoint": "/local/piper-tts",
            "run_mode": "local_live",
            "payload": {
                "job_id": "JOB_LIVE_SMOKE_LOCAL_PIPER_TTS",
                "episode_code": "E01",
                "shot_id": "S01",
                "job_type": "tts",
                "provider": provider,
                "prompt": "这是一条 AIComics 本地 Piper TTS smoke test，请确认声音模型、命令链路和文件写回都正常。",
                "output_path": str(output_path),
                "priority": "high",
                "duration": 4,
                "scene": "会议室",
                "camera": "近景",
            },
        }
    raise ValueError(f"Unsupported live smoke provider: {provider}")


def build_live_smoke_requests(selected_providers: list[str], output_root: Path) -> dict[str, Any]:
    requests = [build_live_smoke_request(provider, output_root) for provider in selected_providers]
    return {
        "request_count": len(requests),
        "ready_count": len(requests),
        "blocked_count": 0,
        "requests": requests,
    }


def resolve_video_workflow_path(project_root: Path, workflow_mode: str) -> Path | None:
    if workflow_mode == "configured":
        return None
    workflow_name = "video_workflow_live_smoke.json" if workflow_mode == "smoke" else "video_workflow.json"
    return project_root / "local_providers" / "comfyui" / "workflows" / workflow_name


def resolve_image_workflow_path(project_root: Path, workflow_mode: str) -> Path | None:
    if workflow_mode == "configured":
        return None
    workflow_name = "image_workflow_live_smoke.json" if workflow_mode == "smoke" else "image_workflow.json"
    return project_root / "local_providers" / "comfyui" / "workflows" / workflow_name


@contextmanager
def temporary_environment(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def filter_provider_requests(provider_requests: dict[str, Any], request_ids: set[str]) -> dict[str, Any]:
    requests = [
        request
        for request in provider_requests.get("requests", [])
        if str(request.get("request_id", "")) in request_ids
    ]
    return {
        "request_count": len(requests),
        "ready_count": len(requests),
        "blocked_count": 0,
        "requests": requests,
    }


def collect_request_previews(
    provider_requests: dict[str, Any],
    providers_config_path: Path,
) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for request in provider_requests.get("requests", []):
        payload = request.get("payload", {})
        provider = str(payload.get("provider", ""))
        preview = build_provider_request_preview(request, providers_config_path)
        preflight = preview.get("preflight", {}) if isinstance(preview, dict) else {}
        previews.append(
            {
                "request_id": str(request.get("request_id", "")),
                "provider": provider,
                "job_type": str(payload.get("job_type", "")),
                "output_path": str(payload.get("output_path", "")),
                "preview": preview,
                "preflight_ready": bool(preflight.get("ready", False)) if isinstance(preflight, dict) else False,
            }
        )
    return previews


def summarize_preflights(previews: list[dict[str, Any]]) -> dict[str, Any]:
    ready_count = sum(1 for item in previews if bool(item.get("preflight_ready", False)))
    return {
        "request_count": len(previews),
        "ready_count": ready_count,
        "not_ready_count": len(previews) - ready_count,
        "providers": [str(item.get("provider", "")) for item in previews],
    }


def describe_output_path(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size_bytes = path.stat().st_size if exists and path.is_file() else 0
    return {
        "path": str(path),
        "exists": exists,
        "is_file": path.is_file() if exists else False,
        "size_bytes": size_bytes,
    }


def collect_output_summaries(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for item in results:
        execution_output = item.get("execution_output", {})
        output_path = str(execution_output.get("output_path", "")).strip()
        if not output_path:
            continue
        summary = describe_output_path(Path(output_path))
        summary["provider"] = str(item.get("provider", ""))
        summary["request_id"] = str(item.get("request_id", ""))
        outputs.append(summary)
    return outputs


def merge_execution_results(
    initial_report: dict[str, Any],
    retry_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    ordered_request_ids = [str(item.get("request_id", "")) for item in initial_report.get("results", [])]
    merged = {
        str(item.get("request_id", "")): dict(item)
        for item in initial_report.get("results", [])
    }
    if retry_report:
        for item in retry_report.get("results", []):
            request_id = str(item.get("request_id", ""))
            retry_item = dict(item)
            initial_item = merged.get(request_id, {})
            if initial_item:
                retry_item["retried_from"] = {
                    "status": str(initial_item.get("status", "")),
                    "error": str(initial_item.get("error", "")),
                }
            merged[request_id] = retry_item
            if request_id not in ordered_request_ids:
                ordered_request_ids.append(request_id)
    return [merged[request_id] for request_id in ordered_request_ids if request_id in merged]


def summarize_execution_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = sum(1 for item in results if item.get("status") == "succeeded")
    failed_count = sum(1 for item in results if item.get("status") == "failed")
    blocked_count = sum(1 for item in results if item.get("status") == "blocked_live_confirmation_required")
    skipped_count = sum(1 for item in results if str(item.get("status", "")).startswith("skipped"))
    stopped_by_guard_count = sum(1 for item in results if item.get("status") == "stopped_by_failure_guard")
    return {
        "request_count": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "blocked_count": blocked_count,
        "skipped_count": skipped_count,
        "stopped_by_failure_guard_count": stopped_by_guard_count,
        "status": "passed" if failed_count == 0 and blocked_count == 0 else "failed",
    }


def collect_failed_comfyui_request_ids(results: list[dict[str, Any]]) -> set[str]:
    failed_request_ids: set[str] = set()
    for item in results:
        provider = str(item.get("provider", ""))
        if provider in LOCAL_COMFYUI_PROVIDERS and item.get("status") == "failed":
            failed_request_ids.add(str(item.get("request_id", "")))
    return failed_request_ids


def run_local_provider_live_smoke(
    providers_config_path: Path,
    selected_providers: set[str] | None = None,
    output_root: Path | None = None,
    image_workflow_mode: str = "smoke",
    video_workflow_mode: str = "smoke",
    skip_comfyui_start: bool = False,
    restart_comfyui: bool = False,
    retry_comfyui_on_failure: bool = True,
    max_failures: int = 1,
    comfyui_host: str = "127.0.0.1",
    comfyui_port: int = 8188,
    wait_timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    project_root = ProjectPaths.project_root()
    output_directory = (output_root or (ProjectPaths.state_dir() / "live_smoke")).resolve()
    provider_order = validate_selected_providers(selected_providers)
    if image_workflow_mode not in IMAGE_WORKFLOW_MODES:
        raise ValueError(f"Unsupported image workflow mode: {image_workflow_mode}")
    if video_workflow_mode not in VIDEO_WORKFLOW_MODES:
        raise ValueError(f"Unsupported video workflow mode: {video_workflow_mode}")
    provider_requests = build_live_smoke_requests(provider_order, output_directory)
    image_workflow_path = resolve_image_workflow_path(project_root, image_workflow_mode)
    video_workflow_path = resolve_video_workflow_path(project_root, video_workflow_mode)
    env_updates: dict[str, str] = {}
    if image_workflow_path is not None:
        env_updates["AICOMIC_COMFYUI_WORKFLOW_PATH"] = str(image_workflow_path)
    if video_workflow_path is not None:
        env_updates["AICOMIC_COMFYUI_VIDEO_WORKFLOW_PATH"] = str(video_workflow_path)

    comfyui_required = any(provider in LOCAL_COMFYUI_PROVIDERS for provider in provider_order)
    service_actions: list[dict[str, Any]] = []
    retry_report: dict[str, Any] | None = None

    with temporary_environment(env_updates):
        previews = collect_request_previews(provider_requests, providers_config_path)
        preflight_summary = summarize_preflights(previews)
        comfyui_status_before = {}
        comfyui_status_after = {}
        if comfyui_required:
            service_config = resolve_comfyui_service_config(project_root=project_root, host=comfyui_host, port=comfyui_port)
            comfyui_status_before = inspect_comfyui_service(service_config)
            if not skip_comfyui_start:
                requested_action = "restart" if restart_comfyui else "start"
                service_actions.append(
                    run_comfyui_service_action(
                        requested_action,
                        project_root=project_root,
                        host=comfyui_host,
                        port=comfyui_port,
                        wait_timeout_seconds=wait_timeout_seconds,
                        poll_interval_seconds=poll_interval_seconds,
                        force=True,
                    )
                )

        initial_report = execute_provider_requests(
            provider_requests,
            providers_config_path,
            set(provider_order),
            dry_run=False,
            confirm_live=True,
            limit=0,
            max_failures=max_failures,
        )

        if comfyui_required and retry_comfyui_on_failure and not skip_comfyui_start:
            retry_request_ids = collect_failed_comfyui_request_ids(initial_report.get("results", []))
            if retry_request_ids:
                service_actions.append(
                    run_comfyui_service_action(
                        "restart",
                        project_root=project_root,
                        host=comfyui_host,
                        port=comfyui_port,
                        wait_timeout_seconds=wait_timeout_seconds,
                        poll_interval_seconds=poll_interval_seconds,
                        force=True,
                    )
                )
                retry_requests = filter_provider_requests(provider_requests, retry_request_ids)
                retry_report = execute_provider_requests(
                    retry_requests,
                    providers_config_path,
                    {LOCAL_COMFYUI_PROVIDER, LOCAL_COMFYUI_VIDEO_PROVIDER},
                    dry_run=False,
                    confirm_live=True,
                    limit=0,
                    max_failures=max(1, len(retry_request_ids)),
                )

        if comfyui_required:
            comfyui_status_after = inspect_comfyui_service(service_config)

    final_results = merge_execution_results(initial_report, retry_report)
    final_summary = summarize_execution_results(final_results)
    output_summaries = collect_output_summaries(final_results)
    return {
        "run_id": f"local_provider_live_smoke_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": now_iso(),
        "status": final_summary["status"],
        "providers_config_path": str(providers_config_path),
        "selected_providers": provider_order,
        "output_root": str(output_directory),
        "image_workflow_mode": image_workflow_mode,
        "image_workflow_path": str(image_workflow_path) if image_workflow_path else "",
        "video_workflow_mode": video_workflow_mode,
        "video_workflow_path": str(video_workflow_path) if video_workflow_path else "",
        "requests": provider_requests,
        "previews": previews,
        "preflight_summary": preflight_summary,
        "comfyui_service": {
            "required": comfyui_required,
            "skip_start": skip_comfyui_start,
            "status_before": comfyui_status_before,
            "actions": service_actions,
            "status_after": comfyui_status_after,
        },
        "initial_execution": initial_report,
        "retry_execution": retry_report or {},
        "final_summary": final_summary,
        "final_results": final_results,
        "output_summaries": output_summaries,
        "report_path": "",
    }


def write_local_provider_live_smoke_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(payload)
    serializable["report_path"] = str(path)
    atomic_write_json(path, serializable)
