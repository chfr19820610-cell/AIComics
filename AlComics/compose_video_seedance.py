#!/usr/bin/env python3
"""
🎬 AIComics Seedance 视频合成管线
管线: 分镜JSON → Seedance 2.0 AI视频 → edge-tts配音 → 字幕合成 → MP4

专为 seedance 生成器设计，使用 seedance_client.py 的 SeedanceVideoClient。
支持 ep01_seedance.json 格式 (prompt_seedance 字段)。

Usage:
  # 只生成前3个镜头验证管线
  python compose_video_seedance.py --manifest manifests/ep01_seedance.json --shots 3 --dry-run
  python compose_video_seedance.py --manifest manifests/ep01_seedance.json --shots 3

  # 完整生成
  python compose_video_seedance.py --manifest manifests/ep01_seedance.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Path config ---
WORKSPACE = Path(os.environ.get("AICOMICS_ROOT", "/app"))
AI_COMICS = Path(os.environ.get("AI_COMICS_DIR", str(WORKSPACE)))
OUTPUT_DIR = AI_COMICS / "output"
TEMP_DIR = AI_COMICS / "temp"
SOURCE_FRAMES_DIR = AI_COMICS / "source_frames"
AUDIO_DIR = AI_COMICS / "audio"
ASSETS_DIR = AI_COMICS / "assets"
MANIFESTS_DIR = AI_COMICS / "manifests"

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
EDGE_TTS = shutil.which("edge-tts") or "edge-tts"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 24
VOICE_ZH = "zh-CN-XiaoxiaoNeural"
FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")
FONT_FALLBACK = os.environ.get("FONT_FALLBACK", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")


# ═══════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════

@dataclass
class ShotTask:
    """A single shot in the seedance pipeline."""
    shot_id: int
    scene_name: str
    shot_type: str
    duration_sec: float
    prompt_seedance: str
    narration: str = ""
    speaker: str = ""
    camera: str = "static"
    transition: str = "cut"

    # Runtime fields
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    segment_path: Optional[Path] = None


@dataclass
class EpisodeManifest:
    """Parsed episode manifest."""
    project: str
    episode: int
    title: str
    generator: str
    target_duration_sec: int
    width: int = 1080
    height: int = 1920
    fps: int = 24
    style: str = ""
    bgm: str = ""
    shots: List[ShotTask] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(s.duration_sec for s in self.shots)


# ═══════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_audio_duration(audio_path: str) -> float:
    cmd = [FFMPEG, "-i", str(audio_path), "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            try:
                parts = line.split("Duration: ")[1].split(",")[0].split(":")
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            except Exception:
                pass
    return 0


def find_bgm(bgm_name: str = "") -> Optional[Path]:
    bgm_dir = ASSETS_DIR / "bgm"
    if bgm_name:
        candidate = bgm_dir / bgm_name
        if candidate.exists():
            return candidate
    if bgm_dir.exists():
        mp3s = sorted(bgm_dir.glob("*.mp3"))
        if mp3s:
            return mp3s[0]
    return None


# ═══════════════════════════════════════════════════════════
# Manifest Parser (handles both prompt_sd and prompt_seedance)
# ═══════════════════════════════════════════════════════════

def parse_manifest(manifest_path: Path, max_shots: Optional[int] = None) -> EpisodeManifest:
    """Parse a seedance manifest JSON file."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    resolution = data.get("resolution", {})
    manifest = EpisodeManifest(
        project=data.get("project", "Untitled"),
        episode=data.get("episode", 1),
        title=data.get("title", f"Ep {data.get('episode', 1)}"),
        generator=data.get("generator", "seedance"),
        target_duration_sec=data.get("target_duration_sec", 240),
        width=resolution.get("width", VIDEO_WIDTH),
        height=resolution.get("height", VIDEO_HEIGHT),
        fps=data.get("fps", FPS),
        style=data.get("style", ""),
        bgm=data.get("bgm", ""),
    )

    scenes = data.get("scenes", [])
    if max_shots:
        scenes = scenes[:max_shots]

    for sc in scenes:
        shot = ShotTask(
            shot_id=sc.get("shot_id", 0),
            scene_name=sc.get("scene", ""),
            shot_type=sc.get("shot_type", "wide"),
            duration_sec=float(sc.get("duration_sec", 5)),
            prompt_seedance=sc.get("prompt_seedance") or sc.get("prompt_sd", ""),
            narration=sc.get("narration", ""),
            speaker=sc.get("speaker", ""),
            camera=sc.get("camera", "static"),
            transition=sc.get("transition", "cut"),
        )
        manifest.shots.append(shot)

    return manifest


