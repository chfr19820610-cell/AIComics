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
def temporary_file_payload(path: Path, payload: dict[str, object]):
    original_exists = path.exists()
    original_bytes = path.read_bytes() if original_exists else b""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
        CREATE TABLE IF NOT EXISTS batch_runtime_monitor_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            runtime_status TEXT NOT NULL,
            job_total_count INTEGER NOT NULL,
            job_active_count INTEGER NOT NULL,
            job_failed_count INTEGER NOT NULL,
            job_manual_required_count INTEGER NOT NULL,
            queue_count INTEGER NOT NULL,
            provider_count INTEGER NOT NULL,
            risk_flag_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_runtime_monitor_validation_runs (
            run_id,
            run_at,
            runtime_status,
            job_total_count,
            job_active_count,
            job_failed_count,
            job_manual_required_count,
            queue_count,
            provider_count,
            risk_flag_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            str(payload["runtime_status"]),
            int(payload["job_total_count"]),
            int(payload["job_active_count"]),
            int(payload["job_failed_count"]),
            int(payload["job_manual_required_count"]),
            int(payload["queue_count"]),
            int(payload["provider_count"]),
            int(payload["risk_flag_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            runtime_status,
            job_total_count,
            job_active_count,
            job_failed_count,
            job_manual_required_count,
            queue_count,
            provider_count,
            risk_flag_count
        FROM batch_runtime_monitor_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "runtime_status": row[2],
        "job_total_count": row[3],
        "job_active_count": row[4],
        "job_failed_count": row[5],
        "job_manual_required_count": row[6],
        "queue_count": row[7],
        "provider_count": row[8],
        "risk_flag_count": row[9],
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_runtime_monitor_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_payload = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "queued"},
            {"job_id": f"{run_id}_002", "episode_code": "E01", "job_type": "video", "provider": "manual_web", "status": "running"},
            {"job_id": f"{run_id}_003", "episode_code": "E01", "job_type": "tts", "provider": "windows_tts", "status": "succeeded"},
            {"job_id": f"{run_id}_004", "episode_code": "E02", "job_type": "image", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_005", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
            {"job_id": f"{run_id}_006", "episode_code": "E03", "job_type": "image", "provider": "manual_web", "status": "pending"},
        ]
    }
    batch_json = {
        "batch": {
            "batch_id": "season1_batch_demo",
            "batch_type": "season_pipeline",
            "scope_type": "season",
            "scope_value": "S01",
            "target_steps": "build_season_jobs,scan_season_assets,build_provider_requests,render_season",
            "provider_filter": "manual_web,windows_tts",
            "status": "running",
            "summary_path": str(settings.reports_dir / "season1_batch_summary.json"),
        },
        "steps": [
            {"step_name": "build_season_jobs", "status": "completed"},
            {"step_name": "scan_season_assets", "status": "completed"},
            {"step_name": "build_provider_requests", "status": "running"},
            {"step_name": "render_season", "status": "planned"},
        ],
    }
    batch_report = {
        "batch_id": "season1_batch_demo",
        "scope_type": "season",
        "scope_value": "S01",
        "step_count": 4,
        "simulated_step_count": 4,
        "status": "running",
        "step_results": [
            {"batch_id": "season1_batch_demo", "step_name": "build_season_jobs", "status": "completed", "output_path": "reports/a.json", "message": "jobs built"},
            {"batch_id": "season1_batch_demo", "step_name": "scan_season_assets", "status": "completed", "output_path": "reports/b.json", "message": "assets scanned"},
            {"batch_id": "season1_batch_demo", "step_name": "build_provider_requests", "status": "running", "output_path": "reports/c.json", "message": "provider requests running"},
            {"batch_id": "season1_batch_demo", "step_name": "render_season", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }
    batch_summary = {
        "batch_id": "season1_batch_demo",
        "status": "running",
        "scope_type": "season",
        "scope_value": "S01",
        "step_count": 4,
        "completed_step_count": 2,
        "next_actions": ["retry failed jobs", "resolve manual required jobs"],
    }

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    batch_json_path = settings.reports_dir / "season1_batch.json"
    batch_report_path = settings.reports_dir / "season1_batch_report.json"
    batch_summary_path = settings.reports_dir / "season1_batch_summary.json"

    with (
        temporary_file_payload(jobs_path, jobs_payload),
        temporary_file_payload(batch_json_path, batch_json),
        temporary_file_payload(batch_report_path, batch_report),
        temporary_file_payload(batch_summary_path, batch_summary),
    ):
        payload = load_batches(settings)

    runtime_monitor = payload.get("runtime_monitor", {})
    queues = list(runtime_monitor.get("queues", []))
    providers = list(runtime_monitor.get("providers", []))
    episodes = list(runtime_monitor.get("episodes", []))
    active_jobs = list(runtime_monitor.get("active_jobs", []))
    risk_flags = list(runtime_monitor.get("risk_flags", []))

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "batch_count": int(payload.get("count", 0)),
        "runtime_status": str(runtime_monitor.get("status", "")),
        "job_total_count": int(runtime_monitor.get("job_total_count", 0)),
        "job_completed_count": int(runtime_monitor.get("job_completed_count", 0)),
        "job_active_count": int(runtime_monitor.get("job_active_count", 0)),
        "job_failed_count": int(runtime_monitor.get("job_failed_count", 0)),
        "job_manual_required_count": int(runtime_monitor.get("job_manual_required_count", 0)),
        "job_completion_rate": float(runtime_monitor.get("job_completion_rate", 0.0)),
        "queue_count": int(runtime_monitor.get("queue_count", 0)),
        "provider_count": int(runtime_monitor.get("provider_count", 0)),
        "episode_count": int(runtime_monitor.get("episode_count", 0)),
        "active_job_count": int(runtime_monitor.get("active_job_count", 0)),
        "risk_flag_count": int(runtime_monitor.get("risk_flag_count", 0)),
        "step_result_count": int(runtime_monitor.get("step_result_count", 0)),
        "first_queue_name": str((queues[0] if queues else {}).get("queue_name", "")),
        "first_provider_name": str((providers[0] if providers else {}).get("provider", "")),
        "first_episode_code": str((episodes[0] if episodes else {}).get("episode_code", "")),
        "first_active_job_status": str((active_jobs[0] if active_jobs else {}).get("status", "")),
        "risk_flag_levels": [str(item.get("level", "")) for item in risk_flags],
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_runtime_monitor_validation_report.json"),
        "database_row": {},
    }

    if report_payload["batch_count"] != 2:
        raise RuntimeError(f"batch_count mismatch: expected 2, got {report_payload['batch_count']}")
    if report_payload["runtime_status"] != "blocked":
        raise RuntimeError(f"runtime_status mismatch: expected blocked, got {report_payload['runtime_status']}")
    if report_payload["job_total_count"] != 6:
        raise RuntimeError(f"job_total_count mismatch: expected 6, got {report_payload['job_total_count']}")
    if report_payload["job_active_count"] != 3:
        raise RuntimeError(f"job_active_count mismatch: expected 3, got {report_payload['job_active_count']}")
    if report_payload["job_failed_count"] != 1:
        raise RuntimeError(f"job_failed_count mismatch: expected 1, got {report_payload['job_failed_count']}")
    if report_payload["job_manual_required_count"] != 1:
        raise RuntimeError(
            "job_manual_required_count mismatch: "
            f"expected 1, got {report_payload['job_manual_required_count']}"
        )
    if report_payload["queue_count"] != 2:
        raise RuntimeError(f"queue_count mismatch: expected 2, got {report_payload['queue_count']}")
    if report_payload["provider_count"] != 2:
        raise RuntimeError(f"provider_count mismatch: expected 2, got {report_payload['provider_count']}")
    if report_payload["episode_count"] != 3:
        raise RuntimeError(f"episode_count mismatch: expected 3, got {report_payload['episode_count']}")
    if report_payload["active_job_count"] != 5:
        raise RuntimeError(f"active_job_count mismatch: expected 5, got {report_payload['active_job_count']}")
    if report_payload["risk_flag_count"] < 2:
        raise RuntimeError(f"risk_flag_count mismatch: expected >=2, got {report_payload['risk_flag_count']}")
    if report_payload["step_result_count"] != 7:
        raise RuntimeError(f"step_result_count mismatch: expected 7, got {report_payload['step_result_count']}")

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_runtime_monitor_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
