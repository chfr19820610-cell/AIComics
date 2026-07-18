from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.creator_bootstrap import (
    build_character_bible,
    build_creator_profile,
    build_episode_blueprint,
    build_prompt_pack_template,
    build_story_bible,
    build_style_bible,
)
from aicomic.core.manifest import write_json
from aicomic.core.project_initializer import initialize_project
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.creator_runtime_service import (
    ProjectNotFoundError,
    ensure_creator_runtime_schema,
    load_authoring_revision_summary,
    synchronize_project_runtime,
    write_json_document_with_revision,
)
from web.backend.settings import WebSettings


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def discover_project_roots(settings: WebSettings) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()

    def append(root: Path) -> None:
        resolved = root.resolve()
        if resolved in seen:
            return
        if not (resolved / "manifests" / "project_manifest.json").exists():
            return
        seen.add(resolved)
        roots.append(resolved)

    append(settings.project_root)
    generated_root = settings.state_dir / "generated_projects"
    if generated_root.exists():
        for manifest_path in sorted(generated_root.glob("*/manifests/project_manifest.json")):
            append(manifest_path.parents[1])
    return roots


def resolve_project_root_by_id(settings: WebSettings, project_id: str = "") -> Path:
    if not project_id:
        return settings.project_root.resolve()
    for root in discover_project_roots(settings):
        project_manifest = read_json(root / "manifests" / "project_manifest.json")
        if str(project_manifest.get("project_id", "")) == project_id:
            return root.resolve()
    raise ProjectNotFoundError(f"未找到项目 `{project_id}`。")


def load_project_runtime_metadata(project_root: Path, project_id: str, user_id: str = "") -> dict[str, Any]:
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    try:
        return synchronize_project_runtime(connection, project_root, project_id, user_id)
    finally:
        connection.close()


def load_recent_project_runs(project_id: str, user_id: str = "", limit: int = 6) -> list[dict[str, Any]]:
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    try:
        table_row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pipeline_runs'"
        ).fetchone()
        if table_row is None:
            return []
        query = """
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
                submitted_at,
                started_at,
                completed_at,
                error_code,
                error_detail,
                result_json
            FROM pipeline_runs
            WHERE project_id = ?
        """
        params: list[Any] = [project_id]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY submitted_at DESC LIMIT ?"
        params.append(max(1, min(limit, 20)))
        rows = connection.execute(query, tuple(params)).fetchall()
        if not rows:
            return []
        run_ids = [str(row[0]) for row in rows]
        placeholders = ", ".join("?" for _ in run_ids)
        step_counts_by_run: dict[str, dict[str, int]] = {}
        for step_row in connection.execute(
            f"""
            SELECT
                run_id,
                COUNT(*) AS step_count,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS completed_step_count
            FROM pipeline_run_steps
            WHERE run_id IN ({placeholders})
            GROUP BY run_id
            """,
            tuple(run_ids),
        ).fetchall():
            step_counts_by_run[str(step_row[0])] = {
                "step_count": int(step_row[1] or 0),
                "completed_step_count": int(step_row[2] or 0),
            }
        artifacts_by_run: dict[str, list[dict[str, Any]]] = {run_id: [] for run_id in run_ids}
        for artifact_row in connection.execute(
            f"""
            SELECT
                run_id,
                artifact_id,
                artifact_key,
                artifact_type,
                artifact_role,
                artifact_status,
                output_path,
                metadata_json,
                created_at
            FROM pipeline_artifacts
            WHERE run_id IN ({placeholders})
            ORDER BY created_at ASC
            """,
            tuple(run_ids),
        ).fetchall():
            artifacts_by_run.setdefault(str(artifact_row[0]), []).append(
                {
                    "artifact_id": str(artifact_row[1]),
                    "artifact_key": str(artifact_row[2]),
                    "artifact_type": str(artifact_row[3]),
                    "artifact_role": str(artifact_row[4]),
                    "artifact_status": str(artifact_row[5]),
                    "output_path": str(artifact_row[6]),
                    "metadata": json.loads(str(artifact_row[7] or "{}")),
                    "created_at": str(artifact_row[8]),
                }
            )
        payload: list[dict[str, Any]] = []
        for row in rows:
            run_id = str(row[0])
            step_counts = step_counts_by_run.get(run_id, {})
            payload.append(
                {
                    "run_id": run_id,
                    "user_id": str(row[1]),
                    "project_id": str(row[2]),
                    "project_root": str(row[3]),
                    "episode_code": str(row[4]),
                    "action": str(row[5]),
                    "action_label": str(row[6]),
                    "status": str(row[7]),
                    "current_step_key": str(row[8]),
                    "submitted_at": str(row[9]),
                    "started_at": str(row[10]),
                    "completed_at": str(row[11]),
                    "error_code": str(row[12]),
                    "error_detail": str(row[13]),
                    "step_count": int(step_counts.get("step_count", 0)),
                    "completed_step_count": int(step_counts.get("completed_step_count", 0)),
                    "result": json.loads(str(row[14] or "{}")),
                    "artifacts": artifacts_by_run.get(run_id, []),
                }
            )
        return payload
    finally:
        connection.close()


