"""Tests for v5.0 P1 quality control modules: quality_gate, artifact_detector, auto_retry, web API."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


# ── ffprobe quality gate ──────────────────────────────────────────────────


class TestFFprobeGate:
    def test_gate_initialization(self):
        from aicomic.video_synthesis.quality_gate import FFprobeGate
        gate = FFprobeGate(min_resolution=720, min_framerate=24.0)
        assert gate.min_resolution == 720
        assert gate.min_framerate == 24.0

    def test_is_available(self):
        from aicomic.video_synthesis.quality_gate import FFprobeGate
        # ffprobe may or may not be installed — just check method doesn't crash
        result = FFprobeGate.is_available()
        assert isinstance(result, bool)

    def test_check_nonexistent_file(self):
        from aicomic.video_synthesis.quality_gate import FFprobeGate
        gate = FFprobeGate()
        report = gate.check("/nonexistent/video.mp4")
        assert report.status == "FAIL"
        assert "File does not exist" in report.issues

    def test_quality_report_to_dict(self):
        from aicomic.video_synthesis.quality_gate import QualityReport
        report = QualityReport(
            status="PASS",
            file_path="/test.mp4",
            metrics={"resolution": "1920x1080"},
            issues=[],
        )
        d = report.to_dict()
        assert d["status"] == "PASS"
        assert d["file_path"] == "/test.mp4"
        assert d["metrics"]["resolution"] == "1920x1080"


# ── AI artifact detector ──────────────────────────────────────────────────


class TestArtifactDetector:
    def test_clean_frames(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactDetector
        detector = ArtifactDetector()
        frames = [
            {"finger_count": 5, "face_confidence": 0.95},
            {"finger_count": 5, "face_confidence": 0.90},
        ]
        report = detector.detect_from_metadata(frames)
        assert report.status == "CLEAN"
        assert report.score == 100
        assert len(report.issues) == 0

    def test_extra_fingers(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactDetector
        detector = ArtifactDetector()
        frames = [{"finger_count": 7, "face_confidence": 0.9}]
        report = detector.detect_from_metadata(frames)
        assert report.status == "FAIL"
        assert any("finger" in i.description.lower() for i in report.issues)
        assert any(i.severity == "critical" for i in report.issues)

    def test_face_warping(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactDetector
        detector = ArtifactDetector()
        frames = [{"finger_count": 5, "face_confidence": 0.3}]
        report = detector.detect_from_metadata(frames)
        assert any("face" in i.description.lower() for i in report.issues)
        assert any(i.severity == "major" for i in report.issues)

    def test_garbled_text(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactDetector
        detector = ArtifactDetector()
        frames = [{"has_text": True, "text_garbled": True}]
        report = detector.detect_from_metadata(frames)
        assert any("garbled" in i.description.lower() for i in report.issues)

    def test_excessive_scene_changes(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactDetector
        detector = ArtifactDetector()
        # 15 frames, 8 scene changes = 53% > 30%
        frames = [{"scene_change": i < 8} for i in range(15)]
        report = detector.detect_from_metadata(frames)
        assert any("scene change" in i.description.lower() for i in report.issues)

    def test_report_to_dict(self):
        from aicomic.video_synthesis.artifact_detector import ArtifactReport, ArtifactIssue
        report = ArtifactReport(
            status="SUSPECT",
            score=65,
            issues=[ArtifactIssue(category="character", severity="major", description="test")],
            checked_frames=5,
        )
        d = report.to_dict()
        assert d["status"] == "SUSPECT"
        assert d["score"] == 65
        assert d["checked_frames"] == 5


# ── Auto-retry loop ───────────────────────────────────────────────────────


class TestAutoRetryLoop:
    def test_pass_on_first_try(self, tmp_path):
        from aicomic.video_synthesis.auto_retry import AutoRetryLoop
        from aicomic.video_synthesis.quality_gate import FFprobeGate

        # Create a dummy video file
        video = tmp_path / "shot.mp4"
        video.write_bytes(b"dummy")

        # Mock generate function that creates the file
        def gen_fn(prompt, **kwargs):
            return {"status": "success", "video_path": str(video)}

        # Use a gate that always passes (mock)
        class MockGate(FFprobeGate):
            def check(self, video_path, expected_duration=None):
                from aicomic.video_synthesis.quality_gate import QualityReport
                return QualityReport(
                    status="PASS",
                    file_path=str(video_path),
                    metrics={"height": 1080},
                    issues=[],
                )

        loop = AutoRetryLoop(max_retries=3, ffprobe_gate=MockGate())
        result = loop.run(gen_fn, video, prompt="test")
        assert result.success is True
        assert result.final_status == "PASS"
        assert result.total_retries == 0

    def test_retry_result_to_dict(self):
        from aicomic.video_synthesis.auto_retry import RetryResult, RetryAttempt
        result = RetryResult(
            success=False,
            final_status="FAIL",
            attempts=[RetryAttempt(attempt=0, quality_status="FAIL", artifact_status="CLEAN", combined_score=30)],
            total_retries=3,
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["total_retries"] == 3
        assert len(d["attempts"]) == 1


# ── Web API ───────────────────────────────────────────────────────────────


class TestWebAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from aicomic.web.app import create_app
        app = create_app(state_dir="state")
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "5.1.0"

    def test_drift_check_pass(self, client):
        resp = client.post("/api/drift/check", json={
            "reference_features": {"hair": "black", "eyes": "blue"},
            "generated_features": {"hair": "black", "eyes": "blue"},
            "score": 95,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PASS"
        assert data["score"] == 95

    def test_drift_check_fail(self, client):
        resp = client.post("/api/drift/check", json={
            "reference_features": {"hair": "black", "eyes": "blue"},
            "generated_features": {"hair": "blonde", "eyes": "red"},
            "score": 20,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAIL"

    def test_artifact_check_clean(self, client):
        resp = client.post("/api/artifact/check", json={
            "frame_metadata": [{"finger_count": 5, "face_confidence": 0.95}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CLEAN"

    def test_artifact_check_fail(self, client):
        resp = client.post("/api/artifact/check", json={
            "frame_metadata": [{"finger_count": 8, "face_confidence": 0.2}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAIL"

    def test_quality_check_nonexistent(self, client):
        resp = client.post("/api/quality/check", json={
            "video_path": "/nonexistent.mp4",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAIL"

    def test_quality_available(self, client):
        resp = client.get("/api/quality/available")
        assert resp.status_code == 200
        data = resp.json()
        assert "ffprobe_available" in data

    # ── v5.1 API tests ──────────────────────────────────────────────────

    def test_silent_failure_check(self, client):
        resp = client.post("/api/silent-failure/check", json={
            "episode_metadata": {"shots": [{"shot_index": 1, "duration_seconds": 5, "audio_duration": 5}]}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CLEAN"

    def test_silent_failure_catalog(self, client):
        resp = client.get("/api/silent-failure/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8

    def test_cost_record_and_dashboard(self, client):
        # Record a cost
        resp = client.post("/api/cost/record", json={
            "provider": "kling", "cents": 15.0, "asset_id": "s1"
        })
        assert resp.status_code == 200
        assert resp.json()["provider"] == "kling"
        # Get dashboard
        resp2 = client.get("/api/cost/dashboard")
        assert resp2.status_code == 200
        assert resp2.json()["asset_count"] >= 1

    def test_cost_budget(self, client):
        resp = client.get("/api/cost/budget")
        assert resp.status_code == 200
        assert "status" in resp.json()

    def test_playback_review(self, client):
        resp = client.post("/api/playback/review", json={
            "episode_metadata": {
                "total_duration": 120,
                "shots": [{"shot_index": i, "duration_seconds": 5, "emotion": e, "resolution": "1080x1920"}
                          for i, e in enumerate(["tense", "happy", "sad", "angry", "neutral", "surprised"])],
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "passed" in data
        assert "overall_score" in data

    def test_keys_status(self, client):
        resp = client.get("/api/keys/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert "unconfigured" in data
