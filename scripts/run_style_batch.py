#!/usr/bin/env python3
"""
Batch video synthesis for AIComics — runs phase_self_produce for
the current style (Hybrid Comic Pop), then Cinematic Liquid Glass.
"""
import sys, os, json, time, logging
from pathlib import Path

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "src"))
os.chdir(str(BASE))
os.environ["PYTHONPATH"] = str(BASE / "src")

from vf_master_loop import (
    phase_self_produce,
    STYLE_PALETTES,
    _get_style_cycle,
    _save_style_cycle,
    count,
    EPISODES,
    LOG,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE / "logs" / "style_batch.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("style_batch")

def check_assets():
    total_img = count("images")
    total_aud = count("audio")
    expected = sum(EPISODES.values())
    log.info(f"📊 Assets: {total_img}/{expected} images, {total_aud}/{expected} audio")
    return total_img >= expected and total_aud >= expected

def run_one_round(label: str):
    """Run one round of Phase D video synthesis."""
    idx = _get_style_cycle()
    palette = STYLE_PALETTES[idx % len(STYLE_PALETTES)]
    log.info(f"=" * 60)
    log.info(f"🎬 Starting synthesis: {label}")
    log.info(f"   Style index: {idx} → {palette['name']}")
    log.info(f"   Palette: {', '.join(palette['colors'])}")
    log.info(f"=" * 60)

    if not check_assets():
        log.error("❌ Assets not ready — aborting")
        return False

    result = phase_self_produce()
    if result:
        log.info(f"✅ {label} — synthesis completed successfully")
    else:
        log.warning(f"⚠️  {label} — phase_self_produce returned {result}")

    # Wait for any async file operations
    time.sleep(2)

    # Show what got produced
    produced_dir = BASE / "state" / "produced_videos"
    round_jsons = sorted(produced_dir.glob(f"round_{palette['slug']}_*.json"))
    if round_jsons:
        latest = round_jsons[-1]
        data = json.loads(latest.read_text())
        ok = data.get("ok_count", 0)
        failed = data.get("failed_count", 0)
        log.info(f"📝 Round report: {latest.name} — {ok} ok, {failed} failed")
    else:
        log.warning(f"⚠️  No round_{palette['slug']}_*.json found in produced_videos/")

    return True


if __name__ == "__main__":
    # ── Round 1: Hybrid Comic Pop (current style index = 1) ──
    idx0 = _get_style_cycle()
    log.info(f"Initial style_cycle index: {idx0} → {STYLE_PALETTES[idx0 % len(STYLE_PALETTES)]['name']}")

    ok1 = run_one_round("Hybrid Comic Pop")

    # Check what the cycle advanced to
    idx1 = _get_style_cycle()
    log.info(f"After round 1, style_cycle index: {idx1} → {STYLE_PALETTES[idx1 % len(STYLE_PALETTES)]['name']}")

    # ── Round 2: Cinematic Liquid Glass ──
    if idx1 == 2:
        log.info("Style cycle already advanced to Cinematic Liquid Glass — proceeding with round 2")
        ok2 = run_one_round("Cinematic Liquid Glass")
    else:
        log.warning(f"⚠️  Style cycle not at index 2 (Cinematic Liquid Glass), is at {idx1}")
        log.info("Forcing style_cycle to Cinematic Liquid Glass (index=2)...")
        _save_style_cycle(2, "Cinematic Liquid Glass")
        ok2 = run_one_round("Cinematic Liquid Glass")

    # ── Verify final state ──
    idx_final = _get_style_cycle()
    log.info(f"\n{'=' * 60}")
    log.info(f"🏁 Final style_cycle index: {idx_final} → {STYLE_PALETTES[idx_final % len(STYLE_PALETTES)]['name']}")
    log.info(f"{'=' * 60}")

    produced_dir = BASE / "state" / "produced_videos"
    mp4s = sorted(produced_dir.glob("*.mp4"))
    log.info(f"\n📁 Videos in produced_videos/ ({len(mp4s)} total):")
    for mp4 in mp4s:
        size_mb = mp4.stat().st_size / (1024 * 1024)
        log.info(f"   {mp4.name}  ({size_mb:.1f} MB)")

    round_jsons = sorted(produced_dir.glob("round_*.json"))
    log.info(f"\n📝 Round logs ({len(round_jsons)} total):")
    for rj in round_jsons:
        log.info(f"   {rj.name}")

    sys.exit(0 if ok1 and ok2 else 1)
