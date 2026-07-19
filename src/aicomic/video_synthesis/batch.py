"""
Batch synthesis — orchestrate video synthesis across multiple episodes.
"""

import json
import sys
from pathlib import Path

from aicomic.video_synthesis.config import (
    ASSET_SOURCE,
    EPISODE_SUBTITLES,
    OUTPUT_DIR,
    SYSTEM_ROOT,
)
from aicomic.video_synthesis.pipeline import log, synthesize_episode


# ── Episode discovery ─────────────────────────────────────────────────────

def discover_episodes(
    asset_sources: dict[str, Path] | None = None,
    subtitle_map: dict[str, list[str]] | None = None,
) -> list[dict]:
    """
    Discover available episodes by probing for images and audio files.

    Returns a list of episode config dicts, each containing:
        episode_code: str
        image_dir: Path
        audio_dir: Path
        scenes: list[dict]

    Only returns episodes where all expected assets exist.
    """
    if asset_sources is None:
        asset_sources = ASSET_SOURCE
    if subtitle_map is None:
        subtitle_map = EPISODE_SUBTITLES

    episodes = []

    for ep_code, source_dir in sorted(asset_sources.items()):
        # Probe asset directories
        if source_dir == SYSTEM_ROOT / "state" / "local_provider_output":
            image_dir = source_dir / ep_code / "images"
            audio_dir = source_dir / ep_code / "audio"
        else:
            image_dir = source_dir / ep_code / "images"
            audio_dir = source_dir / ep_code / "audio"

        subtitles = subtitle_map.get(ep_code, [])
        scene_count = max(len(subtitles), 6)  # at least 6 scenes

        scenes = []
        all_present = True
        for i in range(1, scene_count + 1):
            scene_num = i
            image_name = f"{ep_code}_S{scene_num:02d}_key.png"
            audio_name = f"{ep_code}_S{scene_num:02d}_tts.wav"

            img_path = image_dir / image_name
            aud_path = audio_dir / audio_name

            sub_text = subtitles[i - 1] if i - 1 < len(subtitles) else ""

            if not img_path.exists() and not aud_path.exists():
                if i > 6:
                    break  # don't extend past 6 if no assets
                continue

            scenes.append({
                "num": scene_num,
                "image_name": image_name,
                "audio_name": audio_name,
                "subtitle": sub_text,
                "duration": None,  # auto from audio
            })

            if not img_path.exists():
                log(f"  ⚠ {ep_code}: missing {image_name}")
                all_present = False
            if not aud_path.exists():
                log(f"  ⚠ {ep_code}: missing {audio_name}")
                all_present = False

        if not scenes:
            log(f"  ✗ {ep_code}: no scenes found, skipping")
            continue

        episodes.append({
            "episode_code": ep_code,
            "image_dir": image_dir,
            "audio_dir": audio_dir,
            "scenes": scenes,
            "all_assets_present": all_present,
        })

    return episodes


# ── Batch synthesis ───────────────────────────────────────────────────────

def batch_synthesize(
    episode_codes: list[str] | None = None,
    asset_sources: dict[str, Path] | None = None,
    subtitle_map: dict[str, list[str]] | None = None,
    stop_on_failure: bool = True,
    subtitle_format: str = "ass",
) -> list[dict]:
    """
    Synthesize multiple episodes in batch.

    Args:
        episode_codes: Specific episodes to synthesize (e.g. ["E01", "E02"]).
                       If None, discover and process all available.
        asset_sources: Asset source directory map (default from config).
        subtitle_map: Subtitle text map (default from config).
        stop_on_failure: If True, stop batch on first failure.
        subtitle_format: "ass" or "srt".

    Returns:
        List of report dicts for each processed episode.
    """
    if asset_sources is None:
        asset_sources = ASSET_SOURCE
    if subtitle_map is None:
        subtitle_map = EPISODE_SUBTITLES

    # Discover or filter episodes
    all_episodes = discover_episodes(asset_sources, subtitle_map)

    if episode_codes:
        episodes = [ep for ep in all_episodes if ep["episode_code"] in episode_codes]
        # Also check for requested codes not discovered
        found_codes = {ep["episode_code"] for ep in episodes}
        for code in episode_codes:
            if code not in found_codes and code in asset_sources:
                log(f"  ⚠ {code}: discovered with incomplete assets, still processing")
                episodes.append({
                    "episode_code": code,
                    "image_dir": asset_sources[code] / code / "images",
                    "audio_dir": asset_sources[code] / code / "audio",
                    "scenes": _build_scenes_for(code, subtitle_map.get(code, [])),
                    "all_assets_present": False,
                })
    else:
        episodes = all_episodes

    if not episodes:
        log("✗ No episodes to synthesize")
        return []

    log(f"\n{'='*60}")
    log(f"Batch Video Synthesis — {len(episodes)} episodes")
    log(f"{'='*60}")

    reports = []
    for ep in episodes:
        ep_code = ep["episode_code"]
        output_path = OUTPUT_DIR / f"{ep_code}_full.mp4"
        log(f"\n{'─'*60}")

        report = synthesize_episode(
            episode_code=ep_code,
            scenes=ep["scenes"],
            image_dir=ep["image_dir"],
            audio_dir=ep["audio_dir"],
            output_path=output_path,
            subtitle_format=subtitle_format,
        )

        if report is None:
            log(f"✗ {ep_code}: synthesis failed")
            if stop_on_failure:
                log("  Batch stopped (stop_on_failure=True)")
                break
            reports.append({"episode_code": ep_code, "status": "failed"})
        else:
            reports.append(report)

    # Summary
    ok = sum(1 for r in reports if r and r.get("status") == "ok")
    failed = sum(1 for r in reports if not r or r.get("status") != "ok")
    log(f"\n{'='*60}")
    log(f"Batch Complete: {ok} ok, {failed} failed ({len(reports)} total)")
    log(f"{'='*60}")

    return reports


def _build_scenes_for(ep_code: str, subtitles: list[str]) -> list[dict]:
    """Build scene list for an episode code."""
    scene_count = max(len(subtitles), 6)
    scenes = []
    for i in range(1, scene_count + 1):
        sub_text = subtitles[i - 1] if i - 1 < len(subtitles) else ""
        scenes.append({
            "num": i,
            "image_name": f"{ep_code}_S{i:02d}_key.png",
            "audio_name": f"{ep_code}_S{i:02d}_tts.wav",
            "subtitle": sub_text,
            "duration": None,
        })
    return scenes
