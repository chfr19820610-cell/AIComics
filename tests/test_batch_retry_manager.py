from __future__ import annotations

from aicomic.batch.retry_manager import retry_batch_jobs, write_retry_batch_report
from aicomic.core.models import JobRecord


class TestRetryBatchJobs:
    def test_retries_all_scoped_jobs(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="windows_tts", status="failed"),
            JobRecord(job_id="J3", episode_code="E02", job_type="image", provider="manual_web", status="succeeded"),
        ]
        report, updated = retry_batch_jobs(jobs, retryable_statuses={"failed"})
        assert report["retried_count"] == 2
        assert report["untouched_count"] == 1  # E02 job untouched
        assert report["scoped_job_count"] == 3

    def test_filter_by_episode_code(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="failed"),
            JobRecord(job_id="J2", episode_code="E02", job_type="image", provider="manual_web", status="failed"),
        ]
        report, updated = retry_batch_jobs(jobs, retryable_statuses={"failed"}, episode_code="E01")
        assert report["retried_count"] == 1
        assert len(updated) == 2

    def test_filter_by_provider(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="windows_tts", status="failed"),
        ]
        report, updated = retry_batch_jobs(jobs, retryable_statuses={"failed"}, provider="windows_tts")
        assert report["retried_count"] == 1
        assert len(updated) == 2

    def test_no_retryable_jobs(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="succeeded"),
        ]
        report, updated = retry_batch_jobs(jobs, retryable_statuses={"failed"})
        assert report["retried_count"] == 0
        assert report["scoped_job_count"] == 1

    def test_empty_input(self) -> None:
        report, updated = retry_batch_jobs([], retryable_statuses={"failed"})
        assert report["retried_count"] == 0
        assert updated == []

    def test_retried_job_ids_in_report(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual_web", status="failed"),
        ]
        report, _ = retry_batch_jobs(jobs, retryable_statuses={"failed"})
        assert set(report["retried_job_ids"]) == {"J1", "J2"}

    def test_retries_multiple_statuses(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="failed"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual_web", status="pending"),
        ]
        report, _ = retry_batch_jobs(jobs, retryable_statuses={"failed", "pending"})
        assert report["retried_count"] == 2


class TestWriteRetryBatchReport:
    def test_writes_file(self, tmp_path) -> None:
        path = tmp_path / "retry.json"
        payload = {"retried_count": 1, "scoped_job_count": 1, "retryable_statuses": ["failed"], "retried_job_ids": ["J1"]}
        write_retry_batch_report(path, payload)
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["retried_count"] == 1

    def test_creates_parent_dirs(self, tmp_path) -> None:
        path = tmp_path / "a" / "b" / "retry.json"
        write_retry_batch_report(path, {"retried_count": 0})
        assert path.exists()
