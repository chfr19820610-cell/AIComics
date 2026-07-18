from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_season_summary(
    season_manifest: dict[str, Any],
    season_jobs: dict[str, Any],
    season_scan: dict[str, Any],
    season_render: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project_id": season_manifest["project_id"],
        "season": season_manifest["season"],
        "season_title": season_manifest["season_title"],
        "episode_count": len(season_manifest.get("episodes", [])),
        "job_count": season_jobs.get("job_count", 0),
        "ready_episode_count": season_scan.get("ready_episode_count", 0),
        "missing_required_total": season_scan.get("missing_required_total", 0),
        "render_mode": season_render.get("mode"),
        "rendered_episode_count": season_render.get("episode_count", 0),
    }


def write_season_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

