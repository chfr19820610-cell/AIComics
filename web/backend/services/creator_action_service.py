from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aicomic.core.job_builder import build_jobs_from_episode_manifest, serialize_jobs
from aicomic.core.manifest import load_json, write_json
from aicomic.core.models import JobRecord
from aicomic.core.horror_pipeline import (
    DEFAULT_HORROR_HOOK,
    build_horror_episode_manifest,
    build_horror_story_blueprint,
    write_horror_blueprint,
    write_horror_episode_manifest,
)
from aicomic.core.status import summarize_episode_state
from aicomic.providers.request_builder import build_provider_requests, write_provider_requests
from aicomic.providers.executor import execute_provider_requests, write_provider_execution_report
from aicomic.providers.result_writer import build_provider_result_writeback, write_provider_writeback_report
from aicomic.publish.dashboard import build_dashboard_payload, write_dashboard_html, write_dashboard_json
from aicomic.publish.publish_pack import build_enhanced_publish_pack, write_publish_pack
from aicomic.qc.asset_scanner import scan_episode_assets, write_asset_scan_report
from aicomic.qc.horror_review import (
    build_horror_regeneration_queue,
    load_optional_json,
    write_horror_regeneration_queue,
)
from aicomic.render.release_renderer import build_release_plan, render_release_video
from aicomic.render.preview_renderer import build_render_plan, render_preview_video
from aicomic.review.metrics import write_review_html, write_review_metrics, build_review_metrics
from web.backend.services.creator_review_service import (
    build_auto_review_decision,
    confirm_candidate_publish,
    load_creator_sample_review,
    record_candidate_release,
    require_sample_review_approved,
    review_gate_status,
    update_sample_review_autopilot,
)
from web.backend.services.creator_service import resolve_project_documents, resolve_project_root_by_id
from web.backend.settings import WebSettings


ACTION_LABELS = {
    "generate_horror_sample": "生成恐怖样片",
    "run_horror_assets_live": "执行恐怖样片真实资产",
    "build_horror_regeneration_queue": "生成恐怖重生成队列",
    "generate_horror_blueprint": "生成恐怖故事蓝图",
    "build_horror_episode": "生成恐怖样片镜头",
    "build_jobs": "生成任务包",
    "build_provider_requests": "生成 Provider 请求包",
    "apply_provider_results": "回写 Provider 结果",
    "scan_assets": "扫描素材状态",
    "render_preview": "渲染预览",
    "render_release": "渲染正式版",
    "build_publish_pack": "生成发布包",
    "build_candidate_publish_pack": "生成候选发布包",
    "export_approved_release": "过审后一键导出",
    "auto_repair_episode": "自动修复样片",
    "auto_review_episode": "自动审片",
    "record_candidate_release": "记录候选片",
    "autopilot_candidate_release": "启动自动驾驶",
    "confirm_candidate_publish": "确认候选片发布",
    "refresh_creator_reports": "刷新 Creator 报告",
}

HORROR_PROVIDER_POLICY = {
    "image": "local_comfyui_image",
    "video": "local_comfyui_video",
    "tts": "local_piper_tts",
}


def resolve_creator_provider_policy(documents: dict[str, Any]) -> dict[str, str]:
    creator_profile = documents["project_manifest"].get("default_providers", {})
    return {
        "image": str(creator_profile.get("image", "manual_web")),
        "video": str(creator_profile.get("video", "manual_web")),
        "tts": str(creator_profile.get("tts", "windows_tts")),
    }


def resolve_horror_hook(documents: dict[str, Any]) -> str:
    project_manifest = documents["project_manifest"]
    creator_profile = project_manifest.get("creator_profile", {})
    candidates = [
        str(creator_profile.get("season_hook", "")).strip(),
        str(creator_profile.get("logline", "")).strip(),
        str(documents["season_manifest"].get("theme", "")).strip(),
    ]
    return next((item for item in candidates if item), DEFAULT_HORROR_HOOK)


