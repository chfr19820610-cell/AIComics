from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_expected_assets(episode: dict[str, Any], asset_root: Path) -> list[dict[str, Any]]:
    episode_code = str(episode["episode_code"])
    expected_assets: list[dict[str, Any]] = []
    for shot in episode.get("shots", []):
        shot_id = str(shot["shot_id"])
        expected_assets.append(
            {
                "shot_id": shot_id,
                "asset_type": "image",
                "required": True,
                "path": str(asset_root / episode_code / "images" / f"{episode_code}_{shot_id}_key.png"),
            }
        )
        if shot.get("ai_video") is True:
            expected_assets.append(
                {
                    "shot_id": shot_id,
                    "asset_type": "video",
                    "required": False,
                    "path": str(asset_root / episode_code / "videos" / f"{episode_code}_{shot_id}_motion.mp4"),
                }
            )
        dialogue = str(shot.get("dialogue", "")).strip()
        if dialogue:
            expected_assets.append(
                {
                    "shot_id": shot_id,
                    "asset_type": "audio",
                    "required": False,
                    "path": str(asset_root / episode_code / "audio" / f"{episode_code}_{shot_id}_tts.wav"),
                }
            )
    return expected_assets


def scan_episode_assets(manifest: dict[str, Any], episode_code: str, asset_root: Path) -> dict[str, Any]:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    expected_assets = build_expected_assets(episode, asset_root)

    missing_required: list[dict[str, Any]] = []
    missing_optional: list[dict[str, Any]] = []
    existing_assets: list[dict[str, Any]] = []

    for item in expected_assets:
        asset_path = Path(str(item["path"]))
        record = {
            "shot_id": item["shot_id"],
            "asset_type": item["asset_type"],
            "required": item["required"],
            "path": str(asset_path),
            "exists": asset_path.exists(),
        }
        if asset_path.exists():
            existing_assets.append(record)
        elif item["required"] is True:
            missing_required.append(record)
        else:
            missing_optional.append(record)

    report = {
        "episode_code": episode_code,
        "asset_root": str(asset_root),
        "expected_count": len(expected_assets),
        "existing_count": len(existing_assets),
        "missing_required_count": len(missing_required),
        "missing_optional_count": len(missing_optional),
        "ready_for_preview": len(missing_required) == 0,
        "expected_assets": expected_assets,
        "existing_assets": existing_assets,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }
    return report


def write_asset_scan_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

