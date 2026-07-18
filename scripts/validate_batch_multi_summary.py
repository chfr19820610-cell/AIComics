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


def ensure_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_multi_summary_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            batch_count INTEGER NOT NULL,
            completed_batch_count INTEGER NOT NULL,
            running_batch_count INTEGER NOT NULL,
            blocked_batch_count INTEGER NOT NULL,
            total_step_count INTEGER NOT NULL,
            completed_step_count INTEGER NOT NULL,
            step_completion_rate REAL NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_multi_summary_validation_runs (
            run_id,
            run_at,
            batch_count,
            completed_batch_count,
            running_batch_count,
            blocked_batch_count,
            total_step_count,
            completed_step_count,
            step_completion_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["batch_count"]),
            int(payload["completed_batch_count"]),
            int(payload["running_batch_count"]),
            int(payload["blocked_batch_count"]),
            int(payload["total_step_count"]),
            int(payload["completed_step_count"]),
            float(payload["step_completion_rate"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            batch_count,
            completed_batch_count,
            running_batch_count,
            blocked_batch_count,
            total_step_count,
            completed_step_count,
            step_completion_rate
        FROM batch_multi_summary_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "batch_count": row[2],
        "completed_batch_count": row[3],
        "running_batch_count": row[4],
        "blocked_batch_count": row[5],
        "total_step_count": row[6],
        "completed_step_count": row[7],
        "step_completion_rate": row[8],
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_multi_summary_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

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
            {"job_id": f"{run_id}_004", "episode_code": "E03", "job_type": "image", "provider": "manual_web", "status": "manual_required"},
        ]
    }
    season1_batch = {
        "batch_id": "season1_batch_validation",
        "status": "completed",
        "scope_type": "season",
        "scope_value": "S01",
        "step_count": 4,
    }
    season1_summary = {
        "batch_id": "season1_batch_validation",
        "status": "completed",
        "scope_type": "season",
        "scope_value": "S01",
        "step_count": 4,
        "completed_step_count": 4,
    }
    season1_report = {
        "batch_id": "season1_batch_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season1_batch_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/s1_1.json", "message": "ok"},
            {"batch_id": "season1_batch_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/s1_2.json", "message": "ok"},
            {"batch_id": "season1_batch_validation", "step_name": "build_provider_requests", "status": "completed", "output_path": "reports/s1_3.json", "message": "ok"},
            {"batch_id": "season1_batch_validation", "step_name": "render", "status": "completed", "output_path": "reports/s1_4.json", "message": "ok"},
        ],
    }
    season2_batch = {
        "batch_id": "season2_batch_validation",
        "status": "running",
        "scope_type": "season",
        "scope_value": "S02",
        "step_count": 4,
    }
    season2_summary = {
        "batch_id": "season2_batch_validation",
        "status": "running",
        "scope_type": "season",
        "scope_value": "S02",
        "step_count": 4,
        "completed_step_count": 2,
    }
    season2_report = {
        "batch_id": "season2_batch_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season2_batch_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/s2_1.json", "message": "ok"},
            {"batch_id": "season2_batch_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/s2_2.json", "message": "ok"},
            {"batch_id": "season2_batch_validation", "step_name": "build_provider_requests", "status": "running", "output_path": "reports/s2_3.json", "message": "running"},
            {"batch_id": "season2_batch_validation", "step_name": "render", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }
    season3_batch = {
        "batch_id": "season3_batch_validation",
        "status": "failed",
        "scope_type": "episode",
        "scope_value": "E03",
        "step_count": 3,
    }
    season3_summary = {
        "batch_id": "season3_batch_validation",
        "status": "failed",
        "scope_type": "episode",
        "scope_value": "E03",
        "step_count": 3,
        "completed_step_count": 1,
    }
    season3_report = {
        "batch_id": "season3_batch_validation",
        "step_count": 3,
        "step_results": [
            {"batch_id": "season3_batch_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/s3_1.json", "message": "ok"},
            {"batch_id": "season3_batch_validation", "step_name": "scan_assets", "status": "failed", "output_path": "reports/s3_2.json", "message": "failed"},
            {"batch_id": "season3_batch_validation", "step_name": "render", "status": "blocked", "output_path": "", "message": "blocked"},
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
    runtime_monitor = payload.get("runtime_monitor", {})
    source_payload = runtime_monitor.get("source", {})

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "batch_count": int(payload.get("count", 0)),
        "multi_batch_count": int(multi_batch_summary.get("batch_count", 0)),
        "completed_batch_count": int(multi_batch_summary.get("completed_batch_count", 0)),
        "running_batch_count": int(multi_batch_summary.get("running_batch_count", 0)),
        "blocked_batch_count": int(multi_batch_summary.get("blocked_batch_count", 0)),
        "status_counts": dict(multi_batch_summary.get("status_counts", {})),
        "scope_type_counts": dict(multi_batch_summary.get("scope_type_counts", {})),
        "total_step_count": int(multi_batch_summary.get("total_step_count", 0)),
        "completed_step_count": int(multi_batch_summary.get("completed_step_count", 0)),
        "step_completion_rate": float(multi_batch_summary.get("step_completion_rate", 0.0)),
        "runtime_step_total_count": int(runtime_monitor.get("step_total_count", 0)),
        "runtime_step_result_count": int(runtime_monitor.get("step_result_count", 0)),
        "source_batch_summary_count": len(source_payload.get("batch_summary_paths", [])),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_multi_summary_validation_report.json"),
        "database_row": {},
    }

    if report_payload["batch_count"] != 4 or report_payload["multi_batch_count"] != 4:
        raise RuntimeError(
            f"batch_count mismatch: count={report_payload['batch_count']}, multi={report_payload['multi_batch_count']}"
        )
    if report_payload["completed_batch_count"] != 2:
        raise RuntimeError(f"completed_batch_count mismatch: expected 1, got {report_payload['completed_batch_count']}")
    if report_payload["running_batch_count"] != 1:
        raise RuntimeError(f"running_batch_count mismatch: expected 1, got {report_payload['running_batch_count']}")
    if report_payload["blocked_batch_count"] != 1:
        raise RuntimeError(f"blocked_batch_count mismatch: expected 1, got {report_payload['blocked_batch_count']}")
    if report_payload["status_counts"] != {"completed": 2, "running": 1, "failed": 1}:
        raise RuntimeError(f"status_counts mismatch: {report_payload['status_counts']}")
    if report_payload["scope_type_counts"] != {"episode": 1, "season": 3}:
        raise RuntimeError(f"scope_type_counts mismatch: {report_payload['scope_type_counts']}")
    if report_payload["total_step_count"] != 14 or report_payload["completed_step_count"] != 10:
        raise RuntimeError(
            f"step counts mismatch: total={report_payload['total_step_count']}, completed={report_payload['completed_step_count']}"
        )
    if report_payload["step_completion_rate"] != 63.6:
        raise RuntimeError(f"step_completion_rate mismatch: expected 63.6, got {report_payload['step_completion_rate']}")
    if report_payload["runtime_step_total_count"] != 11 or report_payload["runtime_step_result_count"] != 11:
        raise RuntimeError(
            f"runtime step mismatch: total={report_payload['runtime_step_total_count']}, results={report_payload['runtime_step_result_count']}"
        )
    if report_payload["source_batch_summary_count"] != 3:
        raise RuntimeError(
            f"source_batch_summary_count mismatch: expected 3, got {report_payload['source_batch_summary_count']}"
        )

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_multi_summary_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
