from __future__ import annotations

from typing import Any

from aicomic.core.models import JobRecord


def build_jobs_from_episode_manifest(manifest: dict[str, Any]) -> list[JobRecord]:
    jobs: list[JobRecord] = []
    for episode in manifest.get("episodes", []):
        episode_code = str(episode["episode_code"])
        for shot in episode.get("shots", []):
            shot_id = str(shot["shot_id"])
            jobs.append(
                JobRecord(
                    job_id=f"JOB_{episode_code}_{shot_id}_IMG",
                    episode_code=episode_code,
                    job_type="image",
                    provider="manual_web",
                    status="pending",
                )
            )
            if shot.get("ai_video") is True:
                jobs.append(
                    JobRecord(
                        job_id=f"JOB_{episode_code}_{shot_id}_VID",
                        episode_code=episode_code,
                        job_type="video",
                        provider="manual_web",
                        status="pending",
                    )
                )
            dialogue = str(shot.get("dialogue", "")).strip()
            if dialogue:
                jobs.append(
                    JobRecord(
                        job_id=f"JOB_{episode_code}_{shot_id}_TTS",
                        episode_code=episode_code,
                        job_type="tts",
                        provider="windows_tts",
                        status="pending",
                    )
                )
    return jobs


def serialize_jobs(jobs: list[JobRecord]) -> dict[str, list[dict[str, str]]]:
    return {
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

