from __future__ import annotations

from typing import Any

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from web.backend.auth.auth_middleware import get_request_user, register_auth_middleware
from web.backend.auth.auth_routes import router as auth_router
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, write_audit_log
from web.backend.services.batch_archive_service import (
    cleanup_execution_operations_archives,
    export_execution_operations_report,
    load_execution_operations_archives,
)
from web.backend.services.batch_execution_service import (
    preview_batch_execution_plan,
    queue_batch_execution_plan,
)
from web.backend.services.batch_history_service import (
    get_batch_execution_preview_history_page,
    get_batch_execution_queue_history_page,
    get_batch_retry_history_page,
    update_batch_execution_queue_status_record,
)
from web.backend.services.creator_runtime_service import (
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    RevisionConflictError,
)
from web.backend.services.creator_review_service import (
    load_creator_sample_review,
    resolve_project_asset_path,
    save_creator_sample_review,
)
from web.backend.services.creator_service import (
    create_creator_project,
    delete_creator_shot,
    load_creator_workspace,
    load_projects,
    save_creator_project_profile,
    upsert_creator_episode,
    upsert_creator_shot,
)
from web.backend.services.edition_policy import load_edition_policy
from web.backend.services.edition_service import load_edition_summary
from web.backend.services.pipeline_run_service import (
    SingleFlightConflictError,
    UnsupportedCreatorActionError,
    list_creator_runs,
    submit_creator_action_run,
)
from web.backend.services.report_service import (
    generate_retry_batch_package,
    load_batch_summary,
    load_batches,
    load_dashboard,
    load_episodes,
    load_jobs,
    load_provider_executions,
    load_review_metrics,
    load_validation_report,
)
from web.backend.settings import load_web_settings
from aicomic.characters.routes import build_character_router


app = FastAPI(title="AI漫剧自动生成系统 Web API", version="0.1.0")
settings = load_web_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins) if settings.cors_allow_origins != ("*",) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_auth_middleware(app)
app.include_router(auth_router)

# Character management API
character_router = build_character_router(state_dir=settings.state_dir)
app.include_router(character_router)


# ── Global exception handlers ──────────────────────────────────────────────


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=405, content={"detail": "Method Not Allowed"})


class CreatorProjectCreateRequest(BaseModel):
    project_name: str
    genre: str = "现代都市短剧"
    style_profile: str = "动漫漫剧"
    project_id: str = ""
    logline: str = "一个普通人被卷入高压环境后，靠连续反转赢回主动权。"
    protagonist_name: str = "女主"
    target_audience: str = "短剧用户 / 二次元短视频观众"
    tone: str = "强钩子"
    season_hook: str = "结尾必须留下身份、关系或真相反转。"
    episode_target_count: int = 12


class CreatorProjectProfileRequest(BaseModel):
    project_id: str = ""
    project_name: str
    genre: str
    style_profile: str
    logline: str = ""
    protagonist_name: str = "女主"
    target_audience: str = ""
    tone: str = ""
    season_hook: str = ""
    episode_target_count: int = 12
    target_platforms: list[str] = []
    expected_project_manifest_revision_id: str = ""
    expected_season_manifest_revision_id: str = ""


class CreatorEpisodeRequest(BaseModel):
    project_id: str = ""
    episode_code: str
    title: str
    status: str = "idea"
    publish_title: str = ""
    cover_text: str = ""
    creator_goal: str = ""
    ending_hook: str = ""
    expected_episode_manifest_revision_id: str = ""


class CreatorShotRequest(BaseModel):
    project_id: str = ""
    episode_code: str
    shot_id: str
    duration: int = 3
    scene: str = ""
    characters: list[str] = []
    visual: str = ""
    action: str = ""
    dialogue: str = ""
    emotion: str = ""
    camera: str = ""
    ai_video: bool = False
    priority: str = "medium"
    expected_episode_manifest_revision_id: str = ""


class CreatorShotDeleteRequest(BaseModel):
    project_id: str = ""
    episode_code: str
    shot_id: str
    expected_episode_manifest_revision_id: str = ""


class CreatorActionRunRequest(BaseModel):
    project_id: str = ""
    action: str
    episode_code: str = ""


class CreatorSampleReviewRequest(BaseModel):
    project_id: str = ""
    episode_code: str
    review_status: str = "pending"
    decision_summary: str = ""
    review_notes: str = ""
    issues: list[dict[str, Any]] = []


class BatchRetryGenerateRequest(BaseModel):
    statuses: list[str] = ["failed", "manual_required"]
    episode_code: str = ""
    provider: str = ""
    dry_run: bool = True


class BatchExecutionPlanPreviewRequest(BaseModel):
    plan_key: str
    target: str = ""
    mode: str = "dry_run"


