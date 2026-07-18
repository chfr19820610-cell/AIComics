from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from aicomic.core.config import ProjectPaths
from aicomic.core.dispatcher import resolve_dispatch_channel
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.creator_runtime_service import ProjectAccessDeniedError


def normalize_pagination(page: int = 1, page_size: int = 10, max_page_size: int = 100) -> tuple[int, int, int]:
    normalized_page = max(1, page)
    normalized_page_size = max(1, min(page_size, max_page_size))
    offset = (normalized_page - 1) * normalized_page_size
    return normalized_page, normalized_page_size, offset


def build_paginated_payload(
    items: list[dict[str, Any]],
    total_count: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def parse_audit_detail(detail: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for segment in detail.split(";"):
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def normalize_audit_period(created_at: str) -> str:
    if not created_at:
        return "unknown"
    try:
        normalized = created_at.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return created_at[:10] if len(created_at) >= 10 else created_at


def parse_batch_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def ensure_batch_execution_preview_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_execution_preview_runs (
            preview_run_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan_key TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_key TEXT NOT NULL,
            title TEXT NOT NULL,
            priority TEXT NOT NULL,
            target TEXT NOT NULL,
            mode TEXT NOT NULL,
            execution_command TEXT NOT NULL,
            estimated_step_count INTEGER NOT NULL,
            requires_manual_approval INTEGER NOT NULL,
            status TEXT NOT NULL,
            preview_summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_batch_execution_preview_runs_user_created_at ON batch_execution_preview_runs(user_id, created_at)"
    )
    connection.commit()


def write_batch_execution_preview_run(
    connection: sqlite3.Connection,
    user_id: str,
    plan_payload: dict[str, Any],
    status: str,
    preview_summary: str,
) -> dict[str, Any]:
    preview_run_id = f"batch_execution_preview_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    created_at = datetime.now().astimezone().isoformat()
    connection.execute(
        """
        INSERT INTO batch_execution_preview_runs (
            preview_run_id,
            user_id,
            plan_key,
            source_type,
            source_key,
            title,
            priority,
            target,
            mode,
            execution_command,
            estimated_step_count,
            requires_manual_approval,
            status,
            preview_summary,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            preview_run_id,
            user_id,
            str(plan_payload.get("plan_key", "")),
            str(plan_payload.get("source_type", "")),
            str(plan_payload.get("source_key", "")),
            str(plan_payload.get("title", "")),
            str(plan_payload.get("priority", "")),
            str(plan_payload.get("target", "")),
            str(plan_payload.get("mode", "dry_run")),
            str(plan_payload.get("execution_command", "")),
            int(plan_payload.get("estimated_step_count", 0)),
            1 if bool(plan_payload.get("requires_manual_approval", False)) else 0,
            status,
            preview_summary,
            created_at,
        ),
    )
    connection.commit()
    return {
        "preview_run_id": preview_run_id,
        "created_at": created_at,
    }


def get_batch_execution_preview_history_page(page: int = 1, page_size: int = 10, user_id: str = "") -> dict[str, Any]:
    normalized_page, normalized_page_size, offset = normalize_pagination(page, page_size)
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_preview_schema(connection)
    params: list[Any] = []
    where_clause = ""
    if user_id:
        where_clause = "WHERE user_id = ?"
        params.append(user_id)
    total_count = int(
        connection.execute(
            f"SELECT COUNT(*) FROM batch_execution_preview_runs {where_clause}",
            tuple(params),
        ).fetchone()[0]
    )
    rows = connection.execute(
        f"""
        SELECT
            preview_run_id,
            user_id,
            plan_key,
            source_type,
            source_key,
            title,
            priority,
            target,
            mode,
            execution_command,
            estimated_step_count,
            requires_manual_approval,
            status,
            preview_summary,
            created_at
        FROM batch_execution_preview_runs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [normalized_page_size, offset]),
    ).fetchall()
    connection.close()
    items = [
        {
            "preview_run_id": str(row[0]),
            "user_id": str(row[1]),
            "plan_key": str(row[2]),
            "source_type": str(row[3]),
            "source_key": str(row[4]),
            "title": str(row[5]),
            "priority": str(row[6]),
            "target": str(row[7]),
            "mode": str(row[8]),
            "execution_command": str(row[9]),
            "estimated_step_count": int(row[10]),
            "requires_manual_approval": bool(row[11]),
            "status": str(row[12]),
            "preview_summary": str(row[13]),
            "created_at": str(row[14]),
        }
        for row in rows
    ]
    return build_paginated_payload(items, total_count, normalized_page, normalized_page_size)


def load_batch_execution_preview_history(limit: int = 10, user_id: str = "") -> list[dict[str, Any]]:
    payload = get_batch_execution_preview_history_page(page=1, page_size=max(1, min(limit, 50)), user_id=user_id)
    return list(payload.get("items", []))


def ensure_batch_execution_queue_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_execution_queue_runs (
            queue_run_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan_key TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_key TEXT NOT NULL,
            title TEXT NOT NULL,
            priority TEXT NOT NULL,
            target TEXT NOT NULL,
            mode TEXT NOT NULL,
            execution_command TEXT NOT NULL,
            estimated_step_count INTEGER NOT NULL,
            requires_manual_approval INTEGER NOT NULL,
            queue_status TEXT NOT NULL,
            execution_status TEXT NOT NULL,
            queue_summary TEXT NOT NULL,
            result_note TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    existing_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(batch_execution_queue_runs)").fetchall()
    }
    if "result_note" not in existing_columns:
        connection.execute("ALTER TABLE batch_execution_queue_runs ADD COLUMN result_note TEXT NOT NULL DEFAULT ''")
    if "completed_at" not in existing_columns:
        connection.execute("ALTER TABLE batch_execution_queue_runs ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_batch_execution_queue_runs_user_created_at ON batch_execution_queue_runs(user_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_batch_execution_queue_runs_status_created_at ON batch_execution_queue_runs(queue_status, created_at)"
    )
    connection.commit()


def write_batch_execution_queue_run(
    connection: sqlite3.Connection,
    user_id: str,
    plan_payload: dict[str, Any],
    queue_status: str,
    execution_status: str,
    queue_summary: str,
) -> dict[str, Any]:
    queue_run_id = f"batch_execution_queue_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    created_at = datetime.now().astimezone().isoformat()
    connection.execute(
        """
        INSERT INTO batch_execution_queue_runs (
            queue_run_id,
            user_id,
            plan_key,
            source_type,
            source_key,
            title,
            priority,
            target,
            mode,
            execution_command,
            estimated_step_count,
            requires_manual_approval,
            queue_status,
            execution_status,
            queue_summary,
            result_note,
            completed_at,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            queue_run_id,
            user_id,
            str(plan_payload.get("plan_key", "")),
            str(plan_payload.get("source_type", "")),
            str(plan_payload.get("source_key", "")),
            str(plan_payload.get("title", "")),
            str(plan_payload.get("priority", "")),
            str(plan_payload.get("target", "")),
            str(plan_payload.get("mode", "queued")),
            str(plan_payload.get("execution_command", "")),
            int(plan_payload.get("estimated_step_count", 0)),
            1 if bool(plan_payload.get("requires_manual_approval", False)) else 0,
            queue_status,
            execution_status,
            queue_summary,
            "",
            "",
            created_at,
            created_at,
        ),
    )
    connection.commit()
    return {
        "queue_run_id": queue_run_id,
        "created_at": created_at,
        "updated_at": created_at,
    }


def fetch_batch_execution_queue_history_records(user_id: str = "") -> list[dict[str, Any]]:
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_queue_schema(connection)
    params: list[Any] = []
    where_clause = ""
    if user_id:
        where_clause = "WHERE user_id = ?"
        params.append(user_id)
    rows = connection.execute(
        f"""
        SELECT
            queue_run_id,
            user_id,
            plan_key,
            source_type,
            source_key,
            title,
            priority,
            target,
            mode,
            execution_command,
            estimated_step_count,
            requires_manual_approval,
            queue_status,
            execution_status,
            queue_summary,
            result_note,
            completed_at,
            created_at,
            updated_at
        FROM batch_execution_queue_runs
        {where_clause}
        ORDER BY created_at DESC
        """,
        tuple(params),
    ).fetchall()
    connection.close()
    return [
        {
            "queue_run_id": str(row[0]),
            "user_id": str(row[1]),
            "plan_key": str(row[2]),
            "source_type": str(row[3]),
            "source_key": str(row[4]),
            "title": str(row[5]),
            "priority": str(row[6]),
            "target": str(row[7]),
            "mode": str(row[8]),
            "execution_command": str(row[9]),
            "estimated_step_count": int(row[10]),
            "requires_manual_approval": bool(row[11]),
            "queue_status": str(row[12]),
            "execution_status": str(row[13]),
            "queue_summary": str(row[14]),
            "result_note": str(row[15]),
            "completed_at": str(row[16]),
            "created_at": str(row[17]),
            "updated_at": str(row[18]),
        }
        for row in rows
    ]


def get_batch_execution_queue_history_page(page: int = 1, page_size: int = 10, user_id: str = "") -> dict[str, Any]:
    normalized_page, normalized_page_size, offset = normalize_pagination(page, page_size)
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_queue_schema(connection)
    params: list[Any] = []
    where_clause = ""
    if user_id:
        where_clause = "WHERE user_id = ?"
        params.append(user_id)
    total_count = int(
        connection.execute(
            f"SELECT COUNT(*) FROM batch_execution_queue_runs {where_clause}",
            tuple(params),
        ).fetchone()[0]
    )
    rows = connection.execute(
        f"""
        SELECT
            queue_run_id,
            user_id,
            plan_key,
            source_type,
            source_key,
            title,
            priority,
            target,
            mode,
            execution_command,
            estimated_step_count,
            requires_manual_approval,
            queue_status,
            execution_status,
            queue_summary,
            result_note,
            completed_at,
            created_at,
            updated_at
        FROM batch_execution_queue_runs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [normalized_page_size, offset]),
    ).fetchall()
    connection.close()
    items = [
        {
            "queue_run_id": str(row[0]),
            "user_id": str(row[1]),
            "plan_key": str(row[2]),
            "source_type": str(row[3]),
            "source_key": str(row[4]),
            "title": str(row[5]),
            "priority": str(row[6]),
            "target": str(row[7]),
            "mode": str(row[8]),
            "execution_command": str(row[9]),
            "estimated_step_count": int(row[10]),
            "requires_manual_approval": bool(row[11]),
            "queue_status": str(row[12]),
            "execution_status": str(row[13]),
            "queue_summary": str(row[14]),
            "result_note": str(row[15]),
            "completed_at": str(row[16]),
            "created_at": str(row[17]),
            "updated_at": str(row[18]),
        }
        for row in rows
    ]
    return build_paginated_payload(items, total_count, normalized_page, normalized_page_size)


