"""FLF (First-Last-Frame) interpolator — generates video from keyframe pairs.

Inspired by Frameliq/OiiOii's 2026 script-to-screen pipelines:
  - Supply a first frame (start keyframe) and last frame (end keyframe)
  - The video model interpolates motion between them
  - This provides motion continuity across shots (character walks left in
    shot 3 → keeps walking left in shot 4)

Works with any video provider that supports image-to-video with a start
and end frame (Kling, Seedance, Wan, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FLFRequest:
    """A First-Last-Frame interpolation request."""
    first_frame: str        # path or URL to start keyframe image
    last_frame: str         # path or URL to end keyframe image
    duration: float = 5.0   # target video duration in seconds
    fps: int = 24
    motion_hint: str = ""   # optional text hint for motion direction
    seed: int = -1
    extra: dict[str, Any] = field(default_factory=dict)

    def to_provider_payload(self) -> dict[str, Any]:
        """Convert to a generic provider payload dict."""
        return {
            "mode": "flf",
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "duration": self.duration,
            "fps": self.fps,
            "motion_hint": self.motion_hint,
            "seed": self.seed if self.seed >= 0 else None,
            **self.extra,
        }


@dataclass
class FLFResult:
    """Result of an FLF interpolation."""
    success: bool
    video_path: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class FLFInterpolator:
    """First-Last-Frame interpolator.

    Usage:
        interp = FLFInterpolator(provider=seedance_provider)
        result = interp.interpolate(
            first_frame="shot1_end.png",
            last_frame="shot2_start.png",
            duration=3.0,
            motion_hint="character turns to face the door",
        )
    """

    def __init__(self, provider: Any = None) -> None:
        self.provider = provider

    def interpolate(
        self,
        first_frame: str,
        last_frame: str,
        duration: float = 5.0,
        motion_hint: str = "",
        seed: int = -1,
        **kwargs: Any,
    ) -> FLFResult:
        """Interpolate video between two keyframes.

        Args:
            first_frame: Path or URL to the first keyframe image.
            last_frame: Path or URL to the last keyframe image.
            duration: Target video duration in seconds.
            motion_hint: Optional text describing the intended motion.
            seed: Random seed for reproducibility (-1 = random).
            **kwargs: Extra provider-specific parameters.

        Returns:
            FLFResult with success status and video path or error.
        """
        # Validate inputs
        if not first_frame:
            return FLFResult(success=False, error="first_frame is required")
        if not last_frame:
            return FLFResult(success=False, error="last_frame is required")
        if duration <= 0:
            return FLFResult(success=False, error="duration must be positive")

        req = FLFRequest(
            first_frame=first_frame,
            last_frame=last_frame,
            duration=duration,
            motion_hint=motion_hint,
            seed=seed,
            extra=kwargs,
        )

        if self.provider is None:
            return FLFResult(
                success=False,
                error="No video provider configured",
                metadata={"request": req.to_provider_payload()},
            )

        try:
            payload = req.to_provider_payload()
            result = self.provider.execute_request(payload, config_path=None)
            if isinstance(result, dict) and result.get("output_path"):
                return FLFResult(
                    success=True,
                    video_path=result["output_path"],
                    metadata={"request": payload, "provider_result": result},
                )
            elif isinstance(result, dict) and result.get("error"):
                return FLFResult(
                    success=False,
                    error=result["error"],
                    metadata={"request": payload},
                )
            else:
                return FLFResult(
                    success=False,
                    error="Provider returned unexpected result",
                    metadata={"request": payload, "result": str(result)},
                )
        except Exception as e:
            return FLFResult(success=False, error=str(e))

    def interpolate_batch(
        self,
        keyframe_pairs: list[dict[str, Any]],
    ) -> list[FLFResult]:
        """Interpolate multiple keyframe pairs in sequence.

        Each dict in keyframe_pairs should have:
            first_frame, last_frame, duration (optional), motion_hint (optional)
        """
        results: list[FLFResult] = []
        for pair in keyframe_pairs:
            result = self.interpolate(
                first_frame=pair.get("first_frame", ""),
                last_frame=pair.get("last_frame", ""),
                duration=pair.get("duration", 5.0),
                motion_hint=pair.get("motion_hint", ""),
                seed=pair.get("seed", -1),
            )
            results.append(result)
        return results

    def build_motion_continuity_chain(
        self,
        keyframes: list[str],
        duration_per_shot: float = 3.0,
    ) -> list[FLFRequest]:
        """Build a chain of FLF requests for motion continuity.

        Given keyframes [K1, K2, K3, K4], produces:
            K1→K2, K2→K3, K3→K4

        This ensures a character walking left in shot N keeps walking
        left in shot N+1 — the key innovation from OiiOii/Frameliq.
        """
        if len(keyframes) < 2:
            return []
        requests: list[FLFRequest] = []
        for i in range(len(keyframes) - 1):
            requests.append(FLFRequest(
                first_frame=keyframes[i],
                last_frame=keyframes[i + 1],
                duration=duration_per_shot,
                motion_hint=f"continuous motion from keyframe {i} to {i+1}",
            ))
        return requests
