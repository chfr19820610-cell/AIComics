"""Patch verifier — Jev's diff verification + semantic CI pattern.

Jev's insight: after an agent proposes a change, verify the diff against
explicit team conventions BEFORE applying it. This catches risky changes
that pass compilation but violate architectural boundaries.

AIComics adaptation: when a pipeline stage modifies configuration,
storyboard, or character data, verify the change against conventions:
  - Did the storyboard change break scene continuity?
  - Did a character edit break consistency across episodes?
  - Did a config change alter rendering parameters unsafely?
  - Was a regression test added for the behavior change?

Usage:
    from aicomic.intelligence.patch_verifier import PatchVerifier, VerifyResult

    verifier = PatchVerifier()
    result = verifier.verify_change(
        change_type="storyboard_edit",
        before={"scene_count": 12, "scenes": [...]},
        after={"scene_count": 11, "scenes": [...]},
    )
    if result.should_block:
        reject_change(result.reason)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aicomic.intelligence.calibrated_decision import DecisionEngine, Noul


class VerifyAction(Enum):
    """Actions the verifier can recommend."""
    APPROVE = "approve"
    ANNOTATE = "annotate"   # minor issues, add notes
    REVIEW = "review"       # needs human review
    BLOCK = "block"         # serious violation


@dataclass
class VerifyResult:
    """Result of patch verification."""
    action: VerifyAction
    risk_score: float  # 0-1, higher = riskier
    confidence: float
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reason: str = ""


class PatchVerifier:
    """Verify changes against conventions before applying.

    Jev pattern: use Noul (is this a violation?) + Score (how risky?)
    to produce a calibrated risk assessment for each change. Code then
    routes to approve / annotate / review / block.
    """

    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()

    def verify_change(
        self,
        change_type: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> VerifyResult:
        """Verify a change against conventions.

        Args:
            change_type: Type of change (storyboard_edit, config_change, etc).
            before: State before change.
            after: State after change.

        Returns:
            VerifyResult with action recommendation and risk assessment.
        """
        violations: list[str] = []
        warnings: list[str] = []
        risk = 0.0

        if change_type == "storyboard_edit":
            risk = self._verify_storyboard(before, after, violations, warnings)
        elif change_type == "config_change":
            risk = self._verify_config(before, after, violations, warnings)
        elif change_type == "character_edit":
            risk = self._verify_character(before, after, violations, warnings)
        else:
            # Generic verification
            risk = self._verify_generic(before, after, violations, warnings)

        # Calibrated assessment
        noul: Noul = self.engine.noul(
            state=str(after),
            instructions=f"Does this {change_type} change violate conventions?",
        )
        combined_risk = (risk * 0.7 + noul.probability * 0.3)
        combined_risk = min(1.0, combined_risk)
        confidence = max(noul.confidence, 0.3 + 0.1 * len(violations))

        # Route based on risk and violations
        if violations:
            action = VerifyAction.BLOCK
            reason = f"Blocked: {', '.join(violations)}"
        elif combined_risk >= 0.7:
            action = VerifyAction.REVIEW
            reason = f"High risk ({combined_risk:.2f}) — needs human review"
        elif combined_risk >= 0.4 or warnings:
            action = VerifyAction.ANNOTATE
            reason = f"Minor concerns ({combined_risk:.2f}): {', '.join(warnings) or 'warnings'}"
        else:
            action = VerifyAction.APPROVE
            reason = f"Change approved (risk={combined_risk:.2f})"

        return VerifyResult(
            action=action,
            risk_score=round(combined_risk, 4),
            confidence=round(confidence, 4),
            violations=violations,
            warnings=warnings,
            reason=reason,
        )

    def _verify_storyboard(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        violations: list[str],
        warnings: list[str],
    ) -> float:
        """Verify storyboard changes don't break continuity."""
        risk = 0.0

        before_scenes = before.get("scenes", before.get("scene_count", 0))
        after_scenes = after.get("scenes", after.get("scene_count", 0))

        before_count = len(before_scenes) if isinstance(before_scenes, list) else before_scenes
        after_count = len(after_scenes) if isinstance(after_scenes, list) else after_scenes

        # Scene count decreased — might break episode pacing
        if after_count < before_count:
            diff = before_count - after_count
            if diff > 2:
                violations.append(f"Scene count dropped {before_count}→{after_count} — major pacing disruption")
                risk += 0.4
            else:
                warnings.append(f"Scene count decreased {before_count}→{after_count}")
                risk += 0.15

        # Duration changed significantly
        before_dur = before.get("duration", before.get("total_duration", 0))
        after_dur = after.get("duration", after.get("total_duration", 0))
        if before_dur > 0 and after_dur > 0:
            change_ratio = abs(after_dur - before_dur) / before_dur
            if change_ratio > 0.3:
                violations.append(f"Duration changed {change_ratio:.0%} — exceeds 30% threshold")
                risk += 0.3

        # Character removed
        before_chars = set(before.get("characters", []))
        after_chars = set(after.get("characters", []))
        removed = before_chars - after_chars
        if removed:
            warnings.append(f"Characters removed: {removed}")
            risk += 0.1

        return min(1.0, risk)

    def _verify_config(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        violations: list[str],
        warnings: list[str],
    ) -> float:
        """Verify config changes don't break rendering."""
        risk = 0.0

        # Check critical rendering parameters
        critical_params = ["fps", "resolution", "bitrate", "codec"]
        for param in critical_params:
            if param in before and param in after:
                if before[param] != after[param]:
                    warnings.append(f"{param} changed: {before[param]}→{after[param]}")
                    risk += 0.1

        # Resolution downgrade is risky
        before_res = before.get("resolution", "")
        after_res = after.get("resolution", "")
        if before_res and after_res and before_res != after_res:
            before_num = int(before_res.replace("p", "").replace("k", "000")) if before_res else 0
            after_num = int(after_res.replace("p", "").replace("k", "000")) if after_res else 0
            if after_num < before_num:
                violations.append(f"Resolution downgrade {before_res}→{after_res}")
                risk += 0.3

        return min(1.0, risk)

    def _verify_character(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        violations: list[str],
        warnings: list[str],
    ) -> float:
        """Verify character edits don't break consistency."""
        risk = 0.0

        # Name changed — breaks references across episodes
        if before.get("name") != after.get("name"):
            violations.append(f"Character name changed: '{before.get('name')}'→'{after.get('name')}'")
            risk += 0.3

        # Visual identity changed
        before_style = before.get("style", before.get("appearance", ""))
        after_style = after.get("style", after.get("appearance", ""))
        if before_style and after_style and before_style != after_style:
            warnings.append("Character visual style changed — may break cross-episode consistency")
            risk += 0.15

        return min(1.0, risk)

    def _verify_generic(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        violations: list[str],
        warnings: list[str],
    ) -> float:
        """Generic change verification."""
        risk = 0.0

        # Check for key removal
        before_keys = set(before.keys())
        after_keys = set(after.keys())
        removed_keys = before_keys - after_keys
        if removed_keys:
            warnings.append(f"Keys removed: {removed_keys}")
            risk += 0.1

        return min(1.0, risk)
