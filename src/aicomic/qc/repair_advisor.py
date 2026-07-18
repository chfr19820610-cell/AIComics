from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_repair_suggestions(asset_scan_report: dict[str, Any]) -> dict[str, Any]:
    suggestions = []
    for item in asset_scan_report.get("missing_required", []):
        suggestions.append(
            {
                "severity": "high",
                "shot_id": item["shot_id"],
                "asset_type": item["asset_type"],
                "missing_path": item["path"],
                "action": "补齐必需关键帧素材后重新运行 scan-assets",
            }
        )
    for item in asset_scan_report.get("missing_optional", []):
        action = "可跳过"
        if item["asset_type"] == "video":
            action = "可补 AI 视频增强动感，或继续使用静态关键帧"
        if item["asset_type"] == "audio":
            action = "可补 TTS 音频，或使用占位音轨"
        suggestions.append(
            {
                "severity": "medium",
                "shot_id": item["shot_id"],
                "asset_type": item["asset_type"],
                "missing_path": item["path"],
                "action": action,
            }
        )
    return {
        "episode_code": asset_scan_report["episode_code"],
        "ready_for_preview": asset_scan_report["ready_for_preview"],
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
    }


def write_repair_suggestions(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

