from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.qc.asset_scanner import scan_episode_assets


def scan_season_assets(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
    asset_root: Path,
) -> dict[str, Any]:
    episode_codes = [item["episode_code"] for item in season_manifest.get("episodes", [])]
    episode_reports = [scan_episode_assets(episode_manifest, episode_code, asset_root) for episode_code in episode_codes]
    return {
        "project_id": season_manifest["project_id"],
        "season": season_manifest["season"],
        "episode_count": len(episode_reports),
        "ready_episode_count": sum(1 for item in episode_reports if item["ready_for_preview"] is True),
        "missing_required_total": sum(int(item["missing_required_count"]) for item in episode_reports),
        "episode_reports": episode_reports,
    }


def write_season_scan_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

