"""Guardrail checker — Jev's LLM input/output guard pattern.

Jev's guardrail insight: screen content before it reaches the expensive
generative model and again before output reaches the user. Keep the
policy in code, not in the prompt.

AIComics adaptation: screen prompts before they go to video generation
APIs (which may have content policies) and screen generated descriptions
before they become dialogue/subtitles. This prevents:
  - Sending banned content to paid APIs (wasting credits)
  - Publishing inappropriate dialogue in episodes
  - Triggering provider account suspensions

Usage:
    from aicomic.intelligence.guardrail import Guardrail, GuardResult

    guard = Guardrail()
    result = guard.check_prompt("a beautiful sunset over the mountains")
    if result.blocked:
        skip_generation(result.reason)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aicomic.intelligence.calibrated_decision import DecisionEngine, Noul


class GuardLevel(Enum):
    """Severity levels for guardrail hits."""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GuardResult:
    """Result of a guardrail check."""
    level: GuardLevel
    score: float  # 0-1, higher = more dangerous
    confidence: float
    reason: str
    flagged_categories: list[str] = field(default_factory=list)
    redacted_text: str = ""


class Guardrail:
    """Screen prompts and outputs before/after generation.

    Jev pattern: use Noul (is this dangerous?) + Score (how dangerous?)
    to produce a calibrated risk assessment. Code then decides whether
    to pass, warn, or block based on configurable thresholds.
    """

    # Content categories that trigger guardrails
    BANNED_KEYWORDS: dict[str, list[str]] = {
        "violence_extreme": ["gore", "dismember", "beheading", "torture explicit"],
        "sexual_explicit": ["explicit sex", "pornographic", "nude explicit"],
        "hate_speech": ["racial slur", "ethnic cleansing propaganda"],
        "self_harm": ["suicide method", "self-harm instruction"],
        "personal_info": ["social security number", "credit card number", "home address"],
    }

    WARNING_KEYWORDS: dict[str, list[str]] = {
        "violence_mild": ["fight", "punch", "blood", "weapon", "sword", "gun"],
        "sensitive_topic": ["politics", "religion", "race", "war"],
        "mild_language": ["damn", "hell"],
    }

    def __init__(
        self,
        block_threshold: float = 0.8,
        warn_threshold: float = 0.4,
        engine: DecisionEngine | None = None,
    ) -> None:
        self.block_threshold = block_threshold
        self.warn_threshold = warn_threshold
        self.engine = engine or DecisionEngine()

    def check_prompt(self, text: str) -> GuardResult:
        """Check a generation prompt for policy violations.

        Args:
            text: The prompt text to check.

        Returns:
            GuardResult with level (PASS/WARN/BLOCK), score, and reason.
        """
        text_lower = text.lower()
        flagged: list[str] = []
        danger_score = 0.0

        # Check banned keywords (each hit is serious)
        for category, keywords in self.BANNED_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    flagged.append(category)
                    danger_score += 0.3

        # Check warning keywords (each hit is minor)
        for category, keywords in self.WARNING_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    if category not in flagged:
                        flagged.append(category)
                    danger_score += 0.1

        # Cap at 1.0
        danger_score = min(1.0, danger_score)

        # Use calibrated Noul for additional assessment
        noul: Noul = self.engine.noul(
            state=text,
            instructions="Does this prompt contain content that could violate a video generation API policy?",
        )

        # Combine heuristic danger score with calibrated assessment
        combined_score = (danger_score * 0.6 + noul.probability * 0.4)
        combined_score = min(1.0, combined_score)
        confidence = max(noul.confidence, 0.3 + 0.1 * len(flagged))

        # Determine level
        if combined_score >= self.block_threshold:
            level = GuardLevel.BLOCK
            reason = f"Content blocked: {', '.join(flagged)} (score={combined_score:.2f})"
        elif combined_score >= self.warn_threshold:
            level = GuardLevel.WARN
            reason = f"Content flagged: {', '.join(flagged)} (score={combined_score:.2f}) — proceed with caution"
        else:
            level = GuardLevel.PASS
            reason = f"Content clean (score={combined_score:.2f})"

        # Build redacted version
        redacted = text
        for category, keywords in self.BANNED_KEYWORDS.items():
            for kw in keywords:
                if kw in redacted.lower():
                    # Replace case-insensitively
                    import re
                    redacted = re.sub(re.escape(kw), "[REDACTED]", redacted, flags=re.IGNORECASE)

        return GuardResult(
            level=level,
            score=round(combined_score, 4),
            confidence=round(confidence, 4),
            reason=reason,
            flagged_categories=flagged,
            redacted_text=redacted,
        )

    def check_output(self, text: str) -> GuardResult:
        """Check generated output (dialogue, subtitles) for appropriateness.

        Similar to check_prompt but with different thresholds — output
        has a lower tolerance for issues since it goes to end users.

        Args:
            text: Generated text to check.

        Returns:
            GuardResult with level and recommendations.
        """
        result = self.check_prompt(text)

        # Downgrade: if output is WARN, treat as BLOCK for published content
        if result.level == GuardLevel.WARN:
            return GuardResult(
                level=GuardLevel.BLOCK,
                score=result.score,
                confidence=result.confidence,
                reason=f"Output blocked (stricter for published content): {result.reason}",
                flagged_categories=result.flagged_categories,
                redacted_text=result.redacted_text,
            )

        return result

    def check_batch(self, texts: list[str], is_output: bool = False) -> list[GuardResult]:
        """Check multiple texts in batch.

        Args:
            texts: List of texts to check.
            is_output: If True, use stricter output thresholds.

        Returns:
            List of GuardResults.
        """
        if is_output:
            return [self.check_output(t) for t in texts]
        return [self.check_prompt(t) for t in texts]
