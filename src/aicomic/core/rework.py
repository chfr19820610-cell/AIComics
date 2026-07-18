from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.models import JobRecord
from aicomic.utils.atomic_io import atomic_write_json


def select_rework_jobs(jobs: list[JobRecord], episode_code: str, shot_ids: set[str]) -> list[JobRecord]:
    rework_jobs: list[JobRecord] = []
    for job in jobs:
        if job.episode_code != episode_code:
            continue
        matched_shot = any(f"_{shot_id}_" in job.job_id for shot_id in shot_ids)
        if matched_shot:
            rework_jobs.append(
                JobRecord(
                    job_id=job.job_id,
                    episode_code=job.episode_code,
                    job_type=job.job_type,
                    provider=job.provider,
                    status="queued",
                )
            )
    return rework_jobs


def build_rework_report(
    manifest: dict[str, Any],
    episode_code: str,
    shot_ids: set[str],
    rework_jobs: list[JobRecord],
) -> dict[str, Any]:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    selected_shots = [shot for shot in episode.get("shots", []) if str(shot["shot_id"]) in shot_ids]
    return {
        "episode_code": episode_code,
        "requested_shot_ids": sorted(shot_ids),
        "selected_shot_count": len(selected_shots),
        "selected_shots": selected_shots,
        "rework_job_count": len(rework_jobs),
        "rework_job_ids": [job.job_id for job in rework_jobs],
        "suggested_next_step": "重新生成这些镜头素材后，执行 sync-states / render-preview / render-release",
    }


def write_rework_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, report)