def resolve_project_io_roots(settings: WebSettings, project_root: Path) -> tuple[Path, Path]:
    if project_root.resolve() == settings.project_root.resolve():
        return settings.state_dir, settings.reports_dir
    return project_root / "state", project_root / "reports"


def resolve_project_documents(settings: WebSettings, project_root: Path) -> dict[str, Any]:
    manifests_dir = project_root / "manifests"
    docs_dir = project_root / "docs"
    prompts_dir = project_root / "prompts"
    publish_dir = project_root / "publish"
    state_dir, reports_dir = resolve_project_io_roots(settings, project_root)
    validation_report = read_json(reports_dir / "creator_validation_report.json")
    if not validation_report:
        validation_report = read_json(reports_dir / "demo_validation_report.json")
    return {
        "project_root": project_root,
        "manifests_dir": manifests_dir,
        "docs_dir": docs_dir,
        "prompts_dir": prompts_dir,
        "publish_dir": publish_dir,
        "state_dir": state_dir,
        "reports_dir": reports_dir,
        "project_manifest": read_json(manifests_dir / "project_manifest.json"),
        "season_manifest": read_json(manifests_dir / "season_manifest.json"),
        "episode_manifest": read_json(manifests_dir / "episode_manifest.json"),
        "story_bible": read_json(docs_dir / "creator_story_bible.json"),
        "character_bible": read_json(docs_dir / "character_bible.json"),
        "style_bible": read_json(docs_dir / "style_bible.json"),
        "episode_blueprint": read_json(docs_dir / "episode_blueprint.json"),
        "prompt_pack": read_json(prompts_dir / "prompt_pack_template.json"),
        "horror_story_blueprint": read_json(docs_dir / "horror_story_blueprint.json"),
        "horror_regeneration_queue": read_json(reports_dir / "horror_regeneration_queue_E01.json"),
        "release_checklist": read_text(publish_dir / "release_checklist.md"),
        "jobs_payload": read_json(project_root / "jobs" / "episode_jobs.json"),
        "validation_report": validation_report,
        "review_metrics": read_json(reports_dir / "review_metrics.json"),
    }


def compute_job_distribution(job_payload: dict[str, Any]) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, Any]]]:
    distribution: dict[str, dict[str, int]] = {}
    episode_states: dict[str, dict[str, Any]] = {}
    jobs = job_payload.get("jobs", [])
    for job in jobs if isinstance(jobs, list) else []:
        episode_code = str(job.get("episode_code", ""))
        if not episode_code:
            continue
        status = str(job.get("status", "pending")) or "pending"
        episode_distribution = distribution.setdefault(episode_code, {})
        episode_distribution[status] = int(episode_distribution.get(status, 0)) + 1
        state = episode_states.setdefault(
            episode_code,
            {
                "episode_code": episode_code,
                "completed_jobs": 0,
                "total_jobs": 0,
                "status": "planning",
            },
        )
        state["total_jobs"] = int(state["total_jobs"]) + 1
        if status == "succeeded":
            state["completed_jobs"] = int(state["completed_jobs"]) + 1
    for state in episode_states.values():
        total_jobs = int(state["total_jobs"])
        completed_jobs = int(state["completed_jobs"])
        if total_jobs <= 0:
            state["status"] = "planning"
        elif completed_jobs >= total_jobs:
            state["status"] = "assets_ready"
        elif completed_jobs > 0:
            state["status"] = "in_progress"
        else:
            state["status"] = "queued"
    return distribution, episode_states


