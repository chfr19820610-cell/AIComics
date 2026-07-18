from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.report_service import load_batches
from web.backend.settings import load_web_settings


@contextmanager
def preserve_file(path: Path):
    original_exists = path.exists()
    original_bytes = path.read_bytes() if original_exists else b""
    try:
        yield
    finally:
        if original_exists:
            path.write_bytes(original_bytes)
        elif path.exists():
            path.unlink()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_failure_hotspots_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            failure_hotspot_count INTEGER NOT NULL,
            top_hotspot_score INTEGER NOT NULL,
            top_failed_step_count INTEGER NOT NULL,
            top_blocked_step_count INTEGER NOT NULL,
            top_pending_step_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_failure_hotspots_validation_runs (
            run_id,
            run_at,
            failure_hotspot_count,
            top_hotspot_score,
            top_failed_step_count,
            top_blocked_step_count,
            top_pending_step_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["failure_hotspot_count"]),
            int(payload["top_hotspot_score"]),
            int(payload["top_failed_step_count"]),
            int(payload["top_blocked_step_count"]),
            int(payload["top_pending_step_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            failure_hotspot_count,
            top_hotspot_score,
            top_failed_step_count,
            top_blocked_step_count,
            top_pending_step_count
        FROM batch_failure_hotspots_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "failure_hotspot_count": row[2],
        "top_hotspot_score": row[3],
        "top_failed_step_count": row[4],
        "top_blocked_step_count": row[5],
        "top_pending_step_count": row[6],
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_failure_hotspots_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    season1_batch_path = settings.reports_dir / "season1_batch.json"
    season1_summary_path = settings.reports_dir / "season1_batch_summary.json"
    season1_report_path = settings.reports_dir / "season1_batch_report.json"
    season2_batch_path = settings.reports_dir / "season2_batch.json"
    season2_summary_path = settings.reports_dir / "season2_batch_summary.json"
    season2_report_path = settings.reports_dir / "season2_batch_report.json"
    season3_batch_path = settings.reports_dir / "season3_batch.json"
    season3_summary_path = settings.reports_dir / "season3_batch_summary.json"
    season3_report_path = settings.reports_dir / "season3_batch_report.json"

    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "succeeded"},
            {"job_id": f"{run_id}_002", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "running"},
            {"job_id": f"{run_id}_003", "episode_code": "E03", "job_type": "video", "provider": "manual_web", "status": "failed"},
        ]
    }
    season1_batch = {"batch_id": "season1_hotspot_validation", "status": "completed", "scope_type": "season", "scope_value": "S01", "step_count": 4}
    season1_summary = {"batch_id": "season1_hotspot_validation", "status": "completed", "scope_type": "season", "scope_value": "S01", "step_count": 4, "completed_step_count": 4}
    season1_report = {
        "batch_id": "season1_hotspot_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season1_hotspot_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/h1_1.json", "message": "ok"},
            {"batch_id": "season1_hotspot_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/h1_2.json", "message": "ok"},
            {"batch_id": "season1_hotspot_validation", "step_name": "build_provider_requests", "status": "completed", "output_path": "reports/h1_3.json", "message": "ok"},
            {"batch_id": "season1_hotspot_validation", "step_name": "render", "status": "completed", "output_path": "reports/h1_4.json", "message": "ok"},
        ],
    }
    season2_batch = {"batch_id": "season2_hotspot_validation", "status": "running", "scope_type": "season", "scope_value": "S02", "step_count": 4}
    season2_summary = {"batch_id": "season2_hotspot_validation", "status": "running", "scope_type": "season", "scope_value": "S02", "step_count": 4, "completed_step_count": 2}
    season2_report = {
        "batch_id": "season2_hotspot_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season2_hotspot_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/h2_1.json", "message": "ok"},
            {"batch_id": "season2_hotspot_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/h2_2.json", "message": "ok"},
            {"batch_id": "season2_hotspot_validation", "step_name": "build_provider_requests", "status": "running", "output_path": "reports/h2_3.json", "message": "running"},
            {"batch_id": "season2_hotspot_validation", "step_name": "render", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }
    season3_batch = {"batch_id": "season3_hotspot_validation", "status": "failed", "scope_type": "episode", "scope_value": "E03", "step_count": 3}
    season3_summary = {"batch_id": "season3_hotspot_validation", "status": "failed", "scope_type": "episode", "scope_value": "E03", "step_count": 3, "completed_step_count": 1}
    season3_report = {
        "batch_id": "season3_hotspot_validation",
        "step_count": 3,
        "step_results": [
            {"batch_id": "season3_hotspot_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/h3_1.json", "message": "ok"},
            {"batch_id": "season3_hotspot_validation", "step_name": "scan_assets", "status": "failed", "output_path": "reports/h3_2.json", "message": "failed"},
            {"batch_id": "season3_hotspot_validation", "step_name": "render", "status": "blocked", "output_path": "", "message": "blocked"},
        ],
    }

    with (
        preserve_file(jobs_path),
        preserve_file(season1_batch_path),
        preserve_file(season1_summary_path),
        preserve_file(season1_report_path),
        preserve_file(season2_batch_path),
        preserve_file(season2_summary_path),
        preserve_file(season2_report_path),
        preserve_file(season3_batch_path),
        preserve_file(season3_summary_path),
        preserve_file(season3_report_path),
    ):
        write_json(jobs_path, jobs_fixture)
        write_json(season1_batch_path, season1_batch)
        write_json(season1_summary_path, season1_summary)
        write_json(season1_report_path, season1_report)
        write_json(season2_batch_path, season2_batch)
        write_json(season2_summary_path, season2_summary)
        write_json(season2_report_path, season2_report)
        write_json(season3_batch_path, season3_batch)
        write_json(season3_summary_path, season3_summary)
        write_json(season3_report_path, season3_report)

        payload = load_batches(settings)

    multi_batch_summary = payload.get("multi_batch_summary", {})
    failure_hotspots = list(multi_batch_summary.get("failure_hotspots", []))
    top_hotspot = failure_hotspots[0] if failure_hotspots else {}

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "failure_hotspot_count": int(multi_batch_summary.get("failure_hotspot_count", 0)),
        "top_batch_id": str(top_hotspot.get("batch_id", "")),
        "top_hotspot_level": str(top_hotspot.get("hotspot_level", "")),
        "top_hotspot_score": int(top_hotspot.get("hotspot_score", 0)),
        "top_failed_step_count": int(top_hotspot.get("failed_step_count", 0)),
        "top_blocked_step_count": int(top_hotspot.get("blocked_step_count", 0)),
        "top_pending_step_count": int(top_hotspot.get("pending_step_count", 0)),
        "top_hotspot_bar_width": float(top_hotspot.get("hotspot_bar_width", 0.0)),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_failure_hotspots_validation_report.json"),
        "database_row": {},
    }

    if report_payload["failure_hotspot_count"] != 2:
        raise RuntimeError(
            f"failure_hotspot_count mismatch: expected 2, got {report_payload['failure_hotspot_count']}"
        )
    if report_payload["top_batch_id"] != "season3_hotspot_validation":
        raise RuntimeError(f"top_batch_id mismatch: expected season3_hotspot_validation, got {report_payload['top_batch_id']}")
    if report_payload["top_hotspot_level"] != "critical":
        raise RuntimeError(f"top_hotspot_level mismatch: expected critical, got {report_payload['top_hotspot_level']}")
    if report_payload["top_hotspot_score"] != 7:
        raise RuntimeError(f"top_hotspot_score mismatch: expected 7, got {report_payload['top_hotspot_score']}")
    if report_payload["top_failed_step_count"] != 1 or report_payload["top_blocked_step_count"] != 1:
        raise RuntimeError(
            f"top step mismatch: failed={report_payload['top_failed_step_count']}, blocked={report_payload['top_blocked_step_count']}"
        )
    if report_payload["top_pending_step_count"] != 2:
        raise RuntimeError(
            f"top_pending_step_count mismatch: expected 2, got {report_payload['top_pending_step_count']}"
        )
    if report_payload["top_hotspot_bar_width"] != 100.0:
        raise RuntimeError(
            f"top_hotspot_bar_width mismatch: expected 100.0, got {report_payload['top_hotspot_bar_width']}"
        )

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_failure_hotspots_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
