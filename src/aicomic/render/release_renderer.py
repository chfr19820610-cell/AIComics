from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.render.preview_renderer import build_render_plan, render_preview_video


def build_release_plan(manifest: dict[str, Any], episode_code: str, asset_root: Path) -> dict[str, Any]:
    plan = build_render_plan(manifest, episode_code, asset_root)
    plan["render_profile"] = "release"
    return plan


def render_release_video(
    release_plan: dict[str, Any],
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    report = render_preview_video(
        release_plan,
        output_path,
        report_path,
        width=720,
        height=1280,
        fps=8,
    )
    report["render_profile"] = "release"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

