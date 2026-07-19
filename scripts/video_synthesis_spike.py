#!/usr/bin/env python3
"""
Spike: FFmpeg Video Synthesis Pipeline
验证：图片 + 配音 + 字幕 → MP4

Phase 1: 从单图+配音+字幕合成 MP4 视频剪辑
- Ken Burns 缩放效果 (100% → 105%)
- 配音同步 (WAV → AAC)
- 字幕 burn-in (SRT)
- 多场景拼接
- 输出 720p H.264 + AAC
"""

import os
import sys
import subprocess
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

SYSTEM_ROOT = Path("/Users/eric/Desktop/herness/AIComics/10_System")
FFMPEG = Path("/Users/eric/bin/ffmpeg")
ASSETS_DIR = SYSTEM_ROOT / "state" / "demo_assets" / "E01"
AUDIO_DIR = SYSTEM_ROOT / "state" / "local_provider_output" / "E01" / "audio"
OUTPUT_DIR = SYSTEM_ROOT / "state" / "releases"
SCRIPTS_DIR = SYSTEM_ROOT / "scripts"
TEMP_DIR = Path("/tmp") / "video_spike"

# Scene definitions
SCENES = [
    {
        "num": 1,
        "image": ASSETS_DIR / "images" / "E01_S01_key.png",
        "audio": AUDIO_DIR / "E01_S01_tts.wav",
        "subtitle": "这份方案，是你这种实习生能碰的吗？",
        "duration": 5.0,
    },
    {
        "num": 2,
        "image": ASSETS_DIR / "images" / "E01_S02_key.png",
        "audio": AUDIO_DIR / "E01_S02_tts.wav",
        "subtitle": "如果我能证明这不是我的错呢？",
        "duration": 5.0,
    },
    {
        "num": 3,
        "image": ASSETS_DIR / "images" / "E01_S03_key.png",
        "audio": AUDIO_DIR / "E01_S03_tts.wav",
        "subtitle": "谁批准你们动她的？",
        "duration": 5.0,
    },
    {
        "num": 4,
        "image": ASSETS_DIR / "images" / "E01_S04_key.png",
        "audio": AUDIO_DIR / "E01_S04_tts.wav",
        "subtitle": "她的身份，你还没资格问。",
        "duration": 5.0,
    },
    {
        "num": 5,
        "image": ASSETS_DIR / "images" / "E01_S05_key.png",
        "audio": AUDIO_DIR / "E01_S05_tts.wav",
        "subtitle": "",
        "duration": None,  # auto: max(5s, audio_dur)
    },
    {
        "num": 6,
        "image": ASSETS_DIR / "images" / "E01_S06_key.png",
        "audio": AUDIO_DIR / "E01_S06_tts.wav",
        "subtitle": "",
        "duration": None,
    },
]

FPS = 25
VIDEO_SIZE = "1280:720"
VIDEO_SIZE_X = "1280x720"
CRF = 23
AUDIO_BITRATE = "128k"


# ── Helpers ────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[spike] {msg}", flush=True)


def run_cmd(cmd: list, desc: str = "") -> bool:
    """Run a command, return True on success."""
    log(f"→ {desc or 'run'}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  ✗ FAILED:")
        log(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        return False
    # Print last few lines of ffmpeg output (informational)
    tail = [l for l in result.stderr.split("\n") if l.strip()][-5:]
    for line in tail:
        log(f"  {line}")
    return True


def get_audio_duration(wav_path: Path) -> float:
    """Get duration of a WAV file in seconds."""
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


def create_srt_file(scenes) -> Path:
    """Create an SRT with cumulative timestamps matching the concatenated timeline."""
    srt_path = TEMP_DIR / "episode.srt"
    lines = []
    current_time = 0.0
    sub_idx = 0

    for scene in scenes:
        dur = scene["duration"]
        text = scene["subtitle"]
        if not text or not dur:
            current_time += (dur or 0)
            continue

        sub_idx += 1

        def srt_ts(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(str(sub_idx))
        lines.append(f"{srt_ts(current_time)} --> {srt_ts(current_time + dur)}")
        lines.append(text)
        lines.append("")
        current_time += dur

    srt_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"  SRT: {len(lines)} lines")
    return srt_path


# ── Pipeline ──────────────────────────────────────────────────────────────

def prepare():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (TEMP_DIR / "scenes").mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_scene_video(clip_path: Path, img_path: Path, audio_path: Path, duration: float) -> bool:
    """
    Build a single scene: image + Ken Burns zoom + audio → MP4.
    No subtitles (applied at final stage).
    """
    frames = int(duration * FPS)
    zoom_expr = f"1+0.05*on/{frames}"

    cmd = [
        str(FFMPEG), "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-i", str(audio_path),
        "-vf",
        f"scale={VIDEO_SIZE}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_SIZE},"
        f"zoompan=z='{zoom_expr}':d={frames}:s={VIDEO_SIZE_X}:fps={FPS}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(CRF),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", AUDIO_BITRATE,
        "-shortest",
        "-t", str(duration),
        str(clip_path),
    ]
    return run_cmd(cmd, f"Scene {scene_num_from_path(img_path)}")


def scene_num_from_path(img_path: Path) -> str:
    name = img_path.stem
    parts = name.split("_")
    for p in parts:
        if p.startswith("S0"):
            return p
    return "??"


def concat_scenes(clip_paths: list[Path], output_path: Path) -> bool:
    """Concat all scene clips into one video (stream copy)."""
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


def burn_subtitles(input_path: Path, srt_path: Path, output_path: Path) -> bool:
    """Burn subtitles into the final concatenated video."""
    cmd = [
        str(FFMPEG), "-y",
        "-i", str(input_path),
        "-vf", f"subtitles={str(srt_path)}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(CRF),
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output_path),
    ]
    return run_cmd(cmd, "Burn subtitles")


