"""Best-of-N generation arbitration — Jev pilot pattern, distilled locally.

Jev-pilot's `arbitrate()` picks the winning candidate from multiple LLM
outputs using calibrated choice. We distill this for video generation:
generate N candidate shots in parallel, score each with calibrated metrics,
then pick the winner with confidence-gated escalation.

Usage:
    from aicomic.intelligence.best_of_n import BestOfNArbitrator, Candidate

    arb = BestOfNArbitrator()
    candidates = [
        Candidate(id="a", prompt="...", score_quality=85, score_artifact=90),
        Candidate(id="b", prompt="...", score_quality=78, score_artifact=95),
        Candidate(id="c", prompt="...", score_quality=92, score_artifact=60),
    ]
    result = arb.arbitrate(candidates)
    print(f"Winner: {result.winner_id} (confidence: {result.confidence:.2f})")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aicomic.intelligence.calibrated_decision import DecisionEngine, Choice


@dataclass
class Candidate:
    """A single generation candidate for Best-of-N arbitration."""
    id: str
    prompt: str = ""
    score_quality: float = 0.0       # 0-100
    score_artifact: float = 0.0      # 0-100
    score_drift: float = 0.0         # 0-100
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArbitrationResult:
    """Result of Best-of-N arbitration."""
    winner_id: str
    confidence: float
    ranking: list[dict[str, Any]]  # sorted best-to-worst
    reason: str
    should_escalate: bool = False   # True if confidence too low


class BestOfNArbitrator:
    """Arbitrate among N candidates using Jev's calibrated choice pattern.

    Instead of sequential retry (generate→check→fail→regenerate),
    generate N candidates once and pick the best. Falls back to
    sequential retry only when all candidates are poor.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        quality_floor: float = 50.0,
    ) -> None:
        self.engine = DecisionEngine()
        self.confidence_threshold = confidence_threshold
        self.quality_floor = quality_floor

    def arbitrate(
        self,
        candidates: list[Candidate],
        context: str = "",
    ) -> ArbitrationResult:
        """Pick the best candidate with calibrated confidence.

        Args:
            candidates: N generation candidates with quality/artifact/drift scores.
            context: Optional context for semantic matching.

        Returns:
            ArbitrationResult with winner, ranking, and escalation flag.
        """
        if not candidates:
            return ArbitrationResult(
                winner_id="",
                confidence=0.0,
                ranking=[],
                reason="No candidates provided",
                should_escalate=True,
            )

        if len(candidates) == 1:
            c = candidates[0]
            return ArbitrationResult(
                winner_id=c.id,
                confidence=0.5,
                ranking=[{"id": c.id, "composite": c.score_quality}],
                reason="Single candidate — no arbitration needed",
            )

        # Build composite scores (quality 40%, artifact 35%, drift 25%)
        composites: dict[str, float] = {}
        for c in candidates:
            composite = (
                c.score_quality * 0.40
                + c.score_artifact * 0.35
                + c.score_drift * 0.25
            )
            composites[c.id] = round(composite, 2)

        # Use calibrated choice for winner selection
        # Build option descriptions from composite scores
        options = {
            c.id: f"quality={c.score_quality} artifact={c.score_artifact} drift={c.score_drift} composite={composites[c.id]}"
            for c in candidates
        }
        choice_result: Choice = self.engine.choice(
            state=f"{context} quality artifact drift",
            options=options,
        )

        # Build ranking sorted by composite score
        ranking = sorted(
            (
                {
                    "id": c.id,
                    "composite": composites[c.id],
                    "quality": c.score_quality,
                    "artifact": c.score_artifact,
                    "drift": c.score_drift,
                    "probability": choice_result.probabilities.get(c.id, 0),
                }
                for c in candidates
            ),
            key=lambda x: x["composite"],
            reverse=True,
        )

        winner_id = ranking[0]["id"]
        winner_composite = ranking[0]["composite"]

        # Confidence from choice dominance
        confidence = choice_result.confidence

        # Escalate if below quality floor or low confidence
        should_escalate = (
            winner_composite < self.quality_floor
            or confidence < self.confidence_threshold
        )

        reason = (
            f"Winner {winner_id} composite={winner_composite} "
            f"confidence={confidence:.2f}"
        )
        if should_escalate:
            reason += " → ESCALATE (below threshold)"

        return ArbitrationResult(
            winner_id=winner_id,
            confidence=confidence,
            ranking=ranking,
            reason=reason,
            should_escalate=should_escalate,
        )