def route_jobs_with_provider_policy(jobs: list[JobRecord], provider_policy: dict[str, str]) -> list[JobRecord]:
    routed_jobs: list[JobRecord] = []
    for job in jobs:
        provider = job.provider
        if job.job_type == "image":
            provider = str(provider_policy.get("image", provider or "manual_web"))
        elif job.job_type == "video":
            provider = str(provider_policy.get("video", provider or "manual_web"))
        elif job.job_type == "tts":
            provider = str(provider_policy.get("tts", provider or "windows_tts"))
        routed_jobs.append(
            JobRecord(
                job_id=job.job_id,
                episode_code=job.episode_code,
                job_type=job.job_type,
                provider=provider,
                status=job.status,
            )
        )
    return routed_jobs


def resolve_providers_config(settings: WebSettings, project_root: Path) -> Path:
    candidate = project_root / "config" / "providers.yaml"
    if candidate.exists():
        return candidate
    return settings.project_root / "config" / "providers.yaml"


def parse_jobs(job_payload: dict[str, Any]) -> list[JobRecord]:
    jobs = []
    for item in job_payload.get("jobs", []):
        if not isinstance(item, dict):
            continue
        jobs.append(
            JobRecord(
                job_id=str(item.get("job_id", "")),
                episode_code=str(item.get("episode_code", "")),
                job_type=str(item.get("job_type", "")),
                provider=str(item.get("provider", "manual_web")),
                status=str(item.get("status", "pending")),
            )
        )
    return jobs


def select_episode_code(documents: dict[str, Any], requested_episode_code: str = "") -> str:
    if requested_episode_code:
        return requested_episode_code
    episodes = documents["episode_manifest"].get("episodes", [])
    if isinstance(episodes, list) and episodes:
        return str(episodes[0].get("episode_code", "E01"))
    return "E01"


def build_creator_validation_report(documents: dict[str, Any], provider_requests_path: Path | None = None) -> dict[str, Any]:
    episode_manifest = documents["episode_manifest"]
    jobs = parse_jobs(documents["jobs_payload"])
    episodes = episode_manifest.get("episodes", [])
    episode_states = {
        str(item.get("episode_code", "")): asdict(summarize_episode_state(str(item.get("episode_code", "")), jobs))
        for item in episodes
        if isinstance(item, dict)
    }
    job_status_by_episode: dict[str, dict[str, int]] = {}
    for job in jobs:
        distribution = job_status_by_episode.setdefault(job.episode_code, {})
        distribution[job.status] = int(distribution.get(job.status, 0)) + 1

    provider_requests = {}
    if provider_requests_path and provider_requests_path.exists():
        provider_requests = json.loads(provider_requests_path.read_text(encoding="utf-8"))
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    ready_episode_count = 0
    rendered_episode_count = 0
    for item in episodes if isinstance(episodes, list) else []:
        episode_code = str(item.get("episode_code", ""))
        if episode_states.get(episode_code, {}).get("status") == "assets_ready":
            ready_episode_count += 1
        if (preview_dir / f"{episode_code}_preview.mp4").exists():
            rendered_episode_count += 1

    report = {
        "projects_count": 1,
        "seasons_count": 1,
        "episodes_count": len(episodes) if isinstance(episodes, list) else 0,
        "jobs_count": len(jobs),
        "succeeded_jobs_count": sum(1 for job in jobs if job.status == "succeeded"),
        "provider_request_count": int(provider_requests.get("request_count", 0)),
        "provider_ready_request_count": int(provider_requests.get("ready_count", 0)),
        "provider_count": 3,
        "provider_execution_dry_run_count": 0,
        "provider_execution_local_dry_run_count": 0,
        "provider_execution_local_ready_count": int(provider_requests.get("ready_count", 0)),
        "provider_readiness_status": "creator_workspace_ready",
        "provider_readiness_blocking_count": 0,
        "production_fallback_ready": True,
        "production_live_provider_ready": False,
        "production_local_provider_ready": True,
        "provider_readiness_local_video_ready": True,
        "production_risk_register_status": "creator_workspace_mode",
        "production_risk_blocking_count": 0,
        "production_risk_warning_count": 0,
        "manual_import_imported_count": 0,
        "manual_import_missing_count": 0,
        "manual_import_succeeded_count": 0,
        "manual_import_manual_required_count": 0,
        "retry_batch_retried_count": 0,
        "retry_batch_scoped_job_count": len(jobs),
        "season_ready_episode_count": ready_episode_count,
        "season_rendered_episode_count": rendered_episode_count,
        "episode_states": episode_states,
        "job_status_by_episode": job_status_by_episode,
        "batch_file_path": "",
        "batch_step_count": 0,
        "batch_simulated_step_count": 0,
        "batches_count": 0,
        "batch_runs_count": 0,
        "production_live_provider_required": False,
    }
    return report


