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
from web.backend.services.batch_history_service import ensure_batch_execution_queue_schema
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
        CREATE TABLE IF NOT EXISTS batch_execution_archive_management_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            export_json_count INTEGER NOT NULL,
            export_csv_count INTEGER NOT NULL,
            archive_count INTEGER NOT NULL,
            archived_file_count INTEGER NOT NULL,
            listed_archive_count INTEGER NOT NULL,
            cleanup_eligible_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_execution_archive_management_validation_runs (
            run_id,
            run_at,
            export_json_count,
            export_csv_count,
            archive_count,
            archived_file_count,
            listed_archive_count,
            cleanup_eligible_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["export_json_count"]),
            int(payload["export_csv_count"]),
            int(payload["archive_count"]),
            int(payload["archived_file_count"]),
            int(payload["listed_archive_count"]),
            int(payload["cleanup_eligible_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            export_json_count,
            export_csv_count,
            archive_count,
            archived_file_count,
            listed_archive_count,
            cleanup_eligible_count
        FROM batch_execution_archive_management_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "export_json_count": row[2],
        "export_csv_count": row[3],
        "archive_count": row[4],
        "archived_file_count": row[5],
        "listed_archive_count": row[6],
        "cleanup_eligible_count": row[7],
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_execution_archive_management_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    retry_report_path = settings.reports_dir / "retry_batch_report.json"
    season1_batch_path = settings.reports_dir / "season1_execution_archive_batch.json"
    season1_summary_path = settings.reports_dir / "season1_execution_archive_batch_summary.json"
    season1_report_path = settings.reports_dir / "season1_execution_archive_batch_report.json"

    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_002", "episode_code": "E01", "job_type": "video", "provider": "manual_web", "status": "queued"},
            {"job_id": f"{run_id}_003", "episode_code": "E02", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
        ]
    }
    retry_report = {
        "scoped_job_count": 2,
        "retried_count": 1,
        "untouched_count": 2,
        "episode_code": "",
        "provider": "",
        "retryable_statuses": ["failed", "manual_required"],
        "retried_job_ids": [f"{run_id}_001"],
    }
    season1_batch = {"batch_id": "season1_execution_archive_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4}
    season1_summary = {"batch_id": "season1_execution_archive_validation", "status": "failed", "scope_type": "season", "scope_value": "S01", "step_count": 4, "completed_step_count": 1}
    season1_report = {
        "batch_id": "season1_execution_archive_validation",
        "step_count": 4,
        "step_results": [
            {"batch_id": "season1_execution_archive_validation", "step_name": "build_jobs", "status": "completed", "output_path": "reports/ear1_1.json", "message": "ok"},
            {"batch_id": "season1_execution_archive_validation", "step_name": "scan_assets", "status": "failed", "output_path": "reports/ear1_2.json", "message": "failed"},
            {"batch_id": "season1_execution_archive_validation", "step_name": "render", "status": "planned", "output_path": "", "message": "waiting"},
        ],
    }

    with (
        preserve_file(jobs_path),
        preserve_file(retry_report_path),
        preserve_file(season1_batch_path),
        preserve_file(season1_summary_path),
        preserve_file(season1_report_path),
    ):
        write_json(jobs_path, jobs_fixture)
        write_json(retry_report_path, retry_report)
        write_json(season1_batch_path, season1_batch)
        write_json(season1_summary_path, season1_summary)
        write_json(season1_report_path, season1_report)

        connection = connect_auth_database(ProjectPaths.default_database_path())
        ensure_auth_schema(connection)
        ensure_batch_execution_queue_schema(connection)
        connection.close()

        client = TestClient(app)
        auth_headers = build_validation_auth_headers(f"{run_id}_admin")
        export_json = client.post(
            "/api/batches/execution-operations/export",
            json={"export_format": "json", "export_scope": "operations_report"},
            headers=auth_headers,
        )
        export_csv = client.post(
            "/api/batches/execution-operations/export",
            json={"export_format": "csv", "export_scope": "operations_report"},
            headers=auth_headers,
        )
        archive_export = client.post(
            "/api/batches/execution-operations/export",
            json={"export_format": "json", "export_scope": "report_archive"},
            headers=auth_headers,
        )
        archive_list = client.get("/api/batches/execution-archives?limit=20", headers=auth_headers)
        archive_cleanup = client.post(
            "/api/batches/execution-archives/cleanup",
            json={"retention_days": 30, "dry_run": True},
            headers=auth_headers,
        )

    if export_json.status_code != 200:
        raise RuntimeError(f"export_json failed: {export_json.status_code} {export_json.text}")
    if export_csv.status_code != 200:
        raise RuntimeError(f"export_csv failed: {export_csv.status_code} {export_csv.text}")
    if archive_export.status_code != 200:
        raise RuntimeError(f"archive_export failed: {archive_export.status_code} {archive_export.text}")
    if archive_list.status_code != 200:
        raise RuntimeError(f"archive_list failed: {archive_list.status_code} {archive_list.text}")
    if archive_cleanup.status_code != 200:
        raise RuntimeError(f"archive_cleanup failed: {archive_cleanup.status_code} {archive_cleanup.text}")

    export_json_payload = export_json.json()
    export_csv_payload = export_csv.json()
    archive_export_payload = archive_export.json()
    archive_list_payload = archive_list.json()
    archive_cleanup_payload = archive_cleanup.json()

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "export_json_count": int(export_json_payload.get("export_count", 0)),
        "export_csv_count": int(export_csv_payload.get("export_count", 0)),
        "archive_count": 1,
        "archived_file_count": int(archive_export_payload.get("archived_file_count", 0)),
        "listed_archive_count": int(archive_list_payload.get("archive_count", 0)),
        "cleanup_eligible_count": int(archive_cleanup_payload.get("eligible_count", 0)),
        "archive_path": str(archive_export_payload.get("archive_path", "")),
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_execution_archive_management_validation_report.json"),
        "database_row": {},
    }

    if report_payload["export_json_count"] < 1 or report_payload["export_csv_count"] < 1:
        raise RuntimeError(
            f"export_count mismatch: json={report_payload['export_json_count']}, csv={report_payload['export_csv_count']}"
        )
    if report_payload["archived_file_count"] < 2:
        raise RuntimeError(f"archived_file_count mismatch: got {report_payload['archived_file_count']}")
    if report_payload["listed_archive_count"] < 1:
        raise RuntimeError(f"listed_archive_count mismatch: got {report_payload['listed_archive_count']}")
    if not report_payload["archive_path"]:
        raise RuntimeError("archive_path mismatch: empty")

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, report_payload)
    report_payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_execution_archive_management_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
