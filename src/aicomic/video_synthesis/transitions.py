"""Video transitions — 7 transition effects via FFmpeg xfade filter.

Distilled from MoneyPrinterTurbo schemas.py VideoTransitionMode.
Supports: FadeIn, FadeOut, SlideIn, SlideOut, ZoomIn, ZoomOut, Shuffle.
"""
from __future__ import annotations

import random
import subprocess
import re
from enum import Enum
from pathlib import Path
from typing import Optional

from aicomic.video_synthesis.config import FFMPEG


class TransitionMode(str, Enum):
    none = "none"
    fade = "fade"
    slide = "slideleft"
    slide_right = "slideright"
    zoom_in = "zoomin"
    zoom_out = "zoomout"
    shuffle = "shuffle"


# FFmpeg xfade preset mapping
_XFADE_MAP = {
    TransitionMode.fade: "fade",
    TransitionMode.slide: "slideleft",
    TransitionMode.slide_right: "slideright",
    TransitionMode.zoom_in: "zoomin",
    TransitionMode.zoom_out: "zoomout",
}


def apply_transitions(
    clip_paths: list[Path],
    output_path: Path,
    transition: TransitionMode = TransitionMode.fade,
    duration: float = 0.5,
) -> bool:
    """Concatenate clips with transition effects between them.

    Args:
        clip_paths: List of video clip paths in order.
        output_path: Output video path.
        transition: Transition type (fade/slide/zoom/shuffle).
        duration: Transition duration in seconds.

    Returns True if synthesis succeeded.
    """
    if len(clip_paths) == 0:
        return False
    if len(clip_paths) == 1:
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return output_path.exists()

    # For shuffle mode, randomize transition per cut
    if transition == TransitionMode.shuffle:
        return _concat_with_random_transitions(clip_paths, output_path, duration)

    xfade_type = _XFADE_MAP.get(transition, "fade")
    return _concat_with_xfade(clip_paths, output_path, xfade_type, duration)


def _concat_with_xfade(
    clips: list[Path], output: Path, xfade_type: str, duration: float
) -> bool:
    """Concatenate using FFmpeg xfade filter chain."""
    if len(clips) < 2:
        return False

    # Build xfade chain: [0][1]xfade → [tmp0]; [tmp0][2]xfade → [tmp1]; ...
    inputs = []
    for clip in clips:
        inputs.extend(["-i", str(clip)])

    # Get clip durations for offset calculation
    durations = [_get_video_duration(c) for c in clips]

    filter_parts = []
    prev_label = "0:v"
    offset = 0.0
    for i in range(1, len(clips)):
        offset += durations[i - 1] - duration
        out_label = f"x{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition={xfade_type}:duration={duration}:offset={offset}[{out_label}]"
        )
        prev_label = out_label

    # Audio: concat all audio streams
    audio_parts = []
    for i in range(len(clips)):
        audio_parts.append(f"{i}:a")
    audio_filter = "".join(f"[{a}]" for a in audio_parts) + f"concat=n={len(clips)}:v=0:a=1[aout]"

    full_filter = ";".join(filter_parts) + ";" + audio_filter

    cmd = [
        FFMPEG, "-y", *inputs,
        "-filter_complex", full_filter,
        "-map", f"[{prev_label}]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    result = _run_ffmpeg(cmd)
    return result


def _concat_with_random_transitions(
    clips: list[Path], output: Path, duration: float
) -> bool:
    """Shuffle mode: random transition type per cut."""
    transitions = ["fade", "slideleft", "slideright", "zoomin", "zoomout"]
    if len(clips) < 2:
        return False

    inputs = []
    for clip in clips:
        inputs.extend(["-i", str(clip)])

    durations = [_get_video_duration(c) for c in clips]
    filter_parts = []
    prev_label = "0:v"
    offset = 0.0
    for i in range(1, len(clips)):
        offset += durations[i - 1] - duration
        xfade_type = random.choice(transitions)
        out_label = f"x{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition={xfade_type}:duration={duration}:offset={offset}[{out_label}]"
        )
        prev_label = out_label

    audio_parts = [f"{i}:a" for i in range(len(clips))]
    audio_filter = "".join(f"[{a}]" for a in audio_parts) + f"concat=n={len(clips)}:v=0:a=1[aout]"
    full_filter = ";".join(filter_parts) + ";" + audio_filter

    cmd = [
        FFMPEG, "-y", *inputs,
        "-filter_complex", full_filter,
        "-map", f"[{prev_label}]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    return _run_ffmpeg(cmd)


def _get_video_duration(path: Path) -> float:
    """Get video duration in seconds."""
    import subprocess, re
    try:
        result = subprocess.run(
            [FFMPEG, "-i", str(path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=10,
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 5.0


def _run_ffmpeg(cmd: list) -> bool:
    """Run FFmpeg command, return success."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except Exception:
        return False
