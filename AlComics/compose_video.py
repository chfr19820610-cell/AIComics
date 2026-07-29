#!/usr/bin/env python3
"""
🎬 AIComics 视频合成管线 v3.0 — 全3D漫剧生产引擎
═══════════════════════════════════════════════════════════
管线: 分镜JSON → Tripo3D(模型) → Blender(场景/渲染) → Seedance(AI增强)
     → edge-tts配音 → 视频片段合成 → BGM混音 → 字幕 → MP4

支持: 2D (Ken Burns) 模式 (--manifest) + 3D (Blender) 模式 (--3d)
      单集/批量/Seedance AI视频

技能: aicg-handbook + blender-addon-engineer + comfyui-tripods-3d + donghua-episode-pipeline
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

# ============================================================
# Configuration
# ============================================================

WORKSPACE = Path(os.environ.get("AICOMICS_ROOT", "/app"))
AI_COMICS = Path(os.environ.get("AI_COMICS_DIR", str(WORKSPACE)))
OUTPUT_DIR = AI_COMICS / "output"
TEMP_DIR = AI_COMICS / "temp"
SOURCE_FRAMES_DIR = AI_COMICS / "source_frames"
AUDIO_DIR = AI_COMICS / "audio"
ASSETS_DIR = AI_COMICS / "assets"
MANIFESTS_DIR = AI_COMICS / "manifests"
BLENDER_SCRIPTS_DIR = AI_COMICS / "blender_scripts"
D3_ASSETS_DIR = AI_COMICS / "3d_assets"

# ffmpeg binary — auto-detect
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

# edge-tts binary
EDGE_TTS = shutil.which("edge-tts") or "edge-tts"

# Blender binary
BLENDER_BIN = os.environ.get("BLENDER_BIN", "blender")

# Video defaults
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 24
VOICE_ZH = "zh-CN-XiaoxiaoNeural"
FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")
FONT_FALLBACK = os.environ.get("FONT_FALLBACK", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")

# ============================================================
# Seedance 2.0 Configuration
# ============================================================

SEEDANCE_CONFIG = {
    "base_url": "http://token.yundashi.com/v1",
    "api_key": "sk-1VW5Wz1AZVmZoV7aMqFcQbQMREmqYVHexeUUNzto2sh4IYQJ",
    "model": "seedance20",
    "default_duration": 5,
    "resolution": "1080x1920",
    "fps": 24,
    "poll_interval": 5,
    "poll_timeout": 300,
    "motion_intensity": 0.3,   # Subtle motion for 3D enhancement
    "mode": "img2video",        # Image-to-video for 3D enhancement
}

# ============================================================
# Data Models
# ============================================================

@dataclass
class SceneTask:
    """A single scene in the episode pipeline."""

    scene_id: int
    shot_type: str = "MS"
    narrative: str = ""
    narration: str = ""
    duration_sec: float = 5.0
    prompt_sd: str = ""
    camera: str = "ken_burns"       # 2D: ken_burns/slow_zoom_in; 3D: dolly_in/static/pan_left...
    generator: str = "comfyui"       # 2D: comfyui/seedance; 3D: blender_3d/tripo_3d/seedance
    transition: str = "cut"
    lighting: str = "cinematic_noir" # 3D lighting preset
    seedance_enhance: bool = False   # 3D: enhance render with Seedance

    # 3D fields
    fbx_path: str = ""
    env_fbx_path: str = ""
    camera_3d: dict = field(default_factory=dict)

    # Runtime fields (populated during pipeline)
    frame_path: Optional[Path] = None
    frame_dir: Optional[Path] = None   # PNG sequence directory (3D)
    audio_path: Optional[Path] = None
    video_segment_path: Optional[Path] = None
    actual_duration: float = 0.0


@dataclass
class EpisodeManifest:
    """Parsed episode manifest."""

    project: str = "Untitled"
    episode: int = 1
    title: str = ""
    series_total: int = 12
    target_duration: int = 120
    pipeline_mode: str = "2d"       # "2d" or "3d"
    width: int = 1080
    height: int = 1920
    fps: int = 24
    visual_style: str = "painterly_3d_noir"
    bgm: str = ""
    blender_config: dict = field(default_factory=dict)
    d3_assets: dict = field(default_factory=dict)
    scenes: list = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(s.duration_sec for s in self.scenes)


# ============================================================
# CLI Argument Parser
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="🎬 AIComics 视频合成管线 v3.0 — 2D+3D 双模式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        示例:
          # 2D模式 (默认)
          python3 compose_video.py --manifest manifests/ep01.json

          # 3D模式
          python3 compose_video.py --manifest manifests/ep01_3d.json --3d

          # 批量12集 3D
          python3 compose_video.py --batch 12 --3d --skip-assets

          # 批量12集 2D + Seedance
          python3 compose_video.py --batch 12 --use-seedance
        """),
    )

    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--manifest", type=str, help="单集分镜JSON路径")
    mode.add_argument("--batch", type=int, help="批量生成N集 (按 ep01.json...epN.json)")
    mode.add_argument("--batch-range", type=int, nargs=2, metavar=("START", "END"),
                      help="批量生成指定范围 (如 --batch-range 3 7)")
    mode.add_argument("--qa", type=str, help="质检指定视频文件")
    mode.add_argument("--qa-batch", type=str, help="质检输出目录下所有MP4")

    # Pipeline mode
    parser.add_argument("--3d", dest="pipeline_3d", action="store_true",
                        help="启用3D管线 (Blender渲染模式)")
    parser.add_argument("--render-only", action="store_true",
                        help="仅渲染3D帧，不合成视频 (调试用)")

    # General options
    parser.add_argument("--series-dir", type=str, default=str(MANIFESTS_DIR),
                        help=f"分镜JSON目录 (默认: {MANIFESTS_DIR})")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR),
                        help=f"输出目录 (默认: {OUTPUT_DIR})")
    parser.add_argument("--skip-frames", action="store_true",
                        help="跳过帧生成，使用已有素材")
    parser.add_argument("--skip-assets", action="store_true",
                        help="跳过3D资产生成，使用已有FBX")
    parser.add_argument("--use-seedance", action="store_true",
                        help="启用 Seedance 2.0 AI视频生成 (2D模式)")
    parser.add_argument("--seedance", action="store_true",
                        help="3D模式: 对Blender渲染帧做Seedance增强")
    parser.add_argument("--resume-from", type=int, metavar="N",
                        help="批量模式下从第N集恢复")
    parser.add_argument("--no-bgm", action="store_true", help="跳过BGM")

    # 3D-specific options
    parser.add_argument("--blender-path", type=str, default=BLENDER_BIN,
                        help=f"Blender二进制路径 (默认: {BLENDER_BIN})")
    parser.add_argument("--render-workers", type=int, default=1,
                        help="并行Blender渲染worker数 (默认: 1)")
    parser.add_argument("--render-samples", type=int, default=32,
                        help="Blender渲染采样数 (默认: 32)")
    parser.add_argument("--render-engine", type=str, default="BLENDER_EEVEE_NEXT",
                        choices=["BLENDER_EEVEE_NEXT", "CYCLES"],
                        help="Blender渲染引擎 (默认: BLENDER_EEVEE_NEXT)")
    parser.add_argument("--no-cel-shader", action="store_true",
                        help="3D模式禁用赛璐璐材质")
    parser.add_argument("--regen-character", type=str, metavar="NAME",
                        help="强制重新生成指定角色的3D模型")

    # Legacy
    parser.add_argument("--dry-run", action="store_true",
                        help="仅解析manifest，不实际生成")

    return parser


