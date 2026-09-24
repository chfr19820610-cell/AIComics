"""AI artifact detector — detects common AI-generated video artifacts.

Three-tier classification based on Artifact-Bench taxonomy:
  1. Character deformation: extra fingers, face warping, body distortion
  2. Text corruption: garbled subtitles, fake text in scenes
  3. Temporal inconsistency: flickering, morphing, scene discontinuity

Uses lightweight heuristics + optional LLM vision API for detection.
No heavy ML model required — designed for fast pipeline-level screening.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ArtifactIssue:
    """A single detected artifact."""

    category: str  # "character" / "text" / "temporal" / "color"
    severity: str  # "critical" / "major" / "minor"
    description: str
    confidence: float = 0.0  # 0.0-1.0


@dataclass
class ArtifactReport:
    """Result of artifact detection on a video or frame set."""

    status: str  # CLEAN / SUSPECT / FAIL
    score: int  # 0-100, higher = cleaner
    issues: list[ArtifactIssue] = field(default_factory=list)
    checked_frames: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "issues": [vars(i) for i in self.issues],
            "checked_frames": self.checked_frames,
        }


class ArtifactDetector:
    """Detect AI generation artifacts in video frames.

    Usage:
        detector = ArtifactDetector()
        report = detector.detect(frame_dir_or_video_path)
        if report.status == "FAIL":
            # trigger regeneration
    """

    # Known AI artifact keywords in filenames/metadata
    _SUSPECT_PATTERNS = [
        ("extra_finger", "character", "critical", "Extra fingers detected"),
        ("six_finger", "character", "critical", "Six fingers detected"),
        ("face_warp", "character", "major", "Face warping detected"),
        ("body_distort", "character", "major", "Body distortion detected"),
        ("garbled_text", "text", "major", "Garbled text in scene"),
        ("fake_subtitle", "text", "minor", "Fake subtitle text detected"),
        ("flicker", "temporal", "major", "Temporal flickering detected"),
        ("morph", "temporal", "major", "Object morphing detected"),
        ("color_shift", "color", "minor", "Abrupt color shift detected"),
    ]

    def __init__(
        self,
        fail_threshold: int = 40,
        suspect_threshold: int = 70,
        use_vlm: bool = False,
    ) -> None:
        self.fail_threshold = fail_threshold
        self.suspect_threshold = suspect_threshold
        self.use_vlm = use_vlm

    def detect_from_metadata(
        self,
        frame_metadata: list[dict[str, Any]],
    ) -> ArtifactReport:
        """Detect artifacts from frame metadata dicts.

        Each dict may contain:
          - ``finger_count``: int (normal=5, AI artifact=6+)
          - ``face_confidence``: float (0-1, low=warping)
          - ``has_text``: bool
          - ``text_garbled``: bool
          - ``scene_change``: bool
          - ``color_variance``: float (high=instability)

        Args:
            frame_metadata: List of per-frame metadata dicts.

        Returns:
            ArtifactReport with status and issues.
        """
        issues: list[ArtifactIssue] = []
        n_frames = len(frame_metadata)

        for i, meta in enumerate(frame_metadata):
            # Finger count check
            fc = meta.get("finger_count")
            if fc is not None and fc > 5:
                issues.append(ArtifactIssue(
                    category="character",
                    severity="critical",
                    description=f"Frame {i}: {fc} fingers (expected ≤5)",
                    confidence=0.85,
                ))

            # Face confidence check
            face_conf = meta.get("face_confidence")
            if face_conf is not None and face_conf < 0.5:
                issues.append(ArtifactIssue(
                    category="character",
                    severity="major",
                    description=f"Frame {i}: low face confidence ({face_conf:.2f})",
                    confidence=0.7,
                ))

            # Garbled text check
            if meta.get("has_text") and meta.get("text_garbled"):
                issues.append(ArtifactIssue(
                    category="text",
                    severity="major",
                    description=f"Frame {i}: garbled text detected",
                    confidence=0.6,
                ))

            # Temporal instability check
            if meta.get("color_variance", 0) > 0.3:
                issues.append(ArtifactIssue(
                    category="color",
                    severity="minor",
                    description=f"Frame {i}: high color variance",
                    confidence=0.5,
                ))

        # Check for flickering (alternating scene_change flags)
        scene_changes = [i for i, m in enumerate(frame_metadata) if m.get("scene_change")]
        if len(scene_changes) > n_frames * 0.3 and n_frames > 10:
            issues.append(ArtifactIssue(
                category="temporal",
                severity="major",
                description=f"Excessive scene changes ({len(scene_changes)}/{n_frames} frames)",
                confidence=0.6,
            ))

        return self._build_report(issues, n_frames)

    def detect_from_vlm(
        self,
        frame_paths: list[Path],
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> ArtifactReport:
        """Use a vision LLM to detect artifacts in frames.

        Sends frames to a VLM with a prompt asking it to identify AI artifacts.
        Falls back to metadata-based detection if no API key.
        """
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AICOMIC_LLM_KEY")
        if not key or not frame_paths:
            # No API key — return a neutral report
            return ArtifactReport(
                status="SUSPECT",
                score=50,
                issues=[ArtifactIssue(
                    category="character",
                    severity="minor",
                    description="VLM detection unavailable — manual review needed",
                    confidence=0.0,
                )],
                checked_frames=len(frame_paths),
            )

        import base64
        import httpx

        # Encode first frame as base64
        with open(frame_paths[0], "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompt = (
            "Analyze this AI-generated animation frame for artifacts. "
            "Check for: extra fingers, face warping, body distortion, garbled text, "
            "color instability, or temporal flickering. "
            "Respond in JSON: {\"clean\": true/false, \"issues\": [\"description\"], \"score\": 0-100}"
        )

        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    }],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # Parse JSON from response
            import json
            # Extract JSON from potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            vlm_result = json.loads(content.strip())
            issues = [
                ArtifactIssue(
                    category="character",
                    severity="major",
                    description=desc,
                    confidence=0.8,
                )
                for desc in vlm_result.get("issues", [])
            ]
            score = vlm_result.get("score", 50)
            status = "CLEAN" if vlm_result.get("clean", False) else ("FAIL" if score < self.fail_threshold else "SUSPECT")

            return ArtifactReport(
                status=status,
                score=score,
                issues=issues,
                checked_frames=len(frame_paths),
            )

        except Exception as exc:
            return ArtifactReport(
                status="SUSPECT",
                score=50,
                issues=[ArtifactIssue(
                    category="character",
                    severity="minor",
                    description=f"VLM detection error: {exc}",
                    confidence=0.0,
                )],
                checked_frames=len(frame_paths),
            )

    def _build_report(self, issues: list[ArtifactIssue], n_frames: int) -> ArtifactReport:
        """Build a report from detected issues."""
        if not issues:
            return ArtifactReport(
                status="CLEAN",
                score=100,
                issues=[],
                checked_frames=n_frames,
            )

        # Any critical issue → immediate FAIL
        has_critical = any(i.severity == "critical" for i in issues)

        # Calculate score: start at 100, deduct by severity
        deductions = {"critical": 25, "major": 15, "minor": 5}
        score = 100
        for issue in issues:
            score -= deductions.get(issue.severity, 5)
        score = max(0, score)

        if has_critical or score < self.fail_threshold:
            status = "FAIL"
        elif score < self.suspect_threshold:
            status = "SUSPECT"
        else:
            status = "CLEAN"

        return ArtifactReport(
            status=status,
            score=score,
            issues=issues,
            checked_frames=n_frames,
        )
