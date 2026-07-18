from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aicomic.batch.retry_manager import retry_batch_jobs, write_retry_batch_report
from aicomic.core.dispatcher import resolve_dispatch_channel
from aicomic.core.job_control import write_job_payload
from aicomic.core.models import JobRecord
from aicomic.utils.atomic_io import atomic_write_json
from web.backend.services.batch_execution_service import build_execution_plan_templates as build_execution_plan_templates_service
from web.backend.services.batch_history_service import (
    fetch_batch_execution_queue_history_records as fetch_batch_execution_queue_history_records_paginated,
    get_batch_execution_preview_history_page,
    get_batch_execution_queue_history_page,
    get_batch_retry_history_page,
    load_batch_retry_history as load_batch_retry_history_records,
    load_batch_retry_trends,
)
from web.backend.services.batch_operations_service import (
    build_execution_failure_breakdown as build_execution_failure_breakdown_aggregate,
    build_execution_operations_report as build_execution_operations_report_aggregate,
    build_execution_operations_report_rows as build_execution_operations_report_rows_aggregate,
    build_execution_queue_summary as build_execution_queue_summary_aggregate,
)

from web.backend.settings import WebSettings


DISPATCH_STRATEGY_VERSION = "batch_dispatch_strategy_v1"
DISPATCH_STRATEGY_WEIGHTS: dict[str, int] = {
    "active_count": 2,
    "failed_count": 4,
    "manual_required_count": 3,
    "retried_count": 2,
    "retry_hotspot_score": 1,
}
DISPATCH_STRATEGY_THRESHOLDS: dict[str, int] = {
    "p0_failed_count": 1,
    "p0_manual_required_count": 1,
    "p1_backlog_count": 1,
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload.setdefault("exists", True)
        payload.setdefault("path", str(path))
        return payload
    return {
        "exists": True,
        "path": str(path),
        "items": payload,
    }


def load_dashboard(settings: WebSettings) -> dict[str, Any]:
    return read_json(settings.reports_dir / "dashboard.json")


def load_review_metrics(settings: WebSettings) -> dict[str, Any]:
    return read_json(settings.reports_dir / "review_metrics.json")


def load_validation_report(settings: WebSettings) -> dict[str, Any]:
    return read_json(settings.reports_dir / "demo_validation_report.json")


def load_episodes(settings: WebSettings) -> dict[str, Any]:
    validation_report = load_validation_report(settings)
    episode_manifest = read_json(settings.project_root / "manifests" / "episode_manifest.json")
    episode_states = validation_report.get("episode_states", {})
    manifest_index = {
        str(item.get("episode_code", "")): item
        for item in episode_manifest.get("episodes", [])
        if isinstance(item, dict)
    }
    items: list[dict[str, Any]] = []
    episode_codes = set()
    if isinstance(episode_states, dict):
        episode_codes.update(str(key) for key in episode_states.keys())
    episode_codes.update(code for code in manifest_index.keys() if code)

    for episode_code in sorted(episode_codes):
        state = episode_states.get(episode_code, {}) if isinstance(episode_states, dict) else {}
        manifest_item = manifest_index.get(str(episode_code), {})
        shots = manifest_item.get("shots", [])
        shot_count = len(shots) if isinstance(shots, list) else 0
        total_duration_seconds = sum(
            int(shot.get("duration", 0) or 0)
            for shot in shots
            if isinstance(shot, dict)
        )
        ai_video_shot_count = sum(
            1 for shot in shots if isinstance(shot, dict) and bool(shot.get("ai_video"))
        )
        items.append(
            {
                "episode_code": str(episode_code),
                "title": str(manifest_item.get("title", episode_code)),
                "status": str(state.get("status", "")),
                "completed_jobs": int(state.get("completed_jobs", 0)),
                "total_jobs": int(state.get("total_jobs", 0)),
                "shot_count": shot_count,
                "total_duration_seconds": total_duration_seconds,
                "publish_title": str(manifest_item.get("publish_title", "")),
                "cover_text": str(manifest_item.get("cover_text", "")),
                "preview_exists": (settings.state_dir / "preview_outputs" / f"{episode_code}_preview.mp4").exists(),
                "release_exists": (settings.state_dir / "preview_outputs" / f"{episode_code}_release.mp4").exists(),
                "publish_pack_exists": (settings.reports_dir / f"publish_pack_{episode_code}.json").exists(),
                "ai_video_shot_count": ai_video_shot_count,
                "static_shot_count": max(shot_count - ai_video_shot_count, 0),
            }
        )
    return {
        "items": items,
        "count": len(items),
        "source": validation_report.get("path", ""),
    }


def load_jobs(
    settings: WebSettings,
    episode_code: str = "",
    job_type: str = "",
    status: str = "",
    provider: str = "",
) -> dict[str, Any]:
    payload = read_json(settings.jobs_dir / "episode_jobs.json")
    jobs = payload.get("jobs", [])
    filtered_jobs = []
    for job in jobs if isinstance(jobs, list) else []:
        if episode_code and str(job.get("episode_code", "")) != episode_code:
            continue
        if job_type and str(job.get("job_type", "")) != job_type:
            continue
        if status and str(job.get("status", "")) != status:
            continue
        if provider and str(job.get("provider", "")) != provider:
            continue
        filtered_jobs.append(job)
    return {
        "items": filtered_jobs,
        "count": len(filtered_jobs),
        "source": str(settings.jobs_dir / "episode_jobs.json"),
        "filters": {
            "episode_code": episode_code,
            "job_type": job_type,
            "status": status,
            "provider": provider,
        },
    }


def load_jobs_as_records(path: Path) -> list[JobRecord]:
    payload = read_json(path)
    jobs = payload.get("jobs", [])
    records: list[JobRecord] = []
    for item in jobs if isinstance(jobs, list) else []:
        records.append(
            JobRecord(
                job_id=str(item.get("job_id", "")),
                episode_code=str(item.get("episode_code", "")),
                job_type=str(item.get("job_type", "")),
                provider=str(item.get("provider", "")),
                status=str(item.get("status", "")),
            )
        )
    return records


def parse_batch_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def write_execution_operations_archive(
    settings: WebSettings,
    export_time: datetime,
    export_document: dict[str, Any],
    metric_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamp = export_time.strftime("%Y%m%d%H%M%S")
    archive_dir = settings.reports_dir / "execution_operations_archive" / export_time.strftime("%Y%m%d") / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    json_name = f"execution_operations_report_{timestamp}.json"
    csv_name = f"execution_operations_report_{timestamp}.csv"
    manifest_name = f"execution_operations_archive_manifest_{timestamp}.json"
    json_path = archive_dir / json_name
    csv_path = archive_dir / csv_name
    manifest_path = archive_dir / manifest_name

    atomic_write_json(json_path, export_document)
    fieldnames = ["section", "metric", "value", "extra"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in metric_rows:
            writer.writerow({fieldname: item.get(fieldname, "") for fieldname in fieldnames})

    operations_report = dict(export_document.get("execution_operations_report", {}))
    manifest = {
        "archived_at": export_time.isoformat(),
        "archive_scope": "execution_operations_report_archive",
        "archive_dir": str(archive_dir),
        "health_status": operations_report.get("health_status", ""),
        "top_failure_reason": operations_report.get("top_failure_reason", ""),
        "summary_cards": operations_report.get("summary_cards", []),
        "files": [
            {"name": json_name, "path": str(json_path), "type": "operations_report_json", "count": len(metric_rows)},
            {"name": csv_name, "path": str(csv_path), "type": "operations_report_csv", "count": len(metric_rows)},
        ],
        "file_count": 2,
        "metric_count": len(metric_rows),
    }
    atomic_write_json(manifest_path, manifest)
    return {
        "manifest_name": manifest_name,
        "manifest_path": str(manifest_path),
        "archive_dir": str(archive_dir),
        "archived_files": manifest["files"],
        "archived_file_count": manifest["file_count"],
        "metric_count": manifest["metric_count"],
    }


def load_execution_operations_archives(settings: WebSettings, limit: int = 20) -> dict[str, Any]:
    normalized_limit = max(1, min(limit, 200))
    archive_root = settings.reports_dir / "execution_operations_archive"
    archives: list[dict[str, Any]] = []
    if archive_root.exists():
        for manifest_path in archive_root.glob("*/*/execution_operations_archive_manifest_*.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            archive_dir = Path(str(manifest.get("archive_dir", manifest_path.parent)))
            try:
                resolved_archive_dir = archive_dir.resolve()
                resolved_archive_root = archive_root.resolve()
            except OSError:
                continue
            if resolved_archive_root not in [resolved_archive_dir, *resolved_archive_dir.parents]:
                continue
            archives.append(
                {
                    "archive_id": manifest_path.parent.name,
                    "archived_at": str(manifest.get("archived_at", "")),
                    "archive_dir": str(archive_dir),
                    "manifest_path": str(manifest_path),
                    "manifest_name": manifest_path.name,
                    "file_count": int(manifest.get("file_count", 0)),
                    "metric_count": int(manifest.get("metric_count", 0)),
                    "health_status": str(manifest.get("health_status", "")),
                    "top_failure_reason": str(manifest.get("top_failure_reason", "")),
                    "files": list(manifest.get("files", [])),
                }
            )
    archives.sort(key=lambda item: str(item.get("archived_at", "")), reverse=True)
    return {
        "allowed": True,
        "reason": "Execution operations archives loaded successfully.",
        "archive_root": str(archive_root),
        "archives": archives[:normalized_limit],
        "archive_count": len(archives[:normalized_limit]),
        "total_count": len(archives),
    }


def cleanup_execution_operations_archives(
    settings: WebSettings,
    retention_days: int = 30,
    dry_run: bool = True,
) -> dict[str, Any]:
    normalized_retention_days = max(1, min(retention_days, 365))
    archive_root = settings.reports_dir / "execution_operations_archive"
    cleanup_time = datetime.now().astimezone()
    cutoff_time = cleanup_time - timedelta(days=normalized_retention_days)
    archive_payload = load_execution_operations_archives(settings, limit=200)
    eligible_archives: list[dict[str, Any]] = []
    for archive in list(archive_payload.get("archives", [])):
        archived_at = parse_batch_datetime(str(archive.get("archived_at", "")))
        if archived_at is None or archived_at >= cutoff_time:
            continue
        eligible_archives.append({**archive, "cleanup_reason": f"archived_at before retention cutoff {cutoff_time.isoformat()}"})

    deleted_archives: list[dict[str, Any]] = []
    skipped_archives: list[dict[str, Any]] = []
    if not dry_run and archive_root.exists():
        archive_root_resolved = archive_root.resolve()
        for archive in eligible_archives:
            archive_dir = Path(str(archive.get("archive_dir", "")))
            try:
                resolved_archive_dir = archive_dir.resolve()
            except OSError:
                skipped_archives.append({**archive, "skip_reason": "archive path could not be resolved"})
                continue
            if archive_root_resolved not in [resolved_archive_dir, *resolved_archive_dir.parents]:
                skipped_archives.append({**archive, "skip_reason": "archive path is outside archive root"})
                continue
            if not archive_dir.exists():
                skipped_archives.append({**archive, "skip_reason": "archive path does not exist"})
                continue
            shutil.rmtree(archive_dir)
            deleted_archives.append(archive)
    return {
        "allowed": True,
        "reason": "Execution operations archive cleanup evaluated successfully.",
        "archive_root": str(archive_root),
        "cleanup_at": cleanup_time.isoformat(),
        "retention_days": normalized_retention_days,
        "dry_run": dry_run,
        "eligible_count": len(eligible_archives),
        "deleted_count": len(deleted_archives),
        "skipped_count": len(skipped_archives),
        "archives": eligible_archives,
        "deleted_archives": deleted_archives,
        "skipped_archives": skipped_archives,
    }


def export_execution_operations_report(
    settings: WebSettings,
    export_format: str = "json",
    export_scope: str = "operations_report",
) -> dict[str, Any]:
    normalized_export_format = export_format.strip().lower() or "json"
    normalized_export_scope = export_scope.strip().lower() or "operations_report"
    if normalized_export_format not in {"json", "csv"}:
        raise ValueError(f"Unsupported export format `{export_format}`.")
    if normalized_export_scope not in {"operations_report", "report_archive"}:
        raise ValueError(f"Unsupported export scope `{export_scope}`.")

    payload = load_batches(settings)
    multi_batch_summary = dict(payload.get("multi_batch_summary", {}))
    queue_summary = dict(multi_batch_summary.get("execution_queue_summary", {}))
    failure_breakdown = list(multi_batch_summary.get("execution_failure_breakdown", []))
    operations_report = dict(multi_batch_summary.get("execution_operations_report", {}))
    metric_rows = build_execution_operations_report_rows_aggregate(queue_summary, failure_breakdown, operations_report)
    export_time = datetime.now().astimezone()
    export_document = {
        "exported_at": export_time.isoformat(),
        "export_scope": normalized_export_scope,
        "export_format": normalized_export_format,
        "count": len(metric_rows),
        "items": metric_rows,
        "execution_queue_summary": queue_summary,
        "execution_failure_breakdown": failure_breakdown,
        "execution_operations_report": operations_report,
    }
    timestamp = export_time.strftime("%Y%m%d%H%M%S")
    export_prefix = "execution_operations_report"
    export_name = f"{export_prefix}_{timestamp}.{normalized_export_format}"
    export_path = settings.reports_dir / export_name

    archive_payload: dict[str, Any] | None = None
    if normalized_export_scope == "report_archive":
        archive_payload = write_execution_operations_archive(settings, export_time, export_document, metric_rows)
        export_name = str(archive_payload.get("manifest_name", export_name))
        export_path = Path(str(archive_payload.get("manifest_path", export_path)))
    elif normalized_export_format == "csv":
        fieldnames = ["section", "metric", "value", "extra"]
        with export_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in metric_rows:
                writer.writerow({fieldname: item.get(fieldname, "") for fieldname in fieldnames})
    else:
        atomic_write_json(export_path, export_document)

    result = {
        "allowed": True,
        "reason": "Execution operations report exported successfully.",
        "export_scope": normalized_export_scope,
        "export_format": normalized_export_format,
        "export_name": export_name,
        "export_path": str(export_path),
        "export_count": len(metric_rows),
        "operations_report": operations_report,
        "metric_rows": metric_rows,
        "metric_count": len(metric_rows),
    }
    if archive_payload is not None:
        result.update(
            {
                "archive_path": archive_payload.get("archive_dir", ""),
                "archived_file_count": archive_payload.get("archived_file_count", 0),
                "archived_files": archive_payload.get("archived_files", []),
            }
        )
    return result




def classify_batch_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"completed", "succeeded", "success"}:
        return "completed"
    if normalized in {"failed", "blocked", "manual_required", "partial_failed", "error"}:
        return "blocked"
    if normalized in {"running", "queued", "pending", "planned", "created"}:
        return "running"
    return "other"


def classify_failure_hotspot_level(failed_step_count: int, blocked_step_count: int, pending_step_count: int) -> str:
    if failed_step_count > 0 or blocked_step_count > 0:
        return "critical"
    if pending_step_count > 0:
        return "warning"
    return "info"


def classify_retry_hotspot_level(retry_count: int, generated_count: int) -> str:
    if retry_count >= 4 or (generated_count > 0 and retry_count >= 2):
        return "critical"
    if retry_count > 0:
        return "warning"
    return "info"


def build_retry_hotspots(
    retry_queue_distribution: dict[str, int],
    retry_provider_distribution: dict[str, int],
    retry_episode_distribution: dict[str, int],
    retry_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}

    def ensure_bucket(dimension: str, name: str) -> dict[str, Any]:
        key = f"{dimension}:{name}"
        return buckets.setdefault(
            key,
            {
                "dimension": dimension,
                "name": name,
                "retry_count": 0,
                "current_retry_count": 0,
                "history_action_count": 0,
                "dry_run_count": 0,
                "generated_count": 0,
            },
        )

    for queue_name, count in retry_queue_distribution.items():
        bucket = ensure_bucket("queue", queue_name)
        bucket["retry_count"] += int(count)
        bucket["current_retry_count"] += int(count)
    for provider, count in retry_provider_distribution.items():
        bucket = ensure_bucket("provider", provider)
        bucket["retry_count"] += int(count)
        bucket["current_retry_count"] += int(count)
    for episode_code, count in retry_episode_distribution.items():
        bucket = ensure_bucket("episode", episode_code)
        bucket["retry_count"] += int(count)
        bucket["current_retry_count"] += int(count)

    for item in retry_history:
        retried_count = int(item.get("retried_count", 0))
        if retried_count <= 0:
            continue
        dry_run = bool(item.get("dry_run", False))
        episode_code = str(item.get("episode_code", ""))
        provider = str(item.get("provider", ""))
        queue_name = str(item.get("queue_name", ""))
        if not queue_name and provider:
            _, queue_name = resolve_dispatch_channel(provider)
        targets = []
        if episode_code:
            targets.append(("episode", episode_code))
        if provider:
            targets.append(("provider", provider))
        if queue_name:
            targets.append(("queue", queue_name))
        if not targets:
            targets.append(("batch", "all_retry_scope"))
        for dimension, name in targets:
            bucket = ensure_bucket(dimension, name)
            bucket["retry_count"] += retried_count
            bucket["history_action_count"] += 1
            if dry_run:
                bucket["dry_run_count"] += 1
            else:
                bucket["generated_count"] += 1

    raw_items: list[dict[str, Any]] = []
    for bucket in buckets.values():
        retry_count = int(bucket.get("retry_count", 0))
        generated_count = int(bucket.get("generated_count", 0))
        dry_run_count = int(bucket.get("dry_run_count", 0))
        hotspot_score = retry_count * 2 + generated_count * 2 + dry_run_count
        raw_items.append(
            {
                **bucket,
                "hotspot_score": hotspot_score,
                "hotspot_level": classify_retry_hotspot_level(retry_count, generated_count),
            }
        )
    max_score = max([int(item.get("hotspot_score", 0)) for item in raw_items] or [0])
    raw_items.sort(
        key=lambda item: (
            -int(item.get("hotspot_score", 0)),
            str(item.get("dimension", "")),
            str(item.get("name", "")),
        )
    )
    return [
        {
            **item,
            "hotspot_bar_width": round((int(item.get("hotspot_score", 0)) / max(1, max_score)) * 100, 1),
        }
        for item in raw_items
        if int(item.get("hotspot_score", 0)) > 0
    ]


def build_priority_actions(
    failure_hotspots: list[dict[str, Any]],
    retry_hotspots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    priority_actions: list[dict[str, Any]] = []
    for item in failure_hotspots[:3]:
        priority_actions.append(
            {
                "priority": "P0" if item.get("hotspot_level") == "critical" else "P1",
                "action_type": "resolve_failure_hotspot",
                "target": str(item.get("batch_id", "")),
                "reason": (
                    f"failed={item.get('failed_step_count', 0)}, "
                    f"blocked={item.get('blocked_step_count', 0)}, "
                    f"pending={item.get('pending_step_count', 0)}"
                ),
                "suggested_command": "review_batch_steps",
            }
        )
    for item in retry_hotspots[:3]:
        priority_actions.append(
            {
                "priority": "P1" if item.get("hotspot_level") == "critical" else "P2",
                "action_type": "stabilize_retry_hotspot",
                "target": f"{item.get('dimension', '')}:{item.get('name', '')}",
                "reason": (
                    f"retry_count={item.get('retry_count', 0)}, "
                    f"generated={item.get('generated_count', 0)}, "
                    f"dry_run={item.get('dry_run_count', 0)}"
                ),
                "suggested_command": "inspect_retry_scope",
            }
        )
    if not priority_actions:
        priority_actions.append(
            {
                "priority": "P3",
                "action_type": "monitor_batches",
                "target": "all",
                "reason": "No active failure or retry hotspot detected.",
                "suggested_command": "continue_monitoring",
            }
        )
    return priority_actions[:6]


def build_auto_disposition_templates(
    failure_hotspots: list[dict[str, Any]],
    retry_hotspots: list[dict[str, Any]],
    priority_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    if failure_hotspots:
        hotspot = failure_hotspots[0]
        templates.append(
            {
                "template_key": "failure_hotspot_recovery",
                "title": "Failure Hotspot Recovery",
                "priority": "P0" if str(hotspot.get("hotspot_level", "")) == "critical" else "P1",
                "trigger_type": "failure_hotspot",
                "target": str(hotspot.get("batch_id", "")),
                "suggested_command": "review_batch_steps",
                "checklist": [
                    "Inspect failed and blocked step outputs.",
                    "Rebuild or rerun the failed batch segment.",
                    "Confirm pending steps can continue safely.",
                ],
            }
        )
    if retry_hotspots:
        hotspot = retry_hotspots[0]
        templates.append(
            {
                "template_key": "retry_hotspot_stabilization",
                "title": "Retry Hotspot Stabilization",
                "priority": "P1" if str(hotspot.get("hotspot_level", "")) == "critical" else "P2",
                "trigger_type": "retry_hotspot",
                "target": f"{hotspot.get('dimension', '')}:{hotspot.get('name', '')}",
                "suggested_command": "inspect_retry_scope",
                "checklist": [
                    "Check repeated retry root cause for this scope.",
                    "Compare dry-run vs generated retry counts.",
                    "Reduce duplicate retries before dispatching more jobs.",
                ],
            }
        )
    if priority_actions:
        action = priority_actions[0]
        templates.append(
            {
                "template_key": "priority_action_execution",
                "title": "Priority Action Execution",
                "priority": str(action.get("priority", "P2")),
                "trigger_type": "priority_action",
                "target": str(action.get("target", "")),
                "suggested_command": str(action.get("suggested_command", "continue_monitoring")),
                "checklist": [
                    f"Execute {action.get('suggested_command', 'continue_monitoring')}.",
                    f"Record reason: {action.get('reason', '')}",
                    "Re-check runtime monitor after execution.",
                ],
            }
        )
    if not templates:
        templates.append(
            {
                "template_key": "monitor_only",
                "title": "Monitor Only",
                "priority": "P3",
                "trigger_type": "monitor",
                "target": "all",
                "suggested_command": "continue_monitoring",
                "checklist": ["Keep monitoring batches.", "No immediate action required."],
            }
        )
    return templates[:4]


def build_dispatch_strategy_metadata() -> dict[str, Any]:
    return {
        "strategy_key": DISPATCH_STRATEGY_VERSION,
        "strategy_name": "Batch Dispatch Priority Strategy",
        "description": "Scores queue and provider dispatch targets by active workload, failures, manual blocks, retries and retry hotspots.",
        "weights": DISPATCH_STRATEGY_WEIGHTS,
        "thresholds": DISPATCH_STRATEGY_THRESHOLDS,
        "score_formula": "active*2 + failed*4 + manual*3 + retried*2 + retry_hotspot_score",
    }


def calculate_dispatch_score(
    active_count: int,
    failed_count: int,
    manual_count: int,
    retried_count: int,
    retry_score: int,
    weights: dict[str, int] | None = None,
) -> int:
    score_weights = weights or DISPATCH_STRATEGY_WEIGHTS
    return (
        active_count * int(score_weights.get("active_count", 0))
        + failed_count * int(score_weights.get("failed_count", 0))
        + manual_count * int(score_weights.get("manual_required_count", 0))
        + retried_count * int(score_weights.get("retried_count", 0))
        + retry_score * int(score_weights.get("retry_hotspot_score", 0))
    )


def recommend_dispatch_priority(
    failed_count: int,
    manual_count: int,
    backlog_count: int,
    thresholds: dict[str, int] | None = None,
) -> str:
    priority_thresholds = thresholds or DISPATCH_STRATEGY_THRESHOLDS
    if failed_count >= int(priority_thresholds.get("p0_failed_count", 1)):
        return "P0"
    if manual_count >= int(priority_thresholds.get("p0_manual_required_count", 1)):
        return "P0"
    if backlog_count >= int(priority_thresholds.get("p1_backlog_count", 1)):
        return "P1"
    return "P2"


def build_dispatch_priority_plan(
    queue_items: list[dict[str, Any]],
    provider_items: list[dict[str, Any]],
    retry_hotspots: list[dict[str, Any]],
    weights: dict[str, int] | None = None,
    thresholds: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    retry_hotspot_index = {
        f"{item.get('dimension', '')}:{item.get('name', '')}": item
        for item in retry_hotspots
    }
    plan: list[dict[str, Any]] = []

    for item in queue_items:
        queue_name = str(item.get("queue_name", ""))
        retry_item = retry_hotspot_index.get(f"queue:{queue_name}", {})
        active_count = int(item.get("active_count", 0))
        failed_count = int(item.get("failed_count", 0))
        manual_count = int(item.get("manual_required_count", 0))
        retried_count = int(item.get("retried_count", 0))
        backlog_count = active_count + failed_count + manual_count
        retry_score = int(retry_item.get("hotspot_score", 0))
        dispatch_score = calculate_dispatch_score(
            active_count,
            failed_count,
            manual_count,
            retried_count,
            retry_score,
            weights,
        )
        recommended_priority = recommend_dispatch_priority(failed_count, manual_count, backlog_count, thresholds)
        plan.append(
            {
                "dimension": "queue",
                "target": f"queue:{queue_name}",
                "dispatch_score": dispatch_score,
                "recommended_priority": recommended_priority,
                "active_count": active_count,
                "failed_count": failed_count,
                "manual_required_count": manual_count,
                "retried_count": retried_count,
                "backlog_count": backlog_count,
                "reason": f"active={active_count}, failed={failed_count}, manual={manual_count}, retried={retried_count}",
            }
        )

    for item in provider_items:
        provider = str(item.get("provider", ""))
        retry_item = retry_hotspot_index.get(f"provider:{provider}", {})
        active_count = int(item.get("active_count", 0))
        failed_count = int(item.get("failed_count", 0))
        manual_count = int(item.get("manual_required_count", 0))
        retried_count = int(retry_item.get("current_retry_count", 0))
        backlog_count = active_count + failed_count + manual_count
        retry_score = int(retry_item.get("hotspot_score", 0))
        dispatch_score = calculate_dispatch_score(
            active_count,
            failed_count,
            manual_count,
            retried_count,
            retry_score,
            weights,
        )
        recommended_priority = recommend_dispatch_priority(failed_count, manual_count, backlog_count, thresholds)
        plan.append(
            {
                "dimension": "provider",
                "target": f"provider:{provider}",
                "dispatch_score": dispatch_score,
                "recommended_priority": recommended_priority,
                "active_count": active_count,
                "failed_count": failed_count,
                "manual_required_count": manual_count,
                "retried_count": retried_count,
                "backlog_count": backlog_count,
                "reason": f"active={active_count}, failed={failed_count}, manual={manual_count}, retried={retried_count}",
            }
        )

    max_dispatch_score = max([int(item.get("dispatch_score", 0)) for item in plan] or [0])
    plan.sort(
        key=lambda item: (
            -int(item.get("dispatch_score", 0)),
            str(item.get("dimension", "")),
            str(item.get("target", "")),
        )
    )
    return [
        {
            **item,
            "dispatch_bar_width": round((int(item.get("dispatch_score", 0)) / max(1, max_dispatch_score)) * 100, 1),
        }
        for item in plan
        if int(item.get("dispatch_score", 0)) > 0
    ]


def make_plan_key(prefix: str, value: str) -> str:
    safe_value = "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")
    return f"{prefix}_{safe_value or 'all'}"


def build_execution_steps(source_type: str, target: str, command: str) -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "step_key": "validate_target",
            "title": "Validate target scope",
            "action": f"Confirm target exists before running {command}.",
        },
        {
            "order": 2,
            "step_key": "dry_run",
            "title": "Run dry-run preview",
            "action": f"Preview {source_type} action for {target}.",
        },
        {
            "order": 3,
            "step_key": "record_result",
            "title": "Record execution result",
            "action": "Write execution summary and audit note after preview.",
        },
    ]


def build_execution_plan_templates(
    auto_disposition_templates: list[dict[str, Any]],
    dispatch_priority_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return build_execution_plan_templates_service(auto_disposition_templates, dispatch_priority_plan)


def preview_batch_execution_plan(
    settings: WebSettings,
    plan_key: str,
    user_id: str,
    target: str = "",
    mode: str = "dry_run",
) -> dict[str, Any]:
    from web.backend.services.batch_execution_service import preview_batch_execution_plan as preview_batch_execution_plan_service

    return preview_batch_execution_plan_service(settings, plan_key, user_id, target=target, mode=mode)


def queue_batch_execution_plan(
    settings: WebSettings,
    plan_key: str,
    user_id: str,
    target: str = "",
    mode: str = "queued",
) -> dict[str, Any]:
    from web.backend.services.batch_execution_service import queue_batch_execution_plan as queue_batch_execution_plan_service

    return queue_batch_execution_plan_service(settings, plan_key, user_id, target=target, mode=mode)


def discover_batch_snapshots(settings: WebSettings) -> list[dict[str, Any]]:
    summary_paths = sorted(
        settings.reports_dir.glob("*_batch_summary.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    snapshots: list[dict[str, Any]] = []
    for summary_path in summary_paths:
        summary_payload = read_json(summary_path)
        base_name = summary_path.name.removesuffix("_summary.json")
        batch_path = settings.reports_dir / f"{base_name}.json"
        report_path = settings.reports_dir / f"{base_name}_report.json"
        batch_payload = read_json(batch_path)
        report_payload = read_json(report_path)
        step_count = int(summary_payload.get("step_count", batch_payload.get("step_count", report_payload.get("step_count", 0))) or 0)
        completed_step_count = int(summary_payload.get("completed_step_count", 0) or 0)
        snapshots.append(
            {
                "item": {
                    "batch_id": str(summary_payload.get("batch_id", batch_payload.get("batch_id", base_name))),
                    "status": str(summary_payload.get("status", batch_payload.get("status", "unknown"))),
                    "scope_type": str(summary_payload.get("scope_type", batch_payload.get("scope_type", ""))),
                    "scope_value": str(summary_payload.get("scope_value", batch_payload.get("scope_value", ""))),
                    "step_count": step_count,
                    "completed_step_count": completed_step_count,
                    "step_completion_rate": round((completed_step_count / max(1, step_count)) * 100, 1),
                    "summary_path": str(summary_path),
                    "batch_path": str(batch_path),
                    "batch_report_path": str(report_path),
                    "updated_at": summary_path.stat().st_mtime if summary_path.exists() else 0,
                },
                "summary_path": summary_path,
                "batch_path": batch_path,
                "report_path": report_path,
                "summary_payload": summary_payload,
                "batch_payload": batch_payload,
                "report_payload": report_payload,
            }
        )
    return snapshots


def generate_retry_batch_package(
    settings: WebSettings,
    statuses: list[str] | None = None,
    episode_code: str = "",
    provider: str = "",
    dry_run: bool = True,
) -> dict[str, Any]:
    jobs_path = settings.jobs_dir / "episode_jobs.json"
    report_output_path = settings.reports_dir / "retry_batch_report.json"
    jobs_output_path = settings.jobs_dir / "episode_jobs_batch_retried.json"
    retryable_statuses = {item.strip() for item in (statuses or ["failed", "manual_required"]) if item.strip()}
    jobs = load_jobs_as_records(jobs_path)
    report, updated_jobs = retry_batch_jobs(
        jobs,
        retryable_statuses,
        episode_code=episode_code or None,
        provider=provider or None,
    )
    retry_candidates = [
        {
            "job_id": job.job_id,
            "episode_code": job.episode_code,
            "job_type": job.job_type,
            "provider": job.provider,
            "status": job.status,
        }
        for job in jobs
        if job.job_id in set(str(item) for item in report.get("retried_job_ids", []))
    ]
    if not dry_run:
        write_retry_batch_report(report_output_path, report)
        write_job_payload(jobs_output_path, updated_jobs)
    return {
        "status": "preview_ready" if dry_run else "generated",
        "jobs_path": str(jobs_path),
        "report_output_path": str(report_output_path),
        "jobs_output_path": str(jobs_output_path),
        "retryable_statuses": sorted(retryable_statuses),
        "episode_code": episode_code,
        "provider": provider,
        "dry_run": dry_run,
        "scoped_job_count": int(report.get("scoped_job_count", 0)),
        "retried_count": int(report.get("retried_count", 0)),
        "untouched_count": int(report.get("untouched_count", 0)),
        "retried_job_ids": list(report.get("retried_job_ids", [])),
        "retry_candidates": retry_candidates[:20],
        "retry_candidate_count": len(retry_candidates),
    }


def load_batch_summary(
    settings: WebSettings,
    include_history: bool = False,
    history_page_size: int = 10,
    user_id: str = "",
) -> dict[str, Any]:
    normalized_history_page_size = max(1, min(history_page_size, 100))
    batch_snapshots = discover_batch_snapshots(settings)
    primary_snapshot = batch_snapshots[0] if batch_snapshots else {}
    batch_payload = dict(primary_snapshot.get("batch_payload", read_json(settings.reports_dir / "season1_batch.json")))
    batch_summary = dict(primary_snapshot.get("summary_payload", read_json(settings.reports_dir / "season1_batch_summary.json")))
    batch_report = dict(primary_snapshot.get("report_payload", read_json(settings.reports_dir / "season1_batch_report.json")))
    retry_batch_report = read_json(settings.reports_dir / "retry_batch_report.json")
    jobs_payload = read_json(settings.jobs_dir / "episode_jobs.json")
    jobs = list(jobs_payload.get("jobs", [])) if isinstance(jobs_payload.get("jobs", []), list) else []
    retry_job_ids = {str(item) for item in retry_batch_report.get("retried_job_ids", []) if str(item)}
    batch_items = [dict(item["item"]) for item in batch_snapshots]
    batch_count = len(batch_items)
    status_counts: dict[str, int] = {}
    provider_counts: dict[str, dict[str, Any]] = {}
    queue_counts: dict[str, dict[str, Any]] = {}
    episode_counts: dict[str, dict[str, Any]] = {}
    active_jobs: list[dict[str, Any]] = []

    for job in jobs:
        status = str(job.get("status", "unknown"))
        provider = str(job.get("provider", "unknown"))
        episode_code = str(job.get("episode_code", "unknown"))
        _, queue_name = resolve_dispatch_channel(provider)

        status_counts[status] = status_counts.get(status, 0) + 1

        provider_bucket = provider_counts.setdefault(
            provider,
            {
                "provider": provider,
                "queue_name": queue_name,
                "total_count": 0,
                "succeeded_count": 0,
                "active_count": 0,
                "failed_count": 0,
                "manual_required_count": 0,
            },
        )
        provider_bucket["total_count"] += 1

        queue_bucket = queue_counts.setdefault(
            queue_name,
            {
                "queue_name": queue_name,
                "total_count": 0,
                "active_count": 0,
                "failed_count": 0,
                "manual_required_count": 0,
                "succeeded_count": 0,
                "retried_count": 0,
            },
        )
        queue_bucket["total_count"] += 1
        if str(job.get("job_id", "")) in retry_job_ids:
            queue_bucket["retried_count"] += 1

        episode_bucket = episode_counts.setdefault(
            episode_code,
            {
                "episode_code": episode_code,
                "total_count": 0,
                "completed_count": 0,
                "active_count": 0,
                "failed_count": 0,
                "manual_required_count": 0,
            },
        )
        episode_bucket["total_count"] += 1

        if status in {"succeeded", "cached", "skipped"}:
            provider_bucket["succeeded_count"] += 1
            queue_bucket["succeeded_count"] += 1
            episode_bucket["completed_count"] += 1
        elif status in {"pending", "queued", "running"}:
            provider_bucket["active_count"] += 1
            queue_bucket["active_count"] += 1
            episode_bucket["active_count"] += 1
            active_jobs.append(
                {
                    "job_id": str(job.get("job_id", "")),
                    "episode_code": episode_code,
                    "job_type": str(job.get("job_type", "")),
                    "provider": provider,
                    "queue_name": queue_name,
                    "status": status,
                }
            )
        elif status == "manual_required":
            provider_bucket["manual_required_count"] += 1
            queue_bucket["manual_required_count"] += 1
            episode_bucket["manual_required_count"] += 1
            active_jobs.append(
                {
                    "job_id": str(job.get("job_id", "")),
                    "episode_code": episode_code,
                    "job_type": str(job.get("job_type", "")),
                    "provider": provider,
                    "queue_name": queue_name,
                    "status": status,
                }
            )
        elif status == "failed":
            provider_bucket["failed_count"] += 1
            queue_bucket["failed_count"] += 1
            episode_bucket["failed_count"] += 1
            active_jobs.append(
                {
                    "job_id": str(job.get("job_id", "")),
                    "episode_code": episode_code,
                    "job_type": str(job.get("job_type", "")),
                    "provider": provider,
                    "queue_name": queue_name,
                    "status": status,
                }
            )

    queue_items = sorted(queue_counts.values(), key=lambda item: (-int(item["active_count"]), -int(item["total_count"]), item["queue_name"]))
    provider_items = sorted(provider_counts.values(), key=lambda item: (-int(item["active_count"]), -int(item["total_count"]), item["provider"]))
    episode_items = []
    for item in episode_counts.values():
        completion_rate = round((int(item["completed_count"]) / max(1, int(item["total_count"]))) * 100, 1)
        episode_items.append({**item, "completion_rate": completion_rate})
    episode_items.sort(key=lambda item: (-int(item["active_count"]), -int(item["failed_count"]), item["episode_code"]))

    failed_count = int(status_counts.get("failed", 0))
    manual_required_count = int(status_counts.get("manual_required", 0))
    running_count = int(status_counts.get("running", 0))
    queued_count = int(status_counts.get("queued", 0))
    pending_count = int(status_counts.get("pending", 0))
    completed_count = sum(int(status_counts.get(key, 0)) for key in ("succeeded", "cached", "skipped"))
    total_count = len(jobs)
    runtime_status = "healthy"
    if failed_count > 0 or manual_required_count > 0:
        runtime_status = "blocked"
    elif running_count > 0 or queued_count > 0 or pending_count > 0:
        runtime_status = "running"
    elif total_count > 0 and completed_count == total_count:
        runtime_status = "completed"

    risk_flags: list[dict[str, str]] = []
    if failed_count > 0:
        risk_flags.append({"level": "critical", "name": "failed_jobs", "detail": f"{failed_count} 个任务失败，建议优先重试。"})
    if manual_required_count > 0:
        risk_flags.append({"level": "warning", "name": "manual_required_jobs", "detail": f"{manual_required_count} 个任务待人工处理。"})
    if queued_count + pending_count > 0:
        risk_flags.append({"level": "info", "name": "queued_jobs", "detail": f"{queued_count + pending_count} 个任务仍在排队。"})

    next_actions: list[str] = []
    if failed_count > 0:
        next_actions.append(f"优先处理 {failed_count} 个 failed 任务，并生成 retry-batch 清单。")
    if manual_required_count > 0:
        next_actions.append(f"安排人工补位 {manual_required_count} 个 manual_required 任务。")
    if queued_count + pending_count > 0:
        next_actions.append(f"继续推进 {queued_count + pending_count} 个待执行任务，关注高活跃队列。")
    if not next_actions:
        next_actions.append("批量生成任务运行平稳，可继续推进下一批次。")

    step_results: list[dict[str, Any]] = []
    batch_status_counts: dict[str, int] = {}
    batch_scope_type_counts: dict[str, int] = {}
    batch_group_counts = {"completed": 0, "running": 0, "blocked": 0, "other": 0}
    total_batch_steps = 0
    completed_batch_steps = 0
    failure_hotspots: list[dict[str, Any]] = []
    for snapshot in batch_snapshots:
        item = dict(snapshot["item"])
        status = str(item.get("status", "unknown"))
        scope_type = str(item.get("scope_type", "")) or "unknown"
        status_bucket = classify_batch_status(status)
        batch_status_counts[status] = batch_status_counts.get(status, 0) + 1
        batch_scope_type_counts[scope_type] = batch_scope_type_counts.get(scope_type, 0) + 1
        batch_group_counts[status_bucket] += 1
        total_batch_steps += int(item.get("step_count", 0))
        completed_batch_steps += int(item.get("completed_step_count", 0))
        report_step_results = list(snapshot["report_payload"].get("step_results", [])) if isinstance(snapshot["report_payload"].get("step_results", []), list) else []
        failed_step_count = 0
        blocked_step_count = 0
        for step_result in report_step_results:
            step_status = str(step_result.get("status", "unknown"))
            if step_status in {"failed", "error"}:
                failed_step_count += 1
            if step_status in {"blocked", "manual_required"}:
                blocked_step_count += 1
            step_results.append(
                {
                    "batch_id": step_result.get("batch_id", item.get("batch_id", "")),
                    "step_name": step_result.get("step_name", ""),
                    "status": step_status,
                    "output_path": step_result.get("output_path", ""),
                    "message": step_result.get("message", ""),
                }
            )
        pending_step_count = max(0, int(item.get("step_count", 0)) - int(item.get("completed_step_count", 0)))
        hotspot_score = failed_step_count * 3 + blocked_step_count * 2 + pending_step_count
        if hotspot_score > 0 or status_bucket in {"running", "blocked"}:
            failure_hotspots.append(
                {
                    "batch_id": str(item.get("batch_id", "")),
                    "scope_type": str(item.get("scope_type", "")),
                    "scope_value": str(item.get("scope_value", "")),
                    "status": status,
                    "failed_step_count": failed_step_count,
                    "blocked_step_count": blocked_step_count,
                    "pending_step_count": pending_step_count,
                    "hotspot_score": hotspot_score,
                    "hotspot_level": classify_failure_hotspot_level(
                        failed_step_count,
                        blocked_step_count,
                        pending_step_count,
                    ),
                    "summary_path": str(item.get("summary_path", "")),
                }
            )
    step_status_counts: dict[str, int] = {}
    for item in step_results:
        step_status = str(item.get("status", "unknown"))
        step_status_counts[step_status] = step_status_counts.get(step_status, 0) + 1
    retry_history_page = get_batch_retry_history_page(
        page=1,
        page_size=normalized_history_page_size if include_history else 1,
        user_id=user_id,
    )
    retry_history_records = load_batch_retry_history_records(limit=500, user_id=user_id)
    retry_trends = load_batch_retry_trends(limit=14, user_id=user_id)
    execution_preview_history_page = get_batch_execution_preview_history_page(
        page=1,
        page_size=normalized_history_page_size if include_history else 1,
        user_id=user_id,
    )
    execution_queue_history_page = get_batch_execution_queue_history_page(
        page=1,
        page_size=normalized_history_page_size if include_history else 1,
        user_id=user_id,
    )
    execution_queue_history_records = fetch_batch_execution_queue_history_records_paginated(user_id=user_id)
    execution_queue_summary = build_execution_queue_summary_aggregate(execution_queue_history_records)
    execution_failure_breakdown = build_execution_failure_breakdown_aggregate(execution_queue_history_records)
    execution_operations_report = build_execution_operations_report_aggregate(
        execution_queue_summary,
        execution_queue_history_records,
        execution_failure_breakdown,
    )
    max_queue_total = max([int(item.get("total_count", 0)) for item in queue_items] or [0])
    queue_trends = []
    for item in queue_items:
        backlog_count = int(item.get("active_count", 0)) + int(item.get("failed_count", 0)) + int(item.get("manual_required_count", 0))
        queue_status = "healthy"
        if int(item.get("failed_count", 0)) > 0 or int(item.get("manual_required_count", 0)) > 0:
            queue_status = "blocked"
        elif backlog_count > 0:
            queue_status = "running"
        queue_trends.append(
            {
                **item,
                "backlog_count": backlog_count,
                "queue_status": queue_status,
                "load_bar_width": round((int(item.get("total_count", 0)) / max(1, max_queue_total)) * 100, 1),
                "backlog_bar_width": round((backlog_count / max(1, max_queue_total)) * 100, 1),
            }
        )
    retry_queue_distribution: dict[str, int] = {}
    retry_provider_distribution: dict[str, int] = {}
    retry_episode_distribution: dict[str, int] = {}
    for job in jobs:
        job_id = str(job.get("job_id", ""))
        if job_id not in retry_job_ids:
            continue
        provider = str(job.get("provider", "unknown"))
        episode_code = str(job.get("episode_code", "unknown"))
        _, queue_name = resolve_dispatch_channel(provider)
        retry_queue_distribution[queue_name] = retry_queue_distribution.get(queue_name, 0) + 1
        retry_provider_distribution[provider] = retry_provider_distribution.get(provider, 0) + 1
        retry_episode_distribution[episode_code] = retry_episode_distribution.get(episode_code, 0) + 1
    retry_hotspots = build_retry_hotspots(
        retry_queue_distribution,
        retry_provider_distribution,
        retry_episode_distribution,
        retry_history_records,
    )
    max_hotspot_score = max([int(item.get("hotspot_score", 0)) for item in failure_hotspots] or [0])
    failure_hotspots.sort(
        key=lambda item: (
            -int(item.get("hotspot_score", 0)),
            -int(item.get("failed_step_count", 0)),
            -int(item.get("blocked_step_count", 0)),
            str(item.get("batch_id", "")),
        )
    )
    failure_hotspots = [
        {
            **item,
            "hotspot_bar_width": round((int(item.get("hotspot_score", 0)) / max(1, max_hotspot_score)) * 100, 1),
        }
        for item in failure_hotspots
    ]
    priority_actions = build_priority_actions(failure_hotspots, retry_hotspots)
    auto_disposition_templates = build_auto_disposition_templates(
        failure_hotspots,
        retry_hotspots,
        priority_actions,
    )
    dispatch_strategy = build_dispatch_strategy_metadata()
    dispatch_priority_plan = build_dispatch_priority_plan(
        queue_items,
        provider_items,
        retry_hotspots,
        dispatch_strategy["weights"],
        dispatch_strategy["thresholds"],
    )
    execution_plan_templates = build_execution_plan_templates(
        auto_disposition_templates,
        dispatch_priority_plan,
    )

    embedded_preview_history = list(execution_preview_history_page.get("items", [])) if include_history else []
    embedded_queue_history = list(execution_queue_history_page.get("items", [])) if include_history else []
    embedded_retry_history = list(retry_history_page.get("items", [])) if include_history else []
    embedded_history_page = int(execution_preview_history_page.get("page", 1)) if include_history else 0
    embedded_history_page_size = int(execution_preview_history_page.get("page_size", normalized_history_page_size)) if include_history else 0
    embedded_queue_page = int(execution_queue_history_page.get("page", 1)) if include_history else 0
    embedded_queue_page_size = int(execution_queue_history_page.get("page_size", normalized_history_page_size)) if include_history else 0
    embedded_retry_page = int(retry_history_page.get("page", 1)) if include_history else 0
    embedded_retry_page_size = int(retry_history_page.get("page_size", normalized_history_page_size)) if include_history else 0

    return {
        "items": batch_items,
        "count": batch_count,
        "history_mode": "embedded_first_page" if include_history else "summary_only",
        "multi_batch_summary": {
            "batch_count": batch_count,
            "status_counts": batch_status_counts,
            "scope_type_counts": batch_scope_type_counts,
            "completed_batch_count": batch_group_counts["completed"],
            "running_batch_count": batch_group_counts["running"],
            "blocked_batch_count": batch_group_counts["blocked"],
            "other_batch_count": batch_group_counts["other"],
            "total_step_count": total_batch_steps,
            "completed_step_count": completed_batch_steps,
            "step_completion_rate": round((completed_batch_steps / max(1, total_batch_steps)) * 100, 1),
            "latest_batch_id": str((batch_items[0] if batch_items else {}).get("batch_id", "")),
            "latest_status": str((batch_items[0] if batch_items else {}).get("status", "")),
            "latest_summary_path": str((batch_items[0] if batch_items else {}).get("summary_path", "")),
            "failure_hotspots": failure_hotspots[:10],
            "failure_hotspot_count": len(failure_hotspots),
            "retry_hotspots": retry_hotspots[:12],
            "retry_hotspot_count": len(retry_hotspots),
            "priority_actions": priority_actions,
            "priority_action_count": len(priority_actions),
            "auto_disposition_templates": auto_disposition_templates,
            "auto_disposition_template_count": len(auto_disposition_templates),
            "dispatch_strategy": dispatch_strategy,
            "dispatch_strategy_weights": dispatch_strategy["weights"],
            "dispatch_priority_plan": dispatch_priority_plan[:12],
            "dispatch_priority_count": len(dispatch_priority_plan),
            "execution_plan_templates": execution_plan_templates,
            "execution_plan_template_count": len(execution_plan_templates),
            "execution_preview_history": embedded_preview_history,
            "execution_preview_history_count": int(execution_preview_history_page.get("total_count", 0)),
            "execution_preview_history_page": embedded_history_page,
            "execution_preview_history_page_size": embedded_history_page_size,
            "execution_preview_history_total_pages": int(execution_preview_history_page.get("total_pages", 1)) if include_history else 0,
            "execution_queue_summary": execution_queue_summary,
            "execution_queue_history": embedded_queue_history,
            "execution_queue_history_count": int(execution_queue_history_page.get("total_count", 0)),
            "execution_queue_history_page": embedded_queue_page,
            "execution_queue_history_page_size": embedded_queue_page_size,
            "execution_queue_history_total_pages": int(execution_queue_history_page.get("total_pages", 1)) if include_history else 0,
            "execution_failure_breakdown": execution_failure_breakdown,
            "execution_failure_breakdown_count": len(execution_failure_breakdown),
            "execution_operations_report": execution_operations_report,
        },
        "runtime_monitor": {
            "status": runtime_status,
            "job_total_count": total_count,
            "job_completed_count": completed_count,
            "job_active_count": running_count + queued_count + pending_count,
            "job_failed_count": failed_count,
            "job_manual_required_count": manual_required_count,
            "job_completion_rate": round((completed_count / max(1, total_count)) * 100, 1),
            "step_total_count": total_batch_steps,
            "step_completed_count": completed_batch_steps,
            "step_status_counts": step_status_counts,
            "queues": queue_items,
            "queue_count": len(queue_items),
            "queue_trends": queue_trends,
            "queue_trend_count": len(queue_trends),
            "providers": provider_items,
            "provider_count": len(provider_items),
            "episodes": episode_items,
            "episode_count": len(episode_items),
            "active_jobs": active_jobs[:10],
            "active_job_count": len(active_jobs),
            "risk_flags": risk_flags,
            "risk_flag_count": len(risk_flags),
            "next_actions": next_actions,
            "retry_summary": {
                "exists": bool(retry_batch_report.get("exists", False)),
                "report_path": str(retry_batch_report.get("path", settings.reports_dir / "retry_batch_report.json")),
                "retried_count": int(retry_batch_report.get("retried_count", 0)),
                "scoped_job_count": int(retry_batch_report.get("scoped_job_count", 0)),
                "retryable_statuses": list(retry_batch_report.get("retryable_statuses", [])),
                "retried_job_count": len(retry_job_ids),
                "retried_job_ids": sorted(retry_job_ids),
                "queue_distribution": retry_queue_distribution,
                "provider_distribution": retry_provider_distribution,
                "episode_distribution": retry_episode_distribution,
            },
            "retry_history": embedded_retry_history,
            "retry_history_count": int(retry_history_page.get("total_count", 0)),
            "retry_history_page": embedded_retry_page,
            "retry_history_page_size": embedded_retry_page_size,
            "retry_history_total_pages": int(retry_history_page.get("total_pages", 1)) if include_history else 0,
            "retry_trends": retry_trends,
            "retry_trend_count": len(retry_trends),
            "step_results": step_results,
            "step_result_count": len(step_results),
            "source": {
                "batch_path": str(primary_snapshot.get("batch_path", settings.reports_dir / "season1_batch.json")),
                "batch_report_path": str(primary_snapshot.get("report_path", settings.reports_dir / "season1_batch_report.json")),
                "batch_summary_path": str(primary_snapshot.get("summary_path", settings.reports_dir / "season1_batch_summary.json")),
                "batch_paths": [str(snapshot["batch_path"]) for snapshot in batch_snapshots],
                "batch_report_paths": [str(snapshot["report_path"]) for snapshot in batch_snapshots],
                "batch_summary_paths": [str(snapshot["summary_path"]) for snapshot in batch_snapshots],
                "jobs_path": str(settings.jobs_dir / "episode_jobs.json"),
                "retry_report_path": str(settings.reports_dir / "retry_batch_report.json"),
            },
        },
    }


def load_batches(settings: WebSettings, history_page_size: int = 10, user_id: str = "") -> dict[str, Any]:
    return load_batch_summary(settings, include_history=True, history_page_size=history_page_size, user_id=user_id)


def load_provider_executions(settings: WebSettings) -> dict[str, Any]:
    reports = [
        settings.reports_dir / "provider_execution_openai_dry_run.json",
        settings.reports_dir / "provider_execution_openai_safe_block.json",
        settings.reports_dir / "provider_execution_local_dry_run.json",
    ]
    items = []
    for report_path in reports:
        payload = read_json(report_path)
        if not payload.get("exists", False):
            continue
        items.append(
            {
                "name": report_path.stem,
                "path": str(report_path),
                "request_count": payload.get("request_count", 0),
                "success_count": payload.get("success_count", 0),
                "failed_count": payload.get("failed_count", 0),
                "dry_run_count": payload.get("dry_run_count", 0),
                "blocked_count": payload.get("blocked_count", 0),
                "provider_ready_count": payload.get("provider_ready_count", 0),
                "provider_not_ready_count": payload.get("provider_not_ready_count", 0),
                "confirm_live": payload.get("confirm_live", False),
                "stopped_by_failure_guard": payload.get("stopped_by_failure_guard", False),
            }
        )
    readiness_payload = read_json(settings.reports_dir / "provider_readiness_report.json")
    return {
        "items": items,
        "count": len(items),
        "readiness": {
            "exists": bool(readiness_payload.get("exists", False)),
            "path": str(settings.reports_dir / "provider_readiness_report.json"),
            "status": readiness_payload.get("status", "unknown"),
            "manual_fallback_ready": readiness_payload.get("manual_fallback_ready", False),
            "openai_core_ready": readiness_payload.get("openai_core_ready", False),
            "local_core_ready": readiness_payload.get("local_core_ready", False),
            "local_video_ready": readiness_payload.get("local_video_ready", False),
            "full_local_ready": readiness_payload.get("full_local_ready", False),
            "blocking_reasons": readiness_payload.get("blocking_reasons", []),
        },
    }