# ============================================================
# Utility Functions
# ============================================================

def get_audio_duration(path: str) -> float:
    cmd = [FFMPEG, "-i", str(path), "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    for line in r.stderr.split("\n"):
        if "Duration" in line:
            try:
                parts = line.split("Duration: ")[1].split(",")[0].split(":")
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            except Exception:
                pass
    return 0

def get_video_duration(path: str) -> float:
    cmd = [FFMPEG, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0

def get_video_resolution(path: str) -> tuple:
    cmd = [FFMPEG, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    try:
        w, h = r.stdout.strip().split("x")
        return int(w), int(h)
    except Exception:
        return 0, 0

def get_video_codec(path: str) -> str:
    cmd = [FFMPEG, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return r.stdout.strip()

def get_audio_codec(path: str) -> str:
    cmd = [FFMPEG, "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return r.stdout.strip()

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

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
    legacy = WORKSPACE / "MoneyPrinterTurbo/resource/songs"
    if legacy.exists():
        mp3s = sorted(legacy.glob("*.mp3"))
        if mp3s:
            return mp3s[0]
    return None

def check_blender() -> bool:
    """Check if Blender is available and return version."""
    try:
        r = subprocess.run([BLENDER_BIN, "--version"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            ver_line = r.stdout.split("\n")[0] if r.stdout else "unknown"
            print(f"  🧊 Blender: {ver_line.strip()}")
            return True
    except FileNotFoundError:
        print(f"  ❌ Blender 未找到: {BLENDER_BIN}")
        return False
    except Exception as e:
        print(f"  ❌ Blender 检查失败: {e}")
        return False
    return False


# ============================================================
# Seedance 2.0 Client
# ============================================================

class SeedanceClient:
    """Client for Seedance 2.0 API."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or SEEDANCE_CONFIG
        self.base_url = self.config["base_url"]
        self.api_key = self.config["api_key"]
        self._available = None

    def check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from urllib.request import Request, urlopen
            req = Request(f"{self.base_url}/models",
                          headers={"Authorization": f"Bearer {self.api_key}"})
            urlopen(req, timeout=10)
            self._available = True
        except Exception as e:
            print(f"  ⚠️  Seedance API 不可达: {e}")
            self._available = False
        return self._available

    def generate(self, prompt: str, output_path: Path, duration: Optional[int] = None,
                 resolution: Optional[str] = None, mode: Optional[str] = None) -> Optional[Path]:
        """Generate AI video clip. Returns path or None."""
        from urllib.request import Request, urlopen

        if not self.check_available():
            return None

        duration = duration or self.config["default_duration"]
        resolution = resolution or self.config["resolution"]
        mode = mode or self.config.get("mode", "text2video")

        print(f"  🎥 Seedance [{mode}]: generating {duration}s...")

        try:
            body = json.dumps({
                "model": self.config["model"],
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution,
                "fps": self.config["fps"],
                "mode": mode,
            }).encode()

            req = Request(
                f"{self.base_url}/video/generations",
                data=body,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                method="POST",
            )
            resp = urlopen(req, timeout=30)
            data = json.loads(resp.read())
            gen_id = data.get("id") or data.get("generation_id")
            if not gen_id:
                print(f"  ❌ Seedance: no generation_id in response")
                return None

            # Poll
            elapsed = 0
            while elapsed < self.config["poll_timeout"]:
                time.sleep(self.config["poll_interval"])
                elapsed += self.config["poll_interval"]
                req = Request(
                    f"{self.base_url}/video/generations/{gen_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp = urlopen(req, timeout=10)
                sd = json.loads(resp.read())
                status = sd.get("status", "unknown")

                if status == "completed":
                    video_url = sd.get("video_url") or sd.get("url")
                    if video_url:
                        ensure_dir(output_path.parent)
                        vresp = urlopen(video_url, timeout=120)
                        output_path.write_bytes(vresp.read())
                        kb = output_path.stat().st_size / 1024
                        print(f"  ✅ Seedance: {output_path.name} ({kb:.0f}KB)")
                        return output_path
                elif status == "failed":
                    print(f"  ❌ Seedance failed: {sd.get('error', 'unknown')}")
                    return None

            print(f"  ⚠️  Seedance timeout after {self.config['poll_timeout']}s")
            return None

        except Exception as e:
            print(f"  ❌ Seedance error: {e}")
            return None

    def enhance_frame(self, frame_path: Path, output_path: Path,
                      duration: Optional[int] = None, prompt: str = "") -> Optional[Path]:
        """3D enhancement mode: Blender render → Seedance img2video."""
        return self.generate(
            prompt=prompt or "cinematic anime shot, smooth camera motion, painterly style",
            output_path=output_path,
            duration=duration,
            mode="img2video",
        )


# ============================================================
# ComfyUI Client (with Tripo 3D support)
# ============================================================

class ComfyUIClient:
    """Client for ComfyUI API (image generation + Tripo 3D)."""

    def __init__(self, base_url: str = "http://localhost:8188"):
        self.base_url = base_url
        self._available = None

    def check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from urllib.request import Request, urlopen
            req = Request(f"{self.base_url}/system_stats")
            urlopen(req, timeout=5)
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def generate_frame(self, prompt: str, output_path: Path) -> Optional[Path]:
        """Generate a static frame via ComfyUI (placeholder)."""
        print(f"  🖼️  ComfyUI: would generate frame for: {prompt[:60]}...")
        print(f"  ⚠️  ComfyUI workflow API not configured. Place images manually.")
        return None

    def generate_character_image(self, character_name: str, style_prompt: str,
                                 output_path: Path) -> Optional[Path]:
        """Generate a character reference image via ComfyUI."""
        prompt = (
            f"(masterpiece, best quality:1.2), character sheet, "
            f"{character_name}, full body, {style_prompt}, "
            f"simple background, front view"
        )
        return self.generate_frame(prompt, output_path)

    def tripo_generate_model(self, image_path: Path, output_fbx: Path,
                              character_name: str = "") -> Optional[Path]:
        """
        Submit a Tripo 3D workflow to ComfyUI: image → 3D model → rig → FBX.

        This submits a workflow JSON to ComfyUI's /prompt API.
        The workflow uses:
          LoadImage → TripoImageToModelNode → TripoRigNode → TripoConversionNode → Save

        Returns path to downloaded FBX or None.
        """
        if not self.check_available():
            print(f"  ⚠️  ComfyUI not available — cannot run Tripo workflow")
            return None

        print(f"  🔺 Tripo 3D: generating model for {character_name}...")
        print(f"  ⚠️  Tripo workflow requires ComfyUI workflow API integration.")
        print(f"  💡  Place FBX models manually in {output_fbx.parent}")

        # Placeholder: create a marker file
        ensure_dir(output_fbx.parent)
        marker = output_fbx.parent / f"{output_fbx.stem}.tripo_placeholder"
        marker.write_text(f"Tripo 3D placeholder for {character_name}\n"
                          f"Source image: {image_path}\n"
                          f"Target FBX: {output_fbx}\n")

        return None  # Return None until proper API integration


# ============================================================
# Manifest Parser
# ============================================================

def parse_manifest(manifest_path: Path, force_3d: bool = False) -> EpisodeManifest:
    """Parse storyboard JSON into EpisodeManifest."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    resolution = data.get("resolution", {})
    pipeline_mode = data.get("pipeline_mode", "2d")
    if force_3d:
        pipeline_mode = "3d"

    manifest = EpisodeManifest(
        project=data.get("project", "Untitled"),
        episode=data.get("episode", 1),
        title=data.get("title", f"Episode {data.get('episode', 1)}"),
        series_total=data.get("series_total", 12),
        target_duration=data.get("target_duration", 120),
        pipeline_mode=pipeline_mode,
        width=resolution.get("width", VIDEO_WIDTH),
        height=resolution.get("height", VIDEO_HEIGHT),
        fps=data.get("fps", FPS),
        visual_style=data.get("visual_style", "painterly_3d_noir"),
        bgm=data.get("bgm", ""),
        blender_config=data.get("blender_config", {}),
        d3_assets=data.get("3d_assets", {}),
    )

    for sc in data.get("scenes", []):
        scene = SceneTask(
            scene_id=sc.get("scene_id", 0),
            shot_type=sc.get("shot_type", "MS"),
            narrative=sc.get("narrative", ""),
            narration=sc.get("narration", ""),
            duration_sec=float(sc.get("duration_sec", 5)),
            prompt_sd=sc.get("prompt_sd", ""),
            camera=sc.get("camera", "ken_burns"),
            generator=sc.get("generator", "comfyui"),
            transition=sc.get("transition", "cut"),
            lighting=sc.get("lighting", "cinematic_noir"),
            seedance_enhance=sc.get("seedance_enhance", False),
            fbx_path=sc.get("fbx_path", ""),
            env_fbx_path=sc.get("env_fbx_path", ""),
            camera_3d=sc.get("camera_3d", {}),
        )
        manifest.scenes.append(scene)

    return manifest


def resolve_generator_2d(scene: SceneTask, use_seedance: bool) -> str:
    """Resolve 2D generator routing."""
    if not use_seedance:
        return "comfyui"
    if scene.generator not in ("comfyui", ""):
        return scene.generator
    seedance_shots = {"EW", "WS", "action", "fight"}
    return "seedance" if scene.shot_type in seedance_shots else "comfyui"


# ============================================================
# Phase 1: Parse & Validate
# ============================================================

def phase1_parse(manifest_path: Path, force_3d: bool = False) -> EpisodeManifest:
    print(f"\n{'='*60}")
    print(f"📋 Phase 1: 解析分镜 — {manifest_path.name}")
    print(f"{'='*60}")

    manifest = parse_manifest(manifest_path, force_3d)

    if not manifest.scenes:
        raise ValueError("Manifest 无场景定义 (scenes 为空)")

    print(f"  项目: {manifest.project}")
    print(f"  标题: {manifest.title}")
    print(f"  集数: {manifest.episode}/{manifest.series_total}")
    print(f"  管线: {'3D 🔺' if manifest.pipeline_mode == '3d' else '2D 🖼️'}")
    print(f"  目标时长: {manifest.target_duration}s")
    print(f"  镜头数: {len(manifest.scenes)}")
    print(f"  视觉风格: {manifest.visual_style}")
    print(f"  分镜总时长: {manifest.total_duration:.1f}s")

    return manifest


# ============================================================
# Phase 2: 3D Asset Generation (Tripo)
# ============================================================

def phase2_generate_3d_assets(manifest: EpisodeManifest, skip_assets: bool = False,
                               regen_character: str = "") -> dict:
    """Phase 2 (3D): Generate 3D models via Tripo/ComfyUI."""
    print(f"\n{'='*60}")
    print(f"🔺 Phase 2: 3D资产生成 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if skip_assets:
        print("  ⏭️  跳过3D资产生成 (--skip-assets)")
        print("  💡  将使用 3d_assets/ 目录中的已有FBX")
        return {}

    comfyui = ComfyUIClient()
    if not comfyui.check_available():
        print("  ⚠️  ComfyUI 不可达 — 使用已有FBX")
        return {}

    results = {}
    char_dir = ensure_dir(D3_ASSETS_DIR / "characters")

    # Collect unique characters from scenes
    # In the manifest, we'll use the default character unless per-scene FBX is specified
    default_char_fbx = manifest.d3_assets.get("character_model", "")
    if default_char_fbx:
        fbx_path = Path(default_char_fbx)
        if fbx_path.exists():
            print(f"  ✅ 角色模型已存在: {fbx_path.name}")
        else:
            print(f"  ⚠️  角色模型未找到: {default_char_fbx}")
            print(f"  💡  请运行 Tripo workflow 生成角色模型")

    # Generate additional assets
    for i, scene in enumerate(manifest.scenes):
        if scene.fbx_path and Path(scene.fbx_path).exists():
            continue
        if i == 0:  # Only log once
            print(f"  💡  分镜中引用的FBX将按需生成 (Tripo workflow)")

    return results


# ============================================================
# Phase 3+4: Blender 3D Render
# ============================================================

def run_blender_render(shot: SceneTask, episode: int, output_dir: Path,
                        manifest: EpisodeManifest, blender_bin: str,
                        render_engine: str, render_samples: int,
                        no_cel_shader: bool) -> Optional[Path]:
    """Run Blender to render a single shot as PNG sequence."""
    blender_script = BLENDER_SCRIPTS_DIR / "render_shot.py"

    if not Path(blender_bin).exists():
        print(f"  ❌ Blender binary not found: {blender_bin}")
        return None

    # Determine FBX path
    fbx_path = shot.fbx_path
    if not fbx_path:
        fbx_path = manifest.d3_assets.get("character_model", "")
    if not fbx_path or not Path(fbx_path).exists():
        print(f"  ⚠️  FBX not found, using placeholder cube in Blender")
        fbx_path = ""  # Blender script will create default cube

    env_fbx = shot.env_fbx_path or manifest.d3_assets.get("environment", "")

    shot_dir = ensure_dir(output_dir / f"shot_{shot.scene_id:02d}")
    res_str = f"{manifest.width}x{manifest.height}"

    cmd = [
        blender_bin,
        "--background",
        "--python", str(blender_script),
        "--",
        "--fbx", str(fbx_path) if fbx_path else "placeholder",
        "--output", str(shot_dir),
        "--shot-type", shot.shot_type,
        "--camera", shot.camera if shot.camera not in ("ken_burns", "slow_zoom_in") else "static",
        "--duration", str(shot.duration_sec),
        "--fps", str(manifest.fps),
        "--lighting", shot.lighting,
        "--resolution", res_str,
        "--samples", str(render_samples),
        "--engine", render_engine,
    ]

    if env_fbx and Path(env_fbx).exists():
        cmd.extend(["--env-fbx", env_fbx])

    if no_cel_shader:
        cmd.append("--no-cel-shader")

    print(f"  🧊 Blender渲染 shot_{shot.scene_id:02d}: "
          f"{shot.shot_type}/{shot.camera} {shot.duration_sec}s")

    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=int(shot.duration_sec * shot.fps * 10 + 60),  # Rough timeout
        )
        # Check for output files
        pngs = sorted(shot_dir.glob("*.png"))
        if pngs:
            print(f"    ✅ 渲染完成: {len(pngs)} 帧 → {shot_dir}")
            return shot_dir
        else:
            print(f"    ❌ Blender渲染无输出文件")
            # Print last bit of stderr for debugging
            stderr_tail = r.stderr[-500:] if r.stderr else "(no output)"
            print(f"    [Blender stderr tail]: {stderr_tail}")
            return None
    except subprocess.TimeoutExpired:
        print(f"    ❌ Blender 渲染超时")
        return None
    except Exception as e:
        print(f"    ❌ Blender 渲染失败: {e}")
        return None


def phase3_blender_render(manifest: EpisodeManifest, blender_bin: str,
                           render_engine: str, render_samples: int,
                           no_cel_shader: bool, seedance_enabled: bool) -> list:
    """Phase 3+4 (3D): Blender scene setup + render for all shots."""
    print(f"\n{'='*60}")
    print(f"🧊 Phase 3+4: Blender 3D渲染 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if not check_blender():
        print("  ❌ 无法使用3D管线: Blender 不可用")
        return manifest.scenes

    ep_frame_dir = ensure_dir(SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}")

    for shot in manifest.scenes:
        # Ensure camera is a valid 3D camera type
        if shot.camera in ("ken_burns", "slow_zoom_in", "pan_left"):
            # Map 2D camera names to 3D equivalents
            camera_map = {
                "ken_burns": "dolly_in",
                "slow_zoom_in": "dolly_in",
                "pan_left": "pan_left",
                "static": "static",
            }
            shot.camera = camera_map.get(shot.camera, "static")

        result_dir = run_blender_render(
            shot=shot,
            episode=manifest.episode,
            output_dir=ep_frame_dir,
            manifest=manifest,
            blender_bin=blender_bin,
            render_engine=render_engine,
            render_samples=render_samples,
            no_cel_shader=no_cel_shader,
        )
        if result_dir:
            shot.frame_dir = result_dir
            shot.frame_path = result_dir  # For compatibility
        else:
            print(f"  ⚠️  shot_{shot.scene_id:02d}: 渲染失败，将跳过")

    return manifest.scenes


# ============================================================
# Phase 5: Seedance 3D Enhancement
# ============================================================

def phase5_seedance_enhance(manifest: EpisodeManifest,
                              seedance_client: SeedanceClient) -> list:
    """Phase 5 (3D): Enhance Blender renders with Seedance img2video."""
    print(f"\n{'='*60}")
    print(f"🌐 Phase 5: Seedance AI增强 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if not seedance_client.check_available():
        print("  ⚠️  Seedance API 不可达 — 跳过AI增强")
        return manifest.scenes

    ep_dir = SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}"

    for shot in manifest.scenes:
        if not shot.seedance_enhance:
            continue

        if not shot.frame_dir or not shot.frame_dir.exists():
            print(f"  ⚠️  shot_{shot.scene_id:02d}: 无渲染帧，跳过增强")
            continue

        # Find first frame
        pngs = sorted(shot.frame_dir.glob("*.png"))
        if not pngs:
            continue

        first_frame = pngs[0]
        enhanced_path = shot.frame_dir.parent / f"shot_{shot.scene_id:02d}_sd.mp4"

        print(f"  🎥 shot_{shot.scene_id:02d}: 渲染帧 → Seedance增强")

        result = seedance_client.enhance_frame(
            frame_path=first_frame,
            output_path=enhanced_path,
            duration=int(shot.duration_sec),
            prompt=shot.prompt_sd,
        )

        if result:
            shot.frame_path = result  # Use enhanced video instead of PNG sequence
            shot.generator = "seedance"
            print(f"    ✅ Seedance增强完成: {result.name}")

    return manifest.scenes


# ============================================================
# Phase 2: 2D Frame Generation (original)
# ============================================================

def phase2_generate_frames_2d(manifest: EpisodeManifest, use_seedance: bool = False,
                               skip_frames: bool = False) -> list:
    print(f"\n{'='*60}")
    print(f"🎨 Phase 2: 帧生成 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    if skip_frames:
        print("  ⏭️  跳过帧生成 (--skip-frames)")
        ep_dir = SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}"
        for shot in manifest.scenes:
            candidates = list(ep_dir.glob(f"shot_{shot.scene_id:02d}.*"))
            if candidates:
                shot.frame_path = candidates[0]
                print(f"  ✅ shot_{shot.scene_id:02d}: {candidates[0].name}")
        return manifest.scenes

    comfyui = ComfyUIClient()
    seedance = SeedanceClient() if use_seedance else None

    if seedance and seedance.check_available():
        print("  🌐 Seedance 2.0: 已连接")
    elif seedance:
        print("  ⚠️  Seedance 不可达，降级为 ComfyUI")

    comfyui_ok = comfyui.check_available()
    print(f"  🖼️  ComfyUI: {'已连接' if comfyui_ok else '不可达'}")

    ep_dir = ensure_dir(SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}")

    for shot in manifest.scenes:
        gen = resolve_generator_2d(shot, use_seedance)
        print(f"\n  Scene {shot.scene_id:02d} [{gen}] {shot.shot_type}")

        if gen == "seedance" and seedance and seedance.check_available():
            out = ep_dir / f"shot_{shot.scene_id:02d}.mp4"
            result = seedance.generate(shot.prompt_sd, out, int(shot.duration_sec))
            if result:
                shot.frame_path = result
            else:
                print(f"  ⚠️  Seedance失败→降级ComfyUI")
                shot.frame_path = ep_dir / f"shot_{shot.scene_id:02d}.png"
        else:
            out = ep_dir / f"shot_{shot.scene_id:02d}.png"
            if comfyui_ok:
                result = comfyui.generate_frame(shot.prompt_sd, out)
                if result:
                    shot.frame_path = result
            shot.frame_path = out  # Mark expected path

    return manifest.scenes


# ============================================================
# Phase 3: TTS Narration (shared)
# ============================================================

def phase3_generate_tts(manifest: EpisodeManifest) -> list:
    print(f"\n{'='*60}")
    print(f"📢 Phase TTS: 配音 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    ep_audio_dir = ensure_dir(AUDIO_DIR / f"ep{manifest.episode:02d}")

    for shot in manifest.scenes:
        if not shot.narration.strip():
            continue

        audio_path = ep_audio_dir / f"shot_{shot.scene_id:02d}.mp3"
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
                dur = get_audio_duration(str(audio_path))
                shot.audio_path = audio_path
                shot.actual_duration = dur
                print(f"  ✅ Scene {shot.scene_id:02d}: {dur:.1f}s — {shot.narration[:30]}...")
            else:
                print(f"  ⚠️  Scene {shot.scene_id:02d}: TTS失败")
        except Exception as e:
            print(f"  ⚠️  Scene {shot.scene_id:02d}: TTS错误 — {e}")
            tmp_text.unlink(missing_ok=True)

    return manifest.scenes


# ============================================================
# Phase 4: Video Composition
# ============================================================

def create_ken_burns_segment(image_path: Path, duration_sec: float,
                               output_path: Path, fps: int = 24) -> Optional[Path]:
    """2D Ken Burns slow zoom from static image."""
    duration_frames = int(duration_sec * fps)
    zoom_factor = 1.04

    filter_cmd = (
        f"zoompan=z='min(zoom+0.0015,{zoom_factor})':d={duration_frames}:"
        f"s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={fps},format=yuv420p"
    )
    cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(image_path),
           "-vf", filter_cmd, "-c:v", "libx264", "-preset", "fast",
           "-crf", "22", "-t", str(duration_sec), "-pix_fmt", "yuv420p",
           str(output_path)]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path
    print(f"    KenBurns failed: {r.stderr[-300:]}")
    return None


def create_png_sequence_segment(png_dir: Path, duration_sec: float,
                                  output_path: Path, fps: int = 24) -> Optional[Path]:
    """Convert PNG sequence to video (3D render output)."""
    # Find the PNG files
    pngs = sorted(png_dir.glob("*.png"))
    if not pngs:
        print(f"    ❌ No PNG files in {png_dir}")
        return None

    # Check naming pattern (0001.png or 0001.png style)
    first = pngs[0]
    # Try to detect frame numbering pattern
    stem = first.stem
    # Determine padding: if stem is like "0001", pattern is %04d
    padding = len(stem)
    pattern = f"%0{padding}d"

    cmd = [
        FFMPEG, "-y",
        "-framerate", str(fps),
        "-i", str(png_dir / f"{first.name[0]}{pattern}.png"),  # HACK: reconstruct pattern
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-t", str(duration_sec),
        str(output_path),
    ]

    # Better approach: use a concat or glob
    # Fallback: use image2 demuxer with pattern
    # Let's use the glob approach
    input_file = output_path.parent / "frame_list.txt"
    with open(input_file, "w") as f:
        for p in pngs[:int(duration_sec * fps)]:  # Limit to needed frames
            f.write(f"file '{p}'\n")

    cmd2 = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-r", str(fps),
        "-i", str(input_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-vsync", "vfr",
        str(output_path),
    ]

    r = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
    input_file.unlink(missing_ok=True)

    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path

    # Fallback: try ffmpeg pattern approach
    png_pattern = png_dir / f"*.png"
    cmd3 = [
        FFMPEG, "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob", "-i", str(png_pattern),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-t", str(duration_sec),
        str(output_path),
    ]
    r3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=120)
    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path

    print(f"    PNG sequence encode failed: {r3.stderr[-300:]}")
    return None


def create_seedance_segment(video_path: Path, duration_sec: float,
                              output_path: Path, fps: int = 24) -> Optional[Path]:
    """Standardize a Seedance/Blender video segment."""
    cmd = [FFMPEG, "-y", "-i", str(video_path),
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-r", str(fps), "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
           "-t", str(duration_sec), "-pix_fmt", "yuv420p",
           str(output_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path
    return None


def add_subtitles_to_segment(video_path: Path, audio_path: Optional[Path],
                               subtitle_text: str, output_path: Path,
                               font_path: str = FONT_PATH) -> Optional[Path]:
    """Add drawtext subtitles and audio to a video segment."""
    if not os.path.exists(font_path):
        font_path = FONT_FALLBACK
    if not os.path.exists(font_path):
        print(f"    ⚠️  Font not found, skipping subtitles")
        shutil.copy2(video_path, output_path)
        return output_path

    wrapped = textwrap.wrap(subtitle_text, width=18, max_lines=2)
    sub_display = "\\\\n".join(wrapped[:2]) if wrapped else subtitle_text[:30]
    sub_display = sub_display.replace("'", "’").replace(":", "：").replace(",", "，").replace('"', "”")

    subtitle_filter = (
        f"drawtext=fontfile='{font_path}':text='{sub_display}':"
        f"fontsize=44:fontcolor=white:borderw=3:bordercolor=black@0.6:"
        f"x=(w-text_w)/2:y=h-text_h-160"
    )

    cmd = [FFMPEG, "-y", "-i", str(video_path),
           "-vf", subtitle_filter,
           "-c:v", "libx264", "-preset", "fast", "-crf", "22"]

    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-b:a", "128k",
                     "-shortest", "-map", "0:v:0", "-map", "1:a:0"])
    else:
        cmd.append("-an")

    cmd.append(str(output_path))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path
    print(f"    Subtitle burn failed: {r.stderr[-300:]}")
    return None


def phase4_compose_video(manifest: EpisodeManifest,
                           use_seedance: bool = False) -> list:
    """Phase 4 (shared): Compose video segments from frames (2D or 3D)."""
    print(f"\n{'='*60}")
    print(f"🎥 Phase 4: 视频合成 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    ep_temp = ensure_dir(TEMP_DIR / f"ep{manifest.episode:02d}")
    ep_source = SOURCE_FRAMES_DIR / f"ep{manifest.episode:02d}"
    is_3d = manifest.pipeline_mode == "3d"

    for shot in manifest.scenes:
        print(f"  Scene {shot.scene_id:02d} [{shot.generator}] {shot.duration_sec}s")

        # Determine frame source
        frame_path = shot.frame_path

        # For 3D mode, check if we have a PNG directory
        if is_3d and shot.frame_dir and shot.frame_dir.exists():
            frame_path = shot.frame_dir
        elif not frame_path or not (isinstance(frame_path, Path) and frame_path.exists()):
            # Try to find in source_frames
            candidates = sorted(ep_source.glob(f"shot_{shot.scene_id:02d}.*")) if ep_source.exists() else []
            if candidates:
                frame_path = candidates[0]
                shot.frame_path = frame_path
            elif is_3d:
                # Check for PNG sequence directory
                png_dir = ep_source / f"shot_{shot.scene_id:02d}"
                if png_dir.exists():
                    frame_path = png_dir
                    shot.frame_dir = png_dir
                else:
                    print(f"    ❌ 素材缺失: shot_{shot.scene_id:02d}")
                    continue
            else:
                print(f"    ❌ 素材缺失: shot_{shot.scene_id:02d}")
                continue

        # Create raw video segment
        raw_seg = ep_temp / f"seg_raw_{shot.scene_id:02d}.mp4"

        if isinstance(frame_path, Path) and frame_path.is_dir():
            # PNG sequence (3D render)
            seg = create_png_sequence_segment(
                frame_path, shot.duration_sec, raw_seg, manifest.fps)
        elif isinstance(frame_path, Path) and frame_path.suffix == ".mp4":
            # Video file (Seedance or pre-rendered)
            seg = create_seedance_segment(
                frame_path, shot.duration_sec, raw_seg, manifest.fps)
        elif isinstance(frame_path, Path) and frame_path.suffix in (".png", ".jpg", ".jpeg"):
            # Static image (2D Ken Burns)
            seg = create_ken_burns_segment(
                frame_path, shot.duration_sec, raw_seg, manifest.fps)
        else:
            print(f"    ❌ 未知素材类型: {frame_path}")
            continue

        if not seg:
            print(f"    ❌ 视频片段生成失败")
            continue

        # Add subtitles + audio
        seg_final = ep_temp / f"seg_final_{shot.scene_id:02d}.mp4"
        result = add_subtitles_to_segment(
            seg, shot.audio_path, shot.narration, seg_final)
        if result:
            shot.video_segment_path = result
            print(f"    ✅ {result.name}")

    return manifest.scenes


# ============================================================
# Phase 5: Audio Mixing (shared)
# ============================================================

def phase5_mix_audio(manifest: EpisodeManifest, no_bgm: bool = False) -> Optional[Path]:
    print(f"\n{'='*60}")
    print(f"🔊 Phase 5: 音频混音 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    ep_audio_dir = ensure_dir(AUDIO_DIR / f"ep{manifest.episode:02d}")
    audio_files = [s.audio_path for s in manifest.scenes
                   if s.audio_path and s.audio_path.exists()]

    if not audio_files:
        print("  ⚠️  无旁白音频，跳过混音")
        return None

    # Merge narration
    merged = ep_audio_dir / "merged_narration.mp3"
    concat_file = ep_audio_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for ap in audio_files:
            f.write(f"file '{ap}'\n")

    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(concat_file), "-c", "copy", str(merged)],
                   capture_output=True, timeout=30)
    concat_file.unlink(missing_ok=True)

    if not merged.exists():
        print("  ❌ 旁白合并失败")
        return None

    print(f"  ✅ 旁白合并: {merged.name}")

    # Final audio
    final_audio = ep_audio_dir / "final_audio.m4a"

    if no_bgm:
        subprocess.run([FFMPEG, "-y", "-i", str(merged), "-c:a", "aac",
                         "-b:a", "128k", str(final_audio)],
                       capture_output=True, timeout=30)
        print(f"  ✅ 最终音频 (无BGM): {final_audio.name}")
        return final_audio

    bgm_path = find_bgm(manifest.bgm)
    if bgm_path and bgm_path.exists():
        print(f"  🎵 BGM: {bgm_path.name}")
        cmd = [FFMPEG, "-y", "-i", str(merged), "-i", str(bgm_path),
               "-filter_complex",
               "[1:a]volume=0.08[bgm];[0:a][bgm]amix=inputs=2:duration=first[audio]",
               "-map", "[audio]", "-c:a", "aac", "-b:a", "128k", str(final_audio)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if final_audio.exists():
            print(f"  ✅ 最终音频 (含BGM): {final_audio.name}")
            return final_audio
    else:
        print("  ⚠️  无BGM，使用纯旁白")
        subprocess.run([FFMPEG, "-y", "-i", str(merged), "-c:a", "aac",
                         "-b:a", "128k", str(final_audio)],
                       capture_output=True, timeout=30)

    return final_audio if final_audio.exists() else None


# ============================================================
# Phase 6+7: Final Encode (shared)
# ============================================================

def phase6_final_encode(manifest: EpisodeManifest, output_dir: Path) -> Optional[Path]:
    print(f"\n{'='*60}")
    print(f"📦 Phase 6+7: 最终封装 — Ep{manifest.episode:02d}")
    print(f"{'='*60}")

    ep_temp = TEMP_DIR / f"ep{manifest.episode:02d}"
    ep_audio = AUDIO_DIR / f"ep{manifest.episode:02d}"

    segments = [s.video_segment_path for s in manifest.scenes
                if s.video_segment_path and s.video_segment_path.exists()]

    if not segments:
        print("  ❌ 无有效视频片段，无法封装")
        return None

    # Step 1: Concatenate
    concat_file = ep_temp / "concat.txt"
    intermediate = ep_temp / "intermediate.mp4"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0",
           "-i", str(concat_file), "-c", "copy", str(intermediate)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    concat_file.unlink(missing_ok=True)

    if not intermediate.exists():
        # Retry with re-encode
        with open(concat_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")
        cmd2 = [FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file), "-c:v", "libx264", "-preset", "fast",
                "-crf", "22", "-c:a", "aac", "-b:a", "128k", str(intermediate)]
        subprocess.run(cmd2, capture_output=True, timeout=120)
        concat_file.unlink(missing_ok=True)

    if not intermediate.exists():
        print("  ❌ 视频合并失败")
        return None

    print(f"  ✅ {len(segments)} 个片段已合并")

    # Step 2: Add audio
    final_audio = ep_audio / "final_audio.m4a"
    ensure_dir(output_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_output = output_dir / f"ep{manifest.episode:02d}_{manifest.project}_{ts}.mp4"

    if final_audio.exists():
        cmd = [FFMPEG, "-y", "-i", str(intermediate), "-i", str(final_audio),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-shortest", "-movflags", "+faststart", str(final_output)]
        subprocess.run(cmd, capture_output=True, timeout=120)
    else:
        cmd = [FFMPEG, "-y", "-i", str(intermediate),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", str(final_output)]
        subprocess.run(cmd, capture_output=True, timeout=60)

    if final_output.exists():
        size_mb = final_output.stat().st_size / (1024 * 1024)
        duration = get_video_duration(str(final_output))
        resolution = get_video_resolution(str(final_output))
        vcodec = get_video_codec(str(final_output))
        acodec = get_audio_codec(str(final_output))

        print(f"""
╔══════════════════════════════════════════╗
║  ✅ Ep{manifest.episode:02d} 视频生成完成！           ║
╠══════════════════════════════════════════╣
║  标题: {manifest.title[:35]}
║  管线: {'3D 🔺' if manifest.pipeline_mode == '3d' else '2D 🖼️'}
║  路径: {final_output}
║  时长: {duration:.1f}s
║  大小: {size_mb:.1f}MB
║  分辨率: {resolution[0]}x{resolution[1]}
║  编码: {vcodec}/{acodec}
║  镜头: {len(manifest.scenes)}
║  风格: {manifest.visual_style}
╚══════════════════════════════════════════╝
""")
        return final_output

    print("  ❌ 最终封装失败")
    return None


# ============================================================
# Full Pipeline: Single Episode
# ============================================================

def run_single_episode(manifest_path: Path, output_dir: Path,
                        pipeline_3d: bool = False,
                        use_seedance: bool = False,
                        seedance_enhance: bool = False,
                        skip_frames: bool = False,
                        skip_assets: bool = False,
                        no_bgm: bool = False,
                        dry_run: bool = False,
                        render_only: bool = False,
                        blender_bin: str = BLENDER_BIN,
                        render_engine: str = "BLENDER_EEVEE_NEXT",
                        render_samples: int = 32,
                        no_cel_shader: bool = False,
                        regen_character: str = "",
                        ) -> Optional[Path]:
    """Run full pipeline for one episode (2D or 3D)."""
    start_time = time.time()

    # Phase 1: Parse
    manifest = phase1_parse(manifest_path, force_3d=pipeline_3d)

    if dry_run:
        print("\n🏁 Dry-run 完成，不执行后续阶段")
        return None

    pipeline_mode = manifest.pipeline_mode

    if pipeline_mode == "3d":
        # ===== 3D Pipeline =====
        # Phase 2: 3D Asset Generation
        phase2_generate_3d_assets(manifest, skip_assets, regen_character)

        # Phase 3+4: Blender Render
        manifest.scenes = phase3_blender_render(
            manifest, blender_bin, render_engine, render_samples,
            no_cel_shader, seedance_enhance)

        if render_only:
            print("\n🏁 渲染完成 (--render-only)，不合成视频")
            elapsed = time.time() - start_time
            print(f"\n⏱️  渲染耗时: {elapsed/60:.1f} 分钟")
            return None

        # Phase 5: Seedance Enhancement (optional)
        if seedance_enhance:
            sd_client = SeedanceClient()
            manifest.scenes = phase5_seedance_enhance(manifest, sd_client)

    else:
        # ===== 2D Pipeline =====
        manifest.scenes = phase2_generate_frames_2d(manifest, use_seedance, skip_frames)

    # Shared phases for both pipelines
    # Phase TTS
    manifest.scenes = phase3_generate_tts(manifest)

    # Phase Video Compose
    manifest.scenes = phase4_compose_video(manifest, use_seedance)

    # Phase Audio Mix
    phase5_mix_audio(manifest, no_bgm)

    # Phase Final Encode
    final_path = phase6_final_encode(manifest, output_dir)

    # Cleanup
    ep_temp = TEMP_DIR / f"ep{manifest.episode:02d}"
    if ep_temp.exists():
        shutil.rmtree(ep_temp, ignore_errors=True)

    elapsed = time.time() - start_time
    print(f"\n⏱️  总耗时: {elapsed/60:.1f} 分钟")

    return final_path


# ============================================================
# Batch Processing
# ============================================================

def run_batch(series_dir: Path, output_dir: Path,
               num_episodes: int = 12, start_ep: int = 1,
               end_ep: Optional[int] = None,
               pipeline_3d: bool = False,
               use_seedance: bool = False,
               seedance_enhance: bool = False,
               skip_frames: bool = False,
               skip_assets: bool = False,
               no_bgm: bool = False,
               resume_from: Optional[int] = None,
               render_only: bool = False,
               blender_bin: str = BLENDER_BIN,
               render_engine: str = "BLENDER_EEVEE_NEXT",
               render_samples: int = 32,
               no_cel_shader: bool = False,
               regen_character: str = "",
               ) -> dict:
    """Run pipeline for multiple episodes."""
    if end_ep is None:
        end_ep = num_episodes

    first_ep = resume_from if resume_from else start_ep
    print(f"""
╔══════════════════════════════════════════════╗
║  🎬 批量生产 — Ep{first_ep:02d} → Ep{end_ep:02d}            ║
║  管线: {'3D 🔺' if pipeline_3d else '2D 🖼️'}
║  分镜目录: {series_dir}
║  输出目录: {output_dir}
║  Seedance: {'✅' if (use_seedance or seedance_enhance) else '❌'}
╚══════════════════════════════════════════════╝
""")

    results = {"started": datetime.now().isoformat(),
               "series_dir": str(series_dir), "episodes": {}}

    for ep_num in range(first_ep, end_ep + 1):
        manifest_path = series_dir / f"ep{ep_num:02d}.json"
        if not manifest_path.exists():
            print(f"\n⚠️  Ep{ep_num:02d}: 分镜文件不存在 {manifest_path}，跳过")
            results["episodes"][f"ep{ep_num:02d}"] = {
                "status": "skipped", "reason": "manifest not found"}
            continue

        print(f"\n{'#'*60}")
        print(f"# Episode {ep_num:02d}/{end_ep}")
        print(f"{'#'*60}")

        try:
            result = run_single_episode(
                manifest_path=manifest_path,
                output_dir=output_dir,
                pipeline_3d=pipeline_3d,
                use_seedance=use_seedance,
                seedance_enhance=seedance_enhance,
                skip_frames=skip_frames,
                skip_assets=skip_assets,
                no_bgm=no_bgm,
                render_only=render_only,
                blender_bin=blender_bin,
                render_engine=render_engine,
                render_samples=render_samples,
                no_cel_shader=no_cel_shader,
                regen_character=regen_character,
            )
            if result:
                results["episodes"][f"ep{ep_num:02d}"] = {
                    "status": "completed", "output": str(result),
                    "size_mb": round(result.stat().st_size / (1024 * 1024), 1),
                    "duration_s": round(get_video_duration(str(result)), 1)}
            else:
                results["episodes"][f"ep{ep_num:02d}"] = {
                    "status": "failed", "reason": "final output not found"}
        except Exception as e:
            print(f"\n❌ Ep{ep_num:02d} 异常: {e}")
            results["episodes"][f"ep{ep_num:02d}"] = {
                "status": "failed", "reason": str(e)}

    results["finished"] = datetime.now().isoformat()
    completed = sum(1 for v in results["episodes"].values() if v["status"] == "completed")
    failed = sum(1 for v in results["episodes"].values() if v["status"] == "failed")
    results["summary"] = {"completed": completed, "failed": failed}

    report_path = AI_COMICS / "batch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"""
╔══════════════════════════════════════════════╗
║  📊 批量报告                                  ║
╠══════════════════════════════════════════════╣
║  完成: {completed}/{end_ep - first_ep + 1}
║  失败: {failed}
║  报告: {report_path}
╚══════════════════════════════════════════════╝
""")
    return results


# ============================================================
# QA Functions
# ============================================================

def qa_check(video_path: Path) -> dict:
    results = {"path": str(video_path), "exists": video_path.exists(), "checks": {}}
    if not video_path.exists():
        return results

    duration = get_video_duration(str(video_path))
    resolution = get_video_resolution(str(video_path))
    vcodec = get_video_codec(str(video_path))
    acodec = get_audio_codec(str(video_path))
    size_mb = video_path.stat().st_size / (1024 * 1024)

    results["checks"] = {
        "duration_s": {"value": duration, "ok": duration > 1},
        "resolution": {"value": f"{resolution[0]}x{resolution[1]}",
                       "ok": resolution == (VIDEO_WIDTH, VIDEO_HEIGHT)},
        "video_codec": {"value": vcodec, "ok": "h264" in vcodec},
        "audio_codec": {"value": acodec, "ok": "aac" in acodec},
        "file_size_mb": {"value": round(size_mb, 1), "ok": size_mb > 1},
    }
    results["all_pass"] = all(c["ok"] for c in results["checks"].values())
    return results


def qa_print(results: dict):
    print(f"\n🔍 QA: {results['path']}")
    if not results["exists"]:
        print("  ❌ 文件不存在"); return
    for check, detail in results["checks"].items():
        icon = "✅" if detail["ok"] else "❌"
        print(f"  {icon} {check}: {detail['value']}")
    overall = "✅ ALL PASS" if results["all_pass"] else "❌ ISSUES FOUND"
    print(f"\n  {overall}")


# ============================================================
# Main Entry Point
# ============================================================

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Ensure directories
    for d in [OUTPUT_DIR, TEMP_DIR, SOURCE_FRAMES_DIR, AUDIO_DIR, ASSETS_DIR,
              MANIFESTS_DIR, BLENDER_SCRIPTS_DIR, D3_ASSETS_DIR]:
        ensure_dir(d)

    # QA mode
    if args.qa:
        results = qa_check(Path(args.qa))
        qa_print(results)
        return

    if args.qa_batch:
        qa_dir = Path(args.qa_batch)
        mp4s = sorted(qa_dir.glob("*.mp4"))
        all_pass = True
        for mp4 in mp4s:
            results = qa_check(mp4)
            qa_print(results)
            if not results["all_pass"]:
                all_pass = False
        print(f"\n{'✅ All pass' if all_pass else '❌ Some checks failed'}")
        return

    # Shared pipeline settings
    pipeline_3d = args.pipeline_3d

    # Batch mode
    if args.batch or args.batch_range:
        series_dir = Path(args.series_dir)
        if args.batch_range:
            start_ep, end_ep = args.batch_range
        else:
            start_ep, end_ep = 1, args.batch

        run_batch(
            series_dir=series_dir,
            output_dir=Path(args.output_dir),
            start_ep=start_ep, end_ep=end_ep,
            pipeline_3d=pipeline_3d,
            use_seedance=args.use_seedance,
            seedance_enhance=args.seedance,
            skip_frames=args.skip_frames,
            skip_assets=args.skip_assets,
            no_bgm=args.no_bgm,
            resume_from=args.resume_from,
            render_only=args.render_only,
            blender_bin=args.blender_path,
            render_engine=args.render_engine,
            render_samples=args.render_samples,
            no_cel_shader=args.no_cel_shader,
            regen_character=args.regen_character or "",
        )
        return

    # Single episode mode
    if args.manifest:
        run_single_episode(
            manifest_path=Path(args.manifest),
            output_dir=Path(args.output_dir),
            pipeline_3d=pipeline_3d,
            use_seedance=args.use_seedance,
            seedance_enhance=args.seedance,
            skip_frames=args.skip_frames,
            skip_assets=args.skip_assets,
            no_bgm=args.no_bgm,
            dry_run=args.dry_run,
            render_only=args.render_only,
            blender_bin=args.blender_path,
            render_engine=args.render_engine,
            render_samples=args.render_samples,
            no_cel_shader=args.no_cel_shader,
            regen_character=args.regen_character or "",
        )
        return

    # No mode specified → show help
    parser.print_help()


if __name__ == "__main__":
    main()
