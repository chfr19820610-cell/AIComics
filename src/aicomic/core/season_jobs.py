from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.job_builder import build_jobs_from_episode_manifest
from aicomic.utils.atomic_io import atomic_write_json


def build_season_job_bundle(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
) -> dict[str, Any]:
    jobs = build_jobs_from_episode_manifest(episode_manifest)
    per_episode_counts: dict[str, int] = {}
    for job in jobs:
        per_episode_counts[job.episode_code] = per_episode_counts.get(job.episode_code, 0) + 1

    return {
        "project_id": season_manifest["project_id"],
        "season": season_manifest["season"],
        "season_title": season_manifest["season_title"],
        "episode_count": len(season_manifest.get("episodes", [])),
        "job_count": len(jobs),
        "per_episode_job_count": per_episode_counts,
        "jobs": [
            {
                "job_id": job.job_id,
                "episode_code": job.episode_code,
                "job_type": job.job_type,
                "provider": job.provider,
                "status": job.status,
            }
            for job in jobs
        ],
    }


def write_season_job_bundle(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)

