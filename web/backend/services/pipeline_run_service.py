from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aicomic.providers.provider_planner import collect_available_providers, load_provider_settings
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.creator_action_service import (
    ACTION_LABELS,
    HORROR_PROVIDER_POLICY,
    apply_provider_results_action,
    auto_repair_episode_action,
    auto_review_episode_action,
    build_candidate_publish_pack_action,
    build_horror_regeneration_queue_action,
    build_jobs_action,
    build_horror_episode_action,
    confirm_candidate_publish_action,
    execute_horror_assets_live_action,
    generate_horror_blueprint_action,
    build_provider_requests_action,
    record_candidate_release_action,
    refresh_creator_reports_action,
    render_preview_action,
    render_release_action,
    resolve_creator_provider_policy,
    resolve_providers_config,
    scan_assets_action,
    build_publish_pack_action,
    select_episode_code,
)
from web.backend.services.creator_review_service import record_sample_review_export
from web.backend.services.creator_runtime_service import (
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    ensure_creator_runtime_schema,
    ensure_project_owner,
    load_authoring_revision_summary,
)
from web.backend.services.creator_service import resolve_project_documents, resolve_project_root_by_id
from web.backend.settings import WebSettings


class PipelineRunError(Exception):
    pass


class UnsupportedCreatorActionError(PipelineRunError):
    pass


class SingleFlightConflictError(PipelineRunError):
    def __init__(self, run_id: str, episode_code: str) -> None:
        super().__init__(f"剧集 `{episode_code}` 已有进行中的运行：`{run_id}`。")
        self.run_id = run_id
        self.episode_code = episode_code


class InvalidStateTransitionError(PipelineRunError):
    pass