def write_creator_validation_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_jobs_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    provider_policy: dict[str, str] | None = None,
) -> dict[str, Any]:
    jobs_path = project_root / "jobs" / "episode_jobs.json"
    effective_provider_policy = provider_policy or resolve_creator_provider_policy(documents)
    jobs = build_jobs_from_episode_manifest(documents["episode_manifest"])
    routed_jobs = route_jobs_with_provider_policy(jobs, effective_provider_policy)
    payload = serialize_jobs(routed_jobs)
    write_json(jobs_path, payload)
    return {
        "status": "completed",
        "job_count": len(routed_jobs),
        "output_path": str(jobs_path),
        "provider_policy": effective_provider_policy,
        "episode_code": project_episode_code,
    }


def generate_horror_blueprint_action(
    documents: dict[str, Any],
    project_episode_code: str,
) -> dict[str, Any]:
    output_path = Path(documents["docs_dir"]) / "horror_story_blueprint.json"
    payload = build_horror_story_blueprint(
        resolve_horror_hook(documents),
        episode_code=project_episode_code,
        target_seconds=360,
        max_shots=60,
    )
    write_horror_blueprint(output_path, payload)
    return {
        "status": "completed",
        "output_path": str(output_path),
        "episode_code": project_episode_code,
        "target_seconds": int(payload["target_seconds"]),
        "shot_count": int(payload["shot_count"]),
    }


def build_horror_episode_action(
    documents: dict[str, Any],
    project_episode_code: str,
) -> dict[str, Any]:
    blueprint_path = Path(documents["docs_dir"]) / "horror_story_blueprint.json"
    if not blueprint_path.exists():
        generate_horror_blueprint_action(documents, project_episode_code)
    blueprint = load_json(blueprint_path)
    project_id = str(documents["project_manifest"].get("project_id", "aicomic_system"))
    season = int(documents["season_manifest"].get("season", 1) or 1)
    output_path = Path(documents["manifests_dir"]) / "episode_manifest.json"
    payload = build_horror_episode_manifest(blueprint, project_id=project_id, season=season)
    write_horror_episode_manifest(output_path, payload)
    episode = payload["episodes"][0]
    return {
        "status": "completed",
        "output_path": str(output_path),
        "episode_code": str(episode["episode_code"]),
        "shot_count": len(episode.get("shots", [])),
        "total_duration_seconds": sum(int(shot.get("duration", 0)) for shot in episode.get("shots", [])),
    }


def build_provider_requests_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    providers_config_path: Path,
    asset_root: Path,
    ensure_jobs_if_missing: bool = True,
    provider_policy: dict[str, str] | None = None,
) -> dict[str, Any]:
    jobs_path = project_root / "jobs" / "episode_jobs.json"
    reports_dir = Path(documents["reports_dir"])
    if not jobs_path.exists() and ensure_jobs_if_missing:
        build_jobs_action(
            settings,
            project_root,
            documents,
            project_episode_code,
            provider_policy=provider_policy,
        )
        documents = resolve_project_documents(settings, project_root)
    jobs = parse_jobs(load_json(jobs_path))
    provider_requests = build_provider_requests(
        documents["episode_manifest"],
        jobs,
        providers_config_path,
        asset_root,
        provider_overrides=provider_policy,
    )
    output_path = reports_dir / "provider_requests.json"
    write_provider_requests(output_path, provider_requests)
    return {
        "status": "completed",
        "request_count": provider_requests["request_count"],
        "ready_count": provider_requests["ready_count"],
        "blocked_count": provider_requests["blocked_count"],
        "output_path": str(output_path),
        "episode_code": project_episode_code,
    }


def parse_horror_live_limit() -> int:
    raw_value = os.environ.get("AICOMIC_HORROR_LIVE_LIMIT", "6").strip()
    return int(raw_value) if raw_value.isdigit() else 6


