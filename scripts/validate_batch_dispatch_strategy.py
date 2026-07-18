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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_dispatch_strategy_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            auto_disposition_template_count INTEGER NOT NULL,
            dispatch_priority_count INTEGER NOT NULL,
            top_dispatch_score INTEGER NOT NULL,
            p0_template_count INTEGER NOT NULL,
            p0_dispatch_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_dispatch_strategy_validation_runs (
            run_id,
            run_at,
            auto_disposition_template_count,
            dispatch_priority_count,
            top_dispatch_score,
            p0_template_count,
            p0_dispatch_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["auto_disposition_template_count"]),
            int(payload["dispatch_priority_count"]),
            int(payload["top_dispatch_score"]),
            int(payload["p0_template_count"]),
            int(payload["p0_dispatch_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            auto_disposition_template_count,
            dispatch_priority_count,
            top_dispatch_score,
            p0_template_count,
            p0_dispatch_count
        FROM batch_dispatch_strategy_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "auto_disposition_template_count": row[2],
        "dispatch_priority_count": row[3],
        "top_dispatch_score": row[4],
        "p0_template_count": row[5],
        "p0_dispatch_count": row[6],
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
    run_id = f"batch_dispatch_strategy_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    retry_report_path = settings.reports_dir / "retry_batch_report.json"
    season1_batch_path = settings.reports_dir / "season1_batch.json"
    season1_summary_path = settings.reports_dir / "season1_batch_summary.json"
    season1_report_path = settings.reports_dir / "season1_batch_report.json"
    season2_batch_path = settings.reports_dir / "season2_batch.json"
    season2_summary_path = settings.reports_dir / "season2_batch_summary.json"
    season2_report_path = settings.reports_dir / "season2_batch_report.json"

    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_002", "episode_code": "E01", "job_type": "video", "provider": "manual_web", "status": "queued"},
            {"job_id": f"{run_id}_003", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
            {"job_id": f"{run_id}_004", "episode_code": "E03", "job_type": "tts", "provider": "windows_tts", "status": "succeeded"},
        ]
    }
    retry_report = {
        "scoped_job_count": 3,
        "retried_count": 2,
        "untouched_count": 2,
        "episode_code": "",
        "provider": "",
        "retryable_statuses": ["failed", "manual_required"],
        "retried_job_ids": [f"{run_id}_001", f"{run_id}_003"],
    }
    season1_batch = {"batch_id": "season1_dispatch_strategy_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4}
    season1_summary = {"batch_id": "season1_dispatch_strategy_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4, "completed_step_count": 1}
    season1_report = {
        "batch_id": "season1_dispatch_strategy_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season1_dispatch_strategy_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/ds1_1.json", "message": "ok"},
            {"batch_id": "season1_dispatch_strategy_validation", "step_name": "scan_assets", "status": "failed", "output_path": "reports/ds1_2.json", "message": "failed"},
            {"batch_id": "season1_dispatch_strategy_validation", "step_name": "build_provider_requests", "status": "blocked", "output_path": "", "message": "blocked"},
            {"batch_id": "season1_dispatch_strategy_validation", "step_name": "render", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }
    season2_batch = {"batch_id": "season2_dispatch_strategy_validation", "status": "running", "scope_type": "episode", "scope_value": "E02", "step_count": 3}
    season2_summary = {"batch_id": "season2_dispatch_strategy_validation", "status": "running", "scope_type": "episode", "scope_value": "E02", "step_count": 3, "completed_step_count": 2}
    season2_report = {
        "batch_id": "season2_dispatch_strategy_validation",
        "step_count": 3,
        "step_results": [
            {"batch_id": "season2_dispatch_strategy_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/ds2_1.json", "message": "ok"},
            {"batch_id": "season2_dispatch_strategy_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/ds2_2.json", "message": "ok"},
            {"batch_id": "season2_dispatch_strategy_validation", "step_name": "render", "status": "running", "output_path": "reports/ds2_3.json", "message": "running"},
        ],
    }

    with (
        preserve_file(jobs_path),
        preserve_file(retry_report_path),
        preserve_file(season1_batch_path),
        preserve_file(season1_summary_path),
        preserve_file(season1_report_path),
        preserve_file(season2_batch_path),
        preserve_file(season2_summary_path),
        preserve_file(season2_report_path),
    ):
        write_json(jobs_path, jobs_fixture)
        write_json(retry_report_path, retry_report)
        write_json(season1_batch_path, season1_batch)
        write_json(season1_summary_path, season1_summary)
        write_json(season1_report_path, season1_report)
        write_json(season2_batch_path, season2_batch)
        write_json(season2_summary_path, season2_summary)
        write_json(season2_report_path, season2_report)

        connection = connect_auth_database(ProjectPaths.default_database_path())
        ensure_auth_schema(connection)
        connection.execute(
            """
            DELETE FROM audit_logs
            WHERE action_type = 'batch_retry_generate'
              AND (created_at LIKE '2099-12-27%' OR created_at LIKE '2099-12-28%' OR created_at LIKE '2099-12-29%' OR created_at LIKE '2099-12-30%')
            """
        )
        connection.commit()
        write_audit_log_with_time(
            connection,
            f"{run_id}_operator_a",
            f"{retry_report_path}#1",
            "dry_run=false; statuses=failed; episode_code=E01; provider=manual_web; retried_count=2",
            "2099-12-27T09:00:00+08:00",
        )
        write_audit_log_with_time(
            connection,
            f"{run_id}_operator_b",
            f"{retry_report_path}#2",
            "dry_run=true; statuses=manual_required; episode_code=E02; provider=windows_tts; retried_count=1",
            "2099-12-27T10:00:00+08:00",
        )
        connection.close()

        payload = load_batches(settings)

    multi_batch_summary = payload.get("multi_batch_summary", {})
    auto_disposition_templates = list(multi_batch_summary.get("auto_disposition_templates", []))
    dispatch_priority_plan = list(multi_batch_summary.get("dispatch_priority_plan", []))
    top_dispatch = dispatch_priority_plan[0] if dispatch_priority_plan else {}

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "auto_disposition_template_count": int(multi_batch_summary.get("auto_disposition_template_count", 0)),
        "dispatch_priority_count": int(multi_batch_summary.get("dispatch_priority_count", 0)),
        "top_dispatch_target": str(top_dispatch.get("target", "")),
        "top_dispatch_priority": str(top_dispatch.get("recommended_priority", "")),
        "top_dispatch_score": int(top_dispatch.get("dispatch_score", 0)),
        "p0_template_count": len([item for item in auto_disposition_templates if str(item.get("priority", "")) == "P0"]),
        "p0_dispatch_count": len([item for item in dispatch_priority_plan if str(item.get("recommended_priority", "")) == "P0"]),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_dispatch_strategy_validation_report.json"),
        "database_row": {},
    }

    if report_payload["auto_disposition_template_count"] < 3:
        raise RuntimeError(
            f"auto_disposition_template_count mismatch: expected >=3, got {report_payload['auto_disposition_template_count']}"
        )
    if report_payload["dispatch_priority_count"] < 4:
        raise RuntimeError(
            f"dispatch_priority_count mismatch: expected >=4, got {report_payload['dispatch_priority_count']}"
        )
    if report_payload["top_dispatch_target"] not in {"provider:manual_web", "queue:web_tasks"}:
        raise RuntimeError(f"top_dispatch_target mismatch: got {report_payload['top_dispatch_target']}")
    if report_payload["top_dispatch_priority"] != "P0":
        raise RuntimeError(f"top_dispatch_priority mismatch: expected P0, got {report_payload['top_dispatch_priority']}")
    if report_payload["top_dispatch_score"] < 19:
        raise RuntimeError(
            f"top_dispatch_score mismatch: expected >=19, got {report_payload['top_dispatch_score']}"
        )
    if report_payload["p0_template_count"] < 1 or report_payload["p0_dispatch_count"] < 1:
        raise RuntimeError(
            f"priority mismatch: template_p0={report_payload['p0_template_count']}, dispatch_p0={report_payload['p0_dispatch_count']}"
        )

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_dispatch_strategy_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
