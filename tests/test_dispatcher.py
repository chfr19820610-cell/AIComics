from __future__ import annotations

import json
from pathlib import Path

from aicomic.core.dispatcher import dispatch_jobs, resolve_dispatch_channel, write_dispatch_report
from aicomic.core.models import DispatchDecision, JobRecord


class TestResolveDispatchChannel:
    def test_manual_web(self) -> None:
        channel, queue = resolve_dispatch_channel("manual_web")
        assert channel == "manual"
        assert queue == "web_tasks"

    def test_windows_tts(self) -> None:
        channel, queue = resolve_dispatch_channel("windows_tts")
        assert channel == "local"
        assert queue == "tts_local"

    def test_local_piper_tts(self) -> None:
        channel, queue = resolve_dispatch_channel("local_piper_tts")
        assert channel == "local"
        assert queue == "tts_local"

    def test_local_comfyui_image(self) -> None:
        channel, queue = resolve_dispatch_channel("local_comfyui_image")
        assert channel == "local"
        assert queue == "image_local"

    def test_local_comfyui_video(self) -> None:
        channel, queue = resolve_dispatch_channel("local_comfyui_video")
        assert channel == "local"
        assert queue == "video_local"

    def test_unknown_provider_defaults_to_api(self) -> None:
        channel, queue = resolve_dispatch_channel("some_remote_api")
        assert channel == "api"
        assert queue == "default_api"

    def test_empty_provider_defaults_to_api(self) -> None:
        channel, queue = resolve_dispatch_channel("")
        assert channel == "api"


class TestDispatchJobs:
    def test_dispatch_single_job(self) -> None:
        jobs = [JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="pending")]
        decisions = dispatch_jobs(jobs)
        assert len(decisions) == 1
        assert decisions[0].dispatch_channel == "manual"
        assert decisions[0].queue_name == "web_tasks"

    def test_dispatch_multiple_providers(self) -> None:
        jobs = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="windows_tts", status="pending"),
            JobRecord(job_id="J3", episode_code="E01", job_type="video", provider="local_comfyui_video", status="pending"),
        ]
        decisions = dispatch_jobs(jobs)
        assert len(decisions) == 3
        assert decisions[0].dispatch_channel == "manual"
        assert decisions[1].dispatch_channel == "local"
        assert decisions[1].queue_name == "tts_local"
        assert decisions[2].dispatch_channel == "local"
        assert decisions[2].queue_name == "video_local"

    def test_empty_jobs(self) -> None:
        assert dispatch_jobs([]) == []

    def test_decision_is_dispatch_decision_instance(self) -> None:
        jobs = [JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="pending")]
        decisions = dispatch_jobs(jobs)
        assert isinstance(decisions[0], DispatchDecision)


class TestWriteDispatchReport:
    def test_writes_report(self, tmp_path: Path) -> None:
        path = tmp_path / "dispatch.json"
        decisions = [
            DispatchDecision(job_id="J1", episode_code="E01", provider="manual_web", dispatch_channel="manual", queue_name="web_tasks"),
        ]
        write_dispatch_report(path, decisions)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["dispatch_count"] == 1
        assert data["dispatches"][0]["job_id"] == "J1"

    def test_empty_decisions(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.json"
        write_dispatch_report(path, [])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["dispatch_count"] == 0
        assert data["dispatches"] == []
