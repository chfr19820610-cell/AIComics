"""Drift Gate — post-generation consistency checking (v4.0 P0-3).

Compares generated image features against character reference features.
Returns PASS / WARN / FAIL with a drift score (0-100) and per-attribute diffs.

Design: 极简, <400 行. Pure logic — no image I/O. Callers supply feature dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriftResult:
    """Result of a single drift gate check."""

    status: str  # PASS / WARN / FAIL
    score: int  # 0-100, higher = more consistent
    diffs: list[dict[str, Any]] = field(default_factory=list)
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "diffs": self.diffs,
            "max_retries": self.max_retries,
        }


class DriftGate:
    """Consistency gate: compare reference vs generated features.

    Usage:
        gate = DriftGate(threshold=60)
        result = gate.check(reference_features, generated_features, score=85)
        if result["status"] == "FAIL":
            # trigger rework
    """

    def __init__(self, threshold: int = 60, warn_threshold: int = 75) -> None:
        self.threshold = threshold
        self.warn_threshold = warn_threshold

    def check(
        self,
        reference_features: dict[str, Any],
        generated_features: dict[str, Any],
        score: int | None = None,
    ) -> dict[str, Any]:
        """Run drift gate. Returns dict with status, score, diffs."""
        if score is not None:
            final_score = score
        else:
            final_score = self._compute_score(reference_features, generated_features)

        diffs = self._compute_diffs(reference_features, generated_features)

        if final_score >= self.warn_threshold:
            status = "PASS"
        elif final_score >= self.threshold:
            status = "WARN"
        else:
            status = "FAIL"

        return {
            "status": status,
            "score": final_score,
            "diffs": diffs,
            "max_retries": 3,
        }

    def _compute_score(
        self, reference: dict[str, Any], generated: dict[str, Any]
    ) -> int:
        """Compute similarity score 0-100 based on feature overlap."""
        if not reference:
            return 100
        total = len(reference)
        matched = 0
        for key, ref_val in reference.items():
            gen_val = generated.get(key)
            if gen_val == ref_val:
                matched += 1
            elif gen_val is not None and self._fuzzy_match(ref_val, gen_val):
                matched += 1
        return int((matched / total) * 100) if total > 0 else 100

    def _compute_diffs(
        self, reference: dict[str, Any], generated: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Compute per-attribute differences."""
        diffs: list[dict[str, Any]] = []
        all_keys = set(reference.keys()) | set(generated.keys())
        for key in all_keys:
            ref_val = reference.get(key)
            gen_val = generated.get(key)
            if ref_val != gen_val:
                diffs.append(
                    {
                        "attribute": key,
                        "reference": ref_val,
                        "generated": gen_val,
                        "match": self._fuzzy_match(ref_val, gen_val) if gen_val else False,
                    }
                )
        return diffs

    @staticmethod
    def _fuzzy_match(a: Any, b: Any) -> bool:
        """Loose string match — same root or substring."""
        if not isinstance(a, str) or not isinstance(b, str):
            return a == b
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()
        if a_lower == b_lower:
            return True
        # Check substring (e.g. "black" in "dark_black")
        return a_lower in b_lower or b_lower in a_lower


def run_drift_gate_on_shot(
    shot: dict[str, Any],
    character_references: dict[str, dict[str, Any]],
    gate: DriftGate | None = None,
) -> dict[str, Any]:
    """Convenience: run drift gate for a single shot.

    Args:
        shot: Shot dict with character_id and generated_features.
        character_references: {character_id: {feature: value}}.
        gate: Optional DriftGate instance.

    Returns:
        Gate result dict.
    """
    if gate is None:
        gate = DriftGate()

    char_id = shot.get("character_id", "")
    ref = character_references.get(char_id, {})
    gen = shot.get("generated_features", {})

    return gate.check(ref, gen)
