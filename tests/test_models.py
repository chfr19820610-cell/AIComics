from __future__ import annotations

import pytest

from aicomic.core.models import (
    BatchRecord,
    BatchRunRecord,
    DispatchDecision,
    EpisodeRecord,
    EpisodeState,
    EpisodeStateRecord,
    JobRecord,
    ProjectRecord,
    ProviderRequestRecord,
    ResumeReport,
    SeasonRecord,
)


class TestProjectRecord:
    def test_create(self):
        r = ProjectRecord(
            project_id="P001",
            project_name="Test",
            genre="horror",
            status="active",
        )
        assert r.project_id == "P001"
        assert r.project_name == "Test"
        assert r.genre == "horror"
        assert r.status == "active"

    def test_defaults_not_applicable(self):
        """All fields are required — no default values."""
        r = ProjectRecord(
            project_id="P001", project_name="X", genre="drama", status="inactive"
        )
        assert r.status == "inactive"


class TestSeasonRecord:
    def test_create(self):
        r = SeasonRecord(
            project_id="P001",
            season=1,
            season_title="第一季",
            status="running",
        )
        assert r.project_id == "P001"
        assert r.season == 1
        assert r.season_title == "第一季"
        assert r.status == "running"

    def test_slots_prevent_dynamic_attrs(self):
        r = SeasonRecord(project_id="P001", season=1, season_title="S1", status="done")
        with pytest.raises(AttributeError):
            r.nonexistent = "fail"  # type: ignore[attr-defined]


class TestEpisodeRecord:
    def test_create(self):
        r = EpisodeRecord(
            episode_code="E01",
            title="第一集",
            status="running",
            shot_count=5,
        )
        assert r.episode_code == "E01"
        assert r.title == "第一集"
        assert r.status == "running"
        assert r.shot_count == 5


class TestJobRecord:
    def test_create(self):
        r = JobRecord(
            job_id="JOB_E01_S001_IMG",
            episode_code="E01",
            job_type="image",
            provider="manual_web",
            status="pending",
        )
        assert r.job_id == "JOB_E01_S001_IMG"
        assert r.episode_code == "E01"
        assert r.job_type == "image"
        assert r.provider == "manual_web"
        assert r.status == "pending"


class TestEpisodeState:
    def test_create(self):
        s = EpisodeState(
            episode_code="E01",
            status="running",
            completed_jobs=3,
            total_jobs=10,
        )
        assert s.episode_code == "E01"
        assert s.status == "running"
        assert s.completed_jobs == 3
        assert s.total_jobs == 10

    def test_progress(self):
        s = EpisodeState(
            episode_code="E02",
            status="running",
            completed_jobs=7,
            total_jobs=10,
        )
        assert s.completed_jobs / s.total_jobs == 0.7


class TestEpisodeStateRecord:
    def test_create(self):
        r = EpisodeStateRecord(
            episode_code="E01",
            status="completed",
            completed_jobs=10,
            total_jobs=10,
        )
        assert r.status == "completed"
        assert r.completed_jobs == r.total_jobs


class TestDispatchDecision:
    def test_create(self):
        d = DispatchDecision(
            job_id="JOB_E01_S001_IMG",
            episode_code="E01",
            provider="manual_web",
            dispatch_channel="direct",
            queue_name="default",
        )
        assert d.job_id == "JOB_E01_S001_IMG"
        assert d.dispatch_channel == "direct"
        assert d.queue_name == "default"


class TestResumeReport:
    def test_create(self):
        r = ResumeReport(
            unfinished_episode_count=2,
            unfinished_job_count=15,
            suggested_next_step="rerun_failed",
        )
        assert r.unfinished_episode_count == 2
        assert r.unfinished_job_count == 15
        assert r.suggested_next_step == "rerun_failed"

    def test_no_unfinished(self):
        r = ResumeReport(
            unfinished_episode_count=0,
            unfinished_job_count=0,
            suggested_next_step="all_done",
        )
        assert r.unfinished_episode_count == 0
        assert r.unfinished_job_count == 0


class TestProviderRequestRecord:
    def test_create(self):
        r = ProviderRequestRecord(
            request_id="REQ_001",
            job_id="JOB_E01_S001_IMG",
            provider="manual_web",
            job_type="image",
            request_status="pending",
            endpoint="/api/generate",
            payload_path="/tmp/payload.json",
        )
        assert r.request_id == "REQ_001"
        assert r.request_status == "pending"


class TestBatchRecord:
    def test_create(self):
        r = BatchRecord(
            batch_id="BATCH_001",
            batch_type="full",
            scope_type="episode",
            scope_value="E01-E03",
            target_steps="render",
            provider_filter="",
            status="running",
            summary_path="/tmp/summary.json",
        )
        assert r.batch_id == "BATCH_001"
        assert r.batch_type == "full"
        assert r.status == "running"


class TestBatchRunRecord:
    def test_create(self):
        r = BatchRunRecord(
            run_id="RUN_001",
            batch_id="BATCH_001",
            step_name="render",
            status="completed",
            output_path="/tmp/output/",
        )
        assert r.run_id == "RUN_001"
        assert r.step_name == "render"
        assert r.status == "completed"
        assert r.output_path == "/tmp/output/"
