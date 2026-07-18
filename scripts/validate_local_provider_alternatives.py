from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.core.models import JobRecord
from aicomic.providers.executor import execute_provider_requests
from aicomic.providers.provider_planner import build_provider_plan, resolve_provider_profile
from aicomic.providers.readiness import build_provider_readiness_report
from aicomic.providers.request_builder import build_provider_requests


def build_validation_manifest() -> dict[str, object]:
    return {
        "episodes": [
            {
                "episode_code": "E99",
                "title": "本地 Provider 验证集",
                "shots": [
                    {
                        "shot_id": "S01",
                        "scene": "办公室",
                        "characters": ["林夏"],
                        "visual": "主角站在会议桌前，背光强烈",
                        "action": "她抬头看向众人",
                        "emotion": "克制但坚定",
                        "camera": "中近景缓慢推进",
                        "dialogue": "这一次，我自己来证明。",
                        "duration": 4,
                        "priority": "high",
                    }
                ],
            }
        ]
    }


def build_validation_jobs() -> list[JobRecord]:
    return [
        JobRecord("JOB_E99_S01_image", "E99", "image", "manual_web", "pending"),
        JobRecord("JOB_E99_S01_video", "E99", "video", "manual_web", "pending"),
        JobRecord("JOB_E99_S01_tts", "E99", "tts", "windows_tts", "pending"),
    ]