def parse_horror_request_ids() -> set[str]:
    raw_value = os.environ.get("AICOMIC_HORROR_REQUEST_IDS", "").strip()
    if not raw_value:
        return set()
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def request_ids_for_job_ids(job_ids: list[str]) -> set[str]:
    request_ids: set[str] = set()
    for job_id in job_ids:
        normalized = str(job_id).strip()
        if not normalized:
            continue
        request_ids.add(f"REQ_{normalized}")
    return request_ids


def filter_provider_requests_by_id(provider_requests: dict[str, Any], request_ids: set[str]) -> dict[str, Any]:
    if not request_ids:
        return provider_requests
    selected_requests = [
        request_item
        for request_item in provider_requests.get("requests", [])
        if str(request_item.get("request_id", "")) in request_ids
    ]
    return {
        **provider_requests,
        "requests": selected_requests,
        "request_count": len(selected_requests),
        "filtered_request_ids": sorted(request_ids),
    }


def execute_horror_assets_live_action(
    documents: dict[str, Any],
    project_episode_code: str,
    providers_config_path: Path,
    request_ids: set[str] | None = None,
    limit_override: int | None = None,
) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    requests_path = reports_dir / "provider_requests.json"
    if not requests_path.exists():
        raise RuntimeError("缺少 provider_requests.json，请先生成恐怖样片或 Provider 请求包。")
    provider_requests = load_json(requests_path)
    selected_request_ids = request_ids if request_ids is not None else parse_horror_request_ids()
    provider_requests = filter_provider_requests_by_id(provider_requests, selected_request_ids)
    limit = limit_override if limit_override is not None else parse_horror_live_limit()
    payload = execute_provider_requests(
        provider_requests,
        providers_config_path,
        selected_providers=set(HORROR_PROVIDER_POLICY.values()),
        dry_run=False,
        confirm_live=True,
        limit=limit,
        max_failures=1,
        skip_existing=True,
    )
    output_path = reports_dir / f"horror_provider_execution_{project_episode_code}.json"
    write_provider_execution_report(output_path, payload)
    return {
        "status": "completed",
        "request_count": int(payload["request_count"]),
        "success_count": int(payload["success_count"]),
        "failed_count": int(payload["failed_count"]),
        "skipped_count": int(payload["skipped_count"]),
        "blocked_count": int(payload["blocked_count"]),
        "limit": int(payload["limit"]),
        "selected_request_ids": sorted(selected_request_ids),
        "output_path": str(output_path),
        "episode_code": project_episode_code,
    }


