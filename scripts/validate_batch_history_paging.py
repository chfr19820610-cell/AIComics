from __future__ import annotations

import json
import sqlite3
import sys
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
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, upsert_user, write_audit_log
from web.backend.services.batch_history_service import (
    ensure_batch_execution_preview_schema,
    ensure_batch_execution_queue_schema,
    update_batch_execution_queue_status_record,
    write_batch_execution_preview_run,
    write_batch_execution_queue_run,
)
from web.backend.services.report_service import load_batches
from web.backend.settings import load_web_settings
from validation_auth import build_validation_auth_headers


def ensure_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_history_paging_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            retry_total_count INTEGER NOT NULL,
            retry_page_count INTEGER NOT NULL,
            preview_total_count INTEGER NOT NULL,
            preview_page_count INTEGER NOT NULL,
            queue_total_count INTEGER NOT NULL,
            queue_page_count INTEGER NOT NULL,
            summary_retry_count INTEGER NOT NULL,
            summary_preview_count INTEGER NOT NULL,
            summary_queue_count INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO batch_history_paging_validation_runs (
            run_id,
            run_at,
            retry_total_count,
            retry_page_count,
            preview_total_count,
            preview_page_count,
            queue_total_count,
            queue_page_count,
            summary_retry_count,
            summary_preview_count,
            summary_queue_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            int(payload["retry_total_count"]),
            int(payload["retry_page_count"]),
            int(payload["preview_total_count"]),
            int(payload["preview_page_count"]),
            int(payload["queue_total_count"]),
            int(payload["queue_page_count"]),
            int(payload["summary_retry_count"]),
            int(payload["summary_preview_count"]),
            int(payload["summary_queue_count"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            retry_total_count,
            retry_page_count,
            preview_total_count,
            preview_page_count,
            queue_total_count,
            queue_page_count,
            summary_retry_count,
            summary_preview_count,
            summary_queue_count
        FROM batch_history_paging_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "retry_total_count": row[2],
        "retry_page_count": row[3],
        "preview_total_count": row[4],
        "preview_page_count": row[5],
        "queue_total_count": row[6],
        "queue_page_count": row[7],
        "summary_retry_count": row[8],
        "summary_preview_count": row[9],
        "summary_queue_count": row[10],
    }


def build_preview_plan(run_id: str, index: int) -> dict[str, object]:
    priority = "P0" if index % 4 == 0 else "P1" if index % 3 == 0 else "P2"
    return {
        "plan_key": f"{run_id}_preview_plan_{index:02d}",
        "source_type": "validation_preview",
        "source_key": f"preview_{index:02d}",
        "title": f"Validation Preview {index:02d}",
        "priority": priority,
        "target": f"episode:E{index:02d}",
        "mode": "dry_run",
        "execution_command": f"validate_preview --target episode:E{index:02d} --dry-run",
        "estimated_step_count": 3 + (index % 2),
        "requires_manual_approval": priority in {"P0", "P1"},
    }


def build_queue_plan(run_id: str, index: int) -> dict[str, object]:
    priority = "P0" if index % 5 == 0 else "P1" if index % 2 == 0 else "P2"
    return {
        "plan_key": f"{run_id}_queue_plan_{index:02d}",
        "source_type": "validation_queue",
        "source_key": f"queue_{index:02d}",
        "title": f"Validation Queue {index:02d}",
        "priority": priority,
        "target": f"provider:provider_{index:02d}",
        "mode": "queued",
        "execution_command": f"validate_queue --target provider:provider_{index:02d}",
        "estimated_step_count": 4,
        "requires_manual_approval": priority in {"P0", "P1"},
    }


def main() -> int:
    settings = load_web_settings()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"batch_history_paging_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    validation_username = f"{run_id}_admin"
    validation_user_id = f"user_{validation_username.lower()}"
    preview_seed_count = 12
    queue_seed_count = 11
    retry_seed_count = 14

    before_batches = load_batches(settings, user_id=validation_user_id)
    before_summary = dict(before_batches.get("multi_batch_summary", {}))
    before_runtime = dict(before_batches.get("runtime_monitor", {}))
    before_preview_total = int(before_summary.get("execution_preview_history_count", 0))
    before_queue_total = int(before_summary.get("execution_queue_history_count", 0))
    before_retry_total = int(before_runtime.get("retry_history_count", 0))

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    upsert_user(
        connection,
        validation_username,
        "Validation Creator",
        f"{validation_username}@aicomic.local",
        "creator",
    )
    ensure_batch_execution_preview_schema(connection)
    ensure_batch_execution_queue_schema(connection)

    for index in range(1, preview_seed_count + 1):
      plan_payload = build_preview_plan(run_id, index)
      write_batch_execution_preview_run(
          connection,
          user_id=validation_user_id,
          plan_payload=plan_payload,
          status="preview_ready",
          preview_summary=(
              f"mode=dry_run; priority={plan_payload['priority']};"
              f" target={plan_payload['target']}; estimated_steps={plan_payload['estimated_step_count']}"
          ),
      )

    queue_run_ids: list[str] = []
    for index in range(1, queue_seed_count + 1):
      plan_payload = build_queue_plan(run_id, index)
      queue_run = write_batch_execution_queue_run(
          connection,
          user_id=validation_user_id,
          plan_payload=plan_payload,
          queue_status="queued",
          execution_status="waiting_for_approval" if bool(plan_payload["requires_manual_approval"]) else "ready",
          queue_summary=(
              f"mode=queued; priority={plan_payload['priority']};"
              f" target={plan_payload['target']}; estimated_steps={plan_payload['estimated_step_count']}"
          ),
      )
      queue_run_ids.append(str(queue_run["queue_run_id"]))

    for index, queue_run_id in enumerate(queue_run_ids, start=1):
      if index <= 4:
        update_batch_execution_queue_status_record(
            queue_run_id,
            queue_status="failed",
            execution_status="failed",
            result_note=f"{run_id}_timeout_{index:02d}",
        )
      elif index <= 7:
        update_batch_execution_queue_status_record(
            queue_run_id,
            queue_status="completed",
            execution_status="completed",
            result_note=f"{run_id}_completed_{index:02d}",
        )

    for index in range(1, retry_seed_count + 1):
      provider = "manual_web" if index % 2 == 0 else "windows_tts"
      statuses = "failed,manual_required" if index % 3 == 0 else "failed"
      write_audit_log(
          connection,
          user_id=validation_user_id,
          action_type="batch_retry_generate",
          target_type="batch",
          target_id=f"{run_id}_retry_{index:02d}",
          result="success",
          detail=(
              f"dry_run={'True' if index % 4 != 0 else 'False'};"
              f" statuses={statuses};"
              f" episode_code=E{index:02d};"
              f" provider={provider};"
              f" retried_count={(index % 5) + 1}"
          ),
      )

    connection.close()

    client = TestClient(app)
    auth_headers = build_validation_auth_headers(validation_username)
    retry_response = client.get("/api/batches/retry-history?page=2&page_size=5", headers=auth_headers)
    preview_response = client.get("/api/batches/execution-previews?page=2&page_size=5", headers=auth_headers)
    queue_response = client.get("/api/batches/execution-queue?page=2&page_size=5", headers=auth_headers)
    batches_response = client.get("/api/batches", headers=auth_headers)
    batch_summary_response = client.get("/api/batches/summary", headers=auth_headers)

    if retry_response.status_code != 200:
        raise RuntimeError(f"retry history paging failed: {retry_response.status_code} {retry_response.text}")
    if preview_response.status_code != 200:
        raise RuntimeError(f"execution preview paging failed: {preview_response.status_code} {preview_response.text}")
    if queue_response.status_code != 200:
        raise RuntimeError(f"execution queue paging failed: {queue_response.status_code} {queue_response.text}")
    if batches_response.status_code != 200:
        raise RuntimeError(f"batches summary failed: {batches_response.status_code} {batches_response.text}")
    if batch_summary_response.status_code != 200:
        raise RuntimeError(f"batch summary endpoint failed: {batch_summary_response.status_code} {batch_summary_response.text}")

    retry_payload = retry_response.json()
    preview_payload = preview_response.json()
    queue_payload = queue_response.json()
    batches_payload = batches_response.json()
    summary_payload = batch_summary_response.json()
    multi_batch_summary = dict(batches_payload.get("multi_batch_summary", {}))
    runtime_monitor = dict(batches_payload.get("runtime_monitor", {}))
    summary_multi_batch = dict(summary_payload.get("multi_batch_summary", {}))
    summary_runtime_monitor = dict(summary_payload.get("runtime_monitor", {}))

    after_preview_total = int(multi_batch_summary.get("execution_preview_history_count", 0))
    after_queue_total = int(multi_batch_summary.get("execution_queue_history_count", 0))
    after_retry_total = int(runtime_monitor.get("retry_history_count", 0))

    payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "preview_seed_count": preview_seed_count,
        "queue_seed_count": queue_seed_count,
        "retry_seed_count": retry_seed_count,
        "retry_total_count": int(retry_payload.get("total_count", 0)),
        "retry_page_count": int(retry_payload.get("count", 0)),
        "preview_total_count": int(preview_payload.get("total_count", 0)),
        "preview_page_count": int(preview_payload.get("count", 0)),
        "queue_total_count": int(queue_payload.get("total_count", 0)),
        "queue_page_count": int(queue_payload.get("count", 0)),
        "summary_retry_count": after_retry_total,
        "summary_preview_count": after_preview_total,
        "summary_queue_count": after_queue_total,
        "summary_retry_items_count": len(runtime_monitor.get("retry_history", [])),
        "summary_preview_items_count": len(multi_batch_summary.get("execution_preview_history", [])),
        "summary_queue_items_count": len(multi_batch_summary.get("execution_queue_history", [])),
        "summary_only_retry_items_count": len(summary_runtime_monitor.get("retry_history", [])),
        "summary_only_preview_items_count": len(summary_multi_batch.get("execution_preview_history", [])),
        "summary_only_queue_items_count": len(summary_multi_batch.get("execution_queue_history", [])),
        "queue_summary_queued_count": int(dict(multi_batch_summary.get("execution_queue_summary", {})).get("queued_count", 0)),
        "queue_failure_breakdown_count": int(multi_batch_summary.get("execution_failure_breakdown_count", 0)),
        "before_retry_total": before_retry_total,
        "before_preview_total": before_preview_total,
        "before_queue_total": before_queue_total,
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "batch_history_paging_validation_report.json"),
        "database_row": {},
    }

    if int(retry_payload.get("page", 0)) != 2 or int(retry_payload.get("page_size", 0)) != 5:
        raise RuntimeError("retry history page metadata mismatch")
    if int(preview_payload.get("page", 0)) != 2 or int(preview_payload.get("page_size", 0)) != 5:
        raise RuntimeError("execution preview page metadata mismatch")
    if int(queue_payload.get("page", 0)) != 2 or int(queue_payload.get("page_size", 0)) != 5:
        raise RuntimeError("execution queue page metadata mismatch")
    if payload["retry_page_count"] != 5 or payload["preview_page_count"] != 5 or payload["queue_page_count"] != 5:
        raise RuntimeError(
            "page item count mismatch: "
            f"retry={payload['retry_page_count']}, preview={payload['preview_page_count']}, queue={payload['queue_page_count']}"
        )
    if after_retry_total != int(retry_payload.get("total_count", 0)):
        raise RuntimeError("retry summary total count mismatch with paging endpoint")
    if after_preview_total != int(preview_payload.get("total_count", 0)):
        raise RuntimeError("execution preview summary total count mismatch with paging endpoint")
    if after_queue_total != int(queue_payload.get("total_count", 0)):
        raise RuntimeError("execution queue summary total count mismatch with paging endpoint")
    if after_retry_total < before_retry_total + retry_seed_count:
        raise RuntimeError("retry history total count did not grow as expected")
    if after_preview_total < before_preview_total + preview_seed_count:
        raise RuntimeError("execution preview total count did not grow as expected")
    if after_queue_total < before_queue_total + queue_seed_count:
        raise RuntimeError("execution queue total count did not grow as expected")
    if payload["summary_retry_items_count"] != min(10, after_retry_total):
        raise RuntimeError("retry summary first-page item count mismatch")
    if payload["summary_preview_items_count"] != min(10, after_preview_total):
        raise RuntimeError("execution preview summary first-page item count mismatch")
    if payload["summary_queue_items_count"] != min(10, after_queue_total):
        raise RuntimeError("execution queue summary first-page item count mismatch")
    if int(payload["summary_only_retry_items_count"]) != 0:
        raise RuntimeError("summary-only endpoint should not embed retry history rows")
    if int(payload["summary_only_preview_items_count"]) != 0:
        raise RuntimeError("summary-only endpoint should not embed execution preview history rows")
    if int(payload["summary_only_queue_items_count"]) != 0:
        raise RuntimeError("summary-only endpoint should not embed execution queue history rows")
    if int(payload["queue_summary_queued_count"]) < after_queue_total:
        raise RuntimeError("execution queue summary queued_count should reflect all queue history records")
    if int(payload["queue_failure_breakdown_count"]) <= 0:
        raise RuntimeError("execution failure breakdown should contain seeded failed queue rows")
    if int(summary_runtime_monitor.get("retry_history_count", 0)) != after_retry_total:
        raise RuntimeError("summary-only endpoint retry count mismatch")
    if int(summary_multi_batch.get("execution_preview_history_count", 0)) != after_preview_total:
        raise RuntimeError("summary-only endpoint execution preview count mismatch")
    if int(summary_multi_batch.get("execution_queue_history_count", 0)) != after_queue_total:
        raise RuntimeError("summary-only endpoint execution queue count mismatch")

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_validation_table(connection)
    insert_validation_run(connection, payload)
    payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "batch_history_paging_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