RUN_STATUS_TRANSITIONS = {
    "submitted": {"queued", "running", "failed"},
    "queued": {"running", "failed", "cancelled", "superseded"},
    "running": {"succeeded", "failed", "cancelled"},
    "failed": set(),
    "succeeded": set(),
    "cancelled": set(),
    "superseded": set(),
}
STEP_STATUS_TRANSITIONS = {
    "pending": {"running", "skipped"},
    "running": {"succeeded", "failed"},
    "failed": set(),
    "succeeded": set(),
    "skipped": set(),
}
ACTION_STEP_PLANS: dict[str, list[tuple[str, str]]] = {
    "generate_horror_sample": [
        ("generate_horror_blueprint", "生成恐怖故事蓝图"),
        ("build_horror_episode", "生成 5-10 分钟样片镜头"),
        ("build_jobs", "生成任务包"),
        ("build_provider_requests", "生成本地 Provider 请求包"),
        ("render_release", "渲染正式版样片"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
    ],
    "run_horror_assets_live": [
        ("ensure_jobs", "确保任务包"),
        ("build_provider_requests", "生成本地 Provider 请求包"),
        ("execute_horror_assets_live", "执行受限真实资产生成"),
        ("apply_provider_results", "回写 Provider 产物状态"),
        ("build_horror_regeneration_queue", "生成失败镜头重生成队列"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
    ],
    "build_horror_regeneration_queue": [("build_horror_regeneration_queue", "生成失败镜头重生成队列")],
    "generate_horror_blueprint": [("generate_horror_blueprint", "生成恐怖故事蓝图")],
    "build_horror_episode": [("build_horror_episode", "生成 5-10 分钟样片镜头")],
    "build_jobs": [("build_jobs", "生成任务包")],
    "build_provider_requests": [
        ("ensure_jobs", "确保任务包"),
        ("build_provider_requests", "生成 Provider 请求包"),
    ],
    "apply_provider_results": [("apply_provider_results", "回写 Provider 产物状态")],
    "scan_assets": [("scan_assets", "扫描素材状态")],
    "render_preview": [("render_preview", "渲染预览")],
    "render_release": [("render_release", "渲染正式版")],
    "build_publish_pack": [("build_publish_pack", "生成发布包")],
    "build_candidate_publish_pack": [("build_candidate_publish_pack", "生成候选发布包")],
    "export_approved_release": [
        ("render_release", "渲染正式版"),
        ("build_publish_pack", "生成发布包"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
    ],
    "autopilot_candidate_release": [
        ("ensure_jobs", "确保任务包"),
        ("build_provider_requests", "生成本地 Provider 请求包"),
        ("execute_horror_assets_live", "执行真实资产"),
        ("apply_provider_results", "回写 Provider 产物状态"),
        ("build_horror_regeneration_queue", "生成失败镜头重生成队列"),
        ("auto_repair_episode", "自动修复失败镜头"),
        ("render_release", "渲染正式版"),
        ("build_candidate_publish_pack", "生成候选发布包"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
        ("auto_review_episode", "自动审片"),
        ("record_candidate_release", "记录候选片"),
    ],
    "confirm_candidate_publish": [
        ("confirm_candidate_publish", "确认候选片发布"),
        ("render_release", "渲染正式版"),
        ("build_publish_pack", "生成发布包"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
    ],
    "refresh_creator_reports": [
        ("ensure_jobs", "确保任务包"),
        ("refresh_creator_reports", "刷新 Creator 报告"),
    ],
}
ARTIFACT_FIELDS = {
    "output_path": "output",
    "report_output_path": "report",
    "jobs_output_path": "jobs",
    "validation_report_path": "validation_report",
    "dashboard_path": "dashboard",
    "review_metrics_path": "review_metrics",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def dumps_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def ensure_pipeline_run_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_root TEXT NOT NULL,
            episode_code TEXT NOT NULL,
            action TEXT NOT NULL,
            action_label TEXT NOT NULL,
            status TEXT NOT NULL,
            current_step_key TEXT NOT NULL,
            spec_json TEXT NOT NULL,
            spec_hash TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            error_code TEXT NOT NULL DEFAULT '',
            error_detail TEXT NOT NULL DEFAULT '',
            blocked_reason TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_run_steps (
            step_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            step_key TEXT NOT NULL,
            step_title TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT NOT NULL DEFAULT '{}',
            error_code TEXT NOT NULL DEFAULT '',
            error_detail TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            UNIQUE(run_id, step_key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_run_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            sequence_no INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            step_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, sequence_no)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_artifacts (
            artifact_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            episode_code TEXT NOT NULL,
            artifact_key TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            artifact_role TEXT NOT NULL,
            artifact_status TEXT NOT NULL,
            output_path TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_project_episode_status ON pipeline_runs(project_id, episode_code, status)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user_submitted_at ON pipeline_runs(user_id, submitted_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_run_steps_run_order ON pipeline_run_steps(run_id, step_order)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_run_events_run_sequence ON pipeline_run_events(run_id, sequence_no)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_artifacts_run_role ON pipeline_artifacts(run_id, artifact_role)"
    )
    connection.commit()


def compute_spec_hash(spec: dict[str, Any], recipe: dict[str, Any]) -> str:
    raw = dumps_json({"spec": spec, "recipe": recipe})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_run_recipe(settings: WebSettings, project_root: Path, documents: dict[str, Any], action: str = "") -> dict[str, Any]:
    providers_config_path = resolve_providers_config(settings, project_root)
    provider_settings = load_provider_settings(providers_config_path)
    return {
        "recipe_version": "creator_run_recipe/v1",
        "spec_action": action,
        "current_run_id": "",
        "provider_policy": resolve_creator_provider_policy(documents),
        "providers_config_path": str(providers_config_path),
        "configured_providers": sorted(collect_available_providers(provider_settings)),
    }


def build_run_spec(
    project_id: str,
    project_root: Path,
    episode_code: str,
    action: str,
    revision_summary: dict[str, str],
    user_id: str,
) -> dict[str, Any]:
    return {
        "run_type": "creator_action_run",
        "project_id": project_id,
        "project_root": str(project_root),
        "episode_code": episode_code,
        "action": action,
        "action_label": ACTION_LABELS[action],
        "authoring_revision_summary": revision_summary,
        "submitted_by": user_id,
        "submitted_at": now_iso(),
    }


def load_run_row(connection: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            run_id,
            user_id,
            project_id,
            project_root,
            episode_code,
            action,
            action_label,
            status,
            current_step_key,
            spec_json,
            spec_hash,
            recipe_json,
            submitted_at,
            started_at,
            completed_at,
            error_code,
            error_detail,
            blocked_reason,
            result_json
        FROM pipeline_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        raise PipelineRunError(f"Run `{run_id}` not found.")
    return {
        "run_id": str(row[0]),
        "user_id": str(row[1]),
        "project_id": str(row[2]),
        "project_root": str(row[3]),
        "episode_code": str(row[4]),
        "action": str(row[5]),
        "action_label": str(row[6]),
        "status": str(row[7]),
        "current_step_key": str(row[8]),
        "spec": json.loads(str(row[9])),
        "spec_hash": str(row[10]),
        "recipe": json.loads(str(row[11])),
        "submitted_at": str(row[12]),
        "started_at": str(row[13]),
        "completed_at": str(row[14]),
        "error_code": str(row[15]),
        "error_detail": str(row[16]),
        "blocked_reason": str(row[17]),
        "result": json.loads(str(row[18])),
    }


def load_run_steps(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            step_id,
            run_id,
            step_key,
            step_title,
            step_order,
            status,
            result_json,
            error_code,
            error_detail,
            started_at,
            completed_at
        FROM pipeline_run_steps
        WHERE run_id = ?
        ORDER BY step_order ASC
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "step_id": str(row[0]),
            "run_id": str(row[1]),
            "step_key": str(row[2]),
            "step_title": str(row[3]),
            "step_order": int(row[4]),
            "status": str(row[5]),
            "result": json.loads(str(row[6])),
            "error_code": str(row[7]),
            "error_detail": str(row[8]),
            "started_at": str(row[9]),
            "completed_at": str(row[10]),
        }
        for row in rows
    ]


def load_run_artifacts(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            artifact_id,
            run_id,
            project_id,
            episode_code,
            artifact_key,
            artifact_type,
            artifact_role,
            artifact_status,
            output_path,
            metadata_json,
            created_at
        FROM pipeline_artifacts
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "artifact_id": str(row[0]),
            "run_id": str(row[1]),
            "project_id": str(row[2]),
            "episode_code": str(row[3]),
            "artifact_key": str(row[4]),
            "artifact_type": str(row[5]),
            "artifact_role": str(row[6]),
            "artifact_status": str(row[7]),
            "output_path": str(row[8]),
            "metadata": json.loads(str(row[9])),
            "created_at": str(row[10]),
        }
        for row in rows
    ]


def append_run_event(
    connection: sqlite3.Connection,
    run_id: str,
    event_type: str,
    from_status: str,
    to_status: str,
    step_key: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    current_sequence = connection.execute(
        "SELECT COALESCE(MAX(sequence_no), 0) FROM pipeline_run_events WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    sequence_no = int(current_sequence[0]) + 1 if current_sequence else 1
    connection.execute(
        """
        INSERT INTO pipeline_run_events (
            event_id,
            run_id,
            sequence_no,
            event_type,
            from_status,
            to_status,
            step_key,
            payload_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug("run_event"),
            run_id,
            sequence_no,
            event_type,
            from_status,
            to_status,
            step_key,
            dumps_json(payload or {}),
            now_iso(),
        ),
    )
    connection.commit()


def transition_run_status(
    connection: sqlite3.Connection,
    run_id: str,
    next_status: str,
    step_key: str = "",
    error_code: str = "",
    error_detail: str = "",
    blocked_reason: str = "",
    result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = load_run_row(connection, run_id)
    current_status = run["status"]
    if next_status not in RUN_STATUS_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(f"Run `{run_id}` cannot transition from {current_status} to {next_status}.")
    started_at = run["started_at"] or (now_iso() if next_status == "running" else "")
    completed_at = now_iso() if next_status in {"succeeded", "failed", "cancelled", "superseded"} else ""
    connection.execute(
        """
        UPDATE pipeline_runs
        SET
            status = ?,
            current_step_key = ?,
            started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
            completed_at = CASE WHEN ? = '' THEN completed_at ELSE ? END,
            error_code = ?,
            error_detail = ?,
            blocked_reason = ?,
            result_json = ?
        WHERE run_id = ?
        """,
        (
            next_status,
            step_key,
            started_at,
            completed_at,
            completed_at,
            error_code,
            error_detail,
            blocked_reason,
            dumps_json(result_payload or run["result"]),
            run_id,
        ),
    )
    connection.commit()
    append_run_event(
        connection,
        run_id,
        "run_status_changed",
        current_status,
        next_status,
        step_key=step_key,
        payload={
            "error_code": error_code,
            "error_detail": error_detail,
            "blocked_reason": blocked_reason,
        },
    )
    return load_run_row(connection, run_id)


def transition_step_status(
    connection: sqlite3.Connection,
    run_id: str,
    step_key: str,
    next_status: str,
    result_payload: dict[str, Any] | None = None,
    error_code: str = "",
    error_detail: str = "",
) -> None:
    row = connection.execute(
        """
        SELECT step_id, status, started_at
        FROM pipeline_run_steps
        WHERE run_id = ? AND step_key = ?
        """,
        (run_id, step_key),
    ).fetchone()
    if row is None:
        raise PipelineRunError(f"Step `{step_key}` not found for run `{run_id}`.")
    current_status = str(row[1])
    if next_status not in STEP_STATUS_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(
            f"Step `{step_key}` for run `{run_id}` cannot transition from {current_status} to {next_status}."
        )
    started_at = str(row[2]) or (now_iso() if next_status == "running" else "")
    completed_at = now_iso() if next_status in {"succeeded", "failed", "skipped"} else ""
    connection.execute(
        """
        UPDATE pipeline_run_steps
        SET
            status = ?,
            result_json = ?,
            error_code = ?,
            error_detail = ?,
            started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
            completed_at = CASE WHEN ? = '' THEN completed_at ELSE ? END
        WHERE run_id = ? AND step_key = ?
        """,
        (
            next_status,
            dumps_json(result_payload or {}),
            error_code,
            error_detail,
            started_at,
            completed_at,
            completed_at,
            run_id,
            step_key,
        ),
    )
    connection.commit()
    append_run_event(
        connection,
        run_id,
        "step_status_changed",
        current_status,
        next_status,
        step_key=step_key,
        payload={
            "error_code": error_code,
            "error_detail": error_detail,
        },
    )


def set_run_current_step_key(connection: sqlite3.Connection, run_id: str, step_key: str) -> None:
    connection.execute(
        """
        UPDATE pipeline_runs
        SET current_step_key = ?
        WHERE run_id = ?
        """,
        (step_key, run_id),
    )
    connection.commit()


def insert_pipeline_run(
    connection: sqlite3.Connection,
    user_id: str,
    project_id: str,
    project_root: Path,
    episode_code: str,
    action: str,
    spec: dict[str, Any],
    recipe: dict[str, Any],
) -> str:
    run_id = slug("creator_run")
    submitted_at = now_iso()
    spec_hash = compute_spec_hash(spec, recipe)
    connection.execute(
        """
        INSERT INTO pipeline_runs (
            run_id,
            user_id,
            project_id,
            project_root,
            episode_code,
            action,
            action_label,
            status,
            current_step_key,
            spec_json,
            spec_hash,
            recipe_json,
            submitted_at,
            started_at,
            completed_at,
            error_code,
            error_detail,
            blocked_reason,
            result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', '', '', '', '{}')
        """,
        (
            run_id,
            user_id,
            project_id,
            str(project_root),
            episode_code,
            action,
            ACTION_LABELS[action],
            "submitted",
            "",
            dumps_json(spec),
            spec_hash,
            dumps_json(recipe),
            submitted_at,
        ),
    )
    for step_order, (step_key, step_title) in enumerate(ACTION_STEP_PLANS[action], start=1):
        connection.execute(
            """
            INSERT INTO pipeline_run_steps (
                step_id,
                run_id,
                step_key,
                step_title,
                step_order,
                status,
                result_json,
                error_code,
                error_detail,
                started_at,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', '{}', '', '', '', '')
            """,
            (slug("run_step"), run_id, step_key, step_title, step_order),
        )
    connection.commit()
    append_run_event(
        connection,
        run_id,
        "run_submitted",
        "",
        "submitted",
        payload={"action": action, "episode_code": episode_code},
    )
    return run_id


def find_active_run(connection: sqlite3.Connection, project_id: str, episode_code: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT run_id, status
        FROM pipeline_runs
        WHERE project_id = ? AND episode_code = ? AND status IN ('queued', 'running')
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
        (project_id, episode_code),
    ).fetchone()
    if row is None:
        return None
    return {
        "run_id": str(row[0]),
        "status": str(row[1]),
    }


def append_artifacts(
    connection: sqlite3.Connection,
    run_id: str,
    project_id: str,
    episode_code: str,
    action: str,
    step_key: str,
    result_payload: dict[str, Any],
) -> None:
    created_at = now_iso()
    for field_name, artifact_role in ARTIFACT_FIELDS.items():
        output_path = str(result_payload.get(field_name, "")).strip()
        if not output_path:
            continue
        connection.execute(
            """
            INSERT INTO pipeline_artifacts (
                artifact_id,
                run_id,
                project_id,
                episode_code,
                artifact_key,
                artifact_type,
                artifact_role,
                artifact_status,
                output_path,
                metadata_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug("artifact"),
                run_id,
                project_id,
                episode_code,
                f"{step_key}:{artifact_role}",
                action,
                artifact_role,
                "candidate",
                output_path,
                dumps_json({"field_name": field_name}),
                created_at,
            ),
        )
    connection.commit()


def execute_step(
    settings: WebSettings,
    project_root: Path,
    documents: dict[str, Any],
    episode_code: str,
    recipe: dict[str, Any],
    step_key: str,
    user_id: str = "",
) -> dict[str, Any]:
    asset_root = Path(documents["state_dir"]) / "demo_assets"
    providers_config_path = resolve_providers_config(settings, project_root)
    provider_policy = dict(recipe.get("provider_policy", {}))
    if step_key == "generate_horror_blueprint":
        return generate_horror_blueprint_action(documents, episode_code)
    if step_key == "build_horror_episode":
        return build_horror_episode_action(documents, episode_code)
    if step_key == "execute_horror_assets_live":
        return execute_horror_assets_live_action(documents, episode_code, providers_config_path)
    if step_key == "apply_provider_results":
        return apply_provider_results_action(project_root, documents, episode_code)
    if step_key == "build_horror_regeneration_queue":
        return build_horror_regeneration_queue_action(documents, episode_code)
    if str(recipe.get("spec_action", "")) in {"generate_horror_sample", "run_horror_assets_live", "autopilot_candidate_release"}:
        provider_policy = HORROR_PROVIDER_POLICY
    if step_key == "ensure_jobs":
        jobs_path = project_root / "jobs" / "episode_jobs.json"
        if jobs_path.exists():
            return {
                "status": "completed",
                "output_path": str(jobs_path),
                "reused_existing_jobs": True,
            }
        return build_jobs_action(
            settings,
            project_root,
            documents,
            episode_code,
            provider_policy=provider_policy,
        )
    if step_key == "build_jobs":
        return build_jobs_action(
            settings,
            project_root,
            documents,
            episode_code,
            provider_policy=provider_policy,
        )
    if step_key == "build_provider_requests":
        return build_provider_requests_action(
            settings,
            project_root,
            documents,
            episode_code,
            providers_config_path,
            asset_root,
            ensure_jobs_if_missing=False,
            provider_policy=provider_policy,
        )
    if step_key == "scan_assets":
        return scan_assets_action(documents, episode_code, asset_root)
    if step_key == "render_preview":
        return render_preview_action(documents, episode_code, asset_root)
    if step_key == "render_release":
        return render_release_action(documents, episode_code, asset_root)
    if step_key == "build_publish_pack":
        return build_publish_pack_action(
            settings,
            project_root,
            documents,
            episode_code,
            actor_user_id=user_id,
        )
    if step_key == "build_candidate_publish_pack":
        return build_candidate_publish_pack_action(documents, episode_code)
    if step_key == "auto_repair_episode":
        return auto_repair_episode_action(
            settings,
            project_root,
            documents,
            episode_code,
            providers_config_path,
            actor_user_id=user_id,
        )
    if step_key == "auto_review_episode":
        return auto_review_episode_action(
            settings,
            project_root,
            documents,
            episode_code,
            actor_user_id=user_id,
        )
    if step_key == "record_candidate_release":
        return record_candidate_release_action(
            settings,
            project_root,
            documents,
            episode_code,
            candidate_run_id=str(recipe.get("current_run_id", "")),
            actor_user_id=user_id,
        )
    if step_key == "confirm_candidate_publish":
        return confirm_candidate_publish_action(
            settings,
            project_root,
            documents,
            episode_code,
            actor_user_id=user_id,
        )
    if step_key == "refresh_creator_reports":
        return refresh_creator_reports_action(
            settings,
            project_root,
            documents,
            ensure_jobs_if_missing=False,
        )
    raise PipelineRunError(f"Unsupported step `{step_key}`.")


def execute_pipeline_run(
    connection: sqlite3.Connection,
    settings: WebSettings,
    run_id: str,
) -> dict[str, Any]:
    run = load_run_row(connection, run_id)
    transition_run_status(connection, run_id, "queued")
    transition_run_status(connection, run_id, "running")
    project_root = Path(run["project_root"])
    documents = resolve_project_documents(settings, project_root)
    last_result: dict[str, Any] = {}
    for step in load_run_steps(connection, run_id):
        step_key = str(step["step_key"])
        set_run_current_step_key(connection, run_id, step_key)
        transition_step_status(connection, run_id, step_key, "running")
        try:
            step_result = execute_step(
                settings,
                project_root,
                documents,
                run["episode_code"],
                run["recipe"],
                step_key,
                user_id=str(run["user_id"]),
            )
            transition_step_status(connection, run_id, step_key, "succeeded", result_payload=step_result)
            append_artifacts(
                connection,
                run_id,
                run["project_id"],
                run["episode_code"],
                run["action"],
                step_key,
                step_result,
            )
            last_result = step_result
            documents = resolve_project_documents(settings, project_root)
        except Exception as error:  # noqa: BLE001 - pipeline run should record controlled failure state.
            error_code = error.__class__.__name__
            error_detail = str(error)
            transition_step_status(
                connection,
                run_id,
                step_key,
                "failed",
                error_code=error_code,
                error_detail=error_detail,
            )
            transition_run_status(
                connection,
                run_id,
                "failed",
                step_key=step_key,
                error_code=error_code,
                error_detail=error_detail,
                result_payload=last_result,
            )
            return load_pipeline_run_detail(connection, run_id)
    set_run_current_step_key(connection, run_id, "")
    transition_run_status(
        connection,
        run_id,
        "succeeded",
        result_payload=last_result,
    )
    completed_run = load_pipeline_run_detail(connection, run_id)
    if str(completed_run.get("action", "")) in {"export_approved_release", "confirm_candidate_publish"}:
        result_payload = dict(completed_run.get("result", {}))
        artifacts = completed_run.get("artifacts", [])
        release_output_path = ""
        publish_pack_output_path = ""
        for artifact in artifacts if isinstance(artifacts, list) else []:
            artifact_key = str(artifact.get("artifact_key", ""))
            if artifact_key == "render_release:output":
                release_output_path = str(artifact.get("output_path", ""))
            elif artifact_key == "build_publish_pack:output":
                publish_pack_output_path = str(artifact.get("output_path", ""))
        export_review = record_sample_review_export(
            settings,
            project_id=str(completed_run.get("project_id", "")),
            episode_code=str(completed_run.get("episode_code", "")),
            export_run_id=str(completed_run.get("run_id", "")),
            exported_at=str(completed_run.get("completed_at", now_iso())),
            release_output_path=release_output_path or str(result_payload.get("release_output_path", "")),
            publish_pack_output_path=publish_pack_output_path or str(result_payload.get("publish_pack_output_path", "")),
            actor_user_id=str(completed_run.get("user_id", "")),
        )
        result_payload["release_output_path"] = release_output_path or str(result_payload.get("release_output_path", ""))
        result_payload["publish_pack_output_path"] = publish_pack_output_path or str(result_payload.get("publish_pack_output_path", ""))
        result_payload["export_audit"] = dict(export_review.get("export_audit", {}))
        connection.execute(
            """
            UPDATE pipeline_runs
            SET result_json = ?
            WHERE run_id = ?
            """,
            (dumps_json(result_payload), run_id),
        )
        connection.commit()
        completed_run = load_pipeline_run_detail(connection, run_id)
    return completed_run


def load_pipeline_run_detail(connection: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run = load_run_row(connection, run_id)
    steps = load_run_steps(connection, run_id)
    artifacts = load_run_artifacts(connection, run_id)
    run["steps"] = steps
    run["artifacts"] = artifacts
    run["step_count"] = len(steps)
    run["completed_step_count"] = sum(1 for item in steps if item["status"] == "succeeded")
    return run


def build_action_run_response(run_payload: dict[str, Any]) -> dict[str, Any]:
    result_payload = dict(run_payload.get("result", {}))
    response = {
        "action": run_payload["action"],
        "label": run_payload["action_label"],
        "project_id": run_payload["project_id"],
        "project_root": run_payload["project_root"],
        "episode_code": run_payload["episode_code"],
        "status": "completed" if run_payload["status"] == "succeeded" else run_payload["status"],
        "run_id": run_payload["run_id"],
        "run_status": run_payload["status"],
        "current_step_key": run_payload["current_step_key"],
        "step_count": int(run_payload.get("step_count", 0)),
        "completed_step_count": int(run_payload.get("completed_step_count", 0)),
        "submitted_at": run_payload["submitted_at"],
        "started_at": run_payload["started_at"],
        "completed_at": run_payload["completed_at"],
        "error_code": run_payload["error_code"],
        "error_detail": run_payload["error_detail"],
        "revision_summary": dict(run_payload["spec"].get("authoring_revision_summary", {})),
        "artifacts": run_payload.get("artifacts", []),
    }
    response.update(result_payload)
    return response


def submit_creator_action_run(
    settings: WebSettings,
    user_id: str,
    action: str,
    project_id: str = "",
    episode_code: str = "",
) -> dict[str, Any]:
    if action not in ACTION_STEP_PLANS:
        raise UnsupportedCreatorActionError(f"不支持的 Creator 动作：{action}")
    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    resolved_project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    resolved_episode_code = select_episode_code(documents, episode_code)
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    ensure_pipeline_run_schema(connection)
    try:
        ensure_project_owner(connection, resolved_project_id, project_root, user_id)
        revision_summary = load_authoring_revision_summary(connection, project_root, resolved_project_id)
        spec = build_run_spec(
            resolved_project_id,
            project_root,
            resolved_episode_code,
            action,
            revision_summary,
            user_id,
        )
        recipe = build_run_recipe(settings, project_root, documents, action=action)
        connection.execute("BEGIN IMMEDIATE")
        active_run = find_active_run(connection, resolved_project_id, resolved_episode_code)
        if active_run is not None:
            connection.rollback()
            raise SingleFlightConflictError(active_run["run_id"], resolved_episode_code)
        run_id = insert_pipeline_run(
            connection,
            user_id,
            resolved_project_id,
            project_root,
            resolved_episode_code,
            action,
            spec,
            recipe,
        )
        recipe["current_run_id"] = run_id
        connection.execute(
            """
            UPDATE pipeline_runs
            SET recipe_json = ?
            WHERE run_id = ?
            """,
            (dumps_json(recipe), run_id),
        )
        if connection.in_transaction:
            connection.commit()
        run_payload = execute_pipeline_run(connection, settings, run_id)
        return build_action_run_response(run_payload)
    finally:
        if connection.in_transaction:
            connection.commit()
        connection.close()


def list_creator_runs(
    settings: WebSettings,
    user_id: str,
    project_id: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    project_root = resolve_project_root_by_id(settings, project_id) if project_id else settings.project_root.resolve()
    documents = resolve_project_documents(settings, project_root)
    resolved_project_id = str(documents["project_manifest"].get("project_id", project_root.name))
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    ensure_pipeline_run_schema(connection)
    ensure_project_owner(connection, resolved_project_id, project_root, user_id)
    query = """
        SELECT run_id
        FROM pipeline_runs
        WHERE project_id = ?
    """
    params: list[Any] = [resolved_project_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    query += " ORDER BY submitted_at DESC LIMIT ?"
    params.append(max(1, min(limit, 50)))
    rows = connection.execute(query, tuple(params)).fetchall()
    payload = [load_pipeline_run_detail(connection, str(row[0])) for row in rows]
    connection.close()
    return payload
