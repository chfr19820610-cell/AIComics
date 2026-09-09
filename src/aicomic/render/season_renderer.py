from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.render.preview_renderer import build_render_plan, render_preview_video
from aicomic.render.release_renderer import build_release_plan, render_release_video
from aicomic.render.mode_router import RenderModeRouter
from aicomic.render.two_d.pipeline import TwoDPipeline, TwoDRenderConfig
from aicomic.render.two_half_d.pipeline import TwoHalfDPipeline
from aicomic.render.three_d.pipeline import ThreeDPipeline


def _build_mode_render_plan(
    render_mode: str,
    episode_code: str,
    episode_manifest: dict[str, Any],
    asset_root: Path,
) -> dict[str, Any]:
    """Build a render plan for 2d/2.5d/3d modes using the mode-router pipelines."""
    router = RenderModeRouter()
    episode_lookup = {item["episode_code"]: item for item in episode_manifest.get("episodes", [])}
    episode = episode_lookup.get(episode_code, {})

    # Collect shots from episode manifest
    shots_data = []
    for shot in episode.get("shots", []):
        image_name = None
        if shot.get("image_path"):
            image_name = str(Path(shot["image_path"]).name)
        elif shot.get("shot_id"):
            image_name = f"{episode_code}_{shot['shot_id']}_key.png"
        shots_data.append({
            "shot_id": shot.get("shot_id", ""),
            "image_name": image_name,
            "audio_name": shot.get("audio_name"),
            "duration": shot.get("duration", 3),
            "dialogue": shot.get("dialogue", ""),
        })

    if render_mode == "2d":
        pipeline = TwoDPipeline()
        return pipeline.build_plan(episode_code, shots_data)
    elif render_mode == "2.5d":
        pipeline = TwoHalfDPipeline()
        master_image = str(asset_root / episode_code / "images" / f"{episode_code}_master_sheet.png")
        return pipeline.build_plan(episode_code, master_image)
    elif render_mode == "3d":
        pipeline = ThreeDPipeline()
        character_image = str(asset_root / episode_code / "images" / f"{episode_code}_hero.png")
        return pipeline.build_plan(episode_code, character_image)
    else:
        raise ValueError(f"Unknown render_mode: {render_mode}")


def render_season(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
    asset_root: Path,
    output_dir: Path,
    report_path: Path,
    mode: str = "preview",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    episode_lookup = {item["episode_code"]: item for item in episode_manifest.get("episodes", [])}
    episode_results = []
    for episode in season_manifest.get("episodes", []):
        episode_code = episode["episode_code"]
        if mode == "release":
            plan = build_release_plan(episode_manifest, episode_code, asset_root)
            output_path = output_dir / f"{episode_code}_release.mp4"
            episode_report_path = report_path.parent / f"{episode_code}_season_release.json"
            render_report = render_release_video(plan, output_path, episode_report_path)
        elif mode in ("2d", "2.5d", "3d"):
            # v3.0 three-line render: build plan via mode-router pipelines
            mode_plan = _build_mode_render_plan(mode, episode_code, episode_manifest, asset_root)
            output_path = output_dir / f"{episode_code}_{mode}.json"
            episode_report_path = report_path.parent / f"{episode_code}_season_{mode}.json"
            # 2d falls back to preview renderer (ffmpeg Ken Burns = same engine)
            if mode == "2d":
                plan = build_render_plan(episode_manifest, episode_code, asset_root)
                video_path = output_dir / f"{episode_code}_{mode}.mp4"
                render_report = render_preview_video(plan, video_path, episode_report_path)
                render_report["mode_plan"] = mode_plan
            else:
                # 2.5d/3d require external engines (Blender/Tripo) — emit plan only
                render_report = {
                    "episode_code": episode_code,
                    "render_mode": mode,
                    "plan": mode_plan,
                    "output_path": str(output_path),
                    "status": "plan_ready",
                    "requires_blender": mode_plan.get("requires_blender", False),
                    "requires_tripo": mode_plan.get("requires_tripo", False),
                }
                output_path.write_text(json.dumps(mode_plan, ensure_ascii=False, indent=2), encoding="utf-8")
                episode_report_path.write_text(json.dumps(render_report, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            plan = build_render_plan(episode_manifest, episode_code, asset_root)
            output_path = output_dir / f"{episode_code}_preview.mp4"
            episode_report_path = report_path.parent / f"{episode_code}_season_preview.json"
            render_report = render_preview_video(plan, output_path, episode_report_path)
        episode_results.append(
            {
                "episode_code": episode_code,
                "title": episode_lookup[episode_code]["title"],
                "output_path": str(output_path),
                "report_path": str(episode_report_path),
                "render_mode": render_report.get("render_mode", mode),
            }
        )

    payload = {
        "project_id": season_manifest["project_id"],
        "season": season_manifest["season"],
        "mode": mode,
        "episode_count": len(episode_results),
        "episode_results": episode_results,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

