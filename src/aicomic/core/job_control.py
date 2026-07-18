from __future__ import annotations

import json
from pathlib import Path

from aicomic.core.models import JobRecord
from aicomic.utils.atomic_io import atomic_write_json


def filter_jobs(
    jobs: list[JobRecord],
    episode_code: str | None = None,
    job_type: str | None = None,
    statuses: set[str] | None = None,
) -> list[JobRecord]:
    filtered = jobs
    if episode_code:
        filtered = [job for job in filtered if job.episode_code == episode_code]
    if job_type:
        filtered = [job for job in filtered if job.job_type == job_type]
    if statuses:
        filtered = [job for job in filtered if job.status in statuses]
    return filtered


def retry_jobs(jobs: list[JobRecord], retryable_statuses: set[str]) -> tuple[list[JobRecord], dict[str, int]]:
    updated_jobs: list[JobRecord] = []
    retried_count = 0
    untouched_count = 0
    for job in jobs:
        if job.status in retryable_statuses:
            updated_jobs.append(
                JobRecord(
                    job_id=job.job_id,
                    episode_code=job.episode_code,
                    job_type=job.job_type,
                    provider=job.provider,
                    status="queued",
                )
            )
            retried_count += 1
        else:
            updated_jobs.append(job)
            untouched_count += 1
    return updated_jobs, {"retried_count": retried_count, "untouched_count": untouched_count}


def write_job_payload(path: Path, jobs: list[JobRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "jobs": [
            {
                "job_id": job.job_id,
                "episode_code": job.episode_code,
                "job_type": job.job_type,
                "provider": job.provider,
                "status": job.status,
            }
            for job in jobs
        ]
    }
    atomic_write_json(path, payload)

