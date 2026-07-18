from __future__ import annotations

from aicomic.core.job_builder import build_jobs_from_episode_manifest, serialize_jobs
from aicomic.core.models import JobRecord


class TestBuildJobsFromEpisodeManifest:
    def test_returns_correct_job_count(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        # E01: S001 (IMG+VID+TTS), S002 (IMG only, no dialogue), S003 (IMG+TTS)
        # E02: S001 (IMG+VID+TTS)
        assert len(jobs) == 9

    def test_image_job_for_every_shot(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        image_jobs = [j for j in jobs if j.job_type == "image"]
        assert len(image_jobs) == 4  # 3 shots in E01 + 1 in E02

    def test_tts_job_only_when_dialogue_present(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        tts_jobs = [j for j in jobs if j.job_type == "tts"]
        # E01 S001 (dialogue) + E01 S003 (dialogue) + E02 S001 (dialogue)
        assert len(tts_jobs) == 3
        for job in tts_jobs:
            assert job.provider == "windows_tts"

    def test_video_job_only_when_ai_video_flag(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        video_jobs = [j for j in jobs if j.job_type == "video"]
        # E01 S001 (ai_video=True) + E02 S001 (ai_video=True)
        assert len(video_jobs) == 2

    def test_all_jobs_start_pending(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        assert all(j.status == "pending" for j in jobs)

    def test_job_id_format(self, sample_project_manifest):
        jobs = build_jobs_from_episode_manifest(sample_project_manifest)
        # First job should be JOB_E01_S001_IMG
        assert jobs[0].job_id == "JOB_E01_S001_IMG"
        assert jobs[0].episode_code == "E01"


class TestSerializeJobs:
    def test_serialize_roundtrip(self):
        jobs = [
            JobRecord(
                job_id="JOB_E01_S001_IMG",
                episode_code="E01",
                job_type="image",
                provider="manual_web",
                status="pending",
            ),
            JobRecord(
                job_id="JOB_E01_S001_TTS",
                episode_code="E01",
                job_type="tts",
                provider="windows_tts",
                status="completed",
            ),
        ]
        serialized = serialize_jobs(jobs)
        assert "jobs" in serialized
        assert len(serialized["jobs"]) == 2
        assert serialized["jobs"][0]["job_id"] == "JOB_E01_S001_IMG"
        assert serialized["jobs"][0]["status"] == "pending"
        assert serialized["jobs"][1]["status"] == "completed"

    def test_empty_jobs_list(self):
        assert serialize_jobs([]) == {"jobs": []}
