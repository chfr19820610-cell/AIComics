from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.checkpoint_store import (
    CHECKPOINT_COMPLETED,
    checkpoint_status,
    resume_from,
)
from aicomic.core.models import ResumeReport
from aicomic.core.pipeline_manifest import get_pipeline_manifest
from aicomic.utils.atomic_io import atomic_write_json


def build_resume_report(
    state_snapshot: dict[str, Any],
    jobs_payload: dict[str, Any],
    dispatch_report: dict[str, Any],
) -> ResumeReport:
    unfinished_episodes = [
        item
        for item in state_snapshot.get("episode_states", [])
        if item.get("status") not in {"assets_ready", "preview_rendered", "release_rendered", "publish_pack_ready", "archived"}
    ]
    unfinished_jobs = [
        item
        for item in jobs_payload.get("jobs", [])
        if item.get("status") not in {"succeeded", "cached", "skipped"}
    ]
    suggested_next_step = "继续补素材并重新运行 scan-assets / render-preview"
    if unfinished_jobs and dispatch_report.get("dispatch_count", 0) > 0:
        suggested_next_step = "优先处理未完成任务，然后同步状态并重试渲染"
    return ResumeReport(
        unfinished_episode_count=len(unfinished_episodes),
        unfinished_job_count=len(unfinished_jobs),
        suggested_next_step=suggested_next_step,
    )


def write_resume_report(path: Path, report: ResumeReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "unfinished_episode_count": report.unfinished_episode_count,
        "unfinished_job_count": report.unfinished_job_count,
        "suggested_next_step": report.suggested_next_step,
    }
    atomic_write_json(path, payload)


def resume_stage_from_checkpoints(state_dir: Path, episode_code: str) -> str | None:
    """基于阶段 checkpoint 决定断点续跑起点（P0-3）。

    规则：沿管线清单顺序，返回第一个 status 不是 completed 的阶段；
    若某门禁阶段卡 awaiting_human，同样返回它（人工批准后放行）。
    若某门禁阶段被直写为 completed 但 human_approved 标志未置位（防绕过），
    也返回它（硬门禁：未批准不得越过）。
    全部 completed 返回 None（无需续跑）。
    """
    try:
        manifest = get_pipeline_manifest()
        step_ids = manifest.step_ids
    except Exception:
        manifest = None
        step_ids = []
    if not step_ids or manifest is None:
        return None
    from aicomic.core.approval_gate import is_stage_approved
    from aicomic.core.pipeline_manifest import PipelineManifestError

    for stage_id in step_ids:
        status = checkpoint_status(state_dir, episode_code, stage_id)
        if status != CHECKPOINT_COMPLETED:
            return stage_id
        # 门禁阶段 completed 但未批准 → 仍视为需续跑/拦截（防直写绕过）
        try:
            if manifest.requires_human_approval(stage_id) and not is_stage_approved(
                state_dir, episode_code, stage_id
            ):
                return stage_id
        except PipelineManifestError:
            continue
    return None


def checkpoint_summary(state_dir: Path, episode_code: str) -> dict[str, str]:
    """返回该集各阶段 checkpoint 状态快照，供 resume/看板展示。"""
    try:
        step_ids = get_pipeline_manifest().step_ids
    except Exception:
        step_ids = []
    result: dict[str, str] = {}
    for stage_id in step_ids:
        status = checkpoint_status(state_dir, episode_code, stage_id)
        result[stage_id] = status or "not_started"
    return result

