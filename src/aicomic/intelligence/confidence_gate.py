"""Confidence-gated action routing — Jev's confidence-gated escalation pattern.

Jev's core insight: don't use a single hard threshold. Use calibrated
confidence to route decisions to act / flag / escalate. This mirrors
how a senior engineer reviews: confident decisions ship, uncertain
ones get a second look, risky ones get human sign-off.

AIComics adaptation:
  - Quality gate: score > 80 + confidence > 0.7 → PASS (act)
  - Quality gate: score 50-80 or confidence 0.3-0.7 → REVIEW (flag)
  - Quality gate: score < 50 or confidence < 0.3 → REJECT (escalate)

The gate is *configurable per pipeline stage* — a thumbnail check can
be lenient, a final render must be strict.

Usage:
    from aicomic.intelligence.confidence_gate import ConfidenceGate, GateDecision

    gate = ConfidenceGate(
        pass_threshold=80, pass_confidence=0.7,
        review_threshold=50, review_confidence=0.3,
    )
    decision = gate.evaluate(score=75, confidence=0.5, stage="quality_check")
    if decision.action == GateAction.PASS:
        accept()
    elif decision.action == GateAction.REVIEW:
        flag_for_review(decision.reason)
    else:
        reject(decision.reason)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateAction(Enum):
    """Possible gate actions, ordered by confidence level."""
    REJECT = "reject"      # low score or low confidence → don't ship
    REVIEW = "review"      # medium confidence → flag for second look
    PASS = "pass"          # high confidence → ship it
    ESCALATE = "escalate"  # explicitly needs human/higher-level review


@dataclass
class GateDecision:
    """Result of a confidence-gated evaluation."""
    action: GateAction
    score: float
    confidence: float
    stage: str
    reason: str
    suggested_action: str = ""


class ConfidenceGate:
    """Configurable confidence-gated decision router.

    Maps a (score, confidence) pair to one of PASS / REVIEW / REJECT,
    with per-stage configuration for different strictness levels.
    """

    # Preset configurations for different pipeline stages
    STAGE_PRESETS: dict[str, dict[str, float]] = {
        "thumbnail": {
            "pass_threshold": 60, "pass_confidence": 0.5,
            "review_threshold": 30, "review_confidence": 0.2,
        },
        "quality_check": {
            "pass_threshold": 80, "pass_confidence": 0.7,
            "review_threshold": 50, "review_confidence": 0.3,
        },
        "final_render": {
            "pass_threshold": 90, "pass_confidence": 0.8,
            "review_threshold": 70, "review_confidence": 0.5,
        },
        "artifact_check": {
            "pass_threshold": 85, "pass_confidence": 0.6,
            "review_threshold": 50, "review_confidence": 0.3,
        },
    }

    def __init__(
        self,
        pass_threshold: float = 80,
        pass_confidence: float = 0.7,
        review_threshold: float = 50,
        review_confidence: float = 0.3,
    ) -> None:
        self.pass_threshold = pass_threshold
        self.pass_confidence = pass_confidence
        self.review_threshold = review_threshold
        self.review_confidence = review_confidence

    @classmethod
    def for_stage(cls, stage: str) -> "ConfidenceGate":
        """Create a gate configured for a specific pipeline stage."""
        preset = cls.STAGE_PRESETS.get(stage)
        if preset:
            return cls(**preset)
        return cls()

    def evaluate(
        self,
        score: float,
        confidence: float,
        stage: str = "default",
        force_escalate: bool = False,
    ) -> GateDecision:
        """Evaluate a score+confidence pair and route to an action.

        Args:
            score: Quality score (0-100).
            confidence: Calibration confidence (0-1).
            stage: Pipeline stage name (for logging/presets).
            force_escalate: Override to force escalation (e.g., red-line hit).

        Returns:
            GateDecision with action, reason, and suggested next step.
        """
        if force_escalate:
            return GateDecision(
                action=GateAction.ESCALATE,
                score=score,
                confidence=confidence,
                stage=stage,
                reason="Force escalate — red-line or manual override",
                suggested_action="Human review required before proceeding",
            )

        # PASS: high score AND high confidence
        if score >= self.pass_threshold and confidence >= self.pass_confidence:
            return GateDecision(
                action=GateAction.PASS,
                score=score,
                confidence=confidence,
                stage=stage,
                reason=f"Score {score:.0f} ≥ {self.pass_threshold} and confidence {confidence:.2f} ≥ {self.pass_confidence}",
                suggested_action="Proceed to next stage",
            )

        # REJECT: very low score regardless of confidence
        if score < self.review_threshold:
            return GateDecision(
                action=GateAction.REJECT,
                score=score,
                confidence=confidence,
                stage=stage,
                reason=f"Score {score:.0f} < {self.review_threshold} — below minimum quality",
                suggested_action="Regenerate with different parameters",
            )

        # REJECT: low confidence on a borderline score
        if confidence < self.review_confidence and score < self.pass_threshold:
            return GateDecision(
                action=GateAction.REJECT,
                score=score,
                confidence=confidence,
                stage=stage,
                reason=f"Confidence {confidence:.2f} < {self.review_confidence} on borderline score {score:.0f}",
                suggested_action="Re-evaluate with additional checks or regenerate",
            )

        # REVIEW: medium zone — not clearly pass or reject
        return GateDecision(
            action=GateAction.REVIEW,
            score=score,
            confidence=confidence,
            stage=stage,
            reason=f"Borderline: score {score:.0f} (need {self.pass_threshold}), confidence {confidence:.2f} (need {self.pass_confidence})",
            suggested_action="Flag for manual review or secondary check",
        )

    def evaluate_batch(
        self,
        evaluations: list[dict[str, float]],
        stage: str = "default",
    ) -> list[GateDecision]:
        """Evaluate multiple score+confidence pairs.

        Args:
            evaluations: List of {"score": float, "confidence": float} dicts.
            stage: Pipeline stage name.

        Returns:
            List of GateDecisions in the same order.
        """
        return [
            self.evaluate(
                score=e.get("score", 0.0),
                confidence=e.get("confidence", 0.0),
                stage=stage,
                force_escalate=bool(e.get("force_escalate", False)),
            )
            for e in evaluations
        ]
