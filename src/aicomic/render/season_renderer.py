from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.render.preview_renderer import build_render_plan, render_preview_video
from aicomic.render.release_renderer import build_release_plan, render_release_video


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