def apply_provider_results_action(
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    requests_path = reports_dir / "provider_requests.json"
    jobs_path = project_root / "jobs" / "episode_jobs.json"
    if not requests_path.exists():
        raise RuntimeError("缺少 provider_requests.json，无法回写 Provider 结果。")
    if not jobs_path.exists():
        raise RuntimeError("缺少 episode_jobs.json，无法回写 Provider 结果。")
    jobs = parse_jobs(load_json(jobs_path))
    report, updated_jobs = build_provider_result_writeback(load_json(requests_path), jobs)
    report_output_path = reports_dir / f"provider_writeback_{project_episode_code}.json"
    jobs_output_path = project_root / "jobs" / "episode_jobs_provider_synced.json"
    write_provider_writeback_report(report_output_path, report)
    write_json(jobs_output_path, serialize_jobs(updated_jobs))
    return {
        "status": "completed",
        "changed_count": int(report["changed_count"]),
        "succeeded_count": int(report["succeeded_count"]),
        "manual_required_count": int(report["manual_required_count"]),
        "output_path": str(jobs_output_path),
        "jobs_output_path": str(jobs_output_path),
        "report_output_path": str(report_output_path),
        "episode_code": project_episode_code,
    }


def build_horror_regeneration_queue_action(
    documents: dict[str, Any],
    project_episode_code: str,
) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    writeback_report = load_optional_json(reports_dir / f"provider_writeback_{project_episode_code}.json")
    if not writeback_report:
        writeback_report = load_optional_json(reports_dir / "provider_writeback_report.json")
    execution_report = load_optional_json(reports_dir / f"horror_provider_execution_{project_episode_code}.json")
    payload = build_horror_regeneration_queue(
        documents["episode_manifest"],
        writeback_report,
        execution_report,
        episode_code=project_episode_code,
    )
    output_path = reports_dir / f"horror_regeneration_queue_{project_episode_code}.json"
    write_horror_regeneration_queue(output_path, payload)
    return {
        "status": "completed",
        "queue_count": int(payload["queue_count"]),
        "high_priority_count": int(payload["high_priority_count"]),
        "output_path": str(output_path),
        "episode_code": project_episode_code,
    }


def scan_assets_action(
    documents: dict[str, Any],
    project_episode_code: str,
    asset_root: Path,
) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    output_path = reports_dir / f"asset_scan_{project_episode_code}.json"
    report = scan_episode_assets(documents["episode_manifest"], project_episode_code, asset_root)
    write_asset_scan_report(output_path, report)
    return {
        "status": "completed",
        "ready_for_preview": bool(report.get("ready_for_preview", False)),
        "missing_required_count": int(report.get("missing_required_count", 0)),
        "missing_optional_count": int(report.get("missing_optional_count", 0)),
        "output_path": str(output_path),
        "episode_code": project_episode_code,
    }


def render_preview_action(
    documents: dict[str, Any],
    project_episode_code: str,
    asset_root: Path,
) -> dict[str, Any]:
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    reports_dir = Path(documents["reports_dir"])
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / f"{project_episode_code}_preview.mp4"
    report_output = reports_dir / f"render_preview_{project_episode_code}.json"
    plan = build_render_plan(documents["episode_manifest"], project_episode_code, asset_root)
    report = render_preview_video(plan, output_path, report_output)
    return {
        "status": "completed",
        "shot_count": int(plan.get("shot_count", 0)),
        "used_placeholder_count": int(report.get("used_placeholder_count", 0)),
        "output_path": str(output_path),
        "report_output_path": str(report_output),
        "episode_code": project_episode_code,
    }


def render_release_action(
    documents: dict[str, Any],
    project_episode_code: str,
    asset_root: Path,
) -> dict[str, Any]:
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    reports_dir = Path(documents["reports_dir"])
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / f"{project_episode_code}_release.mp4"
    report_output = reports_dir / f"render_release_{project_episode_code}.json"
    plan = build_release_plan(documents["episode_manifest"], project_episode_code, asset_root)
    report = render_release_video(plan, output_path, report_output)
    return {
        "status": "completed",
        "shot_count": int(plan.get("shot_count", 0)),
        "used_placeholder_count": int(report.get("used_placeholder_count", 0)),
        "output_path": str(output_path),
        "report_output_path": str(report_output),
        "episode_code": project_episode_code,
    }


def build_publish_pack_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    review_payload = require_sample_review_approved(
        settings,
        project_id=project_id,
        episode_code=project_episode_code,
        user_id=actor_user_id,
    )
    reports_dir = Path(documents["reports_dir"])
    output_path = reports_dir / f"publish_pack_{project_episode_code}.json"
    payload = build_enhanced_publish_pack(documents["episode_manifest"], project_episode_code)
    write_publish_pack(output_path, payload)
    gate = review_gate_status(review_payload)
    return {
        "status": "completed",
        "title_candidate_count": len(payload.get("title_candidates", [])),
        "output_path": str(output_path),
        "episode_code": project_episode_code,
        "review_status": str(review_payload.get("review_status", "")),
        "approved_for_export": bool(gate.get("approved_for_export", False)),
    }


def build_candidate_publish_pack_action(
    documents: dict[str, Any],
    project_episode_code: str,
) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    output_path = reports_dir / f"publish_pack_{project_episode_code}.json"
    payload = build_enhanced_publish_pack(documents["episode_manifest"], project_episode_code)
    write_publish_pack(output_path, payload)
    return {
        "status": "completed",
        "title_candidate_count": len(payload.get("title_candidates", [])),
        "output_path": str(output_path),
        "episode_code": project_episode_code,
        "candidate_only": True,
    }


def export_approved_release_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    asset_root: Path,
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    review_payload = require_sample_review_approved(
        settings,
        project_id=project_id,
        episode_code=project_episode_code,
        user_id=actor_user_id,
    )
    release_result = render_release_action(documents, project_episode_code, asset_root)
    documents = resolve_project_documents(settings, project_root)
    publish_result = build_publish_pack_action(
        settings,
        project_root,
        documents,
        project_episode_code,
        actor_user_id=actor_user_id,
    )
    documents = resolve_project_documents(settings, project_root)
    reports_result = refresh_creator_reports_action(
        settings,
        project_root,
        documents,
        ensure_jobs_if_missing=False,
    )
    return {
        "status": "completed",
        "episode_code": project_episode_code,
        "review_status": str(review_payload.get("review_status", "")),
        "release_output_path": str(release_result.get("output_path", "")),
        "publish_pack_output_path": str(publish_result.get("output_path", "")),
        "review_metrics_path": str(reports_result.get("review_metrics_path", "")),
        "dashboard_path": str(reports_result.get("dashboard_path", "")),
        "title_candidate_count": int(publish_result.get("title_candidate_count", 0)),
    }


def refresh_creator_reports_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    ensure_jobs_if_missing: bool = True,
) -> dict[str, Any]:
    jobs_path = project_root / "jobs" / "episode_jobs.json"
    reports_dir = Path(documents["reports_dir"])
    if not jobs_path.exists() and ensure_jobs_if_missing:
        project_episode_code = select_episode_code(documents)
        build_jobs_action(settings, project_root, documents, project_episode_code)
        documents = resolve_project_documents(settings, project_root)
    provider_requests_path = reports_dir / "provider_requests.json"
    creator_validation_path = reports_dir / "creator_validation_report.json"
    dashboard_path = reports_dir / "dashboard.json"
    dashboard_html_path = reports_dir / "dashboard.html"
    review_metrics_path = reports_dir / "review_metrics.json"
    review_html_path = reports_dir / "review_metrics.html"
    validation_payload = build_creator_validation_report(
        documents,
        provider_requests_path if provider_requests_path.exists() else None,
    )
    write_creator_validation_report(creator_validation_path, validation_payload)
    dashboard_payload = build_dashboard_payload(
        creator_validation_path,
        reports_dir / "season1_batch_summary.json",
        reports_dir / "season1_summary.json",
        reports_dir / "manual_import_report.json",
        reports_dir / "retry_batch_report.json",
    )
    write_dashboard_json(dashboard_path, dashboard_payload)
    write_dashboard_html(dashboard_html_path, dashboard_payload)
    review_payload = build_review_metrics(
        creator_validation_path,
        dashboard_path,
        reports_dir / "manual_import_report.json",
        reports_dir / "retry_batch_report.json",
        reports_dir / "provider_execution_openai_dry_run.json",
    )
    write_review_metrics(review_metrics_path, review_payload)
    write_review_html(review_html_path, review_payload)
    return {
        "status": "completed",
        "validation_report_path": str(creator_validation_path),
        "dashboard_path": str(dashboard_path),
        "review_metrics_path": str(review_metrics_path),
        "episode_code": select_episode_code(documents),
    }


