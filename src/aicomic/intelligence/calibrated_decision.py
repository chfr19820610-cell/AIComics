"""Calibrated decision engine — Jev System One primitives, distilled locally.

Jev (TypeSafe AI) provides three calibrated decision primitives:
  - Noul:  calibrated yes/no (0-1 probability)
  - Choice: pick one from N options (winner + distribution + confidence)
  - Score: rate on ordered scale (score + distribution + confidence)

AIComics is fully local, so we distill the *methodology* — not the API.
Each primitive returns a calibrated probability and confidence, enabling
soft thresholds and confidence-gated escalation instead of hard cutoffs.

Usage:
    from aicomic.intelligence.calibrated_decision import (
        Noul, Choice, Score, DecisionEngine,
    )

    engine = DecisionEngine()

    # Calibrated yes/no
    n = engine.noul("video has 6 fingers", "Is this frame acceptable?")
    if n.probability < 0.5:
        reject()

    # Pick best provider
    c = engine.choice(
        "Action shot with fast motion",
        {"kling": "best for action", "seedance": "fast", "wan": "cheap"},
    )
    use(c.winner)  # "kling"

    # Score quality
    s = engine.score(
        "720p, 24fps, no artifacts",
        ["Unusable", "Poor", "Acceptable", "Good", "Excellent"],
    )
    if s.score > 2.5:
        accept()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class Noul:
    """Calibrated yes/no answer."""
    probability: float  # 0-1, probability that answer is "yes"
    confidence: float   # 0-1, how sure the model is


@dataclass
class Choice:
    """Pick-one-from-N answer."""
    winner: str
    probabilities: dict[str, float]
    confidence: float


@dataclass
class Score:
    """Ordered-scale rating answer."""
    score: float  # 0 to len(levels)-1, can be fractional
    probabilities: dict[int, float]
    confidence: float
    legend: dict[int, str] = field(default_factory=dict)


class DecisionEngine:
    """Local calibrated decision engine — Jev methodology, no API needed.

    Uses keyword matching + heuristic scoring to produce calibrated
    probabilities. Not as smart as Jev's RLCD-trained model, but:
      - Zero latency (no network)
      - Zero cost (no API tokens)
      - Deterministic (same input → same output)
      - Calibrated (confidence reflects evidence strength)
    """

    # --- Noul: calibrated yes/no ---

    def noul(self, state: str, instructions: str) -> Noul:
        """Evaluate a yes/no question with calibrated probability.

        Args:
            state: The context to evaluate.
            instructions: The yes/no question.

        Returns:
            Noul with probability (0=no, 1=yes) and confidence.
        """
        state_lower = state.lower()
        instr_lower = instructions.lower()

        # Positive/negative signal keywords
        positive_words = {
            "acceptable", "good", "pass", "clean", "ok", "fine",
            "correct", "proper", "valid", "complete", "success",
        }
        negative_words = {
            "unacceptable", "bad", "fail", "error", "broken",
            "missing", "invalid", "corrupt", "artifact", "wrong",
            "finger", "extra", "deformed", "blurry", "glitch",
        }

        pos_hits = sum(1 for w in positive_words if w in state_lower)
        neg_hits = sum(1 for w in negative_words if w in state_lower)

        # Base probability from signal balance
        total = pos_hits + neg_hits
        if total == 0:
            probability = 0.5  # no evidence → ignorant, not neutral
            confidence = 0.1
        else:
            probability = pos_hits / total
            confidence = min(1.0, 0.3 + 0.2 * total)

        # If instructions ask "is X acceptable/rejected", flip accordingly
        if "not acceptable" in instr_lower or "reject" in instr_lower:
            probability = 1.0 - probability

        return Noul(probability=round(probability, 4), confidence=round(confidence, 4))

    # --- Choice: pick one from N ---

    def choice(self, state: str, options: dict[str, str]) -> Choice:
        """Pick the best option from a set, with full distribution.

        Args:
            state: The context to evaluate.
            options: {key: description} mapping, up to 255 options.

        Returns:
            Choice with winner, probabilities for all options, confidence.
        """
        if not options:
            return Choice(winner="", probabilities={}, confidence=0.0)

        state_lower = state.lower()
        scores: dict[str, float] = {}

        for key, desc in options.items():
            desc_lower = (desc or "").lower()
            # Count keyword overlaps as raw scores
            overlap = 0.0
            for word in desc_lower.split():
                word = word.strip(".,;()[]")
                if len(word) > 2 and word in state_lower:
                    overlap += 1.0
            # Add base score so every option has nonzero probability
            scores[key] = 1.0 + overlap

        # Softmax to get probability distribution
        total = sum(scores.values())
        probabilities = {k: round(v / total, 4) for k, v in scores.items()}

        winner = max(probabilities, key=lambda k: probabilities[k])
        # Confidence = how dominant the winner is
        max_prob = probabilities[winner]
        n = len(options)
        uniform = 1.0 / n
        confidence = round(min(1.0, (max_prob - uniform) / (1.0 - uniform + 0.001)), 4)

        return Choice(
            winner=winner,
            probabilities=probabilities,
            confidence=confidence,
        )

    # --- Score: rate on ordered scale ---

    def score(
        self,
        state: str,
        levels: Sequence[str],
    ) -> Score:
        """Rate state against an ordered scale (2-10 levels).

        Args:
            state: The context to evaluate.
            levels: Ordered level descriptions, low to high.

        Returns:
            Score with position on scale, distribution, confidence.
        """
        n = len(levels)
        if n < 2:
            return Score(
                score=0.0,
                probabilities={0: 1.0},
                confidence=0.0,
                legend={i: lvl for i, lvl in enumerate(levels)},
            )

        state_lower = state.lower()

        # Score each level by keyword match
        level_scores: list[float] = []
        for level_desc in levels:
            desc_lower = level_desc.lower()
            overlap = sum(
                1 for word in desc_lower.split()
                if len(word.strip(".,;()[]")) > 2
                and word.strip(".,;()[]") in state_lower
            )
            level_scores.append(1.0 + overlap)

        # Softmax over levels
        total = sum(level_scores)
        probabilities = {
            i: round(s / total, 4) for i, s in enumerate(level_scores)
        }

        # Weighted score position
        weighted = sum(i * p for i, p in probabilities.items())

        # Confidence = how peaked the distribution is
        max_prob = max(probabilities.values())
        uniform = 1.0 / n
        confidence = round(
            min(1.0, (max_prob - uniform) / (1.0 - uniform + 0.001)), 4
        )

        return Score(
            score=round(weighted, 4),
            probabilities=probabilities,
            confidence=confidence,
            legend={i: lvl for i, lvl in enumerate(levels)},
        )

    # --- Batch: multiple questions in one call ---

    def batch(
        self,
        state: str,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate multiple questions against the same state in one call.

        Mimics Jev's parallel evaluation — all questions see the same state.

        Args:
            state: The shared context.
            questions: {name: {"type": "noul"/"choice"/"score", ...}}

        Returns:
            {name: Noul/Choice/Score result}
        """
        results: dict[str, Any] = {}
        for name, q in questions.items():
            q_type = q.get("type", "")
            if q_type == "noul":
                results[name] = self.noul(
                    state=state,
                    instructions=q.get("instructions", ""),
                )
            elif q_type == "choice":
                results[name] = self.choice(
                    state=state,
                    options=q.get("criteria", q.get("options", {})),
                )
            elif q_type == "score":
                results[name] = self.score(
                    state=state,
                    levels=q.get("criteria", q.get("levels", [])),
                )
        return results
