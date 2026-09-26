"""Speculative fan-out evaluation — Jev's parallel question pattern.

Jev's key efficiency insight: ask ALL questions about a state in one
call, not serially. The model evaluates them independently. Code then
ignores irrelevant answers.

AIComics adaptation: instead of running quality_gate → artifact_detector
→ drift_checker → playback_review in sequence (4 passes), evaluate all
four checks against the same frame/shot metadata in one pass and combine
the results. Saves latency and lets cross-checks inform each other.

Usage:
    from aicomic.intelligence.speculative_fanout import SpeculativeFanout

    fanout = SpeculativeFanout()
    results = fanout.evaluate(
        state="shot: close-up, 24fps, 720p, 6 fingers detected",
        checks={
            "quality": {"type": "score", "levels": ["Poor", "OK", "Good", "Excellent"]},
            "has_artifact": {"type": "noul", "instructions": "Are there visual artifacts?"},
            "drift_risk": {"type": "score", "levels": ["Stable", "Minor drift", "Severe drift"]},
        },
    )
    if results["has_artifact"].probability > 0.5:
        reject()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aicomic.intelligence.calibrated_decision import DecisionEngine


@dataclass
class FanoutResult:
    """Result of a speculative fan-out evaluation."""
    answers: dict[str, Any] = field(default_factory=dict)
    combined_confidence: float = 0.0
    dominant_signal: str = ""
    summary: str = ""


class SpeculativeFanout:
    """Evaluate multiple independent checks against the same state in one pass.

    Mirrors Jev's speculative fan-out: ask all questions up front, let
    code decide which answers matter. Cheaper than serial evaluation
    because the state is analyzed once, not N times.
    """

    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()

    def evaluate(
        self,
        state: str,
        checks: dict[str, dict[str, Any]],
    ) -> FanoutResult:
        """Run all checks against the same state in one pass.

        Args:
            state: The shared context (frame metadata, shot description, etc).
            checks: {name: {"type": "noul"/"choice"/"score", ...}}

        Returns:
            FanoutResult with all answers, combined confidence, and summary.
        """
        answers = self.engine.batch(state=state, questions=checks)

        # Combine confidences — geometric mean penalizes any single low-confidence answer
        confidences = []
        for result in answers.values():
            if hasattr(result, "confidence"):
                confidences.append(result.confidence)

        if confidences:
            # Geometric mean (add epsilon to avoid log(0))
            import math
            log_sum = sum(math.log(max(c, 0.001)) for c in confidences)
            combined_confidence = round(math.exp(log_sum / len(confidences)), 4)
        else:
            combined_confidence = 0.0

        # Find dominant signal — the check with highest confidence
        dominant_signal = ""
        max_conf = 0.0
        for name, result in answers.items():
            if hasattr(result, "confidence") and result.confidence > max_conf:
                max_conf = result.confidence
                dominant_signal = name

        # Build human-readable summary
        summary_parts: list[str] = []
        for name, result in answers.items():
            if hasattr(result, "probability"):
                summary_parts.append(f"{name}: p={result.probability:.2f}")
            elif hasattr(result, "score"):
                summary_parts.append(f"{name}: score={result.score:.1f}")
            elif hasattr(result, "winner"):
                summary_parts.append(f"{name}: {result.winner}")
        summary = " | ".join(summary_parts)

        return FanoutResult(
            answers=answers,
            combined_confidence=combined_confidence,
            dominant_signal=dominant_signal,
            summary=summary,
        )

    def evaluate_with_gate(
        self,
        state: str,
        checks: dict[str, dict[str, Any]],
        gate_check: str = "",
        pass_threshold: float = 80,
    ) -> tuple[FanoutResult, bool]:
        """Evaluate checks and apply a pass/fail gate on one specific check.

        Args:
            state: The shared context.
            checks: All checks to run.
            gate_check: Name of the check to use as the pass/fail gate.
            pass_threshold: Score threshold for the gate check.

        Returns:
            (FanoutResult, passed) tuple.
        """
        result = self.evaluate(state=state, checks=checks)

        if gate_check and gate_check in result.answers:
            gate_answer = result.answers[gate_check]
            if hasattr(gate_answer, "score"):
                passed = gate_answer.score >= pass_threshold
            elif hasattr(gate_answer, "probability"):
                passed = gate_answer.probability >= pass_threshold / 100
            else:
                passed = False
        else:
            passed = False

        return result, passed
