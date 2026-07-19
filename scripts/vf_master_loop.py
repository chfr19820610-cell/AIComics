#!/usr/bin/env python3
"""
🏭 视频工厂主循环 v2.2 — 无限生产+视频合成+风格轮换+自生产

工作原理:
  while True:
    Phase A - 生产 (每30分钟)
      1. health check
      2. 是否缺 assets → 调用 main.py CLI 生成
      3. 写状态报告

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

风格色板来自 aicg-handbook (峰哥AICG动画创作手册):
  - Painterly 3D Noir: 油画质感·暗黑氛围·#E94560锈红
  - Hybrid Comic Pop: 漫画弹入风·高对比·#FF3366霓虹
  - Cinematic Liquid Glass: 液态玻璃·梦幻渐变·#7EB8D8冰蓝

一切自动化, 日志在 logs/vf_loop.log
"""

import os, sys, time, json, subprocess, logging, random, shutil
from datetime import datetime
from pathlib import Path

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


def phase_production():
    """每30分钟: 检查资产状态 + 记录日志"""
    total_img,total_aud=count("images"),count("audio")
    expected=sum(EPISODES.values())
    log.info(f"资产: {total_img}/{expected}图 {total_aud}/{expected}配音")
    
    if total_img>=expected and total_aud>=expected:
        log.info("全部就绪 ✅")
    else:
        missing_img=expected-total_img
        missing_aud=expected-total_aud
        log.info(f"缺 {missing_img}图 {missing_aud}配音 — 等待Agent补充")
        # 实际生产由对话中派发的Agent完成, 这里只监控

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
    """Phase B: 自动发布 — 扫描最新产出并发布到社交平台"""
    # ── Check social-auto-upload availability ──────────────────────────
    SAU = shutil.which("social-auto-upload")
    if SAU is None:
        log.info("📋 TODO: social-auto-upload 未安装 — 跳过自动发布")
        log.info("  安装: pip install social-auto-upload 或 https://github.com/xxx/social-auto-upload")
        return

    # ── Scan produced_videos/ for the latest episode mp4 ───────────────
    produced_dir = STATE / "produced_videos"
    if not produced_dir.exists():
        log.info("📋 TODO: state/produced_videos/ 不存在 — 暂无内容可发布")
        return

    videos = sorted(produced_dir.glob("E*_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        log.info("📋 state/produced_videos/ 暂无 mp4 文件 — 跳过发布")
        return

    latest = videos[0]
    latest_label = latest.with_suffix(".label.json")
    label_info = {}
    if latest_label.exists():
        try:
            label_info = json.loads(latest_label.read_text())
        except Exception as e:
            log.warning(f"无法解析标签文件 {latest_label.name}: {e}")

    ep = label_info.get("episode", latest.stem.split("_")[0])
    style = label_info.get("style", "unknown")
    log.info(f"📤 准备发布: {latest.name}  (ep={ep}, style={style})")

    # ── Publish to 小红书 (xiaohongshu) ────────────────────────────────
    title = f"AI漫剧 {ep} | {style}"
    description = (
        f"🎬 AI漫剧 {ep} — 风格: {style}\n"
        f"#AI漫剧 #{ep} #{style.replace(' ', '')}"
    )
    publish_log = []

    for platform, plat_flag in [("小红书", "xiaohongshu"), ("抖音", "douyin")]:
        try:
            cmd = [
                SAU, "upload",
                "--platform", plat_flag,
                "--title", title,
                "--description", description,
                "--file", str(latest),
            ]
            log.info(f"  → {platform}: {' '.join(cmd)}")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                publish_log.append({"platform": plat_flag, "status": "ok", "output": r.stdout.strip()})
                log.info(f"  ✓ {platform}: 发布成功")
            else:
                publish_log.append({"platform": plat_flag, "status": "failed", "error": r.stderr.strip()[:200]})
                log.warning(f"  ✗ {platform}: 发布失败 (exit={r.returncode}) — {r.stderr.strip()[:200]}")
        except Exception as e:
            publish_log.append({"platform": plat_flag, "status": "error", "error": str(e)})
            log.warning(f"  ⚠ {platform}: 调用异常 — {e}")

    # ── Write publish log ──────────────────────────────────────────────
    publish_record = {
        "timestamp": datetime.now().isoformat(),
        "video": latest.name,
        "episode": ep,
        "style": style,
        "results": publish_log,
    }
    publish_log_path = produced_dir / "publish_log.json"
    records = []
    if publish_log_path.exists():
        try:
            records = json.loads(publish_log_path.read_text())
        except Exception:
            records = []
    records.append(publish_record)
    # Keep last 50 records
    publish_log_path.write_text(json.dumps(records[-50:], ensure_ascii=False, indent=2))
    log.info(f"📝 发布日志写入: {publish_log_path}")
    log.info(f"📊 Phase B 发布结果: {sum(1 for r in publish_log if r['status']=='ok')}/{len(publish_log)} ok")

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
    for ep_code in sorted(EPISODES.keys()):
        image_dir = STATE / "demo_assets" / ep_code / "images"
        audio_dir = STATE / "demo_assets" / ep_code / "audio"
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

        # ── Determine synthesis engine: Seedance (cloud) or FFmpeg (local) ──
        seedance_available = _check_seedance_ready()
        model_type = "seedance" if seedance_available else "ffmpeg"

        log.info(f"  🎬 Synthesizing {ep_code} ({len(scenes)} scenes, {palette['name']}) → {output_name}")
        log.info(f"  🔧 Engine: {model_type}")

        report = None
        if seedance_available:
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

def main():
    log.info("="*60)
    log.info("🏭 视频工厂主循环 v2.1 启动")
    log.info(f"日志: {LOG}")
    log.info("="*60)

    cycle = 0
    last_summary = ""    # 追踪资产状态变化

    while True:
        cycle += 1
        timestamp = datetime.now()
        log.info(f"\n--- 第{cycle}轮 [{timestamp:%H:%M}] ---")

        if not http_ok("http://localhost:7861/api/health"):
            log.error("Backend DOWN, 等5分钟")
            time.sleep(300); continue
        if not http_ok("http://localhost:8188/system_stats"):
            log.error("ComfyUI DOWN, 尝试重启...")
            subprocess.run(["comfy","--workspace=/Users/eric/Documents/comfy/ComfyUI","launch","--background"],
                         capture_output=True,timeout=30)
            time.sleep(60)

        phase_production()

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
    try: main()
    except KeyboardInterrupt: log.info("停止")
    except Exception as e: log.exception(f"崩溃: {e}")
