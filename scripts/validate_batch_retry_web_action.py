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
from web.backend.services.report_service import generate_retry_batch_package
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
        CREATE TABLE IF NOT EXISTS batch_retry_web_action_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            preview_retried_count INTEGER NOT NULL,
            generate_retried_count INTEGER NOT NULL,
            preview_candidate_count INTEGER NOT NULL,
            generated_jobs_count INTEGER NOT NULL,
            report_exists INTEGER NOT NULL,
            jobs_output_exists INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_retry_web_action_validation_runs (
            run_id,
            run_at,
            preview_retried_count,
            generate_retried_count,
            preview_candidate_count,
            generated_jobs_count,
            report_exists,
            jobs_output_exists
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["preview_retried_count"]),
            int(payload["generate_retried_count"]),
            int(payload["preview_candidate_count"]),
            int(payload["generated_jobs_count"]),
            1 if payload["report_exists"] else 0,
            1 if payload["jobs_output_exists"] else 0,
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            preview_retried_count,
            generate_retried_count,
            preview_candidate_count,
            generated_jobs_count,
            report_exists,
            jobs_output_exists
        FROM batch_retry_web_action_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "preview_retried_count": row[2],
        "generate_retried_count": row[3],
        "preview_candidate_count": row[4],
        "generated_jobs_count": row[5],
        "report_exists": bool(row[6]),
        "jobs_output_exists": bool(row[7]),
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_retry_web_action_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    jobs_path = settings.jobs_dir / "episode_jobs.json"
    report_output_path = settings.reports_dir / "retry_batch_report.json"
    jobs_output_path = settings.jobs_dir / "episode_jobs_batch_retried.json"

    jobs_fixture = {
        "jobs": [
            {"job_id": f"{run_id}_001", "episode_code": "E01", "job_type": "image", "provider": "manual_web", "status": "failed"},
            {"job_id": f"{run_id}_002", "episode_code": "E01", "job_type": "tts", "provider": "windows_tts", "status": "manual_required"},
            {"job_id": f"{run_id}_003", "episode_code": "E01", "job_type": "video", "provider": "manual_web", "status": "running"},
            {"job_id": f"{run_id}_004", "episode_code": "E02", "job_type": "image", "provider": "manual_web", "status": "succeeded"},
        ]
    }

    with preserve_file(jobs_path), preserve_file(report_output_path), preserve_file(jobs_output_path):
        jobs_path.write_text(json.dumps(jobs_fixture, ensure_ascii=False, indent=2), encoding="utf-8")

        preview_result = generate_retry_batch_package(
            settings,
            statuses=["failed", "manual_required"],
            episode_code="E01",
            provider="",
            dry_run=True,
        )
        generate_result = generate_retry_batch_package(
            settings,
            statuses=["failed", "manual_required"],
            episode_code="E01",
            provider="",
            dry_run=False,
        )

        generated_report = json.loads(report_output_path.read_text(encoding="utf-8"))
        generated_jobs = json.loads(jobs_output_path.read_text(encoding="utf-8"))

        payload: dict[str, object] = {
            "run_id": run_id,
            "run_at": run_at,
            "preview_status": str(preview_result.get("status", "")),
            "generate_status": str(generate_result.get("status", "")),
            "preview_retried_count": int(preview_result.get("retried_count", 0)),
            "generate_retried_count": int(generate_result.get("retried_count", 0)),
            "preview_candidate_count": int(preview_result.get("retry_candidate_count", 0)),
            "generated_jobs_count": len(generated_jobs.get("jobs", [])),
            "report_exists": report_output_path.exists(),
            "jobs_output_exists": jobs_output_path.exists(),
            "report_retried_count": int(generated_report.get("retried_count", 0)),
            "report_scoped_job_count": int(generated_report.get("scoped_job_count", 0)),
            "database_path": str(ProjectPaths.default_database_path()),
            "report_path": str(PROJECT_ROOT / "reports" / "batch_retry_web_action_validation_report.json"),
            "database_row": {},
        }

        if payload["preview_status"] != "preview_ready":
            raise RuntimeError(f"preview_status mismatch: {payload['preview_status']}")
        if payload["generate_status"] != "generated":
            raise RuntimeError(f"generate_status mismatch: {payload['generate_status']}")
        if payload["preview_retried_count"] != 2 or payload["generate_retried_count"] != 2:
            raise RuntimeError(
                f"retried_count mismatch: preview={payload['preview_retried_count']}, generate={payload['generate_retried_count']}"
            )
        if payload["preview_candidate_count"] != 2:
            raise RuntimeError(f"preview_candidate_count mismatch: expected 2, got {payload['preview_candidate_count']}")
        if payload["generated_jobs_count"] != 4:
            raise RuntimeError(f"generated_jobs_count mismatch: expected 4, got {payload['generated_jobs_count']}")
        if not payload["report_exists"] or not payload["jobs_output_exists"]:
            raise RuntimeError("generated files mismatch: expected report and jobs output to exist")
        if payload["report_retried_count"] != 2 or payload["report_scoped_job_count"] != 3:
            raise RuntimeError(
                f"generated report mismatch: retried={payload['report_retried_count']}, scoped={payload['report_scoped_job_count']}"
            )

        connection = connect_auth_database(ProjectPaths.default_database_path())
        ensure_auth_schema(connection)
        ensure_validation_table(connection)
        insert_validation_run(connection, payload)
        payload["database_row"] = collect_validation_row(connection, run_id)
        connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_retry_web_action_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