def build_episode_items(documents: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = documents["episode_manifest"].get("episodes", [])
    validation_states = documents["validation_report"].get("episode_states", {})
    job_status_by_episode = documents["validation_report"].get("job_status_by_episode", {})
    jobs_payload_distribution, jobs_payload_states = compute_job_distribution(documents["jobs_payload"])
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    reports_dir = Path(documents["reports_dir"])
    items: list[dict[str, Any]] = []
    for item in episodes if isinstance(episodes, list) else []:
        episode_code = str(item.get("episode_code", ""))
        shots = item.get("shots", [])
        total_duration = sum(int(shot.get("duration", 0) or 0) for shot in shots if isinstance(shot, dict))
        ai_video_shot_count = sum(1 for shot in shots if isinstance(shot, dict) and bool(shot.get("ai_video")))
        shot_count = len(shots) if isinstance(shots, list) else 0
        completed_jobs = 0
        total_jobs = 0
        current_status = str(item.get("status", "planning"))
        if isinstance(validation_states, dict) and episode_code in validation_states:
            validation_state = validation_states[episode_code]
            completed_jobs = int(validation_state.get("completed_jobs", 0))
            total_jobs = int(validation_state.get("total_jobs", 0))
            current_status = str(validation_state.get("status", current_status))
        elif episode_code in jobs_payload_states:
            payload_state = jobs_payload_states[episode_code]
            completed_jobs = int(payload_state.get("completed_jobs", 0))
            total_jobs = int(payload_state.get("total_jobs", 0))
            current_status = str(payload_state.get("status", current_status))
        items.append(
            {
                "episode_code": episode_code,
                "title": str(item.get("title", episode_code)),
                "status": current_status,
                "completed_jobs": completed_jobs,
                "total_jobs": total_jobs,
                "shot_count": shot_count,
                "total_duration_seconds": total_duration,
                "publish_title": str(item.get("publish_title", "")),
                "cover_text": str(item.get("cover_text", "")),
                "creator_goal": str(item.get("creator_goal", "")),
                "ending_hook": str(item.get("ending_hook", "")),
                "ai_video_shot_count": ai_video_shot_count,
                "static_shot_count": max(shot_count - ai_video_shot_count, 0),
                "preview_exists": (preview_dir / f"{episode_code}_preview.mp4").exists(),
                "release_exists": (preview_dir / f"{episode_code}_release.mp4").exists(),
                "publish_pack_exists": (reports_dir / f"publish_pack_{episode_code}.json").exists(),
                "job_status_distribution": job_status_by_episode.get(episode_code, jobs_payload_distribution.get(episode_code, {})),
                "shots": shots if isinstance(shots, list) else [],
            }
        )
    return items


def build_project_summary(settings: WebSettings, project_root: Path, user_id: str = "") -> dict[str, Any]:
    documents = resolve_project_documents(settings, project_root)
    project_manifest = documents["project_manifest"]
    season_manifest = documents["season_manifest"]
    creator_profile = project_manifest.get("creator_profile", {})
    episode_items = build_episode_items(documents)
    episode_blueprint = documents["episode_blueprint"]
    project_id = str(project_manifest.get("project_id", project_root.name))
    runtime_metadata = load_project_runtime_metadata(project_root, project_id, user_id=user_id)
    shot_count = sum(int(item.get("shot_count", 0)) for item in episode_items)
    total_duration = sum(int(item.get("total_duration_seconds", 0)) for item in episode_items)
    preview_ready_count = sum(1 for item in episode_items if item.get("preview_exists"))
    publish_ready_count = sum(1 for item in episode_items if item.get("publish_pack_exists"))
    planned_episode_count = int(episode_blueprint.get("episode_target_count", 0) or creator_profile.get("episode_target_count", 0) or len(episode_items))
    return {
        "project_id": project_id,
        "project_name": str(project_manifest.get("project_name", project_root.name)),
        "genre": str(project_manifest.get("genre", "")),
        "style_profile": str(project_manifest.get("style_profile", creator_profile.get("style_profile", ""))),
        "status": str(project_manifest.get("status", "unknown")),
        "logline": str(creator_profile.get("logline", "")),
        "protagonist_name": str(creator_profile.get("protagonist_name", "")),
        "target_audience": str(creator_profile.get("target_audience", "")),
        "tone": str(creator_profile.get("tone", "")),
        "season_hook": str(creator_profile.get("season_hook", season_manifest.get("creator_plan", {}).get("season_hook", ""))),
        "target_platforms": list(project_manifest.get("target_platforms", [])),
        "project_root": str(project_root),
        "source": "workspace" if project_root.resolve() == settings.project_root.resolve() else "generated_project",
        "episode_count": len(episode_items),
        "planned_episode_count": planned_episode_count,
        "shot_count": shot_count,
        "total_duration_seconds": total_duration,
        "preview_ready_count": preview_ready_count,
        "publish_ready_count": publish_ready_count,
        "completion_rate": round((preview_ready_count / len(episode_items)) * 100, 1) if episode_items else 0.0,
        "has_story_bible": bool(documents["story_bible"]) or bool(creator_profile),
        "has_character_bible": bool(documents["character_bible"]),
        "has_style_bible": bool(documents["style_bible"]) or bool(project_manifest.get("style_profile")),
        "owner_user_id": str(runtime_metadata.get("owner", {}).get("user_id", "")),
    }


def load_projects(settings: WebSettings, user_id: str = "") -> dict[str, Any]:
    items = [build_project_summary(settings, root, user_id=user_id) for root in discover_project_roots(settings)]
    items.sort(key=lambda item: (0 if item["source"] == "workspace" else 1, item["project_name"]))
    return {
        "items": items,
        "count": len(items),
        "active_project_id": items[0]["project_id"] if items else "",
        "generated_projects_root": str(settings.state_dir / "generated_projects"),
    }


def build_creator_steps(documents: dict[str, Any], project_summary: dict[str, Any], episode_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    job_payload = documents["jobs_payload"]
    validation_report = documents["validation_report"]
    total_jobs = len(job_payload.get("jobs", [])) if isinstance(job_payload.get("jobs", []), list) else 0
    preview_ready_count = sum(1 for item in episode_items if item.get("preview_exists"))
    publish_ready_count = sum(1 for item in episode_items if item.get("publish_pack_exists"))

    steps = [
        {
            "key": "project_setup",
            "title": "项目初始化",
            "status": "done",
            "detail": f"项目已创建，根目录 {project_summary['project_root']}",
        },
        {
            "key": "story_bible",
            "title": "世界观/角色/风格",
            "status": "done" if project_summary["has_story_bible"] and project_summary["has_style_bible"] else "current",
            "detail": "补齐故事圣经、角色卡和风格模板，后续 Prompt 才能稳定。",
        },
        {
            "key": "episode_outline",
            "title": "分集规划",
            "status": "done" if episode_items else "current",
            "detail": f"已规划 {len(episode_items)} 集，目标 {project_summary['planned_episode_count']} 集。",
        },
        {
            "key": "shot_breakdown",
            "title": "镜头拆解",
            "status": "done" if project_summary["shot_count"] > 0 else "current",
            "detail": f"当前已拆 {project_summary['shot_count']} 个镜头。",
        },
        {
            "key": "asset_generation",
            "title": "素材生产",
            "status": "done" if total_jobs > 0 and int(validation_report.get("succeeded_jobs_count", 0)) >= total_jobs else ("current" if total_jobs > 0 else "pending"),
            "detail": f"任务总数 {total_jobs}，成功任务 {int(validation_report.get('succeeded_jobs_count', 0))}。",
        },
        {
            "key": "preview_render",
            "title": "预览渲染",
            "status": "done" if preview_ready_count == len(episode_items) and episode_items else ("current" if preview_ready_count > 0 else "pending"),
            "detail": f"已导出 {preview_ready_count}/{len(episode_items)} 集预览。",
        },
        {
            "key": "publish_pack",
            "title": "发布包",
            "status": "done" if publish_ready_count == len(episode_items) and episode_items else ("current" if publish_ready_count > 0 else "pending"),
            "detail": f"已生成 {publish_ready_count}/{len(episode_items)} 集发布包。",
        },
    ]
    return steps


def build_creator_deliverables(documents: dict[str, Any], episode_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview_dir = Path(documents["state_dir"]) / "preview_outputs"
    reports_dir = Path(documents["reports_dir"])
    deliverables = [
        {
            "key": "horror_story_blueprint",
            "label": "恐怖故事蓝图",
            "path": str(Path(documents["docs_dir"]) / "horror_story_blueprint.json"),
            "exists": bool(documents.get("horror_story_blueprint")),
            "stage": "story",
        },
        {
            "key": "review_metrics",
            "label": "复盘报告",
            "path": str(reports_dir / "review_metrics.json"),
            "exists": (reports_dir / "review_metrics.json").exists(),
            "stage": "review",
        },
        {
            "key": "horror_regeneration_queue",
            "label": "恐怖重生成队列",
            "path": str(reports_dir / "horror_regeneration_queue_E01.json"),
            "exists": bool(documents.get("horror_regeneration_queue")),
            "stage": "review",
        },
        {
            "key": "dashboard",
            "label": "Dashboard",
            "path": str(reports_dir / "dashboard.json"),
            "exists": (reports_dir / "dashboard.json").exists(),
            "stage": "overview",
        },
        {
            "key": "release_checklist",
            "label": "发布检查单",
            "path": str(Path(documents["publish_dir"]) / "release_checklist.md"),
            "exists": bool(documents["release_checklist"]),
            "stage": "publish",
        },
    ]
    for item in episode_items:
        episode_code = str(item["episode_code"])
        deliverables.extend(
            [
                {
                    "key": f"{episode_code}_preview",
                    "label": f"{episode_code} 预览视频",
                    "path": str(preview_dir / f"{episode_code}_preview.mp4"),
                    "exists": bool(item.get("preview_exists")),
                    "stage": "preview",
                },
                {
                    "key": f"{episode_code}_release",
                    "label": f"{episode_code} 正式版视频",
                    "path": str(preview_dir / f"{episode_code}_release.mp4"),
                    "exists": bool(item.get("release_exists")),
                    "stage": "release",
                },
                {
                    "key": f"{episode_code}_publish_pack",
                    "label": f"{episode_code} 发布包",
                    "path": str(reports_dir / f"publish_pack_{episode_code}.json"),
                    "exists": bool(item.get("publish_pack_exists")),
                    "stage": "publish",
                },
            ]
        )
    return deliverables


def build_creator_next_actions(documents: dict[str, Any], project_summary: dict[str, Any], episode_items: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    if not project_summary["has_story_bible"]:
        actions.append("先补齐故事圣经和角色关系，这会直接影响后续分镜与 Prompt 稳定性。")
    if project_summary["shot_count"] == 0:
        actions.append("先为 E01 拆出 8-12 个镜头，再进入素材生产。")
    if not documents["jobs_payload"]:
        actions.append("执行 build-jobs，把剧本/镜头转成 image、video、tts、subtitle、render 任务包。")
    if documents["jobs_payload"] and not any(item.get("preview_exists") for item in episode_items):
        actions.append("素材回写后先导出预览视频，优先看节奏与钩子是否成立。")
    if any(item.get("preview_exists") for item in episode_items) and not any(item.get("publish_pack_exists") for item in episode_items):
        actions.append("正式版样片审核通过后，再生成发布包或执行一键过审导出。")
    if not actions:
        actions.append("Creator 个人闭环已经跑通，可以开始复制模板做下一集或下一季。")
    return actions


def load_creator_workspace(settings: WebSettings, project_id: str = "", user_id: str = "") -> dict[str, Any]:
    active_root = resolve_project_root_by_id(settings, project_id)

    documents = resolve_project_documents(settings, active_root)
    resolved_project_id = str(documents["project_manifest"].get("project_id", active_root.name))
    runtime_metadata = load_project_runtime_metadata(active_root, resolved_project_id, user_id=user_id)
    project_summary = build_project_summary(settings, active_root, user_id=user_id)
    episode_items = build_episode_items(documents)
    steps = build_creator_steps(documents, project_summary, episode_items)
    deliverables = build_creator_deliverables(documents, episode_items)
    story_bible = documents["story_bible"]
    character_bible = documents["character_bible"]
    style_bible = documents["style_bible"]
    episode_blueprint = documents["episode_blueprint"]
    prompt_pack = documents["prompt_pack"]
    return {
        "project": project_summary,
        "production_summary": {
            "episode_count": len(episode_items),
            "planned_episode_count": project_summary["planned_episode_count"],
            "shot_count": project_summary["shot_count"],
            "total_duration_seconds": project_summary["total_duration_seconds"],
            "preview_ready_count": sum(1 for item in episode_items if item.get("preview_exists")),
            "publish_ready_count": sum(1 for item in episode_items if item.get("publish_pack_exists")),
            "completion_rate": project_summary["completion_rate"],
        },
        "steps": steps,
        "episodes": episode_items,
        "deliverables": deliverables,
        "story_bible_summary": {
            "exists": bool(story_bible) or bool(project_summary["has_story_bible"]),
            "concept_logline": str(story_bible.get("concept_logline", project_summary.get("logline", ""))),
            "core_conflict": str(story_bible.get("core_conflict", "")),
            "tone_keywords": list(story_bible.get("tone_keywords", [])),
        },
        "character_bible_summary": {
            "exists": bool(character_bible),
            "count": len(character_bible.get("characters", [])) if isinstance(character_bible.get("characters", []), list) else 0,
            "names": [str(item.get("name", "")) for item in character_bible.get("characters", []) if isinstance(item, dict)],
        },
        "style_bible_summary": {
            "exists": bool(style_bible) or bool(project_summary["has_style_bible"]),
            "style_profile": str(style_bible.get("style_profile", project_summary.get("style_profile", ""))),
            "aspect_ratio": str(style_bible.get("aspect_ratio", "9:16")),
            "visual_direction": list(style_bible.get("visual_direction", [])),
        },
        "episode_blueprint_summary": {
            "exists": bool(episode_blueprint),
            "episode_target_count": int(episode_blueprint.get("episode_target_count", project_summary["planned_episode_count"])),
            "arc_count": len(episode_blueprint.get("arcs", [])) if isinstance(episode_blueprint.get("arcs", []), list) else 0,
        },
        "prompt_pack_summary": {
            "exists": bool(prompt_pack),
            "image_prompt_template": str(prompt_pack.get("image_prompt_template", "")),
            "video_prompt_template": str(prompt_pack.get("video_prompt_template", "")),
        },
        "release_checklist_exists": bool(documents["release_checklist"]),
        "next_actions": build_creator_next_actions(documents, project_summary, episode_items),
        "revision_summary": runtime_metadata.get("revision_summary", {}),
        "recent_runs": load_recent_project_runs(resolved_project_id, user_id=user_id, limit=6),
        "action_catalog": [
            {
                "key": "generate_horror_sample",
                "label": "生成恐怖样片",
                "description": "按玄学/民俗恐怖模板生成 5-10 分钟样片镜头、任务、请求和正式版审核基线。",
            },
            {
                "key": "autopilot_candidate_release",
                "label": "启动自动驾驶",
                "description": "自动完成真实资产、自动修复、自动审片并生成候选片，人工只保留最终放行。",
            },
            {
                "key": "run_horror_assets_live",
                "label": "执行真实资产",
                "description": "受限执行本地 ComfyUI/Piper 请求，默认最多 6 个请求，失败后生成重试依据。",
            },
            {
                "key": "auto_repair_episode",
                "label": "继续自动修",
                "description": "针对当前重生成队列自动补跑有限镜头，并刷新回写与重生成结果。",
            },
            {
                "key": "auto_review_episode",
                "label": "自动审片",
                "description": "根据当前质量报告、重生成队列和正式版状态执行规则审片。",
            },
            {
                "key": "build_horror_regeneration_queue",
                "label": "生成重生成队列",
                "description": "根据 Provider 回写和执行报告列出需要重试或手工处理的镜头。",
            },
            {
                "key": "build_candidate_publish_pack",
                "label": "生成候选发布包",
                "description": "在未人工过审前生成候选标题、封面文案和描述，用于候选片签发。",
            },
            {
                "key": "generate_horror_blueprint",
                "label": "生成恐怖蓝图",
                "description": "根据项目设定生成 5 幕玄学/民俗恐怖故事蓝图。",
            },
            {
                "key": "build_horror_episode",
                "label": "生成恐怖镜头",
                "description": "把恐怖故事蓝图转成 40-60 个镜头的 Episode Manifest。",
            },
            {
                "key": "build_jobs",
                "label": "生成任务包",
                "description": "把当前剧集和镜头清单转换成 image / video / tts 任务。",
            },
            {
                "key": "build_provider_requests",
                "label": "生成 Provider 请求包",
                "description": "按当前任务包生成图片、视频和 TTS 的请求清单。",
            },
            {
                "key": "scan_assets",
                "label": "扫描素材状态",
                "description": "检查当前剧集素材是否缺失。",
            },
            {
                "key": "render_preview",
                "label": "渲染预览",
                "description": "基于现有素材或占位帧导出预览视频。",
            },
            {
                "key": "render_release",
                "label": "渲染正式版",
                "description": "基于当前素材或占位帧导出正式版竖屏视频。",
            },
            {
                "key": "build_publish_pack",
                "label": "生成发布包",
                "description": "输出标题、封面文案、简介和平台文案。",
                "requires_review_approval": True,
            },
            {
                "key": "export_approved_release",
                "label": "过审后一键导出",
                "description": "仅在样片审核 approved 后执行：重新导出正式版、发布包并刷新报告。",
                "requires_review_approval": True,
            },
            {
                "key": "confirm_candidate_publish",
                "label": "确认发布",
                "description": "将候选片转为已放行状态，并执行正式导出、发布包和审计写回。",
            },
            {
                "key": "refresh_creator_reports",
                "label": "刷新 Creator 报告",
                "description": "重建 Creator validation、Dashboard 与 Review 报告。",
            },
        ],
        "source_paths": {
            "project_root": str(active_root),
            "project_manifest": str(Path(documents["manifests_dir"]) / "project_manifest.json"),
            "season_manifest": str(Path(documents["manifests_dir"]) / "season_manifest.json"),
            "episode_manifest": str(Path(documents["manifests_dir"]) / "episode_manifest.json"),
            "story_bible": str(Path(documents["docs_dir"]) / "creator_story_bible.json"),
            "character_bible": str(Path(documents["docs_dir"]) / "character_bible.json"),
            "style_bible": str(Path(documents["docs_dir"]) / "style_bible.json"),
            "episode_blueprint": str(Path(documents["docs_dir"]) / "episode_blueprint.json"),
            "horror_story_blueprint": str(Path(documents["docs_dir"]) / "horror_story_blueprint.json"),
            "prompt_pack": str(Path(documents["prompts_dir"]) / "prompt_pack_template.json"),
            "release_checklist": str(Path(documents["publish_dir"]) / "release_checklist.md"),
        },
    }


def create_creator_project(settings: WebSettings, payload: dict[str, Any], actor_user_id: str = "") -> dict[str, Any]:
    project = initialize_project(
        settings.state_dir / "generated_projects",
        str(payload.get("project_name", "")).strip() or "未命名 Creator 项目",
        str(payload.get("genre", "现代都市短剧")),
        str(payload.get("style_profile", payload.get("style", "动漫漫剧"))),
        str(payload.get("project_id", "")).strip() or None,
        logline=str(payload.get("logline", "一个普通人被卷入高压环境后，靠连续反转赢回主动权。")),
        protagonist_name=str(payload.get("protagonist_name", "女主")),
        target_audience=str(payload.get("target_audience", "短剧用户 / 二次元短视频观众")),
        tone=str(payload.get("tone", "强钩子")),
        season_hook=str(payload.get("season_hook", "结尾必须留下身份、关系或真相反转。")),
        episode_target_count=int(payload.get("episode_target_count", 12) or 12),
    )
    runtime_metadata = load_project_runtime_metadata(
        Path(str(project["project_root"])),
        str(project["project_id"]),
        user_id=actor_user_id,
    )
    return {
        "created": True,
        **project,
        "revision_summary": runtime_metadata.get("revision_summary", {}),
    }


def save_creator_project_profile(
    settings: WebSettings,
    project_id: str,
    payload: dict[str, Any],
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    project_manifest = documents["project_manifest"]
    if not project_manifest:
        raise ValueError("Project manifest not found")
    resolved_project_id = str(project_manifest.get("project_id", project_root.name))

    project_name = str(payload.get("project_name", project_manifest.get("project_name", ""))).strip() or str(project_manifest.get("project_name", project_root.name))
    genre = str(payload.get("genre", project_manifest.get("genre", ""))).strip() or str(project_manifest.get("genre", "现代都市短剧"))
    style_profile = str(payload.get("style_profile", project_manifest.get("style_profile", ""))).strip() or str(project_manifest.get("style_profile", "动漫漫剧"))
    logline = str(payload.get("logline", project_manifest.get("creator_profile", {}).get("logline", ""))).strip()
    protagonist_name = str(payload.get("protagonist_name", project_manifest.get("creator_profile", {}).get("protagonist_name", "女主"))).strip() or "女主"
    target_audience = str(payload.get("target_audience", project_manifest.get("creator_profile", {}).get("target_audience", "短剧用户"))).strip()
    tone = str(payload.get("tone", project_manifest.get("creator_profile", {}).get("tone", "强钩子"))).strip()
    season_hook = str(payload.get("season_hook", project_manifest.get("creator_profile", {}).get("season_hook", ""))).strip()
    episode_target_count = int(payload.get("episode_target_count", project_manifest.get("creator_profile", {}).get("episode_target_count", 12)) or 12)
    target_platforms = payload.get("target_platforms", project_manifest.get("target_platforms", []))
    if not isinstance(target_platforms, list):
        target_platforms = [str(target_platforms)]
    creator_profile = build_creator_profile(
        project_name,
        genre,
        style_profile,
        logline,
        protagonist_name,
        target_audience,
        tone,
        season_hook,
        episode_target_count,
    )
    project_manifest.update(
        {
            "project_name": project_name,
            "genre": genre,
            "style_profile": style_profile,
            "target_platforms": [str(item).strip() for item in target_platforms if str(item).strip()],
            "creator_profile": creator_profile,
        }
    )
    season_manifest = documents["season_manifest"]
    creator_plan = dict(season_manifest.get("creator_plan", {}))
    creator_plan["season_hook"] = season_hook
    creator_plan["episode_target_count"] = episode_target_count
    season_manifest["creator_plan"] = creator_plan

    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    try:
        synchronize_project_runtime(connection, project_root, resolved_project_id, actor_user_id)
        write_json_document_with_revision(
            connection,
            resolved_project_id,
            "project_manifest",
            Path(documents["manifests_dir"]) / "project_manifest.json",
            project_manifest,
            str(payload.get("expected_project_manifest_revision_id", "")),
            actor_user_id or "system_anonymous",
        )
        write_json_document_with_revision(
            connection,
            resolved_project_id,
            "season_manifest",
            Path(documents["manifests_dir"]) / "season_manifest.json",
            season_manifest,
            str(payload.get("expected_season_manifest_revision_id", "")),
            actor_user_id or "system_anonymous",
        )
        revision_summary = load_authoring_revision_summary(connection, project_root, resolved_project_id)
    finally:
        connection.close()
    write_json(Path(documents["docs_dir"]) / "creator_story_bible.json", build_story_bible(project_name, genre, logline, protagonist_name, tone, season_hook))
    write_json(Path(documents["docs_dir"]) / "character_bible.json", build_character_bible(protagonist_name))
    write_json(Path(documents["docs_dir"]) / "style_bible.json", build_style_bible(style_profile, tone))
    write_json(Path(documents["docs_dir"]) / "episode_blueprint.json", build_episode_blueprint(episode_target_count, protagonist_name, season_hook))
    write_json(Path(documents["prompts_dir"]) / "prompt_pack_template.json", build_prompt_pack_template(project_name, genre, style_profile, protagonist_name, tone))
    return {
        "updated": True,
        "project_id": resolved_project_id,
        "project_root": str(project_root),
        "revision_summary": revision_summary,
    }


def upsert_creator_episode(
    settings: WebSettings,
    project_id: str,
    payload: dict[str, Any],
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    project_manifest = documents["project_manifest"]
    resolved_project_id = str(project_manifest.get("project_id", project_root.name))
    episode_manifest = documents["episode_manifest"]
    episodes = episode_manifest.setdefault("episodes", [])
    episode_code = str(payload.get("episode_code", "")).strip() or "E01"
    target_episode: dict[str, Any] | None = None
    for item in episodes if isinstance(episodes, list) else []:
        if str(item.get("episode_code", "")) == episode_code:
            target_episode = item
            break
    if target_episode is None:
        target_episode = {
            "episode_code": episode_code,
            "shots": [],
        }
        episodes.append(target_episode)
    target_episode.update(
        {
            "title": str(payload.get("title", target_episode.get("title", episode_code))).strip() or episode_code,
            "status": str(payload.get("status", target_episode.get("status", "idea"))).strip() or "idea",
            "publish_title": str(payload.get("publish_title", target_episode.get("publish_title", ""))).strip(),
            "cover_text": str(payload.get("cover_text", target_episode.get("cover_text", ""))).strip(),
            "creator_goal": str(payload.get("creator_goal", target_episode.get("creator_goal", ""))).strip(),
            "ending_hook": str(payload.get("ending_hook", target_episode.get("ending_hook", ""))).strip(),
        }
    )
    target_episode.setdefault("shots", [])
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    try:
        synchronize_project_runtime(connection, project_root, resolved_project_id, actor_user_id)
        write_json_document_with_revision(
            connection,
            resolved_project_id,
            "episode_manifest",
            Path(documents["manifests_dir"]) / "episode_manifest.json",
            episode_manifest,
            str(payload.get("expected_episode_manifest_revision_id", "")),
            actor_user_id or "system_anonymous",
        )
        revision_summary = load_authoring_revision_summary(connection, project_root, resolved_project_id)
    finally:
        connection.close()
    return {
        "updated": True,
        "episode_code": episode_code,
        "project_root": str(project_root),
        "revision_summary": revision_summary,
    }


def upsert_creator_shot(
    settings: WebSettings,
    project_id: str,
    payload: dict[str, Any],
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    project_manifest = documents["project_manifest"]
    resolved_project_id = str(project_manifest.get("project_id", project_root.name))
    episode_manifest = documents["episode_manifest"]
    episode_code = str(payload.get("episode_code", "")).strip() or "E01"
    shot_id = str(payload.get("shot_id", "")).strip() or "S01"
    episodes = episode_manifest.get("episodes", [])
    target_episode = next((item for item in episodes if isinstance(item, dict) and str(item.get("episode_code", "")) == episode_code), None)
    if target_episode is None:
        target_episode = {
            "episode_code": episode_code,
            "title": episode_code,
            "status": "idea",
            "publish_title": "",
            "cover_text": "",
            "shots": [],
        }
        episodes.append(target_episode)
        episode_manifest["episodes"] = episodes
    shots = target_episode.setdefault("shots", [])
    target_shot = next((item for item in shots if isinstance(item, dict) and str(item.get("shot_id", "")) == shot_id), None)
    if target_shot is None:
        target_shot = {"shot_id": shot_id}
        shots.append(target_shot)
    characters = payload.get("characters", target_shot.get("characters", []))
    if isinstance(characters, str):
        characters = [item.strip() for item in characters.split(",") if item.strip()]
    if not isinstance(characters, list):
        characters = []
    target_shot.update(
        {
            "shot_id": shot_id,
            "duration": int(payload.get("duration", target_shot.get("duration", 3)) or 3),
            "scene": str(payload.get("scene", target_shot.get("scene", ""))).strip(),
            "characters": [str(item).strip() for item in characters if str(item).strip()],
            "visual": str(payload.get("visual", target_shot.get("visual", ""))).strip(),
            "action": str(payload.get("action", target_shot.get("action", ""))).strip(),
            "dialogue": str(payload.get("dialogue", target_shot.get("dialogue", ""))).strip(),
            "emotion": str(payload.get("emotion", target_shot.get("emotion", ""))).strip(),
            "camera": str(payload.get("camera", target_shot.get("camera", ""))).strip(),
            "ai_video": bool(payload.get("ai_video", target_shot.get("ai_video", False))),
            "priority": str(payload.get("priority", target_shot.get("priority", "medium"))).strip() or "medium",
        }
    )
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    ensure_creator_runtime_schema(connection)
    try:
        synchronize_project_runtime(connection, project_root, resolved_project_id, actor_user_id)
        write_json_document_with_revision(
            connection,
            resolved_project_id,
            "episode_manifest",
            Path(documents["manifests_dir"]) / "episode_manifest.json",
            episode_manifest,
            str(payload.get("expected_episode_manifest_revision_id", "")),
            actor_user_id or "system_anonymous",
        )
        revision_summary = load_authoring_revision_summary(connection, project_root, resolved_project_id)
    finally:
        connection.close()
    return {
        "updated": True,
        "episode_code": episode_code,
        "shot_id": shot_id,
        "project_root": str(project_root),
        "revision_summary": revision_summary,
    }


def delete_creator_shot(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    shot_id: str,
    expected_episode_manifest_revision_id: str = "",
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    documents = resolve_project_documents(settings, project_root)
    project_manifest = documents["project_manifest"]
    resolved_project_id = str(project_manifest.get("project_id", project_root.name))
    episode_manifest = documents["episode_manifest"]
    removed = False
    for episode in episode_manifest.get("episodes", []):
        if not isinstance(episode, dict) or str(episode.get("episode_code", "")) != episode_code:
            continue
        shots = episode.get("shots", [])
        filtered = [item for item in shots if not (isinstance(item, dict) and str(item.get("shot_id", "")) == shot_id)]
        removed = len(filtered) != len(shots)
        episode["shots"] = filtered
        break
    if removed:
        connection = connect_auth_database()
        ensure_auth_schema(connection)
        ensure_creator_runtime_schema(connection)
        try:
            synchronize_project_runtime(connection, project_root, resolved_project_id, actor_user_id)
            write_json_document_with_revision(
                connection,
                resolved_project_id,
                "episode_manifest",
                Path(documents["manifests_dir"]) / "episode_manifest.json",
                episode_manifest,
                expected_episode_manifest_revision_id,
                actor_user_id or "system_anonymous",
            )
            revision_summary = load_authoring_revision_summary(connection, project_root, resolved_project_id)
        finally:
            connection.close()
    else:
        revision_summary = load_project_runtime_metadata(project_root, resolved_project_id, user_id=actor_user_id).get(
            "revision_summary",
            {},
        )
    return {
        "removed": removed,
        "episode_code": episode_code,
        "shot_id": shot_id,
        "project_root": str(project_root),
        "revision_summary": revision_summary,
    }
