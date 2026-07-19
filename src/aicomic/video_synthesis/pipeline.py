"""
Main video synthesis pipeline — orchestrates scene rendering, concatenation,
subtitle burn-in, and output verification.
"""

import json
import subprocess
import sys
from pathlib import Path

from aicomic.video_synthesis.config import (
    BGM_ENABLED,
    BGM_FADE_IN,
    BGM_FADE_OUT,
    BGM_VOLUME,
    CRF,
    DEFAULT_SCENE_DURATION,
    FFMPEG,
    OUTPUT_DIR,
    TEMP_DIR,
    VIDEO_BITRATE,
)
from aicomic.video_synthesis.scene import build_scene_video, get_audio_duration
from aicomic.video_synthesis.subtitles import write_ass, write_srt


# ── Logging ───────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[synth] {msg}", flush=True)


def run_cmd(cmd: list, desc: str = "") -> bool:
    """Run a command, return True on success."""
    log(f"→ {desc or 'run'}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  ✗ FAILED:")
        log(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        return False
    tail = [l for l in result.stderr.split("\n") if l.strip()][-5:]
    for line in tail:
        log(f"  {line}")
    return True


# ── Pipeline phases ───────────────────────────────────────────────────────

def resolve_scene_durations(
    scenes: list[dict],
    audio_dir: Path,
) -> list[float]:
    """
    Resolve duration for each scene.
    If duration is None, use max(5.0, audio_duration).
    """
    durations = []
    for s in scenes:
        audio_path = audio_dir / s["audio_name"]
        ad = get_audio_duration(audio_path) if audio_path.exists() else DEFAULT_SCENE_DURATION
        if s.get("duration") is None:
            durations.append(max(DEFAULT_SCENE_DURATION, ad))
        else:
            durations.append(float(s["duration"]))
    return durations


def phase_build_scenes(
    scenes: list[dict],
    durations: list[float],
    image_dir: Path,
    audio_dir: Path,
    temp_scenes_dir: Path,
) -> list[Path]:
    """Build all scene clips with Ken Burns + audio."""
    clip_paths = []
    for s, dur in zip(scenes, durations):
        img_path = image_dir / s["image_name"]
        audio_path = audio_dir / s["audio_name"]
        clip = temp_scenes_dir / f"scene_{s['num']:02d}.mp4"
        log(f"  Building S{s['num']:02d} ({dur:.1f}s) ...")
        if build_scene_video(clip, img_path, audio_path, dur, f"S{s['num']:02d}"):
            clip_paths.append(clip)
            size_kb = clip.stat().st_size / 1024 if clip.exists() else 0
            log(f"  ✓ S{s['num']:02d}: {size_kb:.0f} KB")
        else:
            log(f"  ✗ S{s['num']:02d}: failed")
            return []
    return clip_paths


def phase_concat(clip_paths: list[Path], output_path: Path) -> bool:
    """Concatenate scene clips via FFmpeg concat demuxer."""
    concat_file = TEMP_DIR / "concat.txt"
    with open(concat_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.absolute()}'\n")

    cmd = [
        str(FFMPEG), "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]
    return run_cmd(cmd, "Concat scenes")


def phase_bgm_mix(
    input_video: Path,
    output_video: Path,
    episode_code: str,
    episode_duration: float,
) -> bool:
    """
    Mix background music (BGM) into the video's audio track.

    Selects BGM based on episode mood, then:
    1. Loops the BGM to match video duration
    2. Applies fade-in/out on BGM
    3. Mixes BGM at configured volume behind the original audio

    Args:
        input_video: Path to concatenated video (no BGM yet)
        output_video: Output path with BGM mixed in
        episode_code: e.g. "E01" — used to select mood-appropriate BGM
        episode_duration: Total duration in seconds

    Returns:
        True on success
    """
    from aicomic.video_synthesis.audio_mix import (
        BGM_DIR,
        select_bgm_for_episode,
    )

    bgm_path = select_bgm_for_episode(episode_code)
    if bgm_path is None:
        log(f"  ⚠ No BGM track available for {episode_code}, skipping BGM mix")
        import shutil
        shutil.copy2(input_video, output_video)
        return True

    log(f"  🎵 BGM: {bgm_path.name} for {episode_code}")
    log(f"  🎛 Volume: voice=1.0, bgm={BGM_VOLUME}  |  Fade: in={BGM_FADE_IN}s out={BGM_FADE_OUT}s")

    # Extract the original audio from the concat video
    # Then mix with BGM using FFmpeg's amix filter
    cmd = [
        str(FFMPEG), "-y",
        # Input 0: concat video (has voiceover audio)
        "-i", str(input_video),
        # Input 1: BGM (will be looped)
        "-i", str(bgm_path),
        "-filter_complex",
        (
            # Loop BGM to cover full duration, fade in/out
            f"[1:a]aloop=loop=-1:size=44100,"
            f"atrim=duration={episode_duration},"
            f"volume={BGM_VOLUME},"
            f"afade=t=in:d={BGM_FADE_IN},"
            f"afade=t=out:st={max(0, episode_duration - BGM_FADE_OUT)}:d={BGM_FADE_OUT}"
            f"[bgm];"
            # Mix: original voice (unchanged) + BGM
            f"[0:a]volume=1.0[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2"
            f"[out]"
        ),
        # Copy video stream as-is
        "-map", "0:v:0",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-ar", "44100",
        "-b:a", "192k",
        "-ac", "2",        # Stereo for richer sound
        str(output_video),
    ]

    return run_cmd(cmd, f"BGM mix ({bgm_path.name})")


def phase_burn_subtitles(
    input_path: Path,
    sub_path: Path,
    output_path: Path,
    subtitle_format: str = "ass",
) -> bool:
    """
    Burn subtitles into video using FFmpeg subtitles filter.
    Supports both SRT and ASS formats.

    ASS is preferred for styled subtitles (font size, outline, position).
    """
    if subtitle_format == "ass":
        filter_expr = f"ass={str(sub_path)}"
    else:
        filter_expr = f"subtitles={str(sub_path)}"

    cmd = [
        str(FFMPEG), "-y",
        "-i", str(input_path),
        "-vf", filter_expr,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(CRF),
        "-maxrate", VIDEO_BITRATE,
        "-bufsize", "3000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output_path),
    ]
    return run_cmd(cmd, f"Burn subtitles ({subtitle_format.upper()})")


def verify_video(video_path: Path) -> dict:
    """Extract metadata from output video."""
    result = subprocess.run(
        [str(FFMPEG), "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    info = {
        "path": str(video_path),
        "size_bytes": video_path.stat().st_size,
        "size_mb": video_path.stat().st_size / (1024 * 1024),
    }
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            info["duration"] = line.strip().split(",")[0].split("Duration:")[-1].strip()
        if "Stream #0:0" in line and "Video" in line:
            info["video"] = line.strip()
        if "Stream #0:1" in line and "Audio" in line:
            info["audio"] = line.strip()
        if "bitrate" in line and "kb/s" in line:
            parts = line.strip().split(",")
            for p in parts:
                if "kb/s" in p:
                    info["bitrate"] = p.strip()

    info["passes"] = info["size_mb"] > 1.0
    return info


def write_report(report: dict, path: Path):
    """Write synthesis report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Episode synthesis ─────────────────────────────────────────────────────

def synthesize_episode(
    episode_code: str,
    scenes: list[dict],
    image_dir: Path,
    audio_dir: Path,
    output_path: Path | None = None,
    subtitle_format: str = "ass",
) -> dict | None:
    """
    Synthesize a full episode video.

    Pipeline phases:
    1. Determine scene durations (from audio or defaults)
    2. Build each scene (image + Ken Burns + enhanced audio)
    3. Create subtitle file (ASS with styling)
    4. Concatenate scenes
    5. Mix background music (BGM) into voiceover audio
    6. Burn subtitles into final video
    7. Verify output

    Args:
        episode_code: e.g. "E01"
        scenes: List of dicts with keys: num, image_name, audio_name,
                subtitle (str), duration (float or None)
        image_dir: Path to directory with key images.
        audio_dir: Path to directory with audio files.
        output_path: Output MP4 path. Defaults to releases/{episode_code}_full.mp4.
        subtitle_format: "ass" (styled) or "srt" (simple).

    Returns:
        Report dict with metadata, or None on failure.
    """
    log("=" * 60)
    log(f"Video Synthesis — {episode_code}")
    log("=" * 60)

    # ── Preparations ──
    if output_path is None:
        output_path = OUTPUT_DIR / f"{episode_code}_full.mp4"

    temp_ep_dir = TEMP_DIR / episode_code
    temp_scenes_dir = temp_ep_dir / "scenes"
    temp_ep_dir.mkdir(parents=True, exist_ok=True)
    temp_scenes_dir.mkdir(exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Phase 0: Duration analysis ──
    log(f"\n── Phase 0: Duration Analysis ──")
    durations = resolve_scene_durations(scenes, audio_dir)
    for s, dur in zip(scenes, durations):
        audio_path = audio_dir / s["audio_name"]
        ad = get_audio_duration(audio_path) if audio_path.exists() else 0
        log(f"  S{s['num']:02d}: audio={ad:.2f}s → clip={dur:.2f}s   sub={'✓' if s.get('subtitle') else ' '}")

    # ── Phase 1: Build scenes ──
    log(f"\n── Phase 1: Build Scenes ──")
    clip_paths = phase_build_scenes(scenes, durations, image_dir, audio_dir, temp_scenes_dir)
    if not clip_paths:
        log("✗ Scene building failed")
        return None
    log(f"  Built {len(clip_paths)} scenes")

    # ── Phase 2: Create subtitles ──
    log(f"\n── Phase 2: Create Subtitles ──")
    subtitles = [s.get("subtitle", "") for s in scenes]

    if subtitle_format == "ass":
        sub_path = temp_ep_dir / "episode.ass"
        write_ass(sub_path, durations, subtitles)
    else:
        sub_path = temp_ep_dir / "episode.srt"
        write_srt(sub_path, durations, subtitles)

    # Count non-empty subtitles
    sub_count = sum(1 for t in subtitles if t)
    log(f"  {sub_path.name}: {sub_count} entries")

    # ── Phase 3: Concatenate scenes ──
    log(f"\n── Phase 3: Concatenate ──")
    concat_temp = temp_ep_dir / "episode_concat.mp4"
    if not phase_concat(clip_paths, concat_temp):
        return None

    # ── Phase 3b: BGM Mix ──
    bgm_mixed = concat_temp  # default: same file if BGM disabled
    if BGM_ENABLED:
        log(f"\n── Phase 3b: BGM Mix ──")
        total_duration = sum(durations)
        bgm_mixed = temp_ep_dir / "episode_bgm.mp4"
        if not phase_bgm_mix(concat_temp, bgm_mixed, episode_code, total_duration):
            log("  ⚠ BGM mix failed, continuing without BGM")
            bgm_mixed = concat_temp

    # ── Phase 4: Burn subtitles ──
    log(f"\n── Phase 4: Burn Subtitles ──")
    if sub_count > 0:
        if not phase_burn_subtitles(bgm_mixed, sub_path, output_path, subtitle_format):
            return None
    else:
        # No subtitles — just copy bgm_mixed output
        import shutil
        shutil.copy2(bgm_mixed, output_path)
        log("  (no subtitles to burn)")

    # ── Phase 5: Verify ──
    log(f"\n── Phase 5: Verification ──")
    info = verify_video(output_path)
    log(f"  Output:  {info['path']}")
    log(f"  Size:    {info['size_mb']:.2f} MB")
    log(f"  Dur:     {info.get('duration', 'N/A')}")
    log(f"  Video:   {info.get('video', 'N/A')}")
    log(f"  Audio:   {info.get('audio', 'N/A')}")
    log(f"  Bitrate: {info.get('bitrate', 'N/A')}")

    if info["passes"]:
        log(f"\n{'='*60}")
        log(f"✓ {episode_code} SYNTHESIS COMPLETE")
        log(f"  Output: {output_path}")
        log(f"{'='*60}")
        info["status"] = "ok"
    else:
        log(f"\n⚠ Output < 1 MB. Check manually.")
        info["status"] = "small_output"

    # Write report
    report_path = output_path.with_suffix(".report.json")
    write_report(info, report_path)

    return info
