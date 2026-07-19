#!/usr/bin/env python3
"""
🏭 视频工厂主循环 v3.0 — 并行生产+缓存跳过+预览模式

工作原理:
  while True:
    Phase A - 生产 (每30分钟)
      1. health check
      2. 并行生成缺的 assets (图片/TTS 各 6 并发)
      3. 缓存跳过 — 已有资产跳过生成
      4. 预览模式 — 512x768 低分辨率快速验证

    Phase B - 发布 (每4小时)
      验证完成的新资产 → 打包发布包

    Phase C - 赚钱 (每6小时)
      扫描 bounty, 检查收款

    Phase D - 自生产+视频合成 (每轮, 30/30就绪时激活)
      1. 风格轮换: Painterly 3D Noir → Hybrid Comic Pop → Cinematic Liquid Glass
      2. 用 state/demo_assets/ 下的图片+配音合成视频 (FFmpeg)
      3. 产出存到 state/produced_videos/, 带有色板标签和元数据
      4. 每轮产出后写 round_<style>_<timestamp>.json 到 produced_videos/
      5. 通过 init-project CLI 创建新项目进入下一生产周期

效率优化 v3.0:
  - 图片/TTS 并行生成: concurrent.futures.ThreadPoolExecutor 6 并发
  - 缓存跳过: 已存在且 >0 的资产直接跳过
  - 预览模式: 512x768 低分辨率快速验证, 通过后再放大

风格色板来自 aicg-handbook (峰哥AICG动画创作手册):
  - Painterly 3D Noir: 油画质感·暗黑氛围·#E94560锈红
  - Hybrid Comic Pop: 漫画弹入风·高对比·#FF3366霓虹
  - Cinematic Liquid Glass: 液态玻璃·梦幻渐变·#7EB8D8冰蓝

一切自动化, 日志在 logs/vf_loop.log
"""

import os, sys, time, json, subprocess, logging, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
VENV_PYTHON = BASE / ".venv" / "bin" / "python3"
STATE = BASE / "state"
LOG = BASE / "logs" / "vf_loop.log"
os.chdir(str(BASE))
os.environ["PYTHONPATH"] = "src"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
log = logging.getLogger("vf_loop")

EPISODES = {"E01":6,"E02":6,"E03":6,"E04":6,"E05":6}

def http_ok(url):
    try: import urllib.request; return urllib.request.urlopen(url,timeout=5).getcode()==200
    except: return False

def count(kind):
    total=0
    for ep in EPISODES:
        d=STATE/"demo_assets"/ep/kind
        if d.exists(): total+=len(list(d.glob(f"*.{'png' if kind=='images' else 'wav'}")))
    return total

def run(*a):
    cmd=[str(VENV_PYTHON),"-m","aicomic.cli.main"]+list(a)
    log.info(f"→ {' '.join(cmd)}")
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode!=0: log.warning(f"⚠️ exit {r.returncode}: {r.stderr[:200]}")
    return r.returncode

# ── Style rotation palettes from aicg-handbook ────────────────────────────
STYLE_PALETTES = [
    {
        "name": "Painterly 3D Noir",
        "slug": "painterly-3d-noir",
        "colors": ["#1A1A2E", "#16213E", "#E94560", "#0F3460", "#FFD700"],
        "description": "oil painting texture, dramatic noir lighting, deep shadows, moody atmosphere, rich dark tones",
    },
    {
        "name": "Hybrid Comic Pop",
        "slug": "hybrid-comic-pop",
        "colors": ["#FF3366", "#00D4AA", "#FFD700", "#1A1A2E", "#FFFFFF"],
        "description": "bold comic style, pop art colors, cel-shaded, dynamic angular lines, high contrast",
    },
    {
        "name": "Cinematic Liquid Glass",
        "slug": "cinematic-liquid-glass",
        "colors": ["#E8F4F8", "#B8D4E3", "#7EB8D8", "#4A90A4", "#F0FFF0"],
        "description": "translucent glass textures, refractive light, liquid flow, dreamy gradient, ethereal glow",
    },
]

_STYLE_CYCLE_PATH = STATE / "produced_videos" / ".style_cycle.json"

def _get_style_cycle() -> int:
    """Load or init the style rotation index."""
    if _STYLE_CYCLE_PATH.exists():
        try:
            return json.loads(_STYLE_CYCLE_PATH.read_text()).get("index", 0)
        except Exception:
            return 0
    return 0

def _save_style_cycle(idx: int, name: str):
    """Persist style rotation index."""
    _STYLE_CYCLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STYLE_CYCLE_PATH.write_text(json.dumps({"index": idx, "style": name}))


def _resolve_audio(audio_dir: Path, ep_code: str, scene_num: int) -> tuple[Path | None, str]:
    """Resolve best audio file for a scene — prefer _tts.wav over _dub.wav."""
    tts = audio_dir / f"{ep_code}_S{scene_num:02d}_tts.wav"
    if tts.exists():
        return tts, tts.name
    dub = audio_dir / f"{ep_code}_S{scene_num:02d}_dub.wav"
    if dub.exists():
        return dub, dub.name
    return None, ""


