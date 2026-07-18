from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_json
from web.backend.services.batch_history_service import parse_batch_datetime
from web.backend.services.batch_operations_service import build_execution_operations_report_rows
from web.backend.settings import WebSettings


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
    from web.backend.services.report_service import load_batch_summary

    normalized_export_format = export_format.strip().lower() or "json"
    normalized_export_scope = export_scope.strip().lower() or "operations_report"
    if normalized_export_format not in {"json", "csv"}:
        raise ValueError(f"Unsupported export format `{export_format}`.")
    if normalized_export_scope not in {"operations_report", "report_archive"}:
        raise ValueError(f"Unsupported export scope `{export_scope}`.")

    payload = load_batch_summary(settings, include_history=False)
    multi_batch_summary = dict(payload.get("multi_batch_summary", {}))
    queue_summary = dict(multi_batch_summary.get("execution_queue_summary", {}))
    failure_breakdown = list(multi_batch_summary.get("execution_failure_breakdown", []))
    operations_report = dict(multi_batch_summary.get("execution_operations_report", {}))
    metric_rows = build_execution_operations_report_rows(queue_summary, failure_breakdown, operations_report)
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