def verify(video_path: Path) -> dict:
    """Inspect output metadata."""
    result = subprocess.run(
        [str(FFMPEG), "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    info = {"path": str(video_path), "size_bytes": video_path.stat().st_size}
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            info["duration"] = line.strip().split(",")[0].split("Duration:")[-1].strip()
        if "Stream #0:0" in line and "Video" in line:
            info["video"] = line.strip()
        if "Stream #0:1" in line and "Audio" in line:
            info["audio"] = line.strip()

    info["size_mb"] = info["size_bytes"] / (1024 * 1024)
    info["passes"] = info["size_mb"] > 1.0
    return info


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("Video Synthesis Pipeline — Spike Verification")
    log("=" * 60)

    # Pre-flight
    if not FFMPEG.exists():
        log(f"✗ FFmpeg not found at {FFMPEG}")
        sys.exit(1)
    log(f"FFmpeg: {FFMPEG}")

    for d in [ASSETS_DIR, AUDIO_DIR]:
        if not d.exists():
            log(f"✗ Directory not found: {d}")
            sys.exit(1)

    prepare()

    # ── Phase 0: Determine scene durations ──
    log("\n── Phase 0: Duration Analysis ──")
    for s in SCENES:
        ad = get_audio_duration(s["audio"])
        if s["duration"] is None:
            s["duration"] = max(5.0, ad)
        log(f"  S{s['num']:02d}: audio={ad:.2f}s → clip={s['duration']:.2f}s")
        assert s["image"].exists(), f"Missing: {s['image']}"
        assert s["audio"].exists(), f"Missing: {s['audio']}"

    # ── Phase 1: Build each scene (image + audio, no subs) ──
    log("\n── Phase 1: Build Scenes ──")
    clip_paths = []
    for s in SCENES:
        clip = TEMP_DIR / "scenes" / f"scene_{s['num']:02d}.mp4"
        if build_scene_video(clip, s["image"], s["audio"], s["duration"]):
            clip_paths.append(clip)
            log(f"  ✓ S{s['num']:02d}: {clip.stat().st_size / 1024:.0f} KB")
        else:
            sys.exit(1)

    # ── Phase 2: Create SRT (cumulative) ──
    log("\n── Phase 2: Create Subtitles ──")
    srt_path = create_srt_file(SCENES)
    log(f"  Path: {srt_path}")
    for line in srt_path.read_text().strip().split("\n"):
        log(f"  | {line}")

    # ── Phase 3: Concatenate scenes ──
    log("\n── Phase 3: Concatenate ──")
    concat_temp = TEMP_DIR / "episode_concat.mp4"
    if not concat_scenes(clip_paths, concat_temp):
        sys.exit(1)

    # ── Phase 4: Burn subtitles on final video ──
    log("\n── Phase 4: Burn Subtitles ──")
    output_path = OUTPUT_DIR / "E01_spike.mp4"
    if not burn_subtitles(concat_temp, srt_path, output_path):
        sys.exit(1)

    # ── Phase 5: Verify ──
    log("\n── Phase 5: Verification ──")
    info = verify(output_path)
    log(f"  Output:  {info['path']}")
    log(f"  Size:    {info['size_mb']:.2f} MB")
    log(f"  Dur:     {info.get('duration', 'N/A')}")
    log(f"  Video:   {info.get('video', 'N/A')}")
    log(f"  Audio:   {info.get('audio', 'N/A')}")
    log(f"  > 1 MB:  {'✓' if info['passes'] else '✗'}")

    if info["passes"]:
        log("\n" + "=" * 60)
        log("✓ SPIKE VERIFIED: FFmpeg video synthesis pipeline works")
        log(f"  Output: {output_path}")
        log("=" * 60)
    else:
        log("\n⚠ Output < 1 MB. Check manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
