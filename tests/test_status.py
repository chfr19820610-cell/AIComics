from __future__ import annotations

import pytest

from aicomic.core.models import JobRecord
from aicomic.core.status import (
    EPISODE_STATUS_ORDER,
    JOB_STATUSES,
    summarize_episode_state,
    validate_job_status,
)


class TestStatusConstants:
    def test_episode_status_order_is_tuple(self) -> None:
        assert isinstance(EPISODE_STATUS_ORDER, tuple)

    def test_episode_status_contains_expected_values(self) -> None:
        assert "idea" in EPISODE_STATUS_ORDER
        assert "release_rendered" in EPISODE_STATUS_ORDER
        assert "archived" in EPISODE_STATUS_ORDER

    def test_job_statuses_is_set(self) -> None:
        assert isinstance(JOB_STATUSES, set)

    def test_job_statuses_contains_expected(self) -> None:
        assert "pending" in JOB_STATUSES
        assert "succeeded" in JOB_STATUSES
        assert "failed" in JOB_STATUSES
        assert "cached" in JOB_STATUSES


class TestValidateJobStatus:
    def test_valid_statuses(self) -> None:
        for status in JOB_STATUSES:
            validate_job_status(status)  # should not raise

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported job status"):
            validate_job_status("invalid_status")

    def test_empty_status_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_job_status("")


class TestSummarizeEpisodeState:
    def test_no_jobs_returns_jobs_ready(self) -> None:
        state = summarize_episode_state("E01", [])
        assert state.status == "jobs_ready"
        assert state.completed_jobs == 0
        assert state.total_jobs == 0

    def test_all_completed_returns_assets_ready(self) -> None:
        jobs = [
            JobRecord(job_id=f"JOB_{i}", episode_code="E01", job_type="image", provider="manual", status="succeeded")
            for i in range(3)
        ]
        state = summarize_episode_state("E01", jobs)
        assert state.status == "assets_ready"
        assert state.completed_jobs == 3
        assert state.total_jobs == 3

    def test_partial_completed_returns_assets_partial(self) -> None:
        jobs = [
            JobRecord(job_id="JOB_1", episode_code="E01", job_type="image", provider="manual", status="succeeded"),
            JobRecord(job_id="JOB_2", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="JOB_3", episode_code="E01", job_type="tts", provider="manual", status="pending"),
        ]
        state = summarize_episode_state("E01", jobs)
        assert state.status == "assets_partial"
        assert state.completed_jobs == 1

    def test_none_completed_with_jobs_returns_jobs_ready(self) -> None:
        jobs = [
            JobRecord(job_id="JOB_1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="JOB_2", episode_code="E01", job_type="tts", provider="manual", status="failed"),
        ]
        state = summarize_episode_state("E01", jobs)
        assert state.status == "jobs_ready"

    def test_cached_and_skipped_count_as_completed(self) -> None:
        jobs = [
            JobRecord(job_id="JOB_1", episode_code="E01", job_type="image", provider="manual", status="cached"),
            JobRecord(job_id="JOB_2", episode_code="E01", job_type="tts", provider="manual", status="skipped"),
        ]
        state = summarize_episode_state("E01", jobs)
        assert state.status == "assets_ready"
        assert state.completed_jobs == 2

    def test_filters_by_episode_code(self) -> None:
        jobs = [
            JobRecord(job_id="JOB_1", episode_code="E01", job_type="image", provider="manual", status="succeeded"),
            JobRecord(job_id="JOB_2", episode_code="E02", job_type="image", provider="manual", status="pending"),
        ]
        state = summarize_episode_state("E01", jobs)
        assert state.total_jobs == 1
        assert state.episode_code == "E01"