def main() -> int:
    providers_config_path = ProjectPaths.providers_config_path()
    output_root = ProjectPaths.state_dir() / "local_provider_validation_assets"
    jobs = build_validation_jobs()
    routed_jobs = [
        JobRecord(
            job.job_id,
            job.episode_code,
            job.job_type,
            {"image": "local_comfyui_image", "video": "local_comfyui_video", "tts": "local_piper_tts"}.get(job.job_type, job.provider),
            job.status,
        )
        for job in jobs
    ]

    comfyui_profile = resolve_provider_profile("local_comfyui_image")
    comfyui_video_profile = resolve_provider_profile("local_comfyui_video")
    piper_profile = resolve_provider_profile("local_piper_tts")
    if comfyui_profile.dispatch_channel != "local" or "image" not in comfyui_profile.supported_job_types:
        raise RuntimeError("local_comfyui_image profile is not registered correctly")
    if comfyui_video_profile.dispatch_channel != "local" or "video" not in comfyui_video_profile.supported_job_types:
        raise RuntimeError("local_comfyui_video profile is not registered correctly")
    if piper_profile.dispatch_channel != "local" or "tts" not in piper_profile.supported_job_types:
        raise RuntimeError("local_piper_tts profile is not registered correctly")

    provider_plan = build_provider_plan(routed_jobs, providers_config_path)
    configured = set(provider_plan.get("configured_providers", []))
    if "local_comfyui_image" not in configured or "local_comfyui_video" not in configured or "local_piper_tts" not in configured:
        raise RuntimeError(f"local providers missing from providers.yaml: {sorted(configured)}")
    if int(provider_plan["unresolved_provider_count"]) != 0:
        raise RuntimeError(f"unexpected unresolved providers: {provider_plan['unresolved_jobs']}")

    provider_requests = build_provider_requests(
        build_validation_manifest(),
        jobs,
        providers_config_path,
        output_root,
        {"image": "local_comfyui_image", "video": "local_comfyui_video", "tts": "local_piper_tts"},
    )
    requests = list(provider_requests.get("requests", []))
    if int(provider_requests["request_count"]) != 3:
        raise RuntimeError(f"request_count mismatch: {provider_requests['request_count']}")
    if int(provider_requests["blocked_count"]) != 0:
        raise RuntimeError(f"local provider requests should not be statically blocked: {provider_requests['blocked_count']}")

    endpoints = {item["payload"]["provider"]: item["endpoint"] for item in requests}
    if endpoints.get("local_comfyui_image") != "/local/comfyui/prompt":
        raise RuntimeError(f"local_comfyui_image endpoint mismatch: {endpoints}")
    if endpoints.get("local_comfyui_video") != "/local/comfyui/video":
        raise RuntimeError(f"local_comfyui_video endpoint mismatch: {endpoints}")
    if endpoints.get("local_piper_tts") != "/local/piper-tts":
        raise RuntimeError(f"local_piper_tts endpoint mismatch: {endpoints}")

    dry_run_report = execute_provider_requests(
        provider_requests,
        providers_config_path,
        {"local_comfyui_image", "local_comfyui_video", "local_piper_tts"},
        dry_run=True,
    )
    if int(dry_run_report["request_count"]) != 3:
        raise RuntimeError(f"local dry-run request_count mismatch: {dry_run_report['request_count']}")
    if int(dry_run_report["dry_run_count"]) != 3:
        raise RuntimeError(f"local dry-run count mismatch: {dry_run_report['dry_run_count']}")
    if int(dry_run_report["provider_ready_count"]) + int(dry_run_report["provider_not_ready_count"]) != 3:
        raise RuntimeError("local provider preflight counts do not match execution attempts")
    for item in dry_run_report["results"]:
        preview = item.get("request_preview", {})
        if item.get("status") != "dry_run" or "preflight" not in preview:
            raise RuntimeError(f"local dry-run preview missing preflight: {item}")

    safe_block_report = execute_provider_requests(
        provider_requests,
        providers_config_path,
        {"local_comfyui_image", "local_comfyui_video", "local_piper_tts"},
        dry_run=False,
        confirm_live=False,
    )
    if int(safe_block_report["blocked_count"]) != 3:
        raise RuntimeError(f"local safe-block count mismatch: {safe_block_report['blocked_count']}")

    provider_requests_report_path = ProjectPaths.reports_dir() / "local_provider_alternatives_requests_validation.json"
    provider_requests_report_path.parent.mkdir(parents=True, exist_ok=True)
    provider_requests_report_path.write_text(json.dumps(provider_requests, ensure_ascii=False, indent=2), encoding="utf-8")
    readiness_report = build_provider_readiness_report(providers_config_path, provider_requests_report_path)
    if not bool(readiness_report["manual_fallback_ready"]):
        raise RuntimeError("manual fallback should remain ready")
    readiness_items = {
        str(item.get("provider", "")): item
        for item in readiness_report.get("items", [])
        if isinstance(item, dict) and item.get("provider")
    }
    local_video_item = readiness_items.get("local_comfyui_video", {})
    local_video_ready = bool(local_video_item.get("ready", False))
    if local_video_ready:
        local_video_readiness = local_video_item.get("readiness", {}) if isinstance(local_video_item, dict) else {}
        if str(local_video_readiness.get("comfyui_server_mode", "")) != "live":
            raise RuntimeError(f"local video ready must use a live ComfyUI server: {local_video_readiness}")
        if int(local_video_readiness.get("missing_required_model_count", 0)) != 0:
            raise RuntimeError(f"local video ready cannot have missing models: {local_video_readiness}")
        if int(local_video_readiness.get("fixture_required_model_count", 0)) != 0:
            raise RuntimeError(f"local video ready cannot use fixture models: {local_video_readiness}")
        readiness_mode = "live_local_video_ready"
    else:
        if "local_comfyui_video: setup_required" not in readiness_report["blocking_reasons"]:
            raise RuntimeError(f"local video readiness reason missing: {readiness_report['blocking_reasons']}")
        readiness_mode = "local_video_setup_required"

    report_payload = {
        "provider_plan": provider_plan,
        "provider_requests": {
            "request_count": provider_requests["request_count"],
            "ready_count": provider_requests["ready_count"],
            "blocked_count": provider_requests["blocked_count"],
            "endpoints": endpoints,
        },
        "dry_run": {
            "request_count": dry_run_report["request_count"],
            "dry_run_count": dry_run_report["dry_run_count"],
            "provider_ready_count": dry_run_report["provider_ready_count"],
            "provider_not_ready_count": dry_run_report["provider_not_ready_count"],
        },
        "safe_block": {
            "blocked_count": safe_block_report["blocked_count"],
            "confirm_live": safe_block_report["confirm_live"],
        },
        "readiness": {
            "status": readiness_report["status"],
            "manual_fallback_ready": readiness_report["manual_fallback_ready"],
            "local_core_ready": readiness_report["local_core_ready"],
            "local_video_ready": readiness_report["local_video_ready"],
            "blocking_reasons": readiness_report["blocking_reasons"],
            "readiness_mode": readiness_mode,
        },
    }
    report_path = ProjectPaths.reports_dir() / "local_provider_alternatives_validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
