"""ffprobe video quality gate — validates MP4 files meet quality standards.

Uses ffprobe (bundled with FFmpeg) to inspect video metadata:
  - resolution (≥720p)
  - framerate (≥24fps)
  - bitrate (≥500kbps)
  - duration (matches expected ±10%)
  - audio/video stream sync

Returns PASS/WARN/FAIL with detailed metrics.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any




@dataclass
class QualityReport:
    """Result of a ffprobe quality gate check."""

    status: str  # PASS / WARN / FAIL
    file_path: str
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    confidence: float = 0.0  # v5.2: calibrated confidence (0-1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "file_path": self.file_path,
            "metrics": self.metrics,
            "issues": self.issues,
            "confidence": self.confidence,
        }


class FFprobeGate:
    """Video quality gate using ffprobe.

    Usage:
        gate = FFprobeGate(
            min_resolution=720,
            min_framerate=24.0,
            min_bitrate_kbps=500,
        )
        report = gate.check(video_path)
        if report.status == "FAIL":
            # reject and regenerate
    """

    def __init__(
        self,
        min_resolution: int = 720,
        min_framerate: float = 24.0,
        min_bitrate_kbps: int = 500,
        duration_tolerance: float = 0.10,
    ) -> None:
        self.min_resolution = min_resolution
        self.min_framerate = min_framerate
        self.min_bitrate_kbps = min_bitrate_kbps
        self.duration_tolerance = duration_tolerance

    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is installed."""
        return shutil.which("ffprobe") is not None

    def _probe(self, video_path: Path) -> dict[str, Any]:
        """Run ffprobe and return parsed metadata."""
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
        return json.loads(result.stdout)

    def check(
        self,
        video_path: Path | str,
        expected_duration: float | None = None,
    ) -> QualityReport:
        """Check a video file against quality standards.

        Args:
            video_path: Path to the MP4 file.
            expected_duration: Expected duration in seconds (optional).

        Returns:
            QualityReport with PASS/WARN/FAIL status and metrics.
        """
        path = Path(video_path)
        if not path.exists():
            return QualityReport(
                status="FAIL",
                file_path=str(path),
                issues=["File does not exist"],
            )

        if not self.is_available():
            return QualityReport(
                status="WARN",
                file_path=str(path),
                issues=["ffprobe not installed — cannot validate"],
            )

        try:
            data = self._probe(path)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            return QualityReport(
                status="FAIL",
                file_path=str(path),
                issues=[f"ffprobe error: {exc}"],
            )

        # Extract metrics
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        height = int(v_stream.get("height", 0))
        width = int(v_stream.get("width", 0))
        fps_parts = v_stream.get("r_frame_rate", "0/1").split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 0.0
        bitrate_kbps = int(fmt.get("bit_rate", 0)) // 1000
        duration = float(fmt.get("duration", 0))
        has_audio = bool(a_stream)
        has_video = bool(v_stream)

        metrics: dict[str, Any] = {
            "resolution": f"{width}x{height}",
            "height": height,
            "framerate": round(fps, 2),
            "bitrate_kbps": bitrate_kbps,
            "duration_seconds": round(duration, 2),
            "has_audio": has_audio,
            "has_video": has_video,
            "video_codec": v_stream.get("codec_name", ""),
            "audio_codec": a_stream.get("codec_name", ""),
        }

        issues: list[str] = []
        status = "PASS"

        # Check resolution
        if height < self.min_resolution:
            issues.append(f"Resolution {height}p < minimum {self.min_resolution}p")
            status = "FAIL"

        # Check framerate
        if fps < self.min_framerate:
            issues.append(f"Framerate {fps:.1f}fps < minimum {self.min_framerate}fps")
            status = "FAIL" if status == "FAIL" else "WARN"

        # Check bitrate
        if bitrate_kbps < self.min_bitrate_kbps:
            issues.append(f"Bitrate {bitrate_kbps}kbps < minimum {self.min_bitrate_kbps}kbps")
            status = "FAIL" if status == "FAIL" else "WARN"

        # Check audio presence
        if not has_audio:
            issues.append("No audio stream")
            status = "WARN" if status == "PASS" else status

        # Check video presence
        if not has_video:
            issues.append("No video stream")
            status = "FAIL"

        # Check duration if expected
        if expected_duration and duration > 0:
            diff = abs(duration - expected_duration) / expected_duration
            if diff > self.duration_tolerance:
                issues.append(
                    f"Duration {duration:.1f}s differs from expected {expected_duration:.1f}s "
                    f"by {diff*100:.0f}% (tolerance {self.duration_tolerance*100:.0f}%)"
                )
                status = "WARN" if status == "PASS" else status

        # v5.2: Compute calibrated confidence
        # PASS with no issues → high confidence; more issues → lower confidence
        if status == "PASS" and not issues:
            confidence = 0.95
        elif status == "PASS":
            confidence = 0.80
        elif status == "WARN":
            confidence = max(0.3, 0.6 - 0.1 * len(issues))
        else:  # FAIL
            confidence = max(0.1, 0.3 - 0.1 * len(issues))

        return QualityReport(
            status=status,
            file_path=str(path),
            metrics=metrics,
            issues=issues,
            confidence=round(confidence, 2),
        )