def auto_repair_episode_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    providers_config_path: Path,
    actor_user_id: str = "",
) -> dict[str, Any]:
    review_payload = load_creator_sample_review(
        settings,
        str(documents["project_manifest"].get("project_id", project_root.name)),
        project_episode_code,
        user_id=actor_user_id,
    )
    reports_dir = Path(documents["reports_dir"])
    regeneration_queue_path = reports_dir / f"horror_regeneration_queue_{project_episode_code}.json"
    queue_payload = load_optional_json(regeneration_queue_path)
    queue_items = queue_payload.get("items", []) if isinstance(queue_payload.get("items", []), list) else []
    autopilot_state = dict(review_payload.get("autopilot_state", {}))
    current_cycle = int(autopilot_state.get("repair_cycle_count", 0) or 0)
    selected_items = [item for item in queue_items if isinstance(item, dict)][:6]
    selected_job_ids = [str(item.get("job_id", "")).strip() for item in selected_items if str(item.get("job_id", "")).strip()]
    selected_shot_ids = sorted({str(item.get("shot_id", "")).strip() for item in selected_items if str(item.get("shot_id", "")).strip()})
    if not selected_job_ids:
        updated_review = update_sample_review_autopilot(
            settings,
            str(documents["project_manifest"].get("project_id", project_root.name)),
            project_episode_code,
            autopilot_state={
                "autopilot_status": "auto_reviewing",
                "repair_cycle_count": current_cycle,
                "last_transition_reason": "当前没有可自动修复的镜头。",
            },
            actor_user_id=actor_user_id,
        )
        return {
            "status": "completed",
            "queue_count": int(updated_review.get("provider_summary", {}).get("queue_count", 0)),
            "repair_cycle_count": current_cycle,
            "selected_shot_ids": [],
            "output_path": str(regeneration_queue_path),
        }
    live_result = execute_horror_assets_live_action(
        documents,
        project_episode_code,
        providers_config_path,
        request_ids=request_ids_for_job_ids(selected_job_ids),
        limit_override=len(selected_job_ids),
    )
    documents = resolve_project_documents(settings, project_root)
    apply_result = apply_provider_results_action(project_root, documents, project_episode_code)
    documents = resolve_project_documents(settings, project_root)
    queue_result = build_horror_regeneration_queue_action(documents, project_episode_code)
    updated_review = update_sample_review_autopilot(
        settings,
        str(documents["project_manifest"].get("project_id", project_root.name)),
        project_episode_code,
        autopilot_state={
            "autopilot_status": "auto_reviewing",
            "repair_cycle_count": current_cycle + 1,
            "last_decision": "repair_and_retry",
            "last_decision_at": "",
            "last_transition_reason": f"已自动修复 {len(selected_shot_ids)} 个镜头。",
        },
        autopilot_audit={
            "total_repaired_shots": int(review_payload.get("autopilot_audit", {}).get("total_repaired_shots", 0) or 0) + len(selected_shot_ids),
            "repaired_shot_ids": sorted(
                {
                    *[str(item) for item in review_payload.get("autopilot_audit", {}).get("repaired_shot_ids", []) if str(item).strip()],
                    *selected_shot_ids,
                }
            ),
        },
        actor_user_id=actor_user_id,
    )
    return {
        "status": "completed",
        "repair_cycle_count": int(updated_review.get("autopilot_state", {}).get("repair_cycle_count", 0)),
        "selected_job_ids": selected_job_ids,
        "selected_shot_ids": selected_shot_ids,
        "queue_count": int(queue_result.get("queue_count", 0)),
        "success_count": int(live_result.get("success_count", 0)),
        "manual_required_count": int(apply_result.get("manual_required_count", 0)),
        "output_path": str(regeneration_queue_path),
    }


