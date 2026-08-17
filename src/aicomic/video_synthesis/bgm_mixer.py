"""BGM mixer — random/指定 BGM + 音量控制 + 自动平衡.

Distilled from MoneyPrinterTurbo video.py BGM logic.
Wraps AlComics existing audio_mix.py with a clean API.
"""
from __future__ import annotations

import random
import subprocess
from pathlib import Path
from typing import Optional

from aicomic.video_synthesis.config import FFMPEG, AUDIO_SAMPLE_RATE
from aicomic.video_synthesis.audio_mix import BGM_DIR, BGM_TRACKS, select_bgm_for_episode


def mix_bgm(
    voiceover_path: Path,
    output_path: Path,
    bgm_mode: str = "random",
    bgm_file: Optional[str] = None,
    voice_volume: float = 1.0,
    bgm_volume: float = 0.35,
    fade_in_seconds: float = 1.0,
    fade_out_seconds: float = 2.0,
) -> bool:
    """Mix BGM under voiceover with auto volume balance.

    Args:
        voiceover_path: Narration audio file.
        output_path: Mixed output audio file.
        bgm_mode: "random" | "specify" | "none".
        bgm_file: Specific BGM filename (when bgm_mode="specify").
        voice_volume: Voiceover gain (1.0 = original).
        bgm_volume: BGM gain (0.35 ≈ 30% background, 70% voice).
        fade_in_seconds: BGM fade-in duration.
        fade_out_seconds: BGM fade-out duration.

    Returns True if mix succeeded.
    """
    if bgm_mode == "none":
        return _copy_audio(voiceover_path, output_path)

    bgm_path = _resolve_bgm(bgm_mode, bgm_file)
    if not bgm_path or not bgm_path.exists():
        # No BGM available — just copy voiceover
        return _copy_audio(voiceover_path, output_path)

    # FFmpeg amix: voice is foreground, BGM is background
    # Voice gets full volume, BGM gets bgm_volume with fade
    cmd = [
        FFMPEG, "-y",
        "-i", str(voiceover_path),
        "-i", str(bgm_path),
        "-filter_complex",
        f"[0:a]volume={voice_volume}[voice];"
        f"[1:a]volume={bgm_volume},afade=t=in:st=0:d={fade_in_seconds},"
        f"afade=t=out:st={_get_duration(voiceover_path) - fade_out_seconds}:d={fade_out_seconds},"
        f"aloop=loop=-1:size=2e9[bgm];"
        f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0[a]",
        "-map", "[a]",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", "2",
        "-b:a", "192k",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0 and output_path.exists()


def _resolve_bgm(mode: str, filename: Optional[str]) -> Optional[Path]:
    """Resolve BGM file path based on mode."""
    if mode == "specify" and filename:
        path = BGM_DIR / filename
        return path if path.exists() else None
    if mode == "random" and BGM_TRACKS:
        track = random.choice(BGM_TRACKS)
        return BGM_DIR / track[0]
    return None


def _get_duration(audio_path: Path) -> float:
    """Get audio duration in seconds."""
    try:
        result = subprocess.run(
            [FFMPEG, "-i", str(audio_path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=10,
        )
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 60.0  # fallback


def _copy_audio(src: Path, dst: Path) -> bool:
    """Copy audio file as-is."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        import shutil
        shutil.copy2(src, dst)
        return dst.exists()
    except Exception:
        return False
