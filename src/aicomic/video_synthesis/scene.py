"""
Single scene rendering for the video synthesis pipeline.

Each scene is a combination of:
- A key image (PNG)
- Ken Burns zoom effect (100% → 105%)
- Audio track (44100 Hz re-encoded)
"""

import subprocess
from pathlib import Path

from aicomic.video_synthesis.config import (
    AUDIO_BITRATE,
    AUDIO_SAMPLE_RATE,
    CRF,
    FFMPEG,
    FPS,
    VIDEO_BITRATE,
    VIDEO_SIZE,
    VIDEO_SIZE_X,
)


def reencode_audio(wav_path: Path, aac_path: Path) -> bool:
    """
    Re-encode WAV audio to AAC at 44100 Hz.
    Ensures consistent audio format for concatenation.
    """
    cmd = [
        str(FFMPEG), "-y",
        "-i", str(wav_path),
        "-c:a", "aac",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-b:a", AUDIO_BITRATE,
        "-ac", "1",
        str(aac_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [audio] reencode failed: {result.stderr[-500:]}")
        return False
    return True


def get_audio_duration(wav_path: Path) -> float:
    """Get duration of a WAV file in seconds using ffprobe."""
    result = subprocess.run(
        [str(FFMPEG), "-i", str(wav_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            parts = line.strip().split(",")[0]
            dur_str = parts.split("Duration:")[-1].strip()
            h, m, s = dur_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 5.0


def build_scene_video(
    clip_path: Path,
    img_path: Path,
    audio_path: Path,
    duration: float,
    scene_label: str = "",
) -> bool:
    """
    Build a single scene video clip.

    Applies:
    - Ken Burns zoom (100% → 105%) via zoompan filter
    - Centered crop to maintain 1280:720 aspect ratio
    - Audio at 44100 Hz AAC

    Args:
        clip_path: Output MP4 path for this scene.
        img_path: Input key image PNG path.
        audio_path: Input WAV audio path.
        duration: Clip duration in seconds.
        scene_label: Label for logging (e.g. "S01").

    Returns:
        True on success, False on failure.
    """
    frames = int(duration * FPS)
    zoom_expr = f"1+0.05*on/{frames}"  # 100% → 105% over scene duration

    # First re-encode audio to consistent format
    aac_temp = clip_path.with_suffix(".aac")
    if not reencode_audio(audio_path, aac_temp):
        return False

    cmd = [
        str(FFMPEG), "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-i", str(aac_temp),
        "-vf",
        f"scale={VIDEO_SIZE}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_SIZE},"
        f"zoompan=z='{zoom_expr}':d={frames}:s={VIDEO_SIZE_X}:fps={FPS}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-maxrate", VIDEO_BITRATE,
        "-bufsize", "3000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",              # AAC already re-encoded
        "-shortest",
        "-t", str(duration),
        str(clip_path),
    ]

    label = scene_label or clip_path.stem
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [{label}] FAILED: {result.stderr[-800:]}")
        return False

    # Clean up temp AAC
    try:
        aac_temp.unlink()
    except OSError:
        pass

    return True
