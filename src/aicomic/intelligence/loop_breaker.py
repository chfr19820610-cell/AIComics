"""Loop breaker — Jev pilot's stuck-detection pattern, distilled locally.

Jev-pilot's `check_stuck()` detects when an agent is repeating the same
approach without progress. We distill this for AIComics' auto-retry loop:
detect repeated failure patterns and break early instead of wasting
generation budget on the same error.

Usage:
    from aicomic.intelligence.loop_breaker import LoopBreaker

    breaker = LoopBreaker()
    for attempt in retry_loop:
        result = generate(...)
        signal = breaker.observe(result.issues, result.score)
        if signal.should_break:
            break
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoopSignal:
    """Signal from loop breaker — should we continue or break?"""
    should_break: bool
    reason: str
    repetition_count: int = 0
    unique_issues: list[str] = field(default_factory=list)
    progress_score: float = 0.0  # -1=regressing, 0=stuck, 1=progressing


class LoopBreaker:
    """Detect unproductive retry loops in video generation.

    Tracks the issue history across retry attempts. When the same issues
    recur without improvement, signals the loop to break early — saving
    generation tokens that would be wasted on the same error.

    Detection criteria:
      1. Exact issue repetition (same issue strings ≥ N times)
      2. Issue pattern similarity (overlapping keywords ≥ threshold)
      3. Score stagnation (no improvement over K attempts)
      4. Score regression (score decreasing)
    """

    def __init__(
        self,
        max_repeats: int = 2,
        stagnation_window: int = 3,
        similarity_threshold: float = 0.7,
        min_improvement: float = 5.0,
    ) -> None:
        self.max_repeats = max_repeats
        self.stagnation_window = stagnation_window
        self.similarity_threshold = similarity_threshold
        self.min_improvement = min_improvement

        self._issue_history: list[list[str]] = []
        self._score_history: list[float] = []

    def observe(
        self,
        issues: list[str],
        score: float = 0.0,
    ) -> LoopSignal:
        """Observe one retry attempt and decide whether to break.

        Args:
            issues: List of issue strings from this attempt.
            score: Quality/composite score for this attempt.

        Returns:
            LoopSignal with should_break flag and reason.
        """
        self._issue_history.append(issues.copy())
        self._score_history.append(score)

        attempt_count = len(self._issue_history)

        # Need at least 2 attempts to detect patterns
        if attempt_count < 2:
            return LoopSignal(
                should_break=False,
                reason="First attempt — no pattern yet",
                repetition_count=0,
                unique_issues=issues,
                progress_score=0.0,
            )

        # 1. Exact repetition check
        current_set = set(issues)
        repeat_count = 0
        for past_issues in self._issue_history[:-1]:
            if set(past_issues) == current_set and issues:
                repeat_count += 1

        if repeat_count >= self.max_repeats:
            return LoopSignal(
                should_break=True,
                reason=f"Same issues repeated {repeat_count}x — breaking to save tokens",
                repetition_count=repeat_count,
                unique_issues=list(current_set),
                progress_score=-1.0,
            )

        # 2. Pattern similarity check
        if attempt_count >= 2:
            max_similarity = 0.0
            for past_issues in self._issue_history[:-1]:
                sim = self._jaccard_similarity(past_issues, issues)
                max_similarity = max(max_similarity, sim)

            if max_similarity >= self.similarity_threshold and issues:
                # High similarity — check if score is improving
                progress = self._assess_progress()
                if progress <= 0:
                    return LoopSignal(
                        should_break=True,
                        reason=f"Issue similarity {max_similarity:.0%} with no progress — breaking",
                        repetition_count=repeat_count,
                        unique_issues=list(current_set),
                        progress_score=progress,
                    )

        # 3. Score stagnation check
        if attempt_count >= self.stagnation_window:
            recent = self._score_history[-self.stagnation_window:]
            if max(recent) - min(recent) < self.min_improvement:
                return LoopSignal(
                    should_break=True,
                    reason=f"Score stagnated over {self.stagnation_window} attempts (range < {self.min_improvement})",
                    repetition_count=repeat_count,
                    unique_issues=list(current_set),
                    progress_score=0.0,
                )

        # 4. Score regression check
        if attempt_count >= 2:
            progress = self._assess_progress()
            if progress < -self.min_improvement:
                return LoopSignal(
                    should_break=True,
                    reason=f"Score regressing ({progress:.1f} pts) — breaking",
                    repetition_count=repeat_count,
                    unique_issues=list(current_set),
                    progress_score=progress,
                )

        # All clear — continue
        progress = self._assess_progress()
        return LoopSignal(
            should_break=False,
            reason=f"Attempt {attempt_count} — progressing (score={score}, progress={progress:.1f})",
            repetition_count=repeat_count,
            unique_issues=list(current_set),
            progress_score=progress,
        )

    def reset(self) -> None:
        """Clear history for a new generation task."""
        self._issue_history.clear()
        self._score_history.clear()

    def _assess_progress(self) -> float:
        """Assess whether scores are improving. Returns delta."""
        if len(self._score_history) < 2:
            return 0.0
        return self._score_history[-1] - self._score_history[0]

    @staticmethod
    def _jaccard_similarity(a: list[str], b: list[str]) -> float:
        """Jaccard similarity between two issue lists (keyword-level)."""
        if not a or not b:
            return 0.0
        # Tokenize issues into keyword sets
        tokens_a: set[str] = set()
        for issue in a:
            tokens_a.update(issue.lower().split())
        tokens_b: set[str] = set()
        for issue in b:
            tokens_b.update(issue.lower().split())

        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)
