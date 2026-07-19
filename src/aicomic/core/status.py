from __future__ import annotations

from aicomic.core.models import EpisodeState, JobRecord


EPISODE_STATUS_ORDER = (
    "idea",
    "script_ready",
    "shotlist_ready",
    "prompt_ready",
    "jobs_ready",
    "assets_partial",
    "assets_ready",
    "preview_rendered",
    "release_rendered",
    "publish_pack_ready",
    "archived",
)

JOB_STATUSES = {"pending", "queued", "running", "succeeded", "failed", "manual_required", "skipped", "cached"}


def validate_job_status(status: str) -> None:
    if status not in JOB_STATUSES:
        allowed = ", ".join(sorted(JOB_STATUSES))
        raise ValueError(f"Unsupported job status: {status}. Allowed: {allowed}")


def summarize_episode_state(episode_code: str, jobs: list[JobRecord]) -> EpisodeState:
    episode_jobs = [job for job in jobs if job.episode_code == episode_code]
    completed_jobs = sum(1 for job in episode_jobs if job.status in {"succeeded", "cached", "skipped"})
    total_jobs = len(episode_jobs)
    if total_jobs == 0:
        status = "jobs_ready"
    elif completed_jobs == total_jobs:
        status = "assets_ready"
    elif completed_jobs > 0:
        status = "assets_partial"
    else:
        status = "jobs_ready"
    return EpisodeState(
        episode_code=episode_code,
        status=status,
        completed_jobs=completed_jobs,
        total_jobs=total_jobs,
    )

