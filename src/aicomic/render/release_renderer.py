from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aicomic.render.preview_renderer import build_render_plan, render_preview_video
from aicomic.video_synthesis.ai_label import embed_ai_label


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
        width=1024,
        height=1024,
        fps=24,
    )
    report["render_profile"] = "release"
    # SOP §10 #7：正式版发布前必须带 AI 标签；env AICOMIC_AI_LABEL=0 可显式关闭（测试/特殊渠道）。
    label_info: dict[str, str]
    if str(os.environ.get("AICOMIC_AI_LABEL", "1")).strip() == "0":
        label_info = {"status": "skipped"}
    elif Path(str(report.get("video", output_path))).exists():
        try:
            embed_ai_label(output_path)
            label_info = {"status": "ok"}
        except Exception as exc:
            label_info = {"status": "error", "message": str(exc)}
    else:
        label_info = {"status": "skipped"}
    report["ai_label"] = label_info
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

