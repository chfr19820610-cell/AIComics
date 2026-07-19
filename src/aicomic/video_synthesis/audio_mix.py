"""
Audio quality enhancement module for video synthesis.

Provides:
1. Voice audio enhancement — compression, normalization, EQ
2. BGM mixing — layer background music under voiceover
3. BGM selection per episode based on mood/style
"""

import subprocess
import json
import random
from pathlib import Path
from typing import Optional

from aicomic.video_synthesis.config import FFMPEG, AUDIO_SAMPLE_RATE, AUDIO_BITRATE, SYSTEM_ROOT

# ── Paths ───────────────────────────────────────────────────────────────────
BGM_DIR = SYSTEM_ROOT / "assets" / "bgm"

# ── BGM track database ─────────────────────────────────────────────────────
# Each entry: (filename, mood_tags, description)
# Mood tags help auto-select BGM per episode
BGM_TRACKS = [
    # Demo / Universal (fallback)
    ("demo_bgm.wav", ["ambient", "calm", "universal", "dramatic", "cinematic"], "Universal ambient demo BGM — falls back for any episode"),

    # Dramatic / Cinematic
    ("bgm_dramatic_01.mp3", ["dramatic", "cinematic", "narrative"], "A Bizarre Diary — dramatic orchestral cinematic"),
    ("bgm_dramatic_02.mp3", ["dramatic", "cinematic", "subtle"], "A Bizarre Diary UnderscoreMix — softer dramatic underscore"),

    # Action / Intense
    ("bgm_action_01.mp3", ["action", "heroic", "epic"], "Norman — heroic action track"),
    ("bgm_action_02.mp3", ["action", "intense", "energetic"], "Street Warrior — intense action"),
    ("bgm_action_03.mp3", ["action", "energetic", "modern"], "Neophyte — modern energetic"),

    # Dark / Suspense
    ("bgm_dark_dark_world.mp3", ["dark", "mysterious", "noir", "suspense"], "Dark World — dark mysterious atmosphere"),

    # Ambient / Calm
    ("bgm_ambient_01.mp3", ["ambient", "calm", "peaceful", "emotional"], "Any Thing You Can Dream — calm ambient cinematic"),
]

# Episode → BGM mood preference mapping
EPISODE_BGM_MOOD: dict[str, list[str]] = {
    "E01": ["dramatic", "cinematic", "subtle"],  # Intro episode — dramatic but not too intense
    "E02": ["dramatic", "dark", "mysterious"],   # Rising tension
    "E03": ["action", "dramatic", "intense"],     # Mid-point climax
    "E04": ["dark", "mysterious", "suspense"],    # Dark turn
    "E05": ["action", "epic", "dramatic"],        # Finale
}


def select_bgm_for_episode(episode_code: str) -> Optional[Path]:
    """
    Select the best BGM track for a given episode based on mood.

    Falls back to a random track if no mood match is found.
    Returns full path to the MP3 file, or None if no BGM available.
    """
    if not BGM_DIR.exists():
        return None

    available = []
    for filename, moods, _desc in BGM_TRACKS:
        fp = BGM_DIR / filename
        if fp.exists():
            available.append((fp, moods))

    if not available:
        return None

    # Try to match by episode mood preference
    preferred_moods = EPISODE_BGM_MOOD.get(episode_code, ["dramatic", "cinematic"])
    candidates = []

    for fp, moods in available:
        score = sum(1 for m in preferred_moods if m in moods)
        if score > 0:
            candidates.append((score, fp))

    if candidates:
        # Sort by score descending, pick highest
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    # Fallback: random track
    return random.choice(available)[0]


