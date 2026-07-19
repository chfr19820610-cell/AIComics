"""
Single scene rendering for the video synthesis pipeline.

Each scene is a combination of:
- A key image (PNG)
- Ken Burns zoom effect (100% → 105%)
- Audio track (44100 Hz re-encoded, with optional voice enhancement)
"""

import subprocess
from pathlib import Path

from aicomic.video_synthesis.config import (
    AUDIO_BITRATE,
    AUDIO_SAMPLE_RATE,
    AUDIO_ENHANCE_ENABLED,
    AUDIO_ENHANCE_DEBUG_DIR,
    CRF,
    FFMPEG,
    FPS,
    LUT_PATH,
    VIDEO_BITRATE,
    VIDEO_SIZE,
    VIDEO_SIZE_X,
)


def reencode_audio(wav_path: Path, aac_path: Path, voice_enhance: bool = False) -> bool:
    """
    Re-encode WAV audio to AAC at 44100 Hz, optionally with voice enhancement.

    When voice_enhance is True, applies:
    - High-pass filter (remove rumble below 80 Hz)
    - Low-pass filter (remove noise above 8 kHz)
    - Compression (even out dynamics)
    - EQ boost at 3 kHz (vocal presence)
    - Loudness normalization

    Args:
        wav_path: Input WAV file
        aac_path: Output AAC file
        voice_enhance: Apply voice enhancement filters if True

    Returns:
        True on success
    """
    cmd = [
        str(FFMPEG), "-y",
        "-i", str(wav_path),
    ]

    if voice_enhance:
        # FFmpeg audio filter chain for voice enhancement
        af_chain = (
            "highpass=f=80,"
            "lowpass=f=8000,"
            "compand=attacks=0.3:decays=0.5:"
            "points=-80/-105|-62/-62|-40/-30|-20/-12|0/-3:gain=3:volume=0.8,"
            "equalizer=f=3000:t=q:w=1:g=3,"
            "equalizer=f=200:t=q:w=1:g=-2,"
            "loudnorm=I=-16:LRA=11:TP=-1.5"
        )
        cmd += ["-af", af_chain]

    cmd += [
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
            try:
                h, m, s = dur_str.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except (ValueError, IndexError):
                pass
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
    - Audio at 44100 Hz AAC (with optional voice enhancement)
    - LUT color grading (if configured)

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

    # Re-encode audio with optional voice enhancement
    aac_temp = clip_path.with_suffix(".aac")
    if not reencode_audio(audio_path, aac_temp, voice_enhance=AUDIO_ENHANCE_ENABLED):
        return False

    # Save enhanced version for debugging if enabled
    if AUDIO_ENHANCE_ENABLED and AUDIO_ENHANCE_DEBUG_DIR:
        debug_path = AUDIO_ENHANCE_DEBUG_DIR / f"{clip_path.stem}_enhanced.aac"
        if not debug_path.exists():
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(aac_temp, debug_path)

    # Build video filter chain
    vf_parts = [
        f"scale={VIDEO_SIZE}:force_original_aspect_ratio=increase",
        f"crop={VIDEO_SIZE}",
        f"zoompan=z='{zoom_expr}':d={frames}:s={VIDEO_SIZE_X}:fps={FPS}",
    ]

    # Apply LUT color grading if LUT file exists
    if LUT_PATH and LUT_PATH.exists():
        vf_parts.append(f"lut3d=file='{LUT_PATH}'")

    vf_expr = ",".join(vf_parts)

    cmd = [
        str(FFMPEG), "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-i", str(aac_temp),
        "-vf", vf_expr,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(CRF),
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
