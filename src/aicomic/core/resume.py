from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.models import ResumeReport
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

