from __future__ import annotations

import json
from pathlib import Path

from aicomic.core.job_control import retry_jobs
from aicomic.core.models import JobRecord


def retry_batch_jobs(
    jobs: list[JobRecord],
    retryable_statuses: set[str],
    episode_code: str | None = None,
    provider: str | None = None,
) -> tuple[dict[str, object], list[JobRecord]]:
    scoped_jobs: list[JobRecord] = []
    untouched_jobs: list[JobRecord] = []

    for job in jobs:
        if episode_code and job.episode_code != episode_code:
            untouched_jobs.append(job)
            continue
        if provider and job.provider != provider:
            untouched_jobs.append(job)
            continue
        scoped_jobs.append(job)

    updated_scoped_jobs, summary = retry_jobs(scoped_jobs, retryable_statuses)
    updated_jobs = updated_scoped_jobs + untouched_jobs

    retry_candidates = [job for job in scoped_jobs if job.status in retryable_statuses]
    report = {
        "scoped_job_count": len(scoped_jobs),
        "retried_count": int(summary["retried_count"]),
        "untouched_count": int(summary["untouched_count"]) + len(untouched_jobs),
        "episode_code": episode_code or "",
        "provider": provider or "",
        "retryable_statuses": sorted(retryable_statuses),
        "retried_job_ids": [job.job_id for job in retry_candidates],
    }
    return report, updated_jobs


def write_retry_batch_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