def auto_review_episode_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    review_payload = load_creator_sample_review(settings, project_id, project_episode_code, user_id=actor_user_id)
    decision = build_auto_review_decision(review_payload)
    autopilot_status = "candidate_ready" if decision["decision"] == "pass_to_candidate" else "human_hold"
    updated_review = update_sample_review_autopilot(
        settings,
        project_id,
        project_episode_code,
        autopilot_state={
            "autopilot_status": autopilot_status,
            "autopilot_run_id": str(review_payload.get("autopilot_state", {}).get("autopilot_run_id", "")),
            "policy_version": str(decision.get("policy_version", "auto_review_policy_v1")),
            "last_decision": str(decision.get("decision", "")),
            "last_decision_at": "",
            "last_transition_reason": "；".join(str(item) for item in decision.get("reasons", [])),
        },
        autopilot_audit={
            "final_route": "candidate_ready" if decision["decision"] == "pass_to_candidate" else "human_hold",
            "last_escalation_reason": "；".join(str(item) for item in decision.get("reasons", []))
            if decision["decision"] != "pass_to_candidate"
            else "",
        },
        actor_user_id=actor_user_id,
    )
    if decision["decision"] != "pass_to_candidate":
        raise RuntimeError("自动审片未通过：" + "；".join(str(item) for item in decision.get("reasons", [])))
    return {
        "status": "completed",
        "decision": str(decision.get("decision", "")),
        "reasons": list(decision.get("reasons", [])),
        "quality_score": int(decision.get("measured_metrics", {}).get("quality_score", 0)),
        "queue_count": int(updated_review.get("provider_summary", {}).get("queue_count", 0)),
        "output_path": str(updated_review.get("review_file_path", "")),
    }


def record_candidate_release_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    candidate_run_id: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    reports_dir = Path(documents["reports_dir"])
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    release_output_path = str(preview_dir / f"{project_episode_code}_release.mp4")
    publish_pack_output_path = str(reports_dir / f"publish_pack_{project_episode_code}.json")
    updated_review = record_candidate_release(
        settings,
        project_id,
        project_episode_code,
        candidate_run_id=candidate_run_id,
        release_output_path=release_output_path,
        publish_pack_output_path=publish_pack_output_path,
        actor_user_id=actor_user_id,
    )
    return {
        "status": "completed",
        "candidate_status": str(updated_review.get("candidate_release", {}).get("candidate_status", "")),
        "quality_score": int(updated_review.get("candidate_release", {}).get("quality_score", 0)),
        "release_output_path": release_output_path,
        "publish_pack_output_path": publish_pack_output_path,
        "output_path": str(updated_review.get("review_file_path", "")),
    }


