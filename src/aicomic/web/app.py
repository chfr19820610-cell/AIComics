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

from fastapi import FastAPI, HTTPException
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
        description="AI漫剧自动生成系统 — v5.0",
        version="5.0.0",
    )

    # ── Health ─────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "5.0.0"}

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

    # ── Include character router ───────────────────────────────────────

    try:
        from aicomic.characters.routes import build_character_router
        app.include_router(build_character_router(state_dir=state_dir))
    except Exception:
        pass  # character router is optional

    return app
