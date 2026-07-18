from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from aicomic.core.models import DispatchDecision, JobRecord
from aicomic.utils.atomic_io import atomic_write_json


def resolve_dispatch_channel(provider: str) -> tuple[str, str]:
    if provider == "manual_web":
        return "manual", "web_tasks"
    if provider in {"windows_tts", "local_piper_tts"}:
        return "local", "tts_local"
    if provider == "local_comfyui_image":
        return "local", "image_local"
    if provider == "local_comfyui_video":
        return "local", "video_local"
    return "api", "default_api"


def dispatch_jobs(jobs: list[JobRecord]) -> list[DispatchDecision]:
    decisions: list[DispatchDecision] = []
    for job in jobs:
        channel, queue_name = resolve_dispatch_channel(job.provider)
        decisions.append(
            DispatchDecision(
                job_id=job.job_id,
                episode_code=job.episode_code,
                provider=job.provider,
                dispatch_channel=channel,
                queue_name=queue_name,
            )
        )
    return decisions


def write_dispatch_report(path: Path, decisions: list[DispatchDecision]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dispatch_count": len(decisions),
        "dispatches": [asdict(item) for item in decisions],
    }
    atomic_write_json(path, payload)
