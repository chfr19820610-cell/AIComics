"""FastAPI app factory — exposes AIComics APIs as HTTP endpoints.

v5.0 P1: adds Drift Gate, Consistency, and Quality endpoints.

Usage:
    from aicomic.web.app import create_app
    app = create_app(state_dir="state")
    # uvicorn app:app --port 8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from aicomic.image_consistency.drift_gate import DriftGate
from aicomic.video_synthesis.quality_gate import FFprobeGate
from aicomic.video_synthesis.artifact_detector import ArtifactDetector


# ── Request/Response models ───────────────────────────────────────────────


class DriftCheckRequest(BaseModel):
    """Request body for drift gate check."""

    reference_features: dict[str, Any]
    generated_features: dict[str, Any]
    score: int | None = None
    threshold: int = 60
    warn_threshold: int = 75


class ArtifactCheckRequest(BaseModel):
    """Request body for artifact detection."""

    frame_metadata: list[dict[str, Any]] = []
    fail_threshold: int = 40
    suspect_threshold: int = 70


class QualityCheckRequest(BaseModel):
    """Request body for ffprobe quality check."""

    video_path: str
    expected_duration: float | None = None
    min_resolution: int = 720
    min_framerate: float = 24.0
    min_bitrate_kbps: int = 500


# ── v5.1 Request models ────────────────────────────────────────────────────


class SilentFailureRequest(BaseModel):
    """Request body for silent failure check."""
    episode_metadata: dict[str, Any]


class CostRecordRequest(BaseModel):
    """Request body for recording a generation cost."""
    provider: str
    asset_id: str = ""
    credits: float = 0
    cents: float = 0
    model: str = ""
    asset_path: str = ""
    episode_code: str = ""


class BudgetSetRequest(BaseModel):
    """Request body for setting budget."""
    cents: float


class PlaybackReviewRequest(BaseModel):
    """Request body for playback review."""
    episode_metadata: dict[str, Any]
    video_path: str = ""
    require_manual: bool = False


# ── App factory ───────────────────────────────────────────────────────────


def create_app(state_dir: Path | str = "state") -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        state_dir: Directory for state files (SQLite DBs, manifests, etc.).

    Returns:
        Configured FastAPI app with all routers included.
    """
    app = FastAPI(
        title="AIComics API",
        description="AI漫剧自动生成系统 — v5.1",
        version="5.1.0",
    )

    # ── Health ─────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "5.1.0"}

    # ── Drift Gate ─────────────────────────────────────────────────────

    @app.post("/api/drift/check")
    def drift_check(req: DriftCheckRequest) -> dict[str, Any]:
        """Check character consistency via drift gate."""
        gate = DriftGate(
            threshold=req.threshold,
            warn_threshold=req.warn_threshold,
        )
        result = gate.check(
            reference_features=req.reference_features,
            generated_features=req.generated_features,
            score=req.score,
        )
        return result

    # ── Artifact Detection ─────────────────────────────────────────────

    @app.post("/api/artifact/check")
    def artifact_check(req: ArtifactCheckRequest) -> dict[str, Any]:
        """Detect AI generation artifacts from frame metadata."""
        detector = ArtifactDetector(
            fail_threshold=req.fail_threshold,
            suspect_threshold=req.suspect_threshold,
        )
        report = detector.detect_from_metadata(req.frame_metadata)
        return report.to_dict()

    # ── Quality Gate (ffprobe) ─────────────────────────────────────────

    @app.post("/api/quality/check")
    def quality_check(req: QualityCheckRequest) -> dict[str, Any]:
        """Check video quality via ffprobe."""
        gate = FFprobeGate(
            min_resolution=req.min_resolution,
            min_framerate=req.min_framerate,
            min_bitrate_kbps=req.min_bitrate_kbps,
        )
        report = gate.check(req.video_path, expected_duration=req.expected_duration)
        return report.to_dict()

    @app.get("/api/quality/available")
    def quality_available() -> dict[str, Any]:
        """Check if ffprobe is available on this system."""
        return {"ffprobe_available": FFprobeGate.is_available()}

    # ── Silent Failure Check (v5.1) ────────────────────────────────────

    @app.post("/api/silent-failure/check")
    def silent_failure_check(req: SilentFailureRequest) -> dict[str, Any]:
        """Check for 漫剧专属 silent failures (lip sync, subtitle occlusion, etc.)."""
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        checker = SilentFailureChecker()
        report = checker.check(req.episode_metadata)
        return report.to_dict()

    @app.get("/api/silent-failure/catalog")
    def silent_failure_catalog() -> list[dict[str, str]]:
        """Get the full trap catalog."""
        from aicomic.video_synthesis.silent_failure import SilentFailureChecker
        return SilentFailureChecker.get_trap_catalog()

    # ── Cost Dashboard (v5.1) ──────────────────────────────────────────

    @app.post("/api/cost/record")
    def cost_record(req: CostRecordRequest) -> dict[str, Any]:
        """Record a generation cost."""
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=f"{state_dir}/costs")
        entry = dash.record_generation(
            provider=req.provider,
            asset_id=req.asset_id,
            credits=req.credits,
            cents=req.cents,
            model=req.model,
            asset_path=req.asset_path,
            episode_code=req.episode_code,
        )
        return entry.to_dict()

    @app.get("/api/cost/dashboard")
    def cost_dashboard() -> dict[str, Any]:
        """Get cost dashboard summary."""
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=f"{state_dir}/costs")
        return dash.export_dashboard()

    @app.get("/api/cost/budget")
    def cost_budget() -> dict[str, Any]:
        """Get budget status."""
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=f"{state_dir}/costs")
        return dash.get_budget_status().to_dict()

    @app.post("/api/cost/budget")
    def cost_set_budget(req: BudgetSetRequest) -> dict[str, Any]:
        """Set budget limit."""
        from aicomic.core.cost_dashboard import CostDashboard
        dash = CostDashboard(storage_dir=f"{state_dir}/costs")
        dash.set_budget(req.cents)
        return {"budget_cents": req.cents, "status": "set"}

    # ── Playback Review (v5.1) ─────────────────────────────────────────

    @app.post("/api/playback/review")
    def playback_review(req: PlaybackReviewRequest) -> dict[str, Any]:
        """Run playback review gate (final check before publish)."""
        from aicomic.video_synthesis.playback_review import PlaybackReviewGate
        gate = PlaybackReviewGate(require_manual=req.require_manual)
        result = gate.review(req.episode_metadata, req.video_path)
        return result.to_dict()

    # ── API Key Manager (v5.0 P4) ──────────────────────────────────────

    @app.get("/api/keys/status")
    def keys_status() -> dict[str, Any]:
        """Get all API key statuses."""
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=f"{state_dir}/api_keys.json")
        return {"keys": mgr.get_all_status(), "unconfigured": mgr.get_unconfigured()}

    @app.get("/api/keys/unconfigured")
    def keys_unconfigured() -> list[str]:
        """Get list of providers without configured keys."""
        from aicomic.providers.api_key_manager import APIKeyManager
        mgr = APIKeyManager(storage_path=f"{state_dir}/api_keys.json")
        return mgr.get_unconfigured()

    # ── Include character router ───────────────────────────────────────

    try:
        from aicomic.characters.routes import build_character_router
        app.include_router(build_character_router(state_dir=state_dir))
    except Exception:
        pass  # character router is optional

    return app