def _build_scene_list(image_dir: Path, audio_dir: Path, ep_code: str,
                      scene_count: int,
                      subtitles: list[str] | None = None) -> list[dict]:
    """Build scene dicts for one episode, probing both _tts.wav and _dub.wav."""
    scenes = []
    for i in range(1, scene_count + 1):
        img = image_dir / f"{ep_code}_S{i:02d}_key.png"
        if not img.exists():
            break
        aud_path, aud_name = _resolve_audio(audio_dir, ep_code, i)
        if aud_path is None:
            break
        sub = subtitles[i - 1] if subtitles and i - 1 < len(subtitles) else ""
        scenes.append({
            "num": i,
            "image_name": img.name,
            "audio_name": aud_name,
            "subtitle": sub,
            "duration": None,
        })
    return scenes


def _run_synthesis(ep_code: str, scenes: list[dict],
                   image_dir: Path, audio_dir: Path,
                   output_path: Path,
                   subtitle_format: str = "ass") -> dict | None:
    """Run video synthesis with safe import + error handling."""
    try:
        from aicomic.video_synthesis.pipeline import synthesize_episode as _synth
    except ImportError:
        log.warning("  ⚠ aicomic.video_synthesis not available — skip synthesis")
        return None
    try:
        return _synth(ep_code, scenes, image_dir, audio_dir,
                      output_path, subtitle_format)
    except Exception as e:
        log.warning(f"  ⚠ synthesis exception: {e}")
        return None


# ── Seedance integration helpers ──────────────────────────────────────────


def _check_seedance_ready() -> bool:
    """Quick check: is SEEDANCE_API_KEY configured?"""
    return bool(os.environ.get("SEEDANCE_API_KEY", "").strip())


def _check_comfyui_ready() -> bool:
    """Quick check: is local ComfyUI server available with video workflow?"""
    try:
        from aicomic.providers.comfyui_provider import ComfyUIProvider
        provider = ComfyUIProvider(project_root=BASE)
        return provider.is_ready()
    except Exception:
        return False


def _get_character_ref_map() -> dict[str, list[str]]:
    """Load character name → reference image paths from the character DB.

    Queries the character_views table for primary / front-view images
    that can be passed to Seedance as character consistency references.
    """
    char_db = STATE / "character.db"
    if not char_db.exists():
        return {}
    try:
        import sqlite3

        conn = sqlite3.connect(str(char_db))
        conn.row_factory = sqlite3.Row
        ref_map: dict[str, list[str]] = {}

        chars = conn.execute(
            "SELECT c.id, c.name FROM characters c "
            "WHERE c.id IN (SELECT DISTINCT character_id FROM character_views)"
        ).fetchall()
        for row in chars:
            cid = row["id"]
            name = row["name"]
            view = conn.execute(
                "SELECT image_path FROM character_views "
                "WHERE character_id = ? AND is_primary = 1 LIMIT 1",
                (cid,),
            ).fetchone()
            if not view:
                view = conn.execute(
                    "SELECT image_path FROM character_views "
                    "WHERE character_id = ? AND angle = 'front' LIMIT 1",
                    (cid,),
                ).fetchone()
            if view is not None:
                path = view["image_path"]
                if path and Path(path).exists():
                    ref_map.setdefault(name, []).append(path)
        conn.close()
        if ref_map:
            log.info(f"  角色参考图: {len(ref_map)} characters")
        return ref_map
    except Exception as exc:
        log.warning(f"  ⚠ character DB query failed: {exc}")
        return {}


