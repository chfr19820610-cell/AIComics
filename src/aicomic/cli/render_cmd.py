"""CLI `render` command — 2D / 2.5D / 3D three-line render entry point.

Usage:
  aicomic render --mode 2d --episode E01
  aicomic render --mode 2.5d --episode E01 --master character.png
  aicomic render --mode 3d --episode E01 --character character.png
  aicomic render --auto --episode E01  # auto-route by shot type
  aicomic render --list                # list modes + readiness
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def handle_render(args) -> int:
    """Handle the `aicomic render` command."""
    if args.list_modes:
        return _list_modes()

    mode = args.mode or "2d"
    episode = args.episode_code

    from aicomic.render.mode_router import RenderModeRouter
    router = RenderModeRouter()

    # Check environment readiness
    blender_available = shutil.which("blender") is not None or Path(
        "/Applications/Blender.app/Contents/MacOS/Blender"
    ).exists()
    tripo_key_configured = bool(__import__("os").environ.get("TRIPO_API_KEY"))

    readiness = router.check_readiness(
        mode, blender_available=blender_available, tripo_key_configured=tripo_key_configured
    )

    if not readiness["ready"]:
        print(f"❌ Mode '{mode}' not ready:")
        for b in readiness["blockers"]:
            print(f"   ⚠️ {b}")
        print("\nInstall missing dependencies or choose a different mode.")
        return 1

    # Build render plan
    if mode == "2d":
        plan = _build_2d_plan(router, episode, args)
    elif mode == "2.5d":
        plan = _build_2_5d_plan(router, episode, args)
    elif mode == "3d":
        plan = _build_3d_plan(router, episode, args)
    else:
        print(f"❌ Unknown mode '{mode}'")
        return 1

    # Output plan as JSON
    output = args.output or Path(f"render_plan_{episode}_{mode}.json")
    output.write_text(json.dumps(plan, indent=2, ensure_ascii=False, default=str))
    print(f"✅ Render plan saved: {output}")
    print(f"   Mode: {plan['mode']}")
    print(f"   Engine: {plan['engine']}")
    print(f"   Episode: {episode}")
    if "total_frames" in plan:
        print(f"   Total frames: {plan['total_frames']}")
    if "shot_count" in plan:
        print(f"   Shots: {plan['shot_count']}")
    return 0


def _list_modes() -> int:
    """List all render modes and their readiness."""
    from aicomic.render.mode_router import RenderModeRouter, MODE_CAPABILITIES, RenderMode
    import shutil
    import os

    blender_available = shutil.which("blender") is not None or Path(
        "/Applications/Blender.app/Contents/MacOS/Blender"
    ).exists()
    tripo_key_configured = bool(os.environ.get("TRIPO_API_KEY"))

    router = RenderModeRouter()
    print("AIComics v3.0 Render Modes\n")
    for mode in RenderMode.ALL:
        caps = MODE_CAPABILITIES[mode]
        readiness = router.check_readiness(
            mode, blender_available=blender_available, tripo_key_configured=tripo_key_configured
        )
        status = "✅ ready" if readiness["ready"] else "❌ blocked"
        print(f"  {mode:>5s} | {status} | {caps['description']}")
        if not readiness["ready"]:
            for b in readiness["blockers"]:
                print(f"         ⚠️ {b}")
    print(f"\n  Blender: {'✅' if blender_available else '❌ not found'}")
    print(f"  Tripo key: {'✅ configured' if tripo_key_configured else '❌ not set'}")
    return 0


def _build_2d_plan(router, episode: str, args) -> dict[str, Any]:
    from aicomic.render.two_d.pipeline import TwoDPipeline, TwoDRenderConfig
    pipe = TwoDPipeline()
    config = TwoDRenderConfig(
        mode=args.transition_mode,
        duration=args.duration,
        fps=args.fps,
    )
    shots = []  # caller provides shots via manifest
    return pipe.build_plan(episode=episode, shots=shots, config=config)


def _build_2_5d_plan(router, episode: str, args) -> dict[str, Any]:
    from aicomic.render.two_half_d.pipeline import TwoHalfDPipeline, TwoHalfDRenderConfig
    pipe = TwoHalfDPipeline()
    config = TwoHalfDRenderConfig()
    master = args.master_image or "character_master.png"
    return pipe.build_plan(episode=episode, master_image=master, config=config)


def _build_3d_plan(router, episode: str, args) -> dict[str, Any]:
    from aicomic.render.three_d.pipeline import ThreeDPipeline, ThreeDRenderConfig
    pipe = ThreeDPipeline()
    config = ThreeDRenderConfig()
    character = args.character_image or "character.png"
    return pipe.build_plan(episode=episode, character_image=character, config=config)