def load_batch_execution_queue_history(limit: int = 10, user_id: str = "") -> list[dict[str, Any]]:
    payload = get_batch_execution_queue_history_page(page=1, page_size=max(1, min(limit, 50)), user_id=user_id)
    return list(payload.get("items", []))


def update_batch_execution_queue_status_record(
    queue_run_id: str,
    queue_status: str,
    execution_status: str,
    result_note: str = "",
    actor_user_id: str = "",
) -> dict[str, Any]:
    normalized_queue_status = queue_status.strip().lower()
    normalized_execution_status = execution_status.strip().lower()
    allowed_queue_statuses = {"queued", "running", "completed", "failed", "cancelled"}
    allowed_execution_statuses = {"waiting_for_approval", "ready", "running", "completed", "failed", "cancelled"}
    if normalized_queue_status not in allowed_queue_statuses:
        raise ValueError(f"Unsupported queue_status `{queue_status}`.")
    if normalized_execution_status not in allowed_execution_statuses:
        raise ValueError(f"Unsupported execution_status `{execution_status}`.")

    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_queue_schema(connection)
    row = connection.execute(
        """
        SELECT
            queue_run_id,
            user_id,
            plan_key,
            priority,
            target,
            queue_summary
        FROM batch_execution_queue_runs
        WHERE queue_run_id = ?
        """,
        (queue_run_id,),
    ).fetchone()
    if row is None:
        connection.close()
        raise ValueError(f"Queue run `{queue_run_id}` not found.")
    owner_user_id = str(row[1])
    if actor_user_id and owner_user_id != actor_user_id:
        connection.close()
        raise ProjectAccessDeniedError(
            f"Queue run `{queue_run_id}` belongs to `{owner_user_id}` and cannot be updated by `{actor_user_id}`."
        )

    updated_at = datetime.now().astimezone().isoformat()
    completed_at = updated_at if normalized_queue_status in {"completed", "failed", "cancelled"} else ""
    summary_suffix = (
        f"; queue_status={normalized_queue_status};"
        f" execution_status={normalized_execution_status};"
        f" result_note={result_note}"
    )
    queue_summary = f"{str(row[5])}{summary_suffix}"
    connection.execute(
        """
        UPDATE batch_execution_queue_runs
        SET
            queue_status = ?,
            execution_status = ?,
            queue_summary = ?,
            result_note = ?,
            completed_at = ?,
            updated_at = ?
        WHERE queue_run_id = ?
        """,
        (
            normalized_queue_status,
            normalized_execution_status,
            queue_summary,
            result_note,
            completed_at,
            updated_at,
            queue_run_id,
        ),
    )
    connection.commit()
    connection.close()
    return {
        "status": "updated",
        "queue_run_id": queue_run_id,
        "plan_key": str(row[2]),
        "priority": str(row[3]),
        "target": str(row[4]),
        "queue_status": normalized_queue_status,
        "execution_status": normalized_execution_status,
        "queue_summary": queue_summary,
        "result_note": result_note,
        "completed_at": completed_at,
        "updated_at": updated_at,
    }