class BatchExecutionPlanQueueRequest(BaseModel):
    plan_key: str
    target: str = ""
    mode: str = "queued"


class BatchExecutionQueueStatusRequest(BaseModel):
    queue_run_id: str
    queue_status: str
    execution_status: str
    result_note: str = ""


class BatchExecutionOperationsExportRequest(BaseModel):
    export_format: str = "json"
    export_scope: str = "operations_report"


class BatchExecutionOperationsArchiveCleanupRequest(BaseModel):
    retention_days: int = 30
    dry_run: bool = True


@app.get("/api/health")
def health() -> dict[str, Any]:
    edition = load_edition_summary()
    policy = load_edition_policy(settings)
    return {
        "status": "ok",
        "project_root": str(settings.project_root),
        "host": settings.host,
        "port": settings.port,
        "auth_enabled": policy.auth_enabled,
        "edition_name": edition["edition_name"],
        "edition_display_name": edition["display_name"],
    }


@app.get("/api/edition")
def edition() -> dict[str, Any]:
    summary = load_edition_summary()
    summary["policy"] = load_edition_policy(settings).to_dict()
    return summary


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return load_dashboard(settings)


def current_user_id(request: Request) -> str:
    current_user = get_request_user(request)
    return str(current_user["user_id"]) if current_user else ""


@app.get("/api/projects")
def projects(request: Request) -> dict[str, Any]:
    return load_projects(settings, user_id=current_user_id(request))


@app.get("/api/creator/workspace")
def creator_workspace(request: Request, project_id: str = Query(default="")) -> dict[str, Any]:
    try:
        return load_creator_workspace(settings, project_id=project_id, user_id=current_user_id(request))
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@app.get("/api/creator/runs")
def creator_runs(request: Request, project_id: str = Query(default=""), limit: int = Query(default=10)) -> dict[str, Any]:
    try:
        items = list_creator_runs(settings, current_user_id(request), project_id=project_id, limit=limit)
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return {
        "items": items,
        "count": len(items),
    }