def get_audio_duration_ffmpeg(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    result = subprocess.run(
        [str(FFMPEG), "-i", str(audio_path), "-hide_banner"],
        capture_output=True, text=True, timeout=30,
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
    return 30.0


def enhance_voice_audio(input_wav: Path, output_wav: Path) -> bool:
    """
    Apply audio enhancement to voiceover WAV:
    - High-pass filter (reduce low-frequency rumble)
    - Compression (even out volume)
    - Equalization (boost vocal presence ~3-4 kHz)
    - Normalization (bring to consistent level)
    - Noise reduction (mild gate)

    Uses FFmpeg's built-in audio filters — no external dependencies.

    Args:
        input_wav: Original TTS/Dub WAV file
        output_wav: Enhanced output WAV file

    Returns:
        True on success
    """
    # FFmpeg audio filter chain:
    # 1. highpass=f=80:   Remove subsonic rumble (80Hz cutoff)
    # 2. lowpass=f=8000:   Remove high-frequency noise above 8kHz
    # 3. compand:          Dynamic range compression (even out loud/quiet parts)
    # 4. equalizer:        Boost 3kHz vocal presence zone
    # 5. equalizer:        Slight cut at 200Hz to reduce muddiness
    # 6. loudnorm:         EBU R128 loudness normalization (consistent level)
    #
    # Filter syntax: comma-separated filter chain
    filter_chain = (
        "highpass=f=80,"
        "lowpass=f=8000,"
        "compand=attacks=0.3:decays=0.5:points=-80/-105|-62/-62|-40/-30|-20/-12|0/-3:gain=3:volume=0.8,"
        "equalizer=f=3000:t=q:w=1:g=3,"
        "equalizer=f=200:t=q:w=1:g=-2,"
        "loudnorm=I=-16:LRA=11:TP=-1.5"
    )

    cmd = [
        str(FFMPEG), "-y",
        "-i", str(input_wav),
        "-af", filter_chain,
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-sample_fmt", "s16",
        "-ac", "1",
        str(output_wav),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        print(f"  [audio_enhance] FAILED: {result.stderr[-500:]}")
        return False

    if not output_wav.exists() or output_wav.stat().st_size < 100:
        return False

    return True


def mix_bgm_with_voiceover(
    voiceover_path: Path,
    bgm_path: Path,
    output_path: Path,
    voice_volume: float = 1.0,
    bgm_volume: float = 0.35,
    bgm_fade_in: float = 2.0,
    bgm_fade_out: float = 3.0,
    episode_duration: Optional[float] = None,
) -> bool:
    """
    Mix BGM with voiceover audio track.

    The BGM track is:
    - Looped to match voiceover duration (if needed)
    - Volume-adjusted to sit under the voiceover
    - Faded in/out for smooth transitions

    Args:
        voiceover_path: Path to the voiceover audio (enhanced WAV/AAC)
        bgm_path: Path to the BGM MP3 file
        output_path: Output mixed audio path (AAC)
        voice_volume: Voiceover volume multiplier (1.0 = unchanged)
        bgm_volume: BGM volume relative to voice (0.0-1.0). Default 0.35 (≈7:3 ratio)
        bgm_fade_in: BGM fade-in duration in seconds
        bgm_fade_out: BGM fade-out duration in seconds
        episode_duration: Total duration in seconds. Auto-detected if None.

    Returns:
        True on success
    """
    # Determine duration from voiceover
    if episode_duration is None:
        episode_duration = get_audio_duration_ffmpeg(voiceover_path)

    if episode_duration <= 0:
        episode_duration = 30.0

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Strategy: Use amix filter to blend BGM and voiceover
    # We loop the BGM to fit the full episode duration
    cmd = [
        str(FFMPEG), "-y",
        # Input 0: Voiceover
        "-i", str(voiceover_path),
        # Input 1: BGM (will be looped)
        "-i", str(bgm_path),
        # Filter complex:
        "-filter_complex",
        (
            # Loop BGM until it covers the full duration
            f"[1:a]aloop=loop=-1:size=44100,"
            f"atrim=duration={episode_duration},"
            f"volume={bgm_volume},"
            f"afade=t=in:d={bgm_fade_in},"
            f"afade=t=out:st={max(0, episode_duration - bgm_fade_out)}:d={bgm_fade_out}"
            f"[bgm];"
            # Mix: voiceover (main) + BGM (side)
            f"[0:a]volume={voice_volume}[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2"
            f"[out]"
        ),
        # Output
        "-map", "[out]",
        "-c:a", "aac",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-b:a", "192k",
        "-ac", "2",  # Stereo output for richer sound
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"  [bgm_mix] FAILED: {result.stderr[-500:]}")
        return False

    if not output_path.exists() or output_path.stat().st_size < 100:
        return False

    return True


def generate_silence(duration_seconds: float, output_path: Path) -> bool:
    """Generate silent audio file (useful as temp placeholder)."""
    cmd = [
        str(FFMPEG), "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r={AUDIO_SAMPLE_RATE}:cl=mono",
        "-t", str(duration_seconds),
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0 and output_path.exists()
