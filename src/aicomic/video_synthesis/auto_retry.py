"""Auto-retry loop — regenerate failed/low-quality video shots automatically.

Combines ffprobe quality gate + AI artifact detector into a retry pipeline:
  1. Generate video shot
  2. Run ffprobe quality gate
  3. Run artifact detector
  4. If FAIL → refine prompt, switch provider, regenerate (max 3 retries)
  5. Return final result with retry history

Usage:
    loop = AutoRetryLoop(max_retries=3)
    result = loop.run(
        generate_fn=my_generate_function,
        video_path=Path("shot.mp4"),
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aicomic.video_synthesis.quality_gate import FFprobeGate
from aicomic.video_synthesis.artifact_detector import ArtifactDetector, ArtifactReport
from aicomic.intelligence.loop_breaker import LoopBreaker, LoopSignal


@dataclass
class RetryAttempt:
    """Record of a single generation attempt."""

    attempt: int
    quality_status: str
    artifact_status: str
    combined_score: int
    issues: list[str] = field(default_factory=list)
    action_taken: str = ""


@dataclass
class RetryResult:
    """Final result of the auto-retry loop."""

    success: bool
    final_status: str  # PASS / WARN / FAIL
    attempts: list[RetryAttempt] = field(default_factory=list)
    final_video_path: str = ""
    total_retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "final_status": self.final_status,
            "attempts": [vars(a) for a in self.attempts],
            "final_video_path": self.final_video_path,
            "total_retries": self.total_retries,
        }


class AutoRetryLoop:
    """Auto-retry pipeline for video shot generation.

    Args:
        max_retries: Maximum regeneration attempts (default 3).
        ffprobe_gate: Optional custom ffprobe gate.
        artifact_detector: Optional custom artifact detector.
        prompt_refiner: Optional callable(prompt, issues) -> str to refine
            prompts based on detected issues.
        provider_fallback: Optional list of provider names to try in order
            when the primary provider fails.
    """

    def __init__(
        self,
        max_retries: int = 3,
        ffprobe_gate: FFprobeGate | None = None,
        artifact_detector: ArtifactDetector | None = None,
        prompt_refiner: Callable[[str, list[str]], str] | None = None,
        provider_fallback: list[str] | None = None,
        loop_breaker: LoopBreaker | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.gate = ffprobe_gate or FFprobeGate()
        self.detector = artifact_detector or ArtifactDetector()
        self.prompt_refiner = prompt_refiner
        self.provider_fallback = provider_fallback or []
        self.loop_breaker = loop_breaker or LoopBreaker()

    def run(
        self,
        generate_fn: Callable[..., dict[str, Any]],
        video_path: Path | str,
        prompt: str = "",
        expected_duration: float | None = None,
        frame_metadata: list[dict[str, Any]] | None = None,
        **generate_kwargs: Any,
    ) -> RetryResult:
        """Run the generate-check-retry loop.

        Args:
            generate_fn: Callable that generates video. Called as
                ``generate_fn(prompt=..., **generate_kwargs)``. Must return
                a dict with at least ``{"video_path": str, "status": str}``.
            video_path: Expected output path for the generated video.
            prompt: Generation prompt (may be refined on retry).
            expected_duration: Expected video duration in seconds.
            frame_metadata: Optional per-frame metadata for artifact detection.
            **generate_kwargs: Additional kwargs passed to generate_fn.

        Returns:
            RetryResult with full attempt history.
        """
        path = Path(video_path)
        current_prompt = prompt
        current_provider = generate_kwargs.get("provider", "")
        attempts: list[RetryAttempt] = []

        for attempt_num in range(self.max_retries + 1):
            # Step 1: Generate (skip on first attempt if file already exists from caller)
            if attempt_num > 0 or not path.exists():
                try:
                    gen_result = generate_fn(
                        prompt=current_prompt,
                        provider=current_provider,
                        **generate_kwargs,
                    )
                    if gen_result.get("status") == "error":
                        attempts.append(RetryAttempt(
                            attempt=attempt_num,
                            quality_status="SKIP",
                            artifact_status="SKIP",
                            combined_score=0,
                            issues=[gen_result.get("reason", "Generation error")],
                            action_taken="generation_failed",
                        ))
                        continue
                except Exception as exc:
                    attempts.append(RetryAttempt(
                        attempt=attempt_num,
                        quality_status="SKIP",
                        artifact_status="SKIP",
                        combined_score=0,
                        issues=[f"Exception: {exc}"],
                        action_taken="exception",
                    ))
                    continue

            # Step 2: Quality gate
            q_report = self.gate.check(path, expected_duration=expected_duration)

            # Step 3: Artifact detection
            if frame_metadata:
                a_report = self.detector.detect_from_metadata(frame_metadata)
            else:
                # No metadata — just use quality gate
                a_report = ArtifactReport(status="CLEAN", score=100, issues=[], checked_frames=0)

            # Step 4: Combine scores
            combined_score = (q_report.metrics.get("height", 0) + a_report.score) // 2 if q_report.metrics else a_report.score
            all_issues = q_report.issues + [i.description for i in a_report.issues]

            # Determine status
            if q_report.status == "FAIL" or a_report.status == "FAIL":
                status = "FAIL"
            elif q_report.status == "WARN" or a_report.status == "SUSPECT":
                status = "WARN"
            else:
                status = "PASS"

            attempts.append(RetryAttempt(
                attempt=attempt_num,
                quality_status=q_report.status,
                artifact_status=a_report.status,
                combined_score=combined_score,
                issues=all_issues,
                action_taken="checked",
            ))

            # Step 5: If PASS, we're done
            if status == "PASS":
                return RetryResult(
                    success=True,
                    final_status="PASS",
                    attempts=attempts,
                    final_video_path=str(path),
                    total_retries=attempt_num,
                )

            # Step 5b: Loop breaker — check if we're stuck repeating the same errors
            signal: LoopSignal = self.loop_breaker.observe(all_issues, float(combined_score))
            if signal.should_break and attempt_num < self.max_retries:
                attempts[-1].action_taken = f"loop_broken: {signal.reason}"
                return RetryResult(
                    success=status != "FAIL",
                    final_status=f"BROKEN_{status}",
                    attempts=attempts,
                    final_video_path=str(path) if path.exists() else "",
                    total_retries=attempt_num,
                )

            # Step 6: If WARN on last attempt, accept it
            if status == "WARN" and attempt_num == self.max_retries:
                return RetryResult(
                    success=True,
                    final_status="WARN",
                    attempts=attempts,
                    final_video_path=str(path),
                    total_retries=attempt_num,
                )

            # Step 7: Prepare retry — refine prompt and/or switch provider
            if attempt_num < self.max_retries:
                # Refine prompt if refiner available
                if self.prompt_refiner and all_issues:
                    try:
                        current_prompt = self.prompt_refiner(current_prompt, all_issues)
                    except Exception:
                        pass  # keep original prompt

                # Switch provider if fallback list available
                if self.provider_fallback and current_provider in self.provider_fallback:
                    idx = self.provider_fallback.index(current_provider)
                    if idx + 1 < len(self.provider_fallback):
                        current_provider = self.provider_fallback[idx + 1]

        # All retries exhausted
        return RetryResult(
            success=False,
            final_status="FAIL",
            attempts=attempts,
            final_video_path=str(path) if path.exists() else "",
            total_retries=self.max_retries,
        )
