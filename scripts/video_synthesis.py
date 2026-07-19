#!/usr/bin/env python3
"""
Video Synthesis Pipeline — Runner Entrypoint.

Usage:
    python scripts/video_synthesis.py                         # Batch all episodes
    python scripts/video_synthesis.py E01                     # Single episode
    python scripts/video_synthesis.py E01 E03 E05             # Multiple episodes
    python scripts/video_synthesis.py --list                  # List available episodes
    python scripts/video_synthesis.py --format srt            # Use SRT subtitles
"""

import sys
from pathlib import Path

# Ensure src/ is on the path
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from aicomic.video_synthesis import batch_synthesize, discover_episodes
from aicomic.video_synthesis.pipeline import log


def main():
    args = sys.argv[1:]

    # ── --list flag ──
    if "--list" in args:
        log("Discovering episodes ...")
        episodes = discover_episodes()
        for ep in episodes:
            n_scenes = len(ep["scenes"])
            status = "✓ ready" if ep["all_assets_present"] else "⚠ partial"
            log(f"  {ep['episode_code']}: {n_scenes} scenes {status}")
        return

    # ── Subtitle format ──
    subtitle_format = "ass"
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            subtitle_format = args[idx + 1]
            args = args[:idx] + args[idx + 2:]  # remove --format and its value

    # ── Episode codes ──
    episode_codes = [a for a in args if not a.startswith("--")]

    if not episode_codes:
        log("Batch: processing all available episodes ...")
        reports = batch_synthesize(subtitle_format=subtitle_format)
    else:
        log(f"Processing: {', '.join(episode_codes)}")
        reports = batch_synthesize(
            episode_codes=episode_codes,
            stop_on_failure=False,
            subtitle_format=subtitle_format,
        )

    # ── Exit code ──
    failed = sum(1 for r in reports if not r or r.get("status") != "ok")
    if failed > 0:
        log(f"\n⚠ {failed} episode(s) failed")
        sys.exit(1)
    else:
        log(f"\n✓ All {len(reports)} episodes synthesized successfully")


if __name__ == "__main__":
    main()