# ═══════════════════════════════════════════════════════════
# Phase 1: Seedance Video Generation
# ═══════════════════════════════════════════════════════════

def phase1_generate_seedance(
    manifest: EpisodeManifest,
    model: str = "mini",
    concurrency: int = 1,
    dry_run: bool = False,
) -> List[ShotTask]:
    """Generate seedance videos for all shots."""
    print(f"\n{'='*60}")
    print(f"🎥 Phase 1: Seedance 2.0 视频生成 — Ep{manifest.episode:02d}")
    print(f"   Model: {model} | Shots: {len(manifest.shots)} | Concurrency: {concurrency}")
    print(f"{'='*60}")

    if dry_run:
        print("   🔍 DRY RUN — 只验证不实际生成")
        for shot in manifest.shots:
            print(f"   [{shot.shot_id}] {shot.scene_name}")
            print(f"      prompt: {shot.prompt_seedance[:80]}...")
        return manifest.shots

    # Import seedance client
    try:
        sys.path.insert(0, str(AI_COMICS))
        from seedance_client import SeedanceVideoClient
    except ImportError as e:
        print(f"   ❌ 无法导入 seedance_client: {e}")
        return manifest.shots

    client = SeedanceVideoClient(
        model=model,
        max_concurrency=concurrency,
    )

    # Check API reachability
    if not client.check_available(force=True):
        print("   ❌ Seedance API 不可达，终止视频生成")
        return manifest.shots
    print("   ✅ Seedance API 已连接")

    ep_dir = ensure_dir(SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}")

    # Build shot dicts for batch
    shot_dicts = []
    for shot in manifest.shots:
        shot_dicts.append({
            "shot_id": shot.shot_id,
            "prompt_sd": shot.prompt_seedance,
            "narration": shot.narration,
            "shot_type": shot.shot_type,
            "camera": shot.camera,
            "duration_sec": shot.duration_sec,
        })

    # For single-shot or small batch, use sequential generate() for reliability
    if len(shot_dicts) <= 3:
        print(f"\n   Using sequential mode for {len(shot_dicts)} shots...")
        for i, sd in enumerate(shot_dicts):
            shot = manifest.shots[i]
            output_path = ep_dir / f"shot_{shot.shot_id:02d}.mp4"
            print(f"\n   [{i+1}/{len(shot_dicts)}] Shot {shot.shot_id}: {shot.scene_name}")
            print(f"      prompt: {shot.prompt_seedance[:80]}...")

            try:
                task = client.generate(
                    prompt=shot.prompt_seedance,
                    output_path=output_path,
                    model=model,
                )
                if task.status.value == "COMPLETED":
                    shot.video_path = output_path
                    kb = output_path.stat().st_size / 1024 if output_path.exists() else 0
                    print(f"      ✅ 完成: {kb:.0f}KB")
                else:
                    print(f"      ❌ 失败: {task.error_message}")
            except Exception as e:
                print(f"      ❌ 异常: {e}")
    else:
        # Use batch mode for larger sets
        print(f"\n   Using batch mode for {len(shot_dicts)} shots...")
        try:
            result = client.batch_generate(
                shots=shot_dicts,
                output_dir=ep_dir,
                model=model,
                concurrency=concurrency,
            )
            print(f"\n   Batch result: {result.completed}/{result.total} completed")

            for shot in manifest.shots:
                expected = ep_dir / f"{shot.shot_id}.mp4"
                if expected.exists():
                    shot.video_path = expected
        except Exception as e:
            print(f"   ❌ Batch error: {e}")

    completed = sum(1 for s in manifest.shots if s.video_path and s.video_path.exists())
    print(f"\n   ── Phase 1 Summary: {completed}/{len(manifest.shots)} generated ──")
    return manifest.shots


# ═══════════════════════════════════════════════════════════
# Phase 2: TTS Narration
# ═══════════════════════════════════════════════════════════

