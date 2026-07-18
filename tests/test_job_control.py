from __future__ import annotations

from aicomic.core.job_control import filter_jobs, retry_jobs, write_job_payload
from aicomic.core.models import JobRecord


class TestFilterJobs:
    def test_no_filters_returns_all(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="succeeded"),
        ]
        result = filter_jobs(jobs)
        assert len(result) == 2

    def test_filter_by_episode_code(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="J2", episode_code="E02", job_type="tts", provider="manual", status="pending"),
        ]
        result = filter_jobs(jobs, episode_code="E01")
        assert len(result) == 1
        assert result[0].job_id == "J1"

    def test_filter_by_job_type(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="pending"),
        ]
        result = filter_jobs(jobs, job_type="tts")
        assert len(result) == 1
        assert result[0].job_type == "tts"

    def test_filter_by_statuses(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="succeeded"),
            JobRecord(job_id="J3", episode_code="E01", job_type="video", provider="manual", status="failed"),
        ]
        result = filter_jobs(jobs, statuses={"succeeded", "failed"})
        assert len(result) == 2

    def test_empty_jobs_list(self) -> None:
        assert filter_jobs([]) == []

    def test_combined_filters(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="succeeded"),
            JobRecord(job_id="J3", episode_code="E02", job_type="image", provider="manual", status="pending"),
        ]
        result = filter_jobs(jobs, episode_code="E01", job_type="image")
        assert len(result) == 1
        assert result[0].job_id == "J1"


class TestRetryJobs:
    def test_retries_failed_jobs(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="succeeded"),
        ]
        updated, summary = retry_jobs(jobs, retryable_statuses={"failed"})
        assert summary["retried_count"] == 1
        assert summary["untouched_count"] == 1
        assert updated[0].status == "queued"
        assert updated[1].status == "succeeded"

    def test_retries_multiple_statuses(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="pending"),
            JobRecord(job_id="J3", episode_code="E01", job_type="video", provider="manual", status="running"),
        ]
        updated, summary = retry_jobs(jobs, retryable_statuses={"failed", "pending", "running"})
        assert summary["retried_count"] == 3
        assert all(j.status == "queued" for j in updated)

    def test_no_retryable_jobs(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="succeeded"),
        ]
        updated, summary = retry_jobs(jobs, retryable_statuses={"failed"})
        assert summary["retried_count"] == 0
        assert summary["untouched_count"] == 1

    def test_empty_input(self) -> None:
        updated, summary = retry_jobs([], retryable_statuses={"failed"})
        assert updated == []
        assert summary["retried_count"] == 0
        assert summary["untouched_count"] == 0

    def test_retry_preserves_job_identity(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="failed"),
        ]
        updated, _ = retry_jobs(jobs, retryable_statuses={"failed"})
        assert updated[0].job_id == "J1"
        assert updated[0].episode_code == "E01"
        assert updated[0].job_type == "image"
        assert updated[0].provider == "manual"


class TestWriteJobPayload:
    def test_writes_file(self, tmp_path) -> None:
        path = tmp_path / "jobs.json"
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="pending"),
        ]
        write_job_payload(path, jobs)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "J1"

    def test_empty_jobs(self, tmp_path) -> None:
        path = tmp_path / "empty.json"
        write_job_payload(path, [])
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["jobs"] == []

    def test_creates_parent_dirs(self, tmp_path) -> None:
        path = tmp_path / "a" / "b" / "payload.json"
        write_job_payload(path, [])
        assert path.exists()
