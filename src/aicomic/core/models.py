from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProjectRecord:
    project_id: str
    project_name: str
    genre: str
    status: str


@dataclass(slots=True)
class SeasonRecord:
    project_id: str
    season: int
    season_title: str
    status: str


@dataclass(slots=True)
class EpisodeRecord:
    episode_code: str
    title: str
    status: str
    shot_count: int


@dataclass(slots=True)
class JobRecord:
    job_id: str
    episode_code: str
    job_type: str
    provider: str
    status: str


@dataclass(slots=True)
class EpisodeState:
    episode_code: str
    status: str
    completed_jobs: int
    total_jobs: int


@dataclass(slots=True)
class EpisodeStateRecord:
    episode_code: str
    status: str
    completed_jobs: int
    total_jobs: int


@dataclass(slots=True)
class DispatchDecision:
    job_id: str
    episode_code: str
    provider: str
    dispatch_channel: str
    queue_name: str


@dataclass(slots=True)
class ResumeReport:
    unfinished_episode_count: int
    unfinished_job_count: int
    suggested_next_step: str


@dataclass(slots=True)
class ProviderRequestRecord:
    request_id: str
    job_id: str
    provider: str
    job_type: str
    request_status: str
    endpoint: str
    payload_path: str


@dataclass(slots=True)
class BatchRecord:
    batch_id: str
    batch_type: str
    scope_type: str
    scope_value: str
    target_steps: str
    provider_filter: str
    status: str
    summary_path: str


@dataclass(slots=True)
class BatchRunRecord:
    run_id: str
    batch_id: str
    step_name: str
    status: str
    output_path: str