def phase2_generate_tts(manifest: EpisodeManifest, dry_run: bool = False) -> List[ShotTask]:
    """Generate TTS narration audio for shots that have narration text."""
    print(f"\n{'='*60}")
    print(f"📢 Phase 2: TTS配音 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if dry_run:
        for shot in manifest.shots:
            if shot.narration.strip():
                print(f"   [{shot.shot_id}] '{shot.narration[:40]}...' (speaker: {shot.speaker})")
        return manifest.shots

    ep_audio_dir = ensure_dir(AUDIO_DIR / f"ep{manifest.episode:02d}")

    for shot in manifest.shots:
        if not shot.narration.strip():
            continue

        audio_path = ep_audio_dir / f"shot_{shot.shot_id:02d}.mp3"
        # Skip if already exists
        if audio_path.exists() and audio_path.stat().st_size > 100:
            shot.audio_path = audio_path
            print(f"   [{shot.shot_id}] ✅ (cached) {shot.narration[:30]}...")
            continue

        tmp_text = audio_path.with_suffix(".txt")
        tmp_text.write_text(shot.narration, encoding="utf-8")

        try:
            subprocess.run(
                [EDGE_TTS, "--voice", VOICE_ZH, "-f", str(tmp_text),
                 "--write-media", str(audio_path)],
                capture_output=True, text=True, timeout=60,
            )
            tmp_text.unlink(missing_ok=True)

            if audio_path.exists() and audio_path.stat().st_size > 100:
                shot.audio_path = audio_path
                print(f"   [{shot.shot_id}] ✅ {shot.narration[:30]}...")
            else:
                print(f"   [{shot.shot_id}] ⚠️ TTS空文件")
        except Exception as e:
            print(f"   [{shot.shot_id}] ⚠️ TTS错误: {e}")
            tmp_text.unlink(missing_ok=True)

    return manifest.shots


# ═══════════════════════════════════════════════════════════
# Phase 3: Video Composition (standardize + subtitles)
# ═══════════════════════════════════════════════════════════

def phase3_compose_segments(manifest: EpisodeManifest, dry_run: bool = False) -> List[ShotTask]:
    """Compose final video segments: standardize seedance video + add subtitles."""
    print(f"\n{'='*60}")
    print(f"🎬 Phase 3: 视频合成 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if dry_run:
        for shot in manifest.shots:
            has_video = shot.video_path and shot.video_path.exists()
            print(f"   [{shot.shot_id}] video={'✅' if has_video else '❌'} "
                  f"audio={'✅' if shot.audio_path else '-'}")
        return manifest.shots

    ep_temp = ensure_dir(TEMP_DIR / f"ep{manifest.episode:02d}")

    for shot in manifest.shots:
        if not shot.video_path or not shot.video_path.exists():
            print(f"   [{shot.shot_id}] ❌ 无视频素材")
            continue

        # Step 1: Standardize video (re-encode to consistent format)
        raw_seg = ep_temp / f"seg_raw_{shot.shot_id:02d}.mp4"
        cmd_std = [
            FFMPEG, "-y", "-i", str(shot.video_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-r", str(FPS), "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "-t", str(shot.duration_sec), "-pix_fmt", "yuv420p",
            str(raw_seg),
        ]
        subprocess.run(cmd_std, capture_output=True, text=True, timeout=120)

        if not raw_seg.exists() or raw_seg.stat().st_size < 1000:
            print(f"   [{shot.shot_id}] ❌ 标准化失败")
            continue

        # Step 2: Add subtitles + audio
        seg_final = ep_temp / f"seg_final_{shot.shot_id:02d}.mp4"

        # Prepare subtitle text
        sub_text = shot.narration if shot.narration else shot.scene_name
        font = FONT_PATH if os.path.exists(FONT_PATH) else FONT_FALLBACK

        if os.path.exists(font):
            wrapped = textwrap.wrap(sub_text, width=18, max_lines=2)
            sub_display = "\\n".join(wrapped[:2]) if wrapped else sub_text[:30]
            sub_display = (sub_display.replace("'", "’").replace(":", "：")
                          .replace(",", "，").replace('"', "”"))

            subtitle_filter = (
                f"drawtext=fontfile='{font}':"
                f"text='{sub_display}':"
                f"fontsize=44:fontcolor=white:"
                f"borderw=3:bordercolor=black@0.6:"
                f"x=(w-text_w)/2:y=h-text_h-160"
            )
        else:
            subtitle_filter = "null"

        cmd_final = [
            FFMPEG, "-y", "-i", str(raw_seg),
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        ]

        if shot.audio_path and shot.audio_path.exists():
            cmd_final.extend(["-i", str(shot.audio_path)])
            cmd_final.extend(["-c:a", "aac", "-b:a", "128k", "-shortest",
                            "-map", "0:v:0", "-map", "1:a:0"])
        else:
            cmd_final.append("-an")

        cmd_final.append(str(seg_final))
        subprocess.run(cmd_final, capture_output=True, text=True, timeout=120)

        if seg_final.exists() and seg_final.stat().st_size > 1000:
            shot.segment_path = seg_final
            print(f"   [{shot.shot_id}] ✅ {seg_final.name}")
        else:
            print(f"   [{shot.shot_id}] ❌ 字幕合成失败")

    return manifest.shots


# ═══════════════════════════════════════════════════════════
# Phase 4: Final Assembly
# ═══════════════════════════════════════════════════════════

def phase4_assemble_final(
    manifest: EpisodeManifest,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Optional[Path]:
    """Concatenate all segments into final MP4 with optional BGM."""
    print(f"\n{'='*60}")
    print(f"📦 Phase 4: 最终合成 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    out_dir = output_dir or OUTPUT_DIR
    ep_output = out_dir / f"ep{manifest.episode:02d}_seedance.mp4"

    if dry_run:
        ready = [s for s in manifest.shots if s.segment_path and s.segment_path.exists()]
        print(f"   可合成: {len(ready)}/{len(manifest.shots)} 段落")
        print(f"   输出: {ep_output}")
        return None

    # Collect valid segments
    segments = [s for s in manifest.shots if s.segment_path and s.segment_path.exists()]
    if not segments:
        print("   ❌ 无可合成段落")
        return None

    ensure_dir(out_dir)

    # Build concat file
    concat_file = TEMP_DIR / f"ep{manifest.episode:02d}_concat.txt"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.segment_path.absolute()}'\n")

    # Concat
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(ep_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if ep_output.exists() and ep_output.stat().st_size > 1000:
        size_mb = ep_output.stat().st_size / (1024 * 1024)
        print(f"   ✅ 最终视频: {ep_output.name} ({size_mb:.1f}MB)")
        print(f"   📂 {ep_output.absolute()}")
        return ep_output
    else:
        print(f"   ❌ 合成失败: {result.stderr[-500:]}")
        return None


# ═══════════════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════════════

def run_pipeline(
    manifest_path: Path,
    model: str = "mini",
    max_shots: Optional[int] = None,
    concurrency: int = 1,
    dry_run: bool = False,
    skip_tts: bool = False,
    skip_compose: bool = False,
) -> Optional[Path]:
    """Run the full seedance pipeline."""
    start = time.time()

    print(f"\n{'#'*60}")
    print(f"# AIComics Seedance Pipeline")
    print(f"# Manifest: {manifest_path.name}")
    print(f"# Model: {model} | Max shots: {max_shots or 'all'} | Dry run: {dry_run}")
    print(f"{'#'*60}")

    # Parse manifest
    manifest = parse_manifest(manifest_path, max_shots=max_shots)
    print(f"\n📋 {manifest.project} — {manifest.title}")
    print(f"   Generator: {manifest.generator} | Shots: {len(manifest.shots)} | "
          f"Target: {manifest.target_duration_sec}s")

    if not manifest.shots:
        print("❌ 无镜头数据")
        return None

    # Phase 1: Generate seedance videos
    manifest.shots = phase1_generate_seedance(manifest, model=model, concurrency=concurrency, dry_run=dry_run)

    if dry_run:
        elapsed = time.time() - start
        print(f"\n✅ Dry run complete ({elapsed:.0f}s)")
        return None

    # Phase 2: TTS
    if not skip_tts:
        manifest.shots = phase2_generate_tts(manifest)

    # Phase 3: Compose segments
    if not skip_compose:
        manifest.shots = phase3_compose_segments(manifest)

    # Phase 4: Final assembly
    final_path = phase4_assemble_final(manifest)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"🏁 Pipeline complete ({elapsed:.0f}s)")
    print(f"   输出: {final_path.absolute() if final_path else 'N/A'}")
    print(f"{'='*60}")

    return final_path


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AIComics Seedance Video Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run: validate manifest and show what would be generated
  python compose_video_seedance.py -m manifests/ep01_seedance.json --shots 3 --dry-run

  # Generate first 3 shots with mini model
  python compose_video_seedance.py -m manifests/ep01_seedance.json --shots 3 --model mini

  # Full generate 
  python compose_video_seedance.py -m manifests/ep01_seedance.json --model fast
        """,
    )
    parser.add_argument("--manifest", "-m", type=str, required=True, help="Seedance manifest JSON")
    parser.add_argument("--shots", type=int, help="Limit to first N shots")
    parser.add_argument("--model", type=str, default="mini", choices=["pro", "fast", "mini"],
                       help="Seedance model (default: mini)")
    parser.add_argument("--concurrency", type=int, default=1, help="Max parallel tasks")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no generation")
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS phase")
    parser.add_argument("--skip-compose", action="store_true", help="Skip video composition")
    parser.add_argument("--output-dir", "-o", type=str, help="Output directory override")

    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {args.manifest}")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else None
    result = run_pipeline(
        manifest_path=manifest_path,
        model=args.model,
        max_shots=args.shots,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        skip_tts=args.skip_tts,
        skip_compose=args.skip_compose,
    )
    return 0 if result or args.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())