def load_batch_retry_audit_records(limit: int = 10, user_id: str = "") -> list[dict[str, Any]]:
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    params: list[Any] = []
    where_clause = "WHERE action_type = 'batch_retry_generate'"
    if user_id:
        where_clause += " AND user_id = ?"
        params.append(user_id)
    rows = connection.execute(
        f"""
        SELECT
            audit_id,
            user_id,
            result,
            detail,
            created_at
        FROM audit_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        tuple(params + [max(1, min(limit, 500))]),
    ).fetchall()
    connection.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        detail_payload = parse_audit_detail(str(row[3] or ""))
        provider = detail_payload.get("provider", "")
        queue_name = ""
        if provider:
            _, queue_name = resolve_dispatch_channel(provider)
        items.append(
            {
                "audit_id": str(row[0]),
                "user_id": str(row[1]),
                "result": str(row[2]),
                "created_at": str(row[4]),
                "dry_run": detail_payload.get("dry_run", "False").lower() == "true",
                "statuses": [item for item in detail_payload.get("statuses", "").split(",") if item],
                "episode_code": detail_payload.get("episode_code", ""),
                "provider": provider,
                "queue_name": queue_name,
                "retried_count": int(detail_payload.get("retried_count", "0") or 0),
            }
        )
    return items


def load_batch_retry_history(limit: int = 10, user_id: str = "") -> list[dict[str, Any]]:
    return load_batch_retry_audit_records(limit=max(1, min(limit, 500)), user_id=user_id)


def load_batch_retry_trends(limit: int = 14, user_id: str = "") -> list[dict[str, Any]]:
    audit_records = load_batch_retry_audit_records(limit=max(20, min(limit, 31) * 10), user_id=user_id)
    trend_buckets: dict[str, dict[str, Any]] = {}
    for item in audit_records:
        period = normalize_audit_period(str(item.get("created_at", "")))
        bucket = trend_buckets.setdefault(
            period,
            {
                "period": period,
                "action_count": 0,
                "retry_count": 0,
                "dry_run_count": 0,
                "generated_count": 0,
                "success_count": 0,
                "operators": set(),
                "queue_names": set(),
                "episode_codes": set(),
            },
        )
        bucket["action_count"] += 1
        bucket["retry_count"] += int(item.get("retried_count", 0))
        if bool(item.get("dry_run", False)):
            bucket["dry_run_count"] += 1
        else:
            bucket["generated_count"] += 1
        if str(item.get("result", "")) == "success":
            bucket["success_count"] += 1
        user_id = str(item.get("user_id", ""))
        if user_id:
            bucket["operators"].add(user_id)
        queue_name = str(item.get("queue_name", ""))
        if queue_name:
            bucket["queue_names"].add(queue_name)
        elif int(item.get("retried_count", 0)) > 0:
            bucket["queue_names"].add("multi_queue")
        episode_code = str(item.get("episode_code", ""))
        if episode_code:
            bucket["episode_codes"].add(episode_code)
        elif int(item.get("retried_count", 0)) > 0:
            bucket["episode_codes"].add("multi_episode")

    selected_periods = sorted(trend_buckets.keys(), reverse=True)[: max(1, min(limit, 31))]
    raw_trends: list[dict[str, Any]] = []
    for period in selected_periods:
        bucket = trend_buckets[period]
        queue_impact_count = len(bucket["queue_names"])
        episode_impact_count = len(bucket["episode_codes"])
        raw_trends.append(
            {
                "period": period,
                "action_count": int(bucket["action_count"]),
                "retry_count": int(bucket["retry_count"]),
                "dry_run_count": int(bucket["dry_run_count"]),
                "generated_count": int(bucket["generated_count"]),
                "success_count": int(bucket["success_count"]),
                "unique_operator_count": len(bucket["operators"]),
                "queue_impact_count": queue_impact_count,
                "episode_impact_count": episode_impact_count,
                "impact_score": queue_impact_count + episode_impact_count,
            }
        )

    max_retry_count = max([int(item["retry_count"]) for item in raw_trends] or [0])
    max_impact_score = max([int(item["impact_score"]) for item in raw_trends] or [0])
    return [
        {
            **item,
            "retry_bar_width": round((int(item["retry_count"]) / max(1, max_retry_count)) * 100, 1),
            "impact_bar_width": round((int(item["impact_score"]) / max(1, max_impact_score)) * 100, 1),
        }
        for item in raw_trends
    ]


def get_batch_retry_history_page(page: int = 1, page_size: int = 10, user_id: str = "") -> dict[str, Any]:
    normalized_page, normalized_page_size, offset = normalize_pagination(page, page_size)
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    params: list[Any] = []
    where_clause = "WHERE action_type = 'batch_retry_generate'"
    if user_id:
        where_clause += " AND user_id = ?"
        params.append(user_id)
    total_count = int(
        connection.execute(
            f"SELECT COUNT(*) FROM audit_logs {where_clause}",
            tuple(params),
        ).fetchone()[0]
    )
    rows = connection.execute(
        f"""
        SELECT
            audit_id,
            user_id,
            result,
            detail,
            created_at
        FROM audit_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [normalized_page_size, offset]),
    ).fetchall()
    connection.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        detail_payload = parse_audit_detail(str(row[3] or ""))
        provider = detail_payload.get("provider", "")
        queue_name = ""
        if provider:
            _, queue_name = resolve_dispatch_channel(provider)
        items.append(
            {
                "audit_id": str(row[0]),
                "user_id": str(row[1]),
                "result": str(row[2]),
                "created_at": str(row[4]),
                "dry_run": detail_payload.get("dry_run", "False").lower() == "true",
                "statuses": [item for item in detail_payload.get("statuses", "").split(",") if item],
                "episode_code": detail_payload.get("episode_code", ""),
                "provider": provider,
                "queue_name": queue_name,
                "retried_count": int(detail_payload.get("retried_count", "0") or 0),
            }
        )
    return build_paginated_payload(items, total_count, normalized_page, normalized_page_size)
