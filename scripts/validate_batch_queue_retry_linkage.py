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
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, write_audit_log
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
        CREATE TABLE IF NOT EXISTS batch_queue_retry_linkage_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            queue_trend_count INTEGER NOT NULL,
            retry_history_count INTEGER NOT NULL,
            retry_retried_count INTEGER NOT NULL,
            queue_distribution_count INTEGER NOT NULL,
            provider_distribution_count INTEGER NOT NULL,
            episode_distribution_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_queue_retry_linkage_validation_runs (
            run_id,
            run_at,
            queue_trend_count,
            retry_history_count,
            retry_retried_count,
            queue_distribution_count,
            provider_distribution_count,
            episode_distribution_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["queue_trend_count"]),
            int(payload["retry_history_count"]),
            int(payload["retry_retried_count"]),
            int(payload["queue_distribution_count"]),
            int(payload["provider_distribution_count"]),
            int(payload["episode_distribution_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            queue_trend_count,
            retry_history_count,
            retry_retried_count,
            queue_distribution_count,
            provider_distribution_count,
            episode_distribution_count
        FROM batch_queue_retry_linkage_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "queue_trend_count": row[2],
        "retry_history_count": row[3],
        "retry_retried_count": row[4],
        "queue_distribution_count": row[5],
        "provider_distribution_count": row[6],
        "episode_distribution_count": row[7],
    }


def write_audit_log_with_time(
    connection: sqlite3.Connection,
    user_id: str,
    target_id: str,
    detail: str,
    created_at: str,
) -> None:
    write_audit_log(
        connection,
        user_id,
        "batch_retry_generate",
        "batch",
        target_id,
        "success",
        detail,
    )
    connection.execute(
        """
        UPDATE audit_logs
        SET created_at = ?
        WHERE user_id = ? AND action_type = 'batch_retry_generate' AND target_id = ?
        """,
        (created_at, user_id, target_id),
    )
    connection.commit()


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_queue_retry_linkage_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    retry_report_path = settings.reports_dir / "retry_batch_report.json"

    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "queued"},
            {"job_id": f"{run_id}_002", "episode_code": "E01", "job_type": "video", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_003", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
            {"job_id": f"{run_id}_004", "episode_code": "E02", "job_type": "image", "provider": "manual_web", "status": "succeeded"},
        ]
    }
    retry_report = {
        "scoped_job_count": 3,
        "retried_count": 2,
        "untouched_count": 2,
        "episode_code": "",
        "provider": "",
        "retryable_statuses": ["failed", "manual_required"],
        "retried_job_ids": [f"{run_id}_002", f"{run_id}_003"],
    }

    with preserve_file(jobs_path), preserve_file(retry_report_path):
        jobs_path.write_text(json.dumps(jobs_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        retry_report_path.write_text(json.dumps(retry_report, ensure_ascii=False, indent=2), encoding="utf-8")

        connection = connect_auth_database(ProjectPaths.default_database_path())
        ensure_auth_schema(connection)
        base_time = datetime.now().astimezone().replace(microsecond=0)
        write_audit_log_with_time(
            connection,
            "user_retry_preview",
            str(retry_report_path),
            "dry_run=true; statuses=failed,manual_required; episode_code=E01; provider=manual_web; retried_count=1",
            (base_time).isoformat(),
        )
        write_audit_log_with_time(
            connection,
            "user_retry_generate",
            str(retry_report_path),
            "dry_run=false; statuses=failed,manual_required; episode_code=; provider=; retried_count=2",
            (base_time).isoformat(),
        )
        connection.close()

        payload = load_batches(settings)

    runtime_monitor = payload.get("runtime_monitor", {})
    retry_summary = runtime_monitor.get("retry_summary", {})
    queue_trends = list(runtime_monitor.get("queue_trends", []))
    retry_history = list(runtime_monitor.get("retry_history", []))

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "queue_trend_count": int(runtime_monitor.get("queue_trend_count", 0)),
        "retry_history_count": int(runtime_monitor.get("retry_history_count", 0)),
        "retry_retried_count": int(retry_summary.get("retried_count", 0)),
        "queue_distribution_count": len(retry_summary.get("queue_distribution", {})),
        "provider_distribution_count": len(retry_summary.get("provider_distribution", {})),
        "episode_distribution_count": len(retry_summary.get("episode_distribution", {})),
        "first_queue_retried_count": int((queue_trends[0] if queue_trends else {}).get("retried_count", 0)),
        "latest_retry_dry_run": bool((retry_history[0] if retry_history else {}).get("dry_run", False)),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_queue_retry_linkage_validation_report.json"),
        "database_row": {},
    }

    if report_payload["queue_trend_count"] != 2:
        raise RuntimeError(f"queue_trend_count mismatch: expected 2, got {report_payload['queue_trend_count']}")
    if report_payload["retry_history_count"] < 2:
        raise RuntimeError(f"retry_history_count mismatch: expected >=2, got {report_payload['retry_history_count']}")
    if report_payload["retry_retried_count"] != 2:
        raise RuntimeError(f"retry_retried_count mismatch: expected 2, got {report_payload['retry_retried_count']}")
    if report_payload["queue_distribution_count"] != 2:
        raise RuntimeError(f"queue_distribution_count mismatch: expected 2, got {report_payload['queue_distribution_count']}")
    if report_payload["provider_distribution_count"] != 2:
        raise RuntimeError(f"provider_distribution_count mismatch: expected 2, got {report_payload['provider_distribution_count']}")
    if report_payload["episode_distribution_count"] != 2:
        raise RuntimeError(f"episode_distribution_count mismatch: expected 2, got {report_payload['episode_distribution_count']}")
    if report_payload["first_queue_retried_count"] < 1:
        raise RuntimeError(f"first_queue_retried_count mismatch: expected >=1, got {report_payload['first_queue_retried_count']}")

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_queue_retry_linkage_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
