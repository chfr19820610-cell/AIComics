"""Tests for v5.1 godogen migration — silent failure, cost dashboard, playback review."""
from __future__ import annotations

import pytest


# ── Silent Failure Checker ────────────────────────────────────────────────


class TestSilentFailureChecker:
    def test_clean_episode(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [{"shot_index": 1, "duration_seconds": 5, "audio_duration": 5, "has_dialogue": True}]}
        report = checker.check(meta)
        assert report.status == "CLEAN"
        assert report.score == 100

    def test_lip_sync_mismatch(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [
            {"shot_index": 1, "duration_seconds": 5, "audio_duration": 8, "has_dialogue": True}
        ]}
        report = checker.check(meta)
        assert any(t.trap_type == "lip_sync" for t in report.traps_hit)

    def test_subtitle_occlusion(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [
            {"shot_index": 1, "subtitle_y_pct": 0.9, "face_bbox_y": [0.3, 0.85]}
        ]}
        report = checker.check(meta)
        assert any(t.trap_type == "subtitle_occlusion" for t in report.traps_hit)

    def test_jump_cut(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [
            {"shot_index": 1, "scene_id": "S1", "location": "forest"},
            {"shot_index": 2, "scene_id": "S1", "location": "castle"},
        ]}
        report = checker.check(meta)
        assert any(t.trap_type == "jump_cut" for t in report.traps_hit)

    def test_ken_burns_excessive_zoom(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [{"shot_index": 1, "ken_burns_zoom": 3.5}]}
        report = checker.check(meta)
        assert any(t.trap_type == "ken_burns" for t in report.traps_hit)

    def test_color_drift_same_scene(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [
            {"shot_index": 1, "scene_id": "S1", "color_histogram": {"r_mean": 120, "g_mean": 100, "b_mean": 80}},
            {"shot_index": 2, "scene_id": "S1", "color_histogram": {"r_mean": 40, "g_mean": 30, "b_mean": 20}},
        ]}
        report = checker.check(meta)
        assert any(t.trap_type == "color_drift" for t in report.traps_hit)

    def test_aspect_error(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {
            "target_aspect": "9:16",
            "shots": [{"shot_index": 1, "resolution": "1920x1080"}],  # 16:9 not 9:16
        }
        report = checker.check(meta)
        assert any(t.trap_type == "aspect_error" for t in report.traps_hit)
        assert any(t.severity == "critical" for t in report.traps_hit)

    def test_timing_drift(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {
            "shots": [],
            "srt_entries": [{"start": 0, "end": 3, "text": "hello"}],
            "audio_segments": [{"start": 2, "end": 5}],
        }
        report = checker.check(meta)
        assert any(t.trap_type == "timing_drift" for t in report.traps_hit)

    def test_face_stiff(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {"shots": [
            {"shot_index": i, "face_expression": "neutral"} for i in range(10)
        ]}
        report = checker.check(meta)
        assert any(t.trap_type == "face_stiff" for t in report.traps_hit)

    def test_critical_triggers_fail(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        meta = {
            "target_aspect": "9:16",
            "shots": [{"shot_index": 1, "resolution": "1920x1080"}],
        }
        report = checker.check(meta)
        assert report.status == "FAIL"

    def test_trap_catalog(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        catalog = SilentFailureChecker.get_trap_catalog()
        assert len(catalog) == 8
        types = [c["type"] for c in catalog]
        assert "lip_sync" in types
        assert "aspect_error" in types

    def test_report_to_dict(self):
        from aicomic.video_synthesis.silent_failure import SilentFailureReport, TrapHit
        r = SilentFailureReport(status="SUSPECT", score=65, traps_hit=[], traps_checked=["lip_sync"])
        d = r.to_dict()
        assert d["status"] == "SUSPECT"
        assert d["score"] == 65


# ── Cost Dashboard ────────────────────────────────────────────────────────


class TestCostDashboard:
    def test_record_generation(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=1000)
        entry = dash.record_generation("kling", "shot_01", credits=10, cents=15.0)
        assert entry.provider == "kling"
        assert entry.cents == 15.0

    def test_budget_check_under(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=1000)
        dash.record_generation("kling", cents=100)
        assert dash.check_budget() is True

    def test_budget_check_exceeded(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=100)
        dash.record_generation("kling", cents=150)
        assert dash.check_budget() is False

    def test_budget_unlimited(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=0)
        dash.record_generation("kling", cents=999999)
        assert dash.check_budget() is True

    def test_budget_status(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=1000, warn_pct=80)
        dash.record_generation("kling", cents=850)
        status = dash.get_budget_status()
        assert status.status == "warning"
        assert status.spent_pct == 85.0

    def test_cost_by_provider(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"))
        dash.record_generation("kling", cents=15)
        dash.record_generation("kling", cents=20)
        dash.record_generation("seedance", cents=5)
        breakdown = dash.get_cost_by_provider()
        assert breakdown["kling"]["total_cents"] == 35
        assert breakdown["seedance"]["total_cents"] == 5
        assert breakdown["kling"]["count"] == 2

    def test_cost_by_episode(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"))
        dash.record_generation("kling", cents=10, episode_code="E01")
        dash.record_generation("kling", cents=15, episode_code="E01")
        dash.record_generation("kling", cents=5, episode_code="E02")
        breakdown = dash.get_cost_by_episode()
        assert breakdown["E01"]["total_cents"] == 25
        assert breakdown["E02"]["total_cents"] == 5

    def test_asset_table(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"))
        dash.record_generation("kling", asset_id="s1", asset_path="/vid/s1.mp4", cents=15, asset_size_mb=2.5)
        table = dash.get_asset_table()
        assert len(table) == 1
        assert table[0]["asset_path"] == "/vid/s1.mp4"
        assert table[0]["size_mb"] == 2.5

    def test_persistence(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        path = str(tmp_path / "costs")
        dash1 = CostDashboard(storage_dir=path, budget_cents=500)
        dash1.record_generation("kling", cents=50)
        dash2 = CostDashboard(storage_dir=path)
        assert dash2.get_total_cost() == 50
        assert dash2._budget_cents == 500

    def test_export_dashboard(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=1000)
        dash.record_generation("kling", cents=50, episode_code="E01")
        data = dash.export_dashboard()
        assert data["budget_status"]["status"] == "ok"
        assert data["can_proceed"] is True
        assert data["asset_count"] == 1

    def test_set_budget(self, tmp_path):
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=str(tmp_path / "costs"), budget_cents=100)
        dash.set_budget(500)
        assert dash._budget_cents == 500


# ── Playback Review Gate ──────────────────────────────────────────────────


class TestPlaybackReviewGate:
    def test_passing_episode(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 120,
            "shots": [
                {"shot_index": i, "duration_seconds": 5, "emotion": e, "resolution": "1080x1920"}
                for i, e in enumerate(["tense", "happy", "sad", "angry", "neutral", "surprised"])
            ],
            "target_platform": "douyin",
        }
        result = gate.review(meta)
        assert result.passed is True
        assert result.overall_score >= 70

    def test_failing_pacing(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 10,
            "shots": [{"shot_index": 1, "duration_seconds": 1, "emotion": "tense", "resolution": "1080x1920"}],
        }
        result = gate.review(meta)
        # Very short duration → pacing fails
        assert any(not c.passed for c in result.checks)

    def test_narrative_beats(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 120,
            "shots": [
                {"shot_index": i, "duration_seconds": 5, "emotion": "tense", "beat": "intro", "resolution": "1080x1920"}
                for i in range(10)
            ],
        }
        result = gate.review(meta)
        # All same beat → low beat coverage
        narrative = [c for c in result.checks if c.name == "narrative_beats"][0]
        assert narrative.passed is False or narrative.score < 50

    def test_emotion_arc(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 120,
            "shots": [
                {"shot_index": i, "duration_seconds": 5, "emotion": e, "resolution": "1080x1920"}
                for i, e in enumerate(["tense", "happy", "sad", "angry", "neutral", "surprised"])
            ],
        }
        result = gate.review(meta)
        emotion = [c for c in result.checks if c.name == "emotion_arc"][0]
        assert emotion.passed is True

    def test_resolution_inconsistency(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 120,
            "shots": [
                {"shot_index": 1, "duration_seconds": 5, "resolution": "1080x1920"},
                {"shot_index": 2, "duration_seconds": 5, "resolution": "1920x1080"},
            ],
        }
        result = gate.review(meta)
        res = [c for c in result.checks if c.name == "resolution_consistency"][0]
        assert res.passed is False

    def test_prior_gates(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate()
        meta = {
            "total_duration": 120,
            "shots": [{"shot_index": 1, "duration_seconds": 5, "resolution": "1080x1920"}],
            "quality_gate_results": {
                "drift_gate": {"status": "FAIL"},
                "silent_failure": {"status": "CLEAN"},
            },
        }
        result = gate.review(meta)
        drift = [c for c in result.checks if c.name == "drift_gate_passed"][0]
        assert drift.passed is False

    def test_manual_required(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate(require_manual=True)
        meta = {"total_duration": 120, "shots": [{"shot_index": 1, "duration_seconds": 5}]}
        result = gate.review(meta)
        assert result.passed is False
        assert result.review_mode == "manual"
        assert any(c.name == "manual_review_required" for c in result.checks)

    def test_result_to_dict(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewResult, ReviewCheck
        r = PlaybackReviewResult(
            passed=True,
            overall_score=85,
            checks=[ReviewCheck(name="test", category="playback", passed=True, score=90)],
            review_mode="auto",
        )
        d = r.to_dict()
        assert d["passed"] is True
        assert d["overall_score"] == 85
        assert len(d["checks"]) == 1

    def test_vlm_fallback(self):
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate(api_key="")  # no key → fallback
        meta = {"total_duration": 120, "shots": [{"shot_index": 1, "duration_seconds": 5}]}
        result = gate.vlm_review("/fake.mp4", meta)
        assert result.review_mode in ("auto_heuristic", "auto_fallback")
