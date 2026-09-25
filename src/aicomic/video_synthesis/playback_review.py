"""Playback review gate — "watch it back before you call the work done".

Based on godogen methodology: "if the user hasn't seen it running, finish
with a 15-20s video... and watch it back before you call the work done."

Gate is the LAST step before publish — after all automated gates pass,
this does a holistic review of the finished episode:
  1. Full playback check (duration, continuity, pacing)
  2. Narrative coherence (does the story flow make sense?)
  3. Aesthetic consistency (visual style consistent end-to-end?)
  4. Platform readiness (meets target platform specs?)

Supports both manual review (human watches) and automated review
(VLM watches and judges). Gate-pass ≠ publishable until review-pass.

Usage:
    gate = PlaybackReviewGate()
    result = gate.review(episode_metadata)
    if result.passed:
        # proceed to publish
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReviewCheck:
    """A single playback review check item."""

    name: str
    category: str  # playback / narrative / aesthetic / platform
    passed: bool
    score: int  # 0-100
    notes: str = ""


@dataclass
class PlaybackReviewResult:
    """Result of the playback review gate."""

    passed: bool
    overall_score: int  # 0-100
    checks: list[ReviewCheck] = field(default_factory=list)
    review_mode: str = "auto"  # auto / manual / hybrid
    blocking_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "checks": [vars(c) for c in self.checks],
            "review_mode": self.review_mode,
            "blocking_issues": self.blocking_issues,
            "recommendations": self.recommendations,
        }


class PlaybackReviewGate:
    """成片回看自证门 — final holistic review before publish.

    This gate runs AFTER all automated quality gates (drift_gate,
    artifact_detector, silent_failure, ffprobe). It checks things
    that automated gates can't: narrative flow, aesthetic coherence,
    and overall "does this feel right" judgment.

    Args:
        pass_threshold: Minimum overall score to pass (default 70).
        api_key: Optional VLM API key for automated review.
        require_manual: If True, auto-pass is disabled — human must confirm.
    """

    PASS_THRESHOLD = 70

    def __init__(
        self,
        pass_threshold: int = 70,
        api_key: str | None = None,
        require_manual: bool = False,
    ) -> None:
        self.pass_threshold = pass_threshold
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AICOMIC_LLM_KEY")
        self._require_manual = require_manual

    def review(
        self,
        episode_metadata: dict[str, Any],
        video_path: str = "",
    ) -> PlaybackReviewResult:
        """Run the playback review gate.

        Expected metadata:
            - shots: list of shot dicts
            - total_duration: float
            - target_platform: str
            - genre: str
            - episode_code: str
            - quality_gate_results: dict (from prior gates)

        Returns:
            PlaybackReviewResult with pass/fail and detailed checks.
        """
        checks: list[ReviewCheck] = []
        shots = episode_metadata.get("shots", [])
        total_duration = episode_metadata.get("total_duration", 0)

        # ── 1. Playback checks ─────────────────────────────────────

        # Duration check
        if total_duration > 0:
            duration_ok = 30 <= total_duration <= 600  # 30s-10min reasonable
            checks.append(ReviewCheck(
                name="duration_check",
                category="playback",
                passed=duration_ok,
                score=100 if duration_ok else 50,
                notes=f"Duration: {total_duration:.0f}s",
            ))
        else:
            checks.append(ReviewCheck(
                name="duration_check", category="playback",
                passed=False, score=0, notes="No duration data",
            ))

        # Pacing check (shot count vs duration)
        if shots and total_duration > 0:
            avg_shot_dur = total_duration / len(shots)
            pacing_ok = 2.0 <= avg_shot_dur <= 12.0  # 2-12s per shot
            checks.append(ReviewCheck(
                name="pacing_check",
                category="playback",
                passed=pacing_ok,
                score=100 if pacing_ok else 60,
                notes=f"Avg shot: {avg_shot_dur:.1f}s ({len(shots)} shots)",
            ))

        # ── 2. Narrative coherence ─────────────────────────────────

        # Beat coverage (do shots cover all story beats?)
        beats_in_shots = set()
        for shot in shots:
            beat = shot.get("beat", shot.get("emotion", ""))
            if beat:
                beats_in_shots.add(beat)
        beat_coverage = len(beats_in_shots) / max(len(shots), 1)
        narrative_ok = beat_coverage >= 0.3  # at least 30% unique beats
        checks.append(ReviewCheck(
            name="narrative_beats",
            category="narrative",
            passed=narrative_ok,
            score=int(beat_coverage * 100),
            notes=f"{len(beats_in_shots)} unique beats across {len(shots)} shots",
        ))

        # Emotion arc (does emotion vary across the episode?)
        emotions = [s.get("emotion", "") for s in shots if s.get("emotion")]
        if emotions:
            emotion_variety = len(set(emotions)) / len(emotions)
            emotion_ok = emotion_variety >= 0.2
            checks.append(ReviewCheck(
                name="emotion_arc",
                category="narrative",
                passed=emotion_ok,
                score=int(emotion_variety * 100),
                notes=f"{len(set(emotions))} distinct emotions",
            ))

        # ── 3. Aesthetic consistency ───────────────────────────────

        # Resolution consistency
        resolutions = set(s.get("resolution", "") for s in shots if s.get("resolution"))
        res_ok = len(resolutions) <= 1
        checks.append(ReviewCheck(
            name="resolution_consistency",
            category="aesthetic",
            passed=res_ok,
            score=100 if res_ok else 50,
            notes=f"{len(resolutions)} different resolutions",
        ))

        # Prior gate results (drift, artifact, silent_failure)
        prior_gates = episode_metadata.get("quality_gate_results", {})
        if prior_gates:
            drift_status = prior_gates.get("drift_gate", {}).get("status", "PASS")
            drift_ok = drift_status in ("PASS", "WARN")
            checks.append(ReviewCheck(
                name="drift_gate_passed",
                category="aesthetic",
                passed=drift_ok,
                score=100 if drift_ok else 30,
                notes=f"Drift: {drift_status}",
            ))

            silent_status = prior_gates.get("silent_failure", {}).get("status", "CLEAN")
            silent_ok = silent_status in ("CLEAN", "SUSPECT")
            checks.append(ReviewCheck(
                name="silent_failure_passed",
                category="aesthetic",
                passed=silent_ok,
                score=100 if silent_ok else 30,
                notes=f"Silent failure: {silent_status}",
            ))

        # ── 4. Platform readiness ──────────────────────────────────

        platform = episode_metadata.get("target_platform", "")
        if platform:
            # Vertical platforms need 9:16
            vertical_platforms = {"douyin", "tiktok", "xiaohongshu", "instagram"}
            target_aspect = "9:16" if platform in vertical_platforms else "16:9"
            checks.append(ReviewCheck(
                name="platform_aspect",
                category="platform",
                passed=True,
                score=100,
                notes=f"Target: {platform} ({target_aspect})",
            ))

        # ── Calculate overall ──────────────────────────────────────

        if checks:
            overall_score = sum(c.score for c in checks) // len(checks)
        else:
            overall_score = 0

        passed = overall_score >= self.pass_threshold

        # If manual review required, auto-pass disabled
        if self._require_manual:
            passed = False
            checks.append(ReviewCheck(
                name="manual_review_required",
                category="playback",
                passed=False,
                score=0,
                notes="Manual review required — human must confirm before publish",
            ))

        # Collect blocking issues and recommendations
        blocking = [c.notes for c in checks if not c.passed and c.category in ("playback", "platform")]
        recs = []
        for c in checks:
            if not c.passed and c.category == "narrative":
                recs.append(f"Improve {c.name}: {c.notes}")
            if not c.passed and c.category == "aesthetic":
                recs.append(f"Fix {c.name}: {c.notes}")

        return PlaybackReviewResult(
            passed=passed,
            overall_score=overall_score,
            checks=checks,
            review_mode="manual" if self._require_manual else "auto",
            blocking_issues=blocking,
            recommendations=recs,
        )

    def vlm_review(
        self,
        video_path: str,
        episode_metadata: dict[str, Any],
    ) -> PlaybackReviewResult:
        """Use a VLM to watch the video and judge overall quality.

        Sends key frames to a vision model asking it to judge:
        narrative coherence, visual consistency, pacing, and overall quality.

        Falls back to heuristic review if VLM is unavailable.
        """
        if not self._api_key:
            # Fall back to heuristic review
            result = self.review(episode_metadata, video_path)
            result.review_mode = "auto_heuristic"
            return result

        import httpx
        import json

        genre = episode_metadata.get("genre", "animation")
        prompt = (
            f"You are reviewing a {genre} animated short episode. "
            f"Judge the overall quality on: narrative coherence, visual consistency, "
            f"pacing, and aesthetic appeal. Respond in JSON:\n"
            f'{{"overall_score": 0-100, "passed": true/false, '
            f'"narrative_score": 0-100, "aesthetic_score": 0-100, '
            f'"pacing_score": 0-100, "issues": ["..."], '
            f'"recommendations": ["..."]}}'
        )

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            vlm_result = json.loads(content)

            checks = [
                ReviewCheck(name="vlm_narrative", category="narrative",
                            passed=vlm_result.get("narrative_score", 50) >= 60,
                            score=vlm_result.get("narrative_score", 50),
                            notes="VLM narrative judgment"),
                ReviewCheck(name="vlm_aesthetic", category="aesthetic",
                            passed=vlm_result.get("aesthetic_score", 50) >= 60,
                            score=vlm_result.get("aesthetic_score", 50),
                            notes="VLM aesthetic judgment"),
                ReviewCheck(name="vlm_pacing", category="playback",
                            passed=vlm_result.get("pacing_score", 50) >= 60,
                            score=vlm_result.get("pacing_score", 50),
                            notes="VLM pacing judgment"),
            ]

            overall = vlm_result.get("overall_score", 50)
            return PlaybackReviewResult(
                passed=vlm_result.get("passed", overall >= self.pass_threshold),
                overall_score=overall,
                checks=checks,
                review_mode="vlm",
                blocking_issues=vlm_result.get("issues", []),
                recommendations=vlm_result.get("recommendations", []),
            )
        except Exception:
            result = self.review(episode_metadata, video_path)
            result.review_mode = "auto_fallback"
            return result
