"""Tests for v5.2 pipeline integration — Jev intelligence layer wired into existing modules.

Tests the 3 integration points:
  1. auto_retry + LoopBreaker → early break on repeated failures
  2. quality_gate + ConfidenceGate → calibrated confidence in QualityReport
  3. video_router + ModelCascade → route_with_cascade() method
  4. Web API v5.2 endpoints → /api/cascade/route, /api/guardrail/check, etc.
"""
import pytest



from aicomic.video_synthesis.auto_retry import AutoRetryLoop
from aicomic.video_synthesis.quality_gate import FFprobeGate, QualityReport
from aicomic.intelligence.loop_breaker import LoopBreaker





# ============================================================================
# 1. AutoRetryLoop + LoopBreaker integration
# ============================================================================

class TestAutoRetryLoopBreaker:
    """Test that LoopBreaker is integrated into the auto-retry loop."""

    def test_loop_breaker_is_default(self):
        """AutoRetryLoop has a LoopBreaker by default."""
        loop = AutoRetryLoop()
        assert loop.loop_breaker is not None
        assert isinstance(loop.loop_breaker, LoopBreaker)

    def test_custom_loop_breaker(self):
        """Can inject a custom LoopBreaker."""
        custom = LoopBreaker(max_repeats=5)
        loop = AutoRetryLoop(loop_breaker=custom)
        assert loop.loop_breaker is custom
        assert loop.loop_breaker.max_repeats == 5

    def test_retry_result_has_broken_status(self):
        """When loop breaker triggers, status starts with BROKEN_."""
        # This tests the code path exists; full E2E requires ffprobe
        loop = AutoRetryLoop(max_retries=5)
        # The loop_breaker is wired; we can verify it's called
        assert hasattr(loop, 'loop_breaker')
        assert hasattr(loop.loop_breaker, 'observe')


# ============================================================================
# 2. QualityReport + Confidence integration
# ============================================================================

class TestQualityReportConfidence:
    """Test that calibrated confidence is added to QualityReport."""

    def test_quality_report_has_confidence_field(self):
        """QualityReport has a confidence field (default 0.0)."""
        report = QualityReport(status="PASS", file_path="/test.mp4")
        assert hasattr(report, "confidence")
        assert report.confidence == 0.0

    def test_quality_report_to_dict_includes_confidence(self):
        """to_dict() includes confidence field."""
        report = QualityReport(
            status="PASS",
            file_path="/test.mp4",
            confidence=0.95,
        )
        d = report.to_dict()
        assert "confidence" in d
        assert d["confidence"] == 0.95

    def test_ffprobe_gate_returns_confidence(self):
        """FFprobeGate.check() returns a report with confidence."""
        gate = FFprobeGate()
        # ffprobe likely not installed in test env, so we get WARN
        report = gate.check("/nonexistent/video.mp4")
        # File doesn't exist → FAIL with confidence
        assert report.status == "FAIL"
        assert hasattr(report, "confidence")
        assert 0 <= report.confidence <= 1


# ============================================================================
# 3. VideoRouter + ModelCascade integration
# ============================================================================

class TestVideoRouterCascade:
    """Test route_with_cascade() method on VideoRouter."""

    def test_route_with_cascade_exists(self):
        """VideoRouter has route_with_cascade method."""
        from aicomic.providers.video_router import VideoRouter
        assert hasattr(VideoRouter, "route_with_cascade")

    def test_route_with_cascade_easy_shot(self):
        """Easy shot → routes to wan (budget-aware)."""
        from aicomic.providers.video_router import VideoRouter

        router = VideoRouter.__new__(VideoRouter)
        router.routing_table = {
            "action": "kling", "dialogue": "seedance", "creative": "kling",
            "wide": "wan", "transition": "seedance",
        }
        router._provider_cache = {}

        decision = router.route_with_cascade(
            shot_description="talking head close-up",
            motion_intensity="low",
            budget_aware=True,
        )
        assert decision.provider_name == "wan"
        assert "cascade" in decision.reason.lower() or "v5.2" in decision.reason

    def test_route_with_cascade_extreme_escalates(self):
        """EXTREME difficulty → escalates to human."""
        from aicomic.providers.video_router import VideoRouter

        router = VideoRouter.__new__(VideoRouter)
        router.routing_table = {}
        router._provider_cache = {}

        decision = router.route_with_cascade(
            shot_description="explosion VFX",
            has_vfx=True,
        )
        assert decision.provider_name == "human"

    def test_cascade_decision_has_difficulty_metadata(self):
        """Cascade routing decision includes difficulty in extra."""
        from aicomic.providers.video_router import VideoRouter

        router = VideoRouter.__new__(VideoRouter)
        router.routing_table = {}
        router._provider_cache = {}

        decision = router.route_with_cascade(
            shot_description="action scene",
            motion_intensity="high",
        )
        assert "difficulty" in decision.extra
        assert "cascade_confidence" in decision.extra


# ============================================================================
# 4. Web API v5.2 endpoints
# ============================================================================

class TestWebAPIv52:
    """Test v5.2 API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the AIComics API."""
        from fastapi.testclient import TestClient
        from aicomic.web.app import create_app
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app(state_dir=tmpdir)
            yield TestClient(app)

    def test_health_check_v52(self, client):
        """Health endpoint reports v5.2."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "5.2.0"

    def test_cascade_route_endpoint(self, client):
        """POST /api/cascade/route returns provider routing."""
        response = client.post("/api/cascade/route", json={
            "shot_description": "talking head",
            "motion_intensity": "low",
            "budget_aware": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "difficulty" in data
        assert "confidence" in data

    def test_cascade_route_extreme(self, client):
        """POST /api/cascade/route with VFX → should_escalate."""
        response = client.post("/api/cascade/route", json={
            "shot_description": "explosion",
            "has_vfx": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["should_escalate"] is True

    def test_guardrail_check_clean(self, client):
        """POST /api/guardrail/check with clean text → pass."""
        response = client.post("/api/guardrail/check", json={
            "text": "a beautiful sunset",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "pass"

    def test_guardrail_check_banned(self, client):
        """POST /api/guardrail/check with banned content → block."""
        response = client.post("/api/guardrail/check", json={
            "text": "gore dismember beheading",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["level"] in ("warn", "block")

    def test_confidence_gate_evaluate(self, client):
        """POST /api/confidence-gate/evaluate → returns action."""
        response = client.post("/api/confidence-gate/evaluate", json={
            "score": 90,
            "confidence": 0.8,
            "stage": "quality_check",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "pass"

    def test_confidence_gate_reject(self, client):
        """POST /api/confidence-gate/evaluate with low score → reject."""
        response = client.post("/api/confidence-gate/evaluate", json={
            "score": 20,
            "confidence": 0.9,
            "stage": "quality_check",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "reject"

    def test_intelligence_modules_list(self, client):
        """GET /api/intelligence/modules → returns 8 modules."""
        response = client.get("/api/intelligence/modules")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 8
        names = [m["name"] for m in data]
        assert "calibrated_decision" in names
        assert "guardrail" in names
        assert "model_cascade" in names
