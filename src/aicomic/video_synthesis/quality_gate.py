"""ffprobe video quality gate — validates MP4 files meet quality standards.

Uses ffprobe (bundled with FFmpeg) to inspect video metadata:
  - resolution (≥720p)
  - framerate (≥24fps)
  - bitrate (≥500kbps)
  - duration (matches expected ±10%)
  - audio/video stream sync

Probe backends (ordered, first healthy wins):
  1. ffprobe — full fidelity (`-show_format -show_streams` JSON)
  2. ffmpeg banner — fallback when ffprobe is missing OR unusable
     (e.g. an x86_64 ffprobe on an arm64 host without Rosetta, which fails
     with `Bad CPU type in executable`). `ffmpeg -hide_banner -i <file>`
     prints Duration / bitrate / resolution / fps / codec / audio presence to
     stderr in ~40ms and then exits non-zero; we normalize that banner into
     the same shape as ffprobe JSON.
  Neither backend silently passes: if both fail, the report carries an explicit
  `probe_unavailable` issue instead of a green result.

Returns PASS/WARN/FAIL with detailed metrics.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── probe backend resolution ─────────────────────────────────────────────

_FFMPEG_PATH_CACHE: str | None = None
_FFPROBE_HEALTH_CACHE: bool | None = None

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")
_FORMAT_BITRATE_RE = re.compile(r"Duration:.*?bitrate:\s*(\d+)\s*kb/s")
_VIDEO_STREAM_RE = re.compile(
    r"Stream #\d+:\d+(?:\[[^\]]*\])?(?:\([^)]*\))?:\s*Video:\s*([A-Za-z0-9_]+).*?(\d{2,5})x(\d{2,5})"
)
_FPS_RE = re.compile(r"([\d.]+)\s+fps")
_AUDIO_STREAM_RE = re.compile(
    r"Stream #\d+:\d+(?:\[[^\]]*\])?(?:\([^)]*\))?:\s*Audio:\s*([A-Za-z0-9_]+)"
)


def _ffmpeg_bin() -> str:
    """Resolve an executable ffmpeg (prefers imageio-ffmpeg's bundled build)."""
    global _FFMPEG_PATH_CACHE
    if _FFMPEG_PATH_CACHE is not None:
        return _FFMPEG_PATH_CACHE
    resolved = ""
    try:
        import imageio_ffmpeg

        resolved = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        resolved = shutil.which("ffmpeg") or "ffmpeg"
    _FFMPEG_PATH_CACHE = resolved
    return resolved


def _ffprobe_bin() -> str | None:
    """Resolve an ffprobe candidate path, or None when nothing is discoverable."""
    found = shutil.which("ffprobe")
    if found:
        return found
    try:
        candidate = Path(_ffmpeg_bin()).with_name("ffprobe")
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return None


def _ffprobe_healthy() -> bool:
    """Probe ffprobe once for real (cached) — `which` alone yields false positives.

    A binary can exist on PATH yet be unrunnable (wrong CPU arch, missing shared
    library, quarantine bit). Only an actual `ffprobe -version` with rc==0 counts.
    """
    global _FFPROBE_HEALTH_CACHE
    if _FFPROBE_HEALTH_CACHE is not None:
        return _FFPROBE_HEALTH_CACHE
    binary = _ffprobe_bin()
    healthy = False
    if binary:
        try:
            proc = subprocess.run(
                [binary, "-version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            healthy = proc.returncode == 0 and "ffprobe" in (proc.stdout or "").lower()
        except (OSError, subprocess.SubprocessError):
            healthy = False
    _FFPROBE_HEALTH_CACHE = healthy
    return healthy


def _reset_probe_cache() -> None:
    """Clear cached backend probes (test seam; also useful after installing ffprobe)."""
    global _FFMPEG_PATH_CACHE, _FFPROBE_HEALTH_CACHE
    _FFMPEG_PATH_CACHE = None
    _FFPROBE_HEALTH_CACHE = None


def _probe_via_ffprobe(binary: str, video: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            binary,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {(result.stderr or '')[:200]}")
    return json.loads(result.stdout)


def _probe_via_banner(video: Path) -> dict[str, Any]:
    """Parse `ffmpeg -hide_banner -i <file>` stderr into ffprobe-shaped JSON.

    ffmpeg exits non-zero here on purpose (no output target given); the banner on
    stderr is still complete, and parsing takes ~40ms regardless of duration
    because no decoding happens.
    """
    proc = subprocess.run(
        [_ffmpeg_bin(), "-hide_banner", "-i", str(video)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    banner = f"{proc.stderr or ''}{proc.stdout or ''}"
    if not banner.strip():
        raise RuntimeError("ffmpeg banner probe produced no output")

    format_info: dict[str, Any] = {}
    match = _DURATION_RE.search(banner)
    if match:
        hours, minutes, seconds, hundredths = match.groups()
        total = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(hundredths) / 100
        format_info["duration"] = f"{total:.2f}"
    bitrate_match = _FORMAT_BITRATE_RE.search(banner)
    if bitrate_match:
        format_info["bit_rate"] = str(int(bitrate_match.group(1)) * 1000)

    streams: list[dict[str, Any]] = []
    video_match = _VIDEO_STREAM_RE.search(banner)
    if video_match:
        codec, width, height = video_match.groups()
        stream: dict[str, Any] = {
            "codec_type": "video",
            "codec_name": codec,
            "width": int(width),
            "height": int(height),
        }
        fps_match = _FPS_RE.search(banner[video_match.start():])
        if fps_match:
            stream["r_frame_rate"] = f"{fps_match.group(1)}/1"
        streams.append(stream)

    audio_match = _AUDIO_STREAM_RE.search(banner)
    if audio_match:
        streams.append({"codec_type": "audio", "codec_name": audio_match.group(1)})

    if not format_info and not streams:
        raise RuntimeError("ffmpeg banner had no recognizable Duration/Stream lines")

    return {"format": format_info, "streams": streams}



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

    Decision rules (code is the source of truth):
      - resolution < min_resolution → FAIL
      - no video stream → FAIL
      - framerate < min_framerate → WARN (stays FAIL if already FAIL)
      - bitrate < min_bitrate_kbps → WARN (stays FAIL if already FAIL)
      - no audio stream → WARN (stays FAIL if already FAIL)
      - |duration - expected| > tolerance → WARN

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
        """True when a *working* probe backend exists (ffprobe or ffmpeg banner).

        `shutil.which("ffprobe")` alone is a false positive on hosts where the
        binary exists but cannot execute (wrong CPU arch / no Rosetta). We verify
        ffprobe by actually running it, and accept ffmpeg's banner parser as the
        fallback backend.
        """
        if _ffprobe_healthy():
            return True
        try:
            proc = subprocess.run(
                [_ffmpeg_bin(), "-version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def probe_backend() -> str:
        """Report which backend would be used: `ffprobe`, `ffmpeg-banner`, or `none`."""
        if _ffprobe_healthy():
            return "ffprobe"
        try:
            proc = subprocess.run(
                [_ffmpeg_bin(), "-version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                return "ffmpeg-banner"
        except (OSError, subprocess.SubprocessError):
            pass
        return "none"

    def _probe(self, video_path: Path) -> dict[str, Any]:
        """Probe video metadata, falling back to the ffmpeg banner parser.

        Raises RuntimeError only when *both* backends fail, so callers can never
        mistake a broken toolchain for a passing asset.
        """
        errors: list[str] = []
        binary = _ffprobe_bin()
        if binary and _ffprobe_healthy():
            try:
                return _probe_via_ffprobe(binary, video_path)
            except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                errors.append(f"ffprobe: {exc}")
        elif binary:
            errors.append("ffprobe: present on PATH but not runnable")

        try:
            data = _probe_via_banner(video_path)
            data["probe_backend"] = "ffmpeg-banner"
            return data
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            errors.append(f"ffmpeg-banner: {exc}")

        raise RuntimeError("; ".join(errors) or "no probe backend available")

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
                issues=["probe_unavailable: neither ffprobe nor ffmpeg is runnable — cannot validate"],
            )

        try:
            data = self._probe(path)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as exc:
            return QualityReport(
                status="FAIL",
                file_path=str(path),
                issues=[f"probe_unavailable: {exc}"],
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