def confirm_candidate_publish_action(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    project_episode_code: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    updated_review = confirm_candidate_publish(
        settings,
        project_id,
        project_episode_code,
        actor_user_id=actor_user_id,
    )
    return {
        "status": "completed",
        "review_status": str(updated_review.get("review_status", "")),
        "candidate_status": str(updated_review.get("candidate_release", {}).get("candidate_status", "")),
        "output_path": str(updated_review.get("review_file_path", "")),
    }


def execute_creator_action(
    settings: WebSettings,
    action: str,
    project_id: str = "",
    episode_code: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    if action not in ACTION_LABELS:
        raise ValueError(f"Unsupported creator action: {action}")

    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    project_episode_code = select_episode_code(documents, episode_code)
    jobs_path = project_root / "jobs" / "episode_jobs.json"
    reports_dir = Path(documents["reports_dir"])
    state_dir = Path(documents["state_dir"])
    asset_root = state_dir / "demo_assets"
    preview_dir = state_dir / "preview_outputs"
    providers_config_path = resolve_providers_config(settings, project_root)

    result: dict[str, Any] = {
        "action": action,
        "label": ACTION_LABELS[action],
        "project_id": str(documents["project_manifest"].get("project_id", project_root.name)),
        "project_root": str(project_root),
        "episode_code": project_episode_code,
    }

    if action == "build_jobs":
        result.update(build_jobs_action(settings, project_root, documents, project_episode_code))
        return result

    if action == "generate_horror_blueprint":
        result.update(generate_horror_blueprint_action(documents, project_episode_code))
        return result

    if action == "build_horror_episode":
        result.update(build_horror_episode_action(documents, project_episode_code))
        return result

    if action == "build_provider_requests":
        result.update(
            build_provider_requests_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                providers_config_path,
                asset_root,
            )
        )
        return result

    if action == "run_horror_assets_live":
        result.update(
            execute_horror_assets_live_action(
                documents,
                project_episode_code,
                providers_config_path,
            )
        )
        return result

    if action == "apply_provider_results":
        result.update(apply_provider_results_action(project_root, documents, project_episode_code))
        return result

    if action == "build_horror_regeneration_queue":
        result.update(build_horror_regeneration_queue_action(documents, project_episode_code))
        return result

    if action == "scan_assets":
        result.update(scan_assets_action(documents, project_episode_code, asset_root))
        return result

    if action == "render_preview":
        result.update(render_preview_action(documents, project_episode_code, asset_root))
        return result

    if action == "render_release":
        result.update(render_release_action(documents, project_episode_code, asset_root))
        return result

    if action == "build_publish_pack":
        result.update(
            build_publish_pack_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                actor_user_id=user_id,
            )
        )
        return result

    if action == "build_candidate_publish_pack":
        result.update(build_candidate_publish_pack_action(documents, project_episode_code))
        return result

    if action == "auto_repair_episode":
        result.update(
            auto_repair_episode_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                providers_config_path,
                actor_user_id=user_id,
            )
        )
        return result

    if action == "auto_review_episode":
        result.update(
            auto_review_episode_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                actor_user_id=user_id,
            )
        )
        return result

    if action == "record_candidate_release":
        result.update(
            record_candidate_release_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                candidate_run_id="manual_run",
                actor_user_id=user_id,
            )
        )
        return result

    if action == "confirm_candidate_publish":
        result.update(
            confirm_candidate_publish_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                actor_user_id=user_id,
            )
        )
        return result

    if action == "export_approved_release":
        result.update(
            export_approved_release_action(
                settings,
                project_root,
                documents,
                project_episode_code,
                asset_root,
                actor_user_id=user_id,
            )
        )
        return result

    if action == "refresh_creator_reports":
        result.update(refresh_creator_reports_action(settings, project_root, documents))
        return result

    raise ValueError(f"Creator action not implemented: {action}")