@app.post("/api/creator/projects")
def creator_projects_create(payload: CreatorProjectCreateRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    result = create_creator_project(settings, payload.model_dump(), actor_user_id=current_user_id(request))
    write_action_audit_log(
        request,
        "creator_project_create",
        "creator_project",
        str(result.get("project_id", "")),
        "success",
        f"project_name={payload.project_name}",
    )
    return result


@app.patch("/api/creator/project-profile")
def creator_project_profile_save(payload: CreatorProjectProfileRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = save_creator_project_profile(
            settings,
            payload.project_id,
            payload.model_dump(),
            actor_user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_project_profile_save",
        "creator_project",
        str(result.get("project_id", "")),
        "success",
        f"project_name={payload.project_name}",
    )
    return result


@app.put("/api/creator/episodes")
def creator_episode_save(payload: CreatorEpisodeRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = upsert_creator_episode(
            settings,
            payload.project_id,
            payload.model_dump(),
            actor_user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_episode_save",
        "creator_episode",
        payload.episode_code,
        "success",
        f"title={payload.title}",
    )
    return result


@app.put("/api/creator/shots")
def creator_shot_save(payload: CreatorShotRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = upsert_creator_shot(
            settings,
            payload.project_id,
            payload.model_dump(),
            actor_user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_shot_save",
        "creator_shot",
        payload.shot_id,
        "success",
        f"episode_code={payload.episode_code}",
    )
    return result


@app.post("/api/creator/shots/delete")
def creator_shot_remove(payload: CreatorShotDeleteRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = delete_creator_shot(
            settings,
            payload.project_id,
            payload.episode_code,
            payload.shot_id,
            expected_episode_manifest_revision_id=payload.expected_episode_manifest_revision_id,
            actor_user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_shot_delete",
        "creator_shot",
        payload.shot_id,
        "success" if result.get("removed") else "failed",
        f"episode_code={payload.episode_code}",
    )
    return result


@app.post("/api/creator/actions/run")
def creator_action_run(payload: CreatorActionRunRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = submit_creator_action_run(
            settings,
            current_user_id(request),
            payload.action,
            project_id=payload.project_id,
            episode_code=payload.episode_code,
        )
    except UnsupportedCreatorActionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except SingleFlightConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_action_run",
        "creator_action",
        payload.action,
        str(result.get("status", "unknown")),
        f"episode_code={payload.episode_code}; project_id={payload.project_id}",
    )
    return result


@app.get("/api/creator/sample-review")
def creator_sample_review(request: Request, project_id: str = Query(default=""), episode_code: str = Query(default="E01")) -> dict[str, Any]:
    try:
        return load_creator_sample_review(
            settings,
            project_id=project_id,
            episode_code=episode_code,
            user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@app.put("/api/creator/sample-review")
def creator_sample_review_save(payload: CreatorSampleReviewRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = save_creator_sample_review(
            settings,
            payload.project_id,
            payload.episode_code,
            payload.model_dump(),
            actor_user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "creator_sample_review_save",
        "creator_sample_review",
        f"{payload.project_id}:{payload.episode_code}",
        "success",
        f"review_status={payload.review_status}",
    )
    return result


@app.get("/api/creator/assets")
def creator_asset_file(request: Request, project_id: str = Query(default=""), path: str = Query(default="")) -> FileResponse:
    try:
        asset_path = resolve_project_asset_path(
            settings,
            project_id=project_id,
            raw_path=path,
            user_id=current_user_id(request),
        )
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"文件不存在：{error.args[0]}") from error
    return FileResponse(asset_path)


@app.get("/api/review-metrics")
def review_metrics() -> dict[str, Any]:
    return load_review_metrics(settings)


@app.get("/api/validation")
def validation() -> dict[str, Any]:
    return load_validation_report(settings)


@app.get("/api/episodes")
def episodes() -> dict[str, Any]:
    return load_episodes(settings)


@app.get("/api/jobs")
def jobs(
    episode_code: str = Query(default=""),
    job_type: str = Query(default=""),
    status: str = Query(default=""),
    provider: str = Query(default=""),
) -> dict[str, Any]:
    return load_jobs(settings, episode_code, job_type, status, provider)


@app.get("/api/batches")
def batches(request: Request) -> dict[str, Any]:
    return load_batches(settings, user_id=current_user_id(request))


@app.get("/api/batches/summary")
def batch_summary(request: Request) -> dict[str, Any]:
    return load_batch_summary(settings, include_history=False, user_id=current_user_id(request))


@app.get("/api/batches/retry-history")
def batch_retry_history(
    request: Request,
    page: int = Query(default=1),
    page_size: int = Query(default=10),
) -> dict[str, Any]:
    return get_batch_retry_history_page(page=page, page_size=page_size, user_id=current_user_id(request))


@app.get("/api/batches/execution-previews")
def batch_execution_previews(
    request: Request,
    page: int = Query(default=1),
    page_size: int = Query(default=10),
) -> dict[str, Any]:
    return get_batch_execution_preview_history_page(page=page, page_size=page_size, user_id=current_user_id(request))


@app.get("/api/batches/execution-queue")
def batch_execution_queue(
    request: Request,
    page: int = Query(default=1),
    page_size: int = Query(default=10),
) -> dict[str, Any]:
    return get_batch_execution_queue_history_page(page=page, page_size=page_size, user_id=current_user_id(request))


@app.post("/api/batches/retry")
def batches_retry_generate(payload: BatchRetryGenerateRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    result = generate_retry_batch_package(
        settings,
        statuses=payload.statuses,
        episode_code=payload.episode_code,
        provider=payload.provider,
        dry_run=payload.dry_run,
    )
    write_action_audit_log(
        request,
        "batch_retry_generate",
        "batch",
        str(result.get("report_output_path", "")),
        "success",
        (
            f"dry_run={payload.dry_run};"
            f" statuses={','.join(payload.statuses)};"
            f" episode_code={payload.episode_code};"
            f" provider={payload.provider};"
            f" retried_count={result.get('retried_count', 0)}"
        ),
    )
    return result


@app.post("/api/batches/execution-plans/preview")
def batches_execution_plan_preview(payload: BatchExecutionPlanPreviewRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    current_user = get_request_user(request)
    user_id = str(current_user["user_id"]) if current_user else "system_anonymous"
    try:
        result = preview_batch_execution_plan(
            settings,
            plan_key=payload.plan_key,
            user_id=user_id,
            target=payload.target,
            mode=payload.mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    write_action_audit_log(
        request,
        "batch_execution_plan_preview",
        "batch_execution_plan",
        str(result.get("preview_run_id", payload.plan_key)),
        "success",
        (
            f"plan_key={payload.plan_key};"
            f" target={result.get('target', payload.target)};"
            f" mode={result.get('mode', payload.mode)};"
            f" priority={result.get('priority', '')};"
            f" requires_manual_approval={result.get('requires_manual_approval', False)}"
        ),
    )
    return result


@app.post("/api/batches/execution-plans/queue")
def batches_execution_plan_queue(payload: BatchExecutionPlanQueueRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    current_user = get_request_user(request)
    user_id = str(current_user["user_id"]) if current_user else "system_anonymous"
    try:
        result = queue_batch_execution_plan(
            settings,
            plan_key=payload.plan_key,
            user_id=user_id,
            target=payload.target,
            mode=payload.mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    write_action_audit_log(
        request,
        "batch_execution_plan_queue",
        "batch_execution_plan",
        str(result.get("queue_run_id", payload.plan_key)),
        "success",
        (
            f"plan_key={payload.plan_key};"
            f" target={result.get('target', payload.target)};"
            f" mode={result.get('mode', payload.mode)};"
            f" priority={result.get('priority', '')};"
            f" queue_status={result.get('queue_status', '')};"
            f" execution_status={result.get('execution_status', '')}"
        ),
    )
    return result


@app.post("/api/batches/execution-plans/queue/status")
def batches_execution_queue_status(payload: BatchExecutionQueueStatusRequest, request: Request) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = update_batch_execution_queue_status_record(
            payload.queue_run_id,
            payload.queue_status,
            payload.execution_status,
            payload.result_note,
            actor_user_id=current_user_id(request),
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    write_action_audit_log(
        request,
        "batch_execution_queue_status_update",
        "batch_execution_queue",
        payload.queue_run_id,
        "success",
        (
            f"queue_status={result.get('queue_status', '')};"
            f" execution_status={result.get('execution_status', '')};"
            f" result_note={payload.result_note}"
        ),
    )
    return result


@app.post("/api/batches/execution-operations/export")
def batches_execution_operations_export(
    payload: BatchExecutionOperationsExportRequest,
    request: Request,
) -> dict[str, Any]:
    ensure_permission(request)
    try:
        result = export_execution_operations_report(
            settings,
            export_format=payload.export_format,
            export_scope=payload.export_scope,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    write_action_audit_log(
        request,
        "batch_execution_operations_export",
        "batch_execution_operations_report",
        str(result.get("export_name", "")),
        "success",
        (
            f"export_scope={payload.export_scope};"
            f" export_format={payload.export_format};"
            f" export_count={result.get('export_count', 0)}"
        ),
    )
    return result


@app.get("/api/batches/execution-archives")
def batches_execution_archives(request: Request, limit: int = Query(default=20)) -> dict[str, Any]:
    ensure_permission(request)
    return load_execution_operations_archives(settings, limit=limit)


@app.post("/api/batches/execution-archives/cleanup")
def batches_execution_archives_cleanup(
    payload: BatchExecutionOperationsArchiveCleanupRequest,
    request: Request,
) -> dict[str, Any]:
    ensure_permission(request)
    result = cleanup_execution_operations_archives(
        settings,
        retention_days=payload.retention_days,
        dry_run=payload.dry_run,
    )
    write_action_audit_log(
        request,
        "batch_execution_operations_archive_cleanup",
        "batch_execution_operations_archive",
        str(result.get("archive_root", "")),
        "success",
        (
            f"retention_days={payload.retention_days};"
            f" dry_run={payload.dry_run};"
            f" eligible_count={result.get('eligible_count', 0)};"
            f" deleted_count={result.get('deleted_count', 0)}"
        ),
    )
    return result


@app.get("/api/providers/executions")
def provider_executions() -> dict[str, Any]:
    return load_provider_executions(settings)


# ── Video preview API ─────────────────────────────────────────────────────


def _resolve_videos_dir() -> Path:
    """Resolve produced_videos/ under the state directory."""
    return settings.state_dir / "produced_videos"


@app.get("/api/videos")
def list_videos() -> dict[str, Any]:
    """List all MP4 files in produced_videos/ with metadata."""
    videos_dir = _resolve_videos_dir()
    if not videos_dir.is_dir():
        return {"items": [], "count": 0}

    items: list[dict[str, Any]] = []
    for entry in sorted(videos_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if entry.suffix.lower() == ".mp4" and not entry.name.startswith("."):
            stat = entry.stat()
            # Resolve symlinks so the stream endpoint gets the real file
            real_path = entry.resolve()
            items.append({
                "filename": entry.name,
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "is_symlink": entry.is_symlink(),
                "real_filename": real_path.name if entry.is_symlink() else None,
            })

    return {"items": items, "count": len(items)}


@app.get("/api/videos/stream/{filename:path}")
def stream_video(filename: str) -> Response:
    """Stream a single MP4 file from produced_videos/ with byte-range support."""
    videos_dir = _resolve_videos_dir()
    # Prevent directory traversal
    safe_path = (videos_dir / filename).resolve()
    if not str(safe_path).startswith(str(videos_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not safe_path.is_file() or safe_path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(str(safe_path), media_type="video/mp4")


def ensure_permission(request: Request) -> None:
    if not load_edition_policy(settings).auth_enabled:
        return
    current_user = get_request_user(request)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")


def write_action_audit_log(
    request: Request,
    action_type: str,
    target_type: str,
    target_id: str,
    result: str,
    detail: str,
) -> None:
    current_user = get_request_user(request)
    user_id = str(current_user["user_id"]) if current_user else "system_anonymous"
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    write_audit_log(connection, user_id, action_type, target_type, target_id, result, detail)
    connection.close()
