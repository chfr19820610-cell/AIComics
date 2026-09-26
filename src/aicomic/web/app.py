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


# ── v5.2 Request models ────────────────────────────────────────────────────


class CascadeRouteRequest(BaseModel):
    """Request body for v5.2 model cascade routing."""
    shot_description: str = ""
    motion_intensity: str = "medium"
    character_count: int = 1
    has_vfx: bool = False
    budget_aware: bool = True


class GuardrailCheckRequest(BaseModel):
    """Request body for v5.2 guardrail check."""
    text: str
    is_output: bool = False


class ConfidenceGateRequest(BaseModel):
    """Request body for v5.2 confidence gate evaluation."""
    score: float
    confidence: float
    stage: str = "quality_check"
    force_escalate: bool = False


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
        description="AI漫剧自动生成系统 — v5.2",
        version="5.2.0",
    )

    # ── Health ─────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "5.2.0"}

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

    # ── v5.2: Jev Intelligence Layer endpoints ────────────────────────

    @app.post("/api/cascade/route")
    def cascade_route(req: CascadeRouteRequest) -> dict[str, Any]:
        """Route a shot to the best provider using Jev-calibrated difficulty."""
        from aicomic.intelligence.model_cascade import ModelCascade
        cascade = ModelCascade()
        result = cascade.route(
            shot_description=req.shot_description,
            motion_intensity=req.motion_intensity,
            character_count=req.character_count,
            has_vfx=req.has_vfx,
            budget_aware=req.budget_aware,
        )
        return {
            "provider": result.provider,
            "difficulty": result.difficulty.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "estimated_cost": result.estimated_cost,
            "should_escalate": result.should_escalate,
        }

    @app.post("/api/guardrail/check")
    def guardrail_check(req: GuardrailCheckRequest) -> dict[str, Any]:
        """Check text for content policy violations before sending to API."""
        from aicomic.intelligence.guardrail import Guardrail
        guard = Guardrail()
        if req.is_output:
            result = guard.check_output(req.text)
        else:
            result = guard.check_prompt(req.text)
        return {
            "level": result.level.value,
            "score": result.score,
            "confidence": result.confidence,
            "reason": result.reason,
            "flagged_categories": result.flagged_categories,
        }

    @app.post("/api/confidence-gate/evaluate")
    def confidence_gate_evaluate(req: ConfidenceGateRequest) -> dict[str, Any]:
        """Evaluate a score+confidence pair against configurable thresholds."""
        from aicomic.intelligence.confidence_gate import ConfidenceGate
        gate = ConfidenceGate.for_stage(req.stage)
        decision = gate.evaluate(
            score=req.score,
            confidence=req.confidence,
            stage=req.stage,
            force_escalate=req.force_escalate,
        )
        return {
            "action": decision.action.value,
            "score": decision.score,
            "confidence": decision.confidence,
            "stage": decision.stage,
            "reason": decision.reason,
            "suggested_action": decision.suggested_action,
        }

    @app.get("/api/intelligence/modules")
    def intelligence_modules() -> list[dict[str, str]]:
        """List all v5.2 intelligence layer modules."""
        return [
            {"name": "calibrated_decision", "jev_primitive": "Noul/Choice/Score", "description": "校准概率+置信度替代硬阈值"},
            {"name": "confidence_gate", "jev_primitive": "Confidence-gated routing", "description": "高→通过/中→复核/低→拒绝"},
            {"name": "best_of_n", "jev_primitive": "Best-of-N arbitration", "description": "多候选取最优，替代串行重试"},
            {"name": "loop_breaker", "jev_primitive": "Stuck detection", "description": "重试循环早停，省生成预算"},
            {"name": "speculative_fanout", "jev_primitive": "Parallel fan-out", "description": "多检查一次性并行评估"},
            {"name": "model_cascade", "jev_primitive": "Model cascade", "description": "难度→模型级联，省API成本"},
            {"name": "guardrail", "jev_primitive": "Input/output guardrails", "description": "prompt送API前检测违禁内容"},
            {"name": "patch_verifier", "jev_primitive": "Diff verification", "description": "分镜/配置/角色改动前验连续性"},
        ]

    return app
