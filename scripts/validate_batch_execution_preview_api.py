from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from web.backend.app import app
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.batch_history_service import ensure_batch_execution_preview_schema
from web.backend.services.report_service import load_batches
from web.backend.settings import load_web_settings
from validation_auth import build_validation_auth_headers


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
        CREATE TABLE IF NOT EXISTS batch_execution_preview_api_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            preview_call_count INTEGER NOT NULL,
            execution_preview_history_count INTEGER NOT NULL,
            audit_log_count INTEGER NOT NULL,
            latest_preview_priority TEXT NOT NULL,
            latest_preview_status TEXT NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_execution_preview_api_validation_runs (
            run_id,
            run_at,
            preview_call_count,
            execution_preview_history_count,
            audit_log_count,
            latest_preview_priority,
            latest_preview_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["preview_call_count"]),
            int(payload["execution_preview_history_count"]),
            int(payload["audit_log_count"]),
            str(payload["latest_preview_priority"]),
            str(payload["latest_preview_status"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            preview_call_count,
            execution_preview_history_count,
            audit_log_count,
            latest_preview_priority,
            latest_preview_status
        FROM batch_execution_preview_api_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "preview_call_count": row[2],
        "execution_preview_history_count": row[3],
        "audit_log_count": row[4],
        "latest_preview_priority": row[5],
        "latest_preview_status": row[6],
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_execution_preview_api_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    retry_report_path = settings.reports_dir / "retry_batch_report.json"
    season1_batch_path = settings.reports_dir / "season1_execution_preview_api_batch.json"
    season1_summary_path = settings.reports_dir / "season1_execution_preview_api_batch_summary.json"
    season1_report_path = settings.reports_dir / "season1_execution_preview_api_batch_report.json"
    season2_batch_path = settings.reports_dir / "season2_execution_preview_api_batch.json"
    season2_summary_path = settings.reports_dir / "season2_execution_preview_api_batch_summary.json"
    season2_report_path = settings.reports_dir / "season2_execution_preview_api_batch_report.json"

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
    season1_batch = {"batch_id": "season1_execution_preview_api_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4}
    season1_summary = {"batch_id": "season1_execution_preview_api_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4, "completed_step_count": 1}
    season1_report = {
        "batch_id": "season1_execution_preview_api_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season1_execution_preview_api_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/eap1_1.json", "message": "ok"},
            {"batch_id": "season1_execution_preview_api_validation", "step_name": "scan_assets", "status": "failed", "output_path": "reports/eap1_2.json", "message": "failed"},
            {"batch_id": "season1_execution_preview_api_validation", "step_name": "build_provider_requests", "status": "blocked", "output_path": "", "message": "blocked"},
            {"batch_id": "season1_execution_preview_api_validation", "step_name": "render", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }
    season2_batch = {"batch_id": "season2_execution_preview_api_validation", "status": "running", "scope_type": "episode", "scope_value": "E02", "step_count": 3}
    season2_summary = {"batch_id": "season2_execution_preview_api_validation", "status": "running", "scope_type": "episode", "scope_value": "E02", "step_count": 3, "completed_step_count": 2}
    season2_report = {
        "batch_id": "season2_execution_preview_api_validation",
        "step_count": 3,
        "step_results": [
            {"batch_id": "season2_execution_preview_api_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/eap2_1.json", "message": "ok"},
            {"batch_id": "season2_execution_preview_api_validation", "step_name": "scan_assets", "status": "completed", "output_path": "reports/eap2_2.json", "message": "ok"},
            {"batch_id": "season2_execution_preview_api_validation", "step_name": "render", "status": "running", "output_path": "reports/eap2_3.json", "message": "running"},
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
        ensure_batch_execution_preview_schema(connection)
        connection.close()

        client = TestClient(app)
        auth_headers = build_validation_auth_headers(f"{run_id}_admin")
        initial_batches = load_batches(settings)
        execution_plan_templates = list(initial_batches.get("multi_batch_summary", {}).get("execution_plan_templates", []))
        selected_failure_plan = next(
            (
                item for item in execution_plan_templates
                if str(item.get("target", "")) == "season1_execution_preview_api_validation"
            ),
            execution_plan_templates[0] if execution_plan_templates else None,
        )
        selected_dispatch_plan = next(
            (
                item for item in execution_plan_templates
                if str(item.get("target", "")) == "provider:manual_web"
            ),
            execution_plan_templates[1] if len(execution_plan_templates) > 1 else selected_failure_plan,
        )
        if selected_failure_plan is None or selected_dispatch_plan is None:
            raise RuntimeError("execution_plan_templates mismatch: expected at least 2 execution plans")
        response_a = client.post(
            "/api/batches/execution-plans/preview",
            json={
                "plan_key": str(selected_failure_plan.get("plan_key", "")),
                "target": str(selected_failure_plan.get("target", "")),
                "mode": "dry_run",
            },
            headers=auth_headers,
        )
        response_b = client.post(
            "/api/batches/execution-plans/preview",
            json={
                "plan_key": str(selected_dispatch_plan.get("plan_key", "")),
                "target": str(selected_dispatch_plan.get("target", "")),
                "mode": "dry_run",
            },
            headers=auth_headers,
        )
        if response_a.status_code != 200:
            raise RuntimeError(f"preview response_a failed: {response_a.status_code} {response_a.text}")
        if response_b.status_code != 200:
            raise RuntimeError(f"preview response_b failed: {response_b.status_code} {response_b.text}")

        payload_a = response_a.json()
        payload_b = response_b.json()
        batches_payload = load_batches(settings)

    execution_preview_history = list(batches_payload.get("multi_batch_summary", {}).get("execution_preview_history", []))
    preview_run_ids = [str(payload_a.get("preview_run_id", "")), str(payload_b.get("preview_run_id", ""))]

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_preview_schema(connection)
    audit_log_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM audit_logs
        WHERE action_type = 'batch_execution_plan_preview'
          AND target_id IN (?, ?)
        """,
        (preview_run_ids[0], preview_run_ids[1]),
    ).fetchone()[0]

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "preview_call_count": 2,
        "execution_preview_history_count": int(batches_payload.get("multi_batch_summary", {}).get("execution_preview_history_count", 0)),
        "preview_run_ids": preview_run_ids,
        "audit_log_count": int(audit_log_count),
        "latest_preview_plan_key": str((execution_preview_history[0] if execution_preview_history else {}).get("plan_key", "")),
        "latest_preview_priority": str((execution_preview_history[0] if execution_preview_history else {}).get("priority", "")),
        "latest_preview_status": str((execution_preview_history[0] if execution_preview_history else {}).get("status", "")),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_execution_preview_api_validation_report.json"),
        "database_row": {},
    }

    if payload_a.get("status") != "preview_ready" or payload_b.get("status") != "preview_ready":
        raise RuntimeError("preview status mismatch")
    if report_payload["execution_preview_history_count"] < 2:
        raise RuntimeError(
            "execution_preview_history_count mismatch: "
            f"expected >=2, got {report_payload['execution_preview_history_count']}"
        )
    if report_payload["audit_log_count"] != 2:
        raise RuntimeError(f"audit_log_count mismatch: expected 2, got {report_payload['audit_log_count']}")
    if not all(preview_run_ids):
        raise RuntimeError(f"preview_run_ids mismatch: {preview_run_ids}")
    if report_payload["latest_preview_status"] != "preview_ready":
        raise RuntimeError(
            f"latest_preview_status mismatch: expected preview_ready, got {report_payload['latest_preview_status']}"
        )

    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_execution_preview_api_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
