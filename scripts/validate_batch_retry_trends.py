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
        CREATE TABLE IF NOT EXISTS batch_retry_trends_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            retry_trend_count INTEGER NOT NULL,
            latest_retry_count INTEGER NOT NULL,
            latest_generated_count INTEGER NOT NULL,
            latest_operator_count INTEGER NOT NULL,
            latest_queue_impact_count INTEGER NOT NULL,
            latest_episode_impact_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_retry_trends_validation_runs (
            run_id,
            run_at,
            retry_trend_count,
            latest_retry_count,
            latest_generated_count,
            latest_operator_count,
            latest_queue_impact_count,
            latest_episode_impact_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["retry_trend_count"]),
            int(payload["latest_retry_count"]),
            int(payload["latest_generated_count"]),
            int(payload["latest_operator_count"]),
            int(payload["latest_queue_impact_count"]),
            int(payload["latest_episode_impact_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            retry_trend_count,
            latest_retry_count,
            latest_generated_count,
            latest_operator_count,
            latest_queue_impact_count,
            latest_episode_impact_count
        FROM batch_retry_trends_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "retry_trend_count": row[2],
        "latest_retry_count": row[3],
        "latest_generated_count": row[4],
        "latest_operator_count": row[5],
        "latest_queue_impact_count": row[6],
        "latest_episode_impact_count": row[7],
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
    run_id = f"batch_retry_trends_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    retry_report_path = settings.reports_dir / "retry_batch_report.json"
    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_002", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
            {"job_id": f"{run_id}_003", "episode_code": "E03", "job_type": "video", "provider": "manual_web", "status": "queued"},
        ]
    }
    retry_report = {
        "scoped_job_count": 2,
        "retried_count": 2,
        "untouched_count": 1,
        "episode_code": "",
        "provider": "",
        "retryable_statuses": ["failed", "manual_required"],
        "retried_job_ids": [f"{run_id}_001", f"{run_id}_002"],
    }

    with preserve_file(jobs_path), preserve_file(retry_report_path):
        jobs_path.write_text(json.dumps(jobs_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        retry_report_path.write_text(json.dumps(retry_report, ensure_ascii=False, indent=2), encoding="utf-8")

        connection = connect_auth_database(ProjectPaths.default_database_path())
        ensure_auth_schema(connection)
        connection.execute(
            """
            DELETE FROM audit_logs
            WHERE action_type = 'batch_retry_generate'
              AND (created_at LIKE '2099-12-30%' OR created_at LIKE '2099-12-29%')
            """
        )
        connection.commit()
        write_audit_log_with_time(
            connection,
            f"{run_id}_operator_a",
            f"{retry_report_path}#1",
            "dry_run=true; statuses=failed,manual_required; episode_code=E01; provider=manual_web; retried_count=1",
            "2099-12-30T09:00:00+08:00",
        )
        write_audit_log_with_time(
            connection,
            f"{run_id}_operator_b",
            f"{retry_report_path}#2",
            "dry_run=false; statuses=failed,manual_required; episode_code=E02; provider=windows_tts; retried_count=2",
            "2099-12-30T10:00:00+08:00",
        )
        write_audit_log_with_time(
            connection,
            f"{run_id}_operator_a",
            f"{retry_report_path}#3",
            "dry_run=false; statuses=failed; episode_code=E03; provider=manual_web; retried_count=1",
            "2099-12-29T11:00:00+08:00",
        )
        connection.close()

        payload = load_batches(settings)

    runtime_monitor = payload.get("runtime_monitor", {})
    retry_trends = list(runtime_monitor.get("retry_trends", []))
    latest_trend = retry_trends[0] if retry_trends else {}
    previous_trend = retry_trends[1] if len(retry_trends) > 1 else {}

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "retry_trend_count": int(runtime_monitor.get("retry_trend_count", 0)),
        "latest_period": str(latest_trend.get("period", "")),
        "latest_retry_count": int(latest_trend.get("retry_count", 0)),
        "latest_dry_run_count": int(latest_trend.get("dry_run_count", 0)),
        "latest_generated_count": int(latest_trend.get("generated_count", 0)),
        "latest_success_count": int(latest_trend.get("success_count", 0)),
        "latest_operator_count": int(latest_trend.get("unique_operator_count", 0)),
        "latest_queue_impact_count": int(latest_trend.get("queue_impact_count", 0)),
        "latest_episode_impact_count": int(latest_trend.get("episode_impact_count", 0)),
        "latest_retry_bar_width": float(latest_trend.get("retry_bar_width", 0.0)),
        "latest_impact_bar_width": float(latest_trend.get("impact_bar_width", 0.0)),
        "previous_period": str(previous_trend.get("period", "")),
        "previous_retry_count": int(previous_trend.get("retry_count", 0)),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_retry_trends_validation_report.json"),
        "database_row": {},
    }

    if report_payload["retry_trend_count"] < 2:
        raise RuntimeError(f"retry_trend_count mismatch: expected >=2, got {report_payload['retry_trend_count']}")
    if report_payload["latest_period"] != "2099-12-30":
        raise RuntimeError(f"latest_period mismatch: expected 2099-12-30, got {report_payload['latest_period']}")
    if report_payload["latest_retry_count"] != 3:
        raise RuntimeError(f"latest_retry_count mismatch: expected 3, got {report_payload['latest_retry_count']}")
    if report_payload["latest_dry_run_count"] != 1 or report_payload["latest_generated_count"] != 1:
        raise RuntimeError(
            "latest run mode mismatch: "
            f"dry_run={report_payload['latest_dry_run_count']}, generated={report_payload['latest_generated_count']}"
        )
    if report_payload["latest_success_count"] != 2:
        raise RuntimeError(f"latest_success_count mismatch: expected 2, got {report_payload['latest_success_count']}")
    if report_payload["latest_operator_count"] != 2:
        raise RuntimeError(f"latest_operator_count mismatch: expected 2, got {report_payload['latest_operator_count']}")
    if report_payload["latest_queue_impact_count"] != 2:
        raise RuntimeError(
            f"latest_queue_impact_count mismatch: expected 2, got {report_payload['latest_queue_impact_count']}"
        )
    if report_payload["latest_episode_impact_count"] != 2:
        raise RuntimeError(
            f"latest_episode_impact_count mismatch: expected 2, got {report_payload['latest_episode_impact_count']}"
        )
    if report_payload["latest_retry_bar_width"] <= 0:
        raise RuntimeError(
            f"latest_retry_bar_width mismatch: expected >0, got {report_payload['latest_retry_bar_width']}"
        )
    if report_payload["previous_period"] != "2099-12-29" or report_payload["previous_retry_count"] != 1:
        raise RuntimeError(
            f"previous trend mismatch: period={report_payload['previous_period']}, retry={report_payload['previous_retry_count']}"
        )

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_retry_trends_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