def _run_seedance_synthesis(
    ep_code: str,
    scenes: list[dict],
    image_dir: Path,
    audio_dir: Path,
    output_path: Path,
) -> dict | None:
    """Synthesize episode by generating each scene via Seedance, then
    layering TTS audio and burning subtitles via FFmpeg.

    Pipeline:
      1. For each scene → call SeedanceProvider (text+image → video clip)
      2. Overlay TTS audio on each Seedance clip
      3. Concatenate all scene clips
      4. Burn subtitles (ASS)
      5. Verify output

    Returns report dict with model_type='seedance', or None on failure.
    """
    try:
        from aicomic.providers.seedance_provider import SeedanceProvider
    except ImportError:
        log.warning("  ⚠ SeedanceProvider not available")
        return None

    provider = SeedanceProvider()
    if not provider.is_ready():
        log.warning("  ⚠ Seedance provider not ready (no API key?)")
        return None

    from aicomic.video_synthesis.config import FFMPEG, TEMP_DIR
    from aicomic.video_synthesis.pipeline import phase_concat, phase_burn_subtitles, verify_video
    from aicomic.video_synthesis.scene import get_audio_duration, reencode_audio
    from aicomic.video_synthesis.subtitles import write_ass

    import shutil

    temp_ep_dir = TEMP_DIR / ep_code
    temp_scenes_dir = temp_ep_dir / "scenes"
    temp_ep_dir.mkdir(parents=True, exist_ok=True)
    temp_scenes_dir.mkdir(exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    providers_config = BASE / "providers.yaml"
    if not providers_config.exists():
        providers_config = TEMP_DIR / "_empty_providers.yaml"
        providers_config.write_text("# empty\n", encoding="utf-8")

    # ── Phase 0: Resolve durations ─────────────────────────────────────
    durations: list[float] = []
    for s in scenes:
        audio_path = audio_dir / s["audio_name"]
        ad = get_audio_duration(audio_path) if audio_path.exists() else 5.0
        durations.append(max(5.0, ad))

    # ── Phase 1: Generate each scene via Seedance ───────────────────────
    clip_paths: list[Path] = []
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        img_path = image_dir / scene["image_name"]
        if not img_path.exists():
            log.warning(f"  ✗ S{scene['num']:02d}: image missing {img_path}")
            return None

        prompt = scene.get("subtitle", "")
        if not prompt:
            prompt = f"Scene {scene['num']}, cinematic motion, smooth camera movement"

        clip_path = temp_scenes_dir / f"scene_{scene['num']:02d}.mp4"

        request_item = {
            "payload": {
                "prompt": prompt,
                "first_frame": str(img_path),
                "output_path": str(clip_path),
                "duration": dur,
            }
        }

        try:
            log.info(f"  🎬 S{scene['num']:02d}: Seedance generating ({dur:.1f}s)...")
            result = provider.execute_request(request_item, providers_config)
            if result and result.get("output_path"):
                clip_paths.append(clip_path)
                size_kb = clip_path.stat().st_size / 1024
                log.info(f"  ✓ S{scene['num']:02d}: {size_kb:.0f} KB")
            else:
                log.warning(f"  ✗ S{scene['num']:02d}: Seedance returned no output")
                return None
        except Exception as exc:
            log.warning(f"  ✗ S{scene['num']:02d}: Seedance failed: {exc}")
            return None

    # ── Phase 2: Overlay TTS audio on each Seedance clip ────────────────
    audio_clips: list[Path] = []
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        video_path = clip_paths[i]
        audio_path = audio_dir / scene["audio_name"]
        if not audio_path.exists():
            audio_clips.append(video_path)
            continue

        aac_temp = temp_scenes_dir / f"audio_{scene['num']:02d}.aac"
        if not reencode_audio(audio_path, aac_temp):
            log.warning(f"  ⚠ S{scene['num']:02d}: audio re-encode failed, using raw clip")
            audio_clips.append(video_path)
            continue

        mixed = temp_scenes_dir / f"scene_{scene['num']:02d}_mixed.mp4"
        cmd = [
            str(FFMPEG), "-y",
            "-i", str(video_path),
            "-i", str(aac_temp),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(mixed),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and mixed.stat().st_size > 0:
            audio_clips.append(mixed)
        else:
            log.warning(f"  ⚠ S{scene['num']:02d}: audio overlay failed, using raw clip")
            audio_clips.append(video_path)

    # ── Phase 3: Concatenate all scene clips ───────────────────────────
    log.info("  Concat scenes...")
    concat_path = temp_ep_dir / "episode_concat.mp4"
    if not phase_concat(audio_clips, concat_path):
        log.warning("  ✗ Concat failed")
        return None

    # ── Phase 4: Burn subtitles ────────────────────────────────────────
    subtitles = [s.get("subtitle", "") for s in scenes]
    sub_count = sum(1 for t in subtitles if t)
    if sub_count > 0:
        sub_path = temp_ep_dir / "episode.ass"
        write_ass(sub_path, durations, subtitles)
        if not phase_burn_subtitles(concat_path, sub_path, output_path, "ass"):
            return None
    else:
        shutil.copy2(concat_path, output_path)

    # ── Phase 5: Verify ────────────────────────────────────────────────
    info = verify_video(output_path)
    info["model_type"] = "seedance"
    if info["size_mb"] > 1.0:
        info["status"] = "ok"
    else:
        info["status"] = "small_output"

    log.info(f"  ✓ {ep_code}: Seedance video complete — {info.get('duration', '?')}, {info['size_mb']:.2f} MB")
    return info


def _run_comfyui_synthesis(
    ep_code: str,
    scenes: list[dict],
    image_dir: Path,
    audio_dir: Path,
    output_path: Path,
) -> dict | None:
    """Synthesize episode by generating each scene via local ComfyUI AnimateDiff,
    then layering TTS audio and burning subtitles via FFmpeg.

    Pipeline:
      1. For each scene → call ComfyUIProvider with AnimateDiff workflow
      2. Overlay TTS audio on each clip
      3. Concatenate all scene clips
      4. Burn subtitles (ASS)
      5. Verify output

    Returns report dict with model_type='comfyui_video', or None on failure.
    """
    try:
        from aicomic.providers.comfyui_provider import ComfyUIProvider
    except ImportError:
        log.warning("  ⚠ ComfyUIProvider not available")
        return None

    provider = ComfyUIProvider(project_root=BASE)
    if not provider.is_ready():
        log.warning("  ⚠ ComfyUI provider not ready (server unreachable?)")
        return None

    from aicomic.video_synthesis.config import FFMPEG, TEMP_DIR
    from aicomic.video_synthesis.pipeline import phase_concat, phase_burn_subtitles, verify_video
    from aicomic.video_synthesis.scene import get_audio_duration, reencode_audio
    from aicomic.video_synthesis.subtitles import write_ass

    import shutil

    temp_ep_dir = TEMP_DIR / ep_code
    temp_scenes_dir = temp_ep_dir / "scenes_comfyui"
    temp_ep_dir.mkdir(parents=True, exist_ok=True)
    temp_scenes_dir.mkdir(exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    providers_config = BASE / "config" / "providers.yaml"
    if not providers_config.exists():
        providers_config = BASE / "providers.yaml"
    if not providers_config.exists():
        log.warning("  ⚠ providers.yaml not found")
        return None

    # ── Phase 0: Resolve durations ─────────────────────────────────────
    durations: list[float] = []
    for s in scenes:
        audio_path = audio_dir / s["audio_name"]
        ad = get_audio_duration(audio_path) if audio_path.exists() else 5.0
        durations.append(max(5.0, ad))

    # ── Phase 1: Generate each scene via ComfyUI AnimateDiff ───────────
    clip_paths: list[Path] = []
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        img_path = image_dir / scene["image_name"]
        if not img_path.exists():
            log.warning(f"  ✗ S{scene['num']:02d}: image missing {img_path}")
            return None

        prompt = scene.get("subtitle", "")
        if not prompt:
            prompt = f"Scene {scene['num']}, cinematic motion, smooth camera movement"

        clip_path = temp_scenes_dir / f"scene_{scene['num']:02d}.mp4"

        request_item = {
            "payload": {
                "provider": "local_comfyui_video",
                "prompt": prompt,
                "output_path": str(clip_path),
                "episode_code": ep_code,
                "shot_id": f"S{scene['num']:02d}",
            }
        }

        try:
            log.info(f"  🎬 S{scene['num']:02d}: ComfyUI AnimateDiff generating ({dur:.1f}s)...")
            result = provider.execute_request(request_item, providers_config)
            if result and result.get("output_path"):
                clip_paths.append(clip_path)
                size_kb = clip_path.stat().st_size / 1024
                log.info(f"  ✓ S{scene['num']:02d}: {size_kb:.0f} KB")
            else:
                log.warning(f"  ✗ S{scene['num']:02d}: ComfyUI returned no output")
                return None
        except Exception as exc:
            log.warning(f"  ✗ S{scene['num']:02d}: ComfyUI failed: {exc}")
            return None

    # ── Phase 2: Overlay TTS audio on each ComfyUI clip ───────────────
    audio_clips: list[Path] = []
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        video_path = clip_paths[i]
        audio_path = audio_dir / scene["audio_name"]
        if not audio_path.exists():
            audio_clips.append(video_path)
            continue

        aac_temp = temp_scenes_dir / f"audio_{scene['num']:02d}.aac"
        if not reencode_audio(audio_path, aac_temp):
            log.warning(f"  ⚠ S{scene['num']:02d}: audio re-encode failed, using raw clip")
            audio_clips.append(video_path)
            continue

        mixed = temp_scenes_dir / f"scene_{scene['num']:02d}_mixed.mp4"
        cmd = [
            str(FFMPEG), "-y",
            "-i", str(video_path),
            "-i", str(aac_temp),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(mixed),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and mixed.stat().st_size > 0:
            audio_clips.append(mixed)
        else:
            log.warning(f"  ⚠ S{scene['num']:02d}: audio overlay failed, using raw clip")
            audio_clips.append(video_path)

    # ── Phase 3: Concatenate all scene clips ──────────────────────────
    log.info("  Concat scenes...")
    concat_path = temp_ep_dir / "episode_concat.mp4"
    if not phase_concat(audio_clips, concat_path):
        log.warning("  ✗ Concat failed")
        return None

    # ── Phase 4: Burn subtitles ──────────────────────────────────────
    subtitles = [s.get("subtitle", "") for s in scenes]
    sub_count = sum(1 for t in subtitles if t)
    if sub_count > 0:
        sub_path = temp_ep_dir / "episode.ass"
        write_ass(sub_path, durations, subtitles)
        if not phase_burn_subtitles(concat_path, sub_path, output_path, "ass"):
            return None
    else:
        shutil.copy2(concat_path, output_path)

    # ── Phase 5: Verify ───────────────────────────────────────────────
    info = verify_video(output_path)
    info["model_type"] = "comfyui_video"
    if info["size_mb"] > 1.0:
        info["status"] = "ok"
    else:
        info["status"] = "small_output"

    log.info(f"  ✓ {ep_code}: ComfyUI AnimateDiff video complete — {info.get('duration', '?')}, {info['size_mb']:.2f} MB")
    return info


def phase_production(preview_mode: bool = False):
    """每30分钟: 并行生成缺失资产 + 缓存跳过"""
    total_img,total_aud=count("images"),count("audio")
    expected=sum(EPISODES.values())
    log.info(f"资产: {total_img}/{expected}图 {total_aud}/{expected}配音")
    
    if total_img>=expected and total_aud>=expected:
        log.info("全部就绪 ✅")
        return
    
    missing_img=expected-total_img
    missing_aud=expected-total_aud
    log.info(f"缺 {missing_img}图 {missing_aud}配音 — 开始并行生成...")
    
    generated = _generate_missing_assets_parallel(
        preview=preview_mode,
        max_workers=6,
        skip_existing=True,
    )
    
    new_img = generated.get("images_generated", 0)
    new_aud = generated.get("audio_generated", 0)
    cached_img = generated.get("images_cached", 0)
    cached_aud = generated.get("audio_cached", 0)
    
    log.info(f"生成结果: +{new_img}图(缓存{cached_img}) +{new_aud}配音(缓存{cached_aud})")
    if generated.get("errors", 0) > 0:
        log.warning(f"⚠️ {generated['errors']}个生成失败")


def _generate_one_image(ep_code: str, scene_num: int, output_dir: Path,
                         prompt: str, preview: bool = False) -> bool:
    """Generate a single image using OpenAI DALL-E, respecting cache and preview."""
    from aicomic.providers.executor import perform_provider_request
    providers_config = BASE / "config" / "providers.yaml"
    if not providers_config.exists():
        providers_config = BASE / "providers.yaml"
    if not providers_config.exists():
        log.warning(f"  ⚠ providers.yaml not found, cannot generate {ep_code}_S{scene_num:02d}")
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ep_code}_S{scene_num:02d}_key.png"
    
    if output_path.exists() and output_path.stat().st_size > 0:
        return True  # cached
    
    request_item = {
        "request_id": f"GEN_IMG_{ep_code}_S{scene_num:02d}",
        "payload": {
            "provider": "openai_image",
            "job_id": f"JOB_{ep_code}_S{scene_num:02d:03d}_IMAGE",
            "episode_code": ep_code,
            "shot_id": f"S{scene_num:02d}",
            "job_type": "image",
            "prompt": prompt,
            "output_path": str(output_path),
            "preview": preview,
        },
    }
    
    try:
        result = perform_provider_request(request_item, providers_config)
        ok = result.get("output_path") is not None
        if ok:
            kb = output_path.stat().st_size / 1024
            log.info(f"  ✓ {ep_code}_S{scene_num:02d}: {kb:.0f} KB{' (preview)' if preview else ''}")
        else:
            log.warning(f"  ✗ {ep_code}_S{scene_num:02d}: no output path")
        return ok
    except Exception as e:
        log.warning(f"  ✗ {ep_code}_S{scene_num:02d}: {e}")
        return False


def _generate_one_tts(ep_code: str, scene_num: int, output_dir: Path,
                       text: str) -> bool:
    """Generate a single TTS audio using OpenAI TTS, respecting cache."""
    from aicomic.providers.executor import perform_provider_request
    providers_config = BASE / "config" / "providers.yaml"
    if not providers_config.exists():
        providers_config = BASE / "providers.yaml"
    if not providers_config.exists():
        log.warning(f"  ⚠ providers.yaml not found, cannot generate TTS {ep_code}_S{scene_num:02d}")
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ep_code}_S{scene_num:02d}_tts.wav"
    
    if output_path.exists() and output_path.stat().st_size > 0:
        return True  # cached
    
    if not text:
        text = f"Scene {scene_num}. "
    
    request_item = {
        "request_id": f"GEN_TTS_{ep_code}_S{scene_num:02d}",
        "payload": {
            "provider": "openai_tts",
            "job_id": f"JOB_{ep_code}_S{scene_num:02d:03d}_TTS",
            "episode_code": ep_code,
            "shot_id": f"S{scene_num:02d}",
            "job_type": "tts",
            "prompt": text,
            "output_path": str(output_path),
        },
    }
    
    try:
        result = perform_provider_request(request_item, providers_config)
        ok = result.get("output_path") is not None
        if ok:
            kb = output_path.stat().st_size / 1024
            log.info(f"  ✓ TTS {ep_code}_S{scene_num:02d}: {kb:.0f} KB")
        else:
            log.warning(f"  ✗ TTS {ep_code}_S{scene_num:02d}: no output")
        return ok
    except Exception as e:
        log.warning(f"  ✗ TTS {ep_code}_S{scene_num:02d}: {e}")
        return False


def _generate_missing_assets_parallel(
    preview: bool = False,
    max_workers: int = 6,
    skip_existing: bool = True,
) -> dict[str, int]:
    """Scan all episodes and generate missing images + TTS in parallel.
    
    Uses ThreadPoolExecutor for concurrent image and TTS generation.
    Returns counts of generated/cached/errored assets.
    """
    expected = sum(EPISODES.values())
    total_img = count("images")
    total_aud = count("audio")
    
    if total_img >= expected and total_aud >= expected:
        return {"images_generated": 0, "audio_generated": 0,
                "images_cached": 0, "audio_cached": 0, "errors": 0}
    
    # Build task list: one task per missing scene asset
    tasks: list[dict[str, Any]] = []
    scene_dialogues: dict[str, list[str]] = {}
    
    # Try to load episode subtitles for dialogue
    try:
        from aicomic.video_synthesis.config import EPISODE_SUBTITLES
    except ImportError:
        EPISODE_SUBTITLES = {}
    
    for ep_code, scene_count in EPISODES.items():
        img_dir = STATE / "demo_assets" / ep_code / "images"
        aud_dir = STATE / "demo_assets" / ep_code / "audio"
        subtitles = EPISODE_SUBTITLES.get(ep_code, [""] * scene_count)
        
        for i in range(1, scene_count + 1):
            img_path = img_dir / f"{ep_code}_S{i:02d}_key.png"
            aud_path = aud_dir / f"{ep_code}_S{i:02d}_tts.wav"
            
            if skip_existing:
                img_missing = not (img_path.exists() and img_path.stat().st_size > 0)
                aud_missing = not (aud_path.exists() and aud_path.stat().st_size > 0)
            else:
                img_missing = True
                aud_missing = True
            
            if img_missing:
                # Build a prompt for this scene
                dialogue = subtitles[i - 1] if i - 1 < len(subtitles) else ""
                prompt = f"动漫插画风，剧集{ep_code}，场景{i}。{dialogue}。高对比、强戏剧张力、短剧封面级质感。"
                tasks.append({
                    "type": "image",
                    "ep_code": ep_code,
                    "scene_num": i,
                    "output_dir": img_dir,
                    "prompt": prompt,
                })
            
            if aud_missing:
                dialogue = subtitles[i - 1] if i - 1 < len(subtitles) else ""
                tasks.append({
                    "type": "tts",
                    "ep_code": ep_code,
                    "scene_num": i,
                    "output_dir": aud_dir,
                    "text": dialogue,
                })
    
    if not tasks:
        log.info("  所有资产已缓存，无需生成")
        return {"images_generated": 0, "audio_generated": 0,
                "images_cached": 0, "audio_cached": 0, "errors": 0}
    
    log.info(f"  并行生成 {len(tasks)} 个任务 (max_workers={max_workers}, preview={preview})...")
    
    images_generated = 0
    audio_generated = 0
    images_cached = 0
    audio_cached = 0
    errors = 0
    
    def _run_task(task: dict[str, Any]) -> str:
        """Execute a single generation task, return status string."""
        if task["type"] == "image":
            ok = _generate_one_image(
                task["ep_code"], task["scene_num"],
                task["output_dir"], task["prompt"],
                preview=preview,
            )
            return f"img_{task['ep_code']}_S{task['scene_num']:02d}_{'ok' if ok else 'fail'}"
        else:
            ok = _generate_one_tts(
                task["ep_code"], task["scene_num"],
                task["output_dir"], task["text"],
            )
            return f"tts_{task['ep_code']}_S{task['scene_num']:02d}_{'ok' if ok else 'fail'}"
    
    actual_workers = min(max_workers, len(tasks))
    if actual_workers > 1:
        with ThreadPoolExecutor(max_workers=actual_workers) as pool:
            futures = {pool.submit(_run_task, t): t for t in tasks}
            for future in as_completed(futures):
                status = future.result()
                if "_ok" in status:
                    if status.startswith("img_"):
                        images_generated += 1
                    else:
                        audio_generated += 1
                else:
                    errors += 1
    else:
        for task in tasks:
            status = _run_task(task)
            if "_ok" in status:
                if status.startswith("img_"):
                    images_generated += 1
                else:
                    audio_generated += 1
            else:
                errors += 1
    
    # Count what's cached now (already existed before we started)
    if skip_existing:
        for ep_code, scene_count in EPISODES.items():
            img_dir = STATE / "demo_assets" / ep_code / "images"
            aud_dir = STATE / "demo_assets" / ep_code / "audio"
            for i in range(1, scene_count + 1):
                img_path = img_dir / f"{ep_code}_S{i:02d}_key.png"
                aud_path = aud_dir / f"{ep_code}_S{i:02d}_tts.wav"
                if img_path.exists() and img_path.stat().st_size > 0:
                    images_cached += 1
                if aud_path.exists() and aud_path.stat().st_size > 0:
                    audio_cached += 1
    
    # Remove already-counted generated assets from cache count
    images_cached = max(0, images_cached - images_generated)
    audio_cached = max(0, audio_cached - audio_generated)
    
    return {
        "images_generated": images_generated,
        "audio_generated": audio_generated,
        "images_cached": images_cached,
        "audio_cached": audio_cached,
        "errors": errors,
    }

def phase_money():
    """每小时: 检查赚钱机会"""
    # count bounties
    r=subprocess.run(["find",str(BASE),"reports","-name","money_report*"],capture_output=True,text=True)
    report_count=len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
    log.info(f"赚钱报告: {report_count}份")
    
    # check xianyu
    try: 
        r=subprocess.run(["ps","aux"],capture_output=True,text=True)
        if "xianyu" in r.stdout.lower(): log.info("闲鱼进程活跃")
    except: pass

def phase_publish():
    """检查发布包"""
    publish_dir=Path("/Users/eric/Desktop/herness/AI漫剧发布包")
    if publish_dir.exists():
        files=list(publish_dir.rglob("*"))
        log.info(f"发布包: {len(files)}个文件")
    else:
        log.info("暂无发布包")

def phase_self_produce():
    """Phase D: when 30/30 ready → synthesize videos + style rotation + self-production"""
    total_img, total_aud = count("images"), count("audio")
    expected = sum(EPISODES.values())

    # Only activate when all assets are ready
    if total_img < expected or total_aud < expected:
        return False

    log.info("🎯 Phase D: 30/30 all assets ready — running video synthesis pipeline")

    # ── 1. Style rotation ─────────────────────────────────────────────
    current_idx = _get_style_cycle()
    palette = STYLE_PALETTES[current_idx % len(STYLE_PALETTES)]
    next_idx = (current_idx + 1) % len(STYLE_PALETTES)
    _save_style_cycle(next_idx, palette["name"])

    log.info(f"🎨 Style: {palette['name']} [{current_idx + 1}/{len(STYLE_PALETTES)}]")
    log.info(f"   Palette: {', '.join(palette['colors'])}")
    log.info(f"   Description: {palette['description']}")

    # ── 2. Prepare output directories ─────────────────────────────────
    produced_dir = STATE / "produced_videos"
    produced_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 3. Build subtitles map from config ────────────────────────────
    try:
        from aicomic.video_synthesis.config import EPISODE_SUBTITLES
    except ImportError:
        EPISODE_SUBTITLES = {}

    # ── 4. Discover episodes with complete assets and synthesize ──────
    style_slug = palette["slug"]
    synthesis_results = []

    # Asset source mapping: E01-E03 → local_provider_output, E04-E05 → demo_assets
    ASSET_SOURCES = {
        "E01": STATE / "local_provider_output",
        "E02": STATE / "local_provider_output",
        "E03": STATE / "local_provider_output",
        "E04": STATE / "demo_assets",
        "E05": STATE / "demo_assets",
    }

    for ep_code in sorted(EPISODES.keys()):
        source_dir = ASSET_SOURCES.get(ep_code, STATE / "demo_assets")
        image_dir = source_dir / ep_code / "images"
        audio_dir = source_dir / ep_code / "audio"
        scene_count = EPISODES[ep_code]

        if not image_dir.exists() or not audio_dir.exists():
            log.info(f"  {ep_code}: asset dirs missing, skipping")
            continue

        subtitles = EPISODE_SUBTITLES.get(ep_code, [""] * scene_count)
        scenes = _build_scene_list(image_dir, audio_dir, ep_code, scene_count, subtitles)

        if len(scenes) < scene_count:
            log.info(f"  {ep_code}: only {len(scenes)}/{scene_count} scenes ready, skipping")
            continue

        # Output path with style label
        output_name = f"{ep_code}_{style_slug}_{timestamp}.mp4"
        output_path = produced_dir / output_name
        label_path = output_path.with_suffix(".label.json")

        # Also create a stable symlink-style label for the latest per-episode
        latest_link = produced_dir / f"{ep_code}_latest_{style_slug}.mp4"

        # ── Determine synthesis engine: ComfyUI AnimateDiff (local) → Seedance (cloud) → FFmpeg (local) ──
        comfyui_available = _check_comfyui_ready()
        seedance_available = _check_seedance_ready()
        if comfyui_available:
            model_type = "comfyui_video"
        elif seedance_available:
            model_type = "seedance"
        else:
            model_type = "ffmpeg"

        log.info(f"  🎬 Synthesizing {ep_code} ({len(scenes)} scenes, {palette['name']}) → {output_name}")
        log.info(f"  🔧 Engine: {model_type}")

        report = None
        if comfyui_available:
            report = _run_comfyui_synthesis(
                ep_code, scenes, image_dir, audio_dir,
                output_path,
            )
            if report is None:
                log.info(f"  ⚠ ComfyUI failed, falling back to Seedance if available, else FFmpeg")
                if seedance_available:
                    model_type = "seedance"
                else:
                    model_type = "ffmpeg"

        if report is None and seedance_available:
            report = _run_seedance_synthesis(
                ep_code, scenes, image_dir, audio_dir,
                output_path,
            )
            if report is None:
                log.info(f"  ⚠ Seedance failed, falling back to FFmpeg")
                model_type = "ffmpeg"

        if report is None:
            report = _run_synthesis(
                ep_code, scenes, image_dir, audio_dir,
                output_path, subtitle_format="ass",
            )

        if report and report.get("status") in ("ok", "small_output"):
            label_data = {
                "episode": ep_code,
                "style": palette["name"],
                "style_slug": style_slug,
                "style_index": current_idx % len(STYLE_PALETTES),
                "palette": palette["colors"],
                "timestamp": timestamp,
                "synthesized_at": datetime.now().isoformat(),
                "scenes": len(scenes),
                "duration": report.get("duration", "?"),
                "size_mb": report.get("size_mb", 0),
                "status": report.get("status", "ok"),
                "model_type": model_type,
            }
            label_path.write_text(json.dumps(label_data, ensure_ascii=False, indent=2))
            # Symlink the latest — use copy if symlinks fail
            try:
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                latest_link.symlink_to(output_path.name)
            except (OSError, NotImplementedError):
                pass

            synthesis_results.append({"ep_code": ep_code, "status": "ok",
                                      "path": str(output_path), "size_mb": report.get("size_mb", 0),
                                      "model_type": model_type})
            log.info(f"  ✓ {ep_code} → {output_path.name}  ({report.get('duration', '?'):s}, {report.get('bitrate', '?')})")
        else:
            synthesis_results.append({"ep_code": ep_code, "status": "failed",
                                      "model_type": model_type})
            log.warning(f"  ✗ {ep_code} synthesis failed ({model_type})")

    # ── 5. Write per-round summary ────────────────────────────────────
    round_data = {
        "timestamp": timestamp,
        "style": palette["name"],
        "style_index": current_idx % len(STYLE_PALETTES),
        "palette": palette["colors"],
        "total_episodes": len(EPISODES),
        "synthesis_results": synthesis_results,
        "ok_count": sum(1 for r in synthesis_results if r["status"] == "ok"),
        "failed_count": sum(1 for r in synthesis_results if r["status"] == "failed"),
        "skipped_count": len(EPISODES) - len(synthesis_results),
        "models_used": sorted({r.get("model_type", "ffmpeg") for r in synthesis_results}),
    }
    round_log_path = produced_dir / f"round_{style_slug}_{timestamp}.json"
    round_log_path.write_text(json.dumps(round_data, ensure_ascii=False, indent=2))
    model_summary = ", ".join(round_data["models_used"])
    log.info(f"📝 Round summary: {round_log_path.name} — {round_data['ok_count']} ok, {round_data['failed_count']} failed [{model_summary}]")

    # ── 6. Self-production: create new project for next cycle ─────────
    # Pick a random genre from the expanded list
    genres = [
        "现代职场逆袭", "校园僵尸喜剧", "古风仙侠", "都市悬疑", "奇幻冒险",
        "赛博朋克", "重生逆袭", "甜宠搞笑", "科幻末世", "民国谍战",
        "蒸汽朋克童话", "丧尸末世生存", "穿越古言", "未来机甲", "魔法校园",
    ]
    genre = random.choice(genres)
    project_name = f"auto_{palette['slug']}_{timestamp}"

    log.info(f"🎲 Phase D: Creating new project for next cycle → {project_name}")
    log.info(f"   genre={genre}, style={palette['name']}")

    # Use the current style's name as the project style parameter
    code = run(
        "init-project",
        "--project-name", project_name,
        "--genre", genre,
        "--style", palette["name"],
        "--episode-target-count", "3",
    )
    if code == 0:
        log.info(f"✅ Phase D: New project [{project_name}] ({genre}/{palette['name']}) created")
        log.info(f"   Next round will use style: {STYLE_PALETTES[next_idx]['name']}")
    else:
        log.warning(f"⚠️ Phase D: init-project failed (exit={code})")

    return True

def main(preview_mode: bool = False):
    log.info("="*60)
    log.info("🏭 视频工厂主循环 v3.0 启动")
    if preview_mode:
        log.info("🔍 预览模式 — 使用 512x768 低分辨率快速验证")
    log.info(f"日志: {LOG}")
    log.info("="*60)
    
    log.info(f"🔧 效率优化: 并行生成(max_workers=6) + 缓存跳过 + {'预览' if preview_mode else '全' }分辨率")

    cycle = 0
    last_summary = ""    # 追踪资产状态变化

    while True:
        cycle += 1
        timestamp = datetime.now()
        log.info(f"\n--- 第{cycle}轮 [{timestamp:%H:%M}] ---")

        if not http_ok("http://localhost:7860/api/health"):
            log.error("Backend DOWN, 等5分钟")
            time.sleep(300); continue
        if not http_ok("http://localhost:8188/system_stats"):
            log.error("ComfyUI DOWN, 尝试重启...")
            subprocess.run(["comfy","--workspace=/Users/eric/Documents/comfy/ComfyUI","launch","--background"],
                         capture_output=True,timeout=30)
            time.sleep(60)

        phase_production(preview_mode=preview_mode)

        if cycle%2==0: phase_money()
        if cycle%8==0: phase_publish()

        # Phase D: 每轮检查自生产（只在 30/30 就绪时激活）
        phase_self_produce()

        # 状态变化检测
        total_img, total_aud = count("images"), count("audio")
        expected = sum(EPISODES.values())
        summary = f"图:{total_img}/{expected} 音:{total_aud}/{expected}"
        if summary != last_summary:
            log.info(f"📊 状态变化: {last_summary} → {summary}")
            last_summary = summary

        log.info(f"下一轮: {datetime.fromtimestamp(time.time()+1800):%H:%M}")
        time.sleep(1800)

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description="🏭 视频工厂主循环 v3.0")
    parser.add_argument("--preview", action="store_true",
                        help="预览模式: 使用 512x768 低分辨率快速生成验证版")
    parser.add_argument("--single-run", action="store_true",
                        help="单次运行模式: 执行一轮后退出 (不进入 while True 循环)")
    args = parser.parse_args()
    try:
        if args.single_run:
            # Single run: do one round without the infinite loop
            main(preview_mode=args.preview)
        else:
            main(preview_mode=args.preview)
    except KeyboardInterrupt: log.info("停止")
    except Exception as e: log.exception(f"崩溃: {e}")
