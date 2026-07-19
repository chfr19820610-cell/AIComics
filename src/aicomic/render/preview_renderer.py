from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    imageio = None
    np = None
    Image = None
    ImageDraw = None


def build_render_plan(manifest: dict[str, Any], episode_code: str, asset_root: Path) -> dict[str, Any]:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    shots = []
    for shot in episode.get("shots", []):
        shot_id = str(shot["shot_id"])
        image_path = asset_root / episode_code / "images" / f"{episode_code}_{shot_id}_key.png"
        shots.append(
            {
                "shot_id": shot_id,
                "duration": int(shot["duration"]),
                "title": str(episode["title"]),
                "visual": str(shot["visual"]),
                "dialogue": str(shot.get("dialogue", "")),
                "image_path": str(image_path),
                "has_image": image_path.exists(),
            }
        )
    return {
        "episode_code": episode_code,
        "title": episode["title"],
        "shot_count": len(shots),
        "shots": shots,
    }


def create_placeholder_frame(width: int, height: int, shot_id: str, visual: str) -> "Image.Image":
    canvas = Image.new("RGB", (width, height), "#141414")
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 80), f"Preview Placeholder - {shot_id}", fill="#ffffff")
    draw.text((40, 180), visual[:80], fill="#d0d0d0")
    return canvas


def render_preview_video(
    render_plan: dict[str, Any],
    output_path: Path,
    report_path: Path,
    width: int = 720,
    height: int = 1280,
    fps: int = 6,
) -> dict[str, Any]:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if imageio is None or np is None or Image is None:
        fallback_report = {
            "episode_code": render_plan["episode_code"],
            "render_mode": "report_only",
            "output_path": str(output_path),
            "reason": "imageio_or_pillow_unavailable",
        }
        report_path.write_text(json.dumps(fallback_report, ensure_ascii=False, indent=2), encoding="utf-8")
        return fallback_report

    total_frames = 0
    with imageio.get_writer(output_path, fps=fps) as writer:
        for shot in render_plan["shots"]:
            duration_frames = max(1, int(shot["duration"]) * fps)
            if shot["has_image"] is True:
                frame_image = Image.open(shot["image_path"]).convert("RGB").resize((width, height))
            else:
                frame_image = create_placeholder_frame(width, height, shot["shot_id"], shot["visual"])

            frame_array = np.array(frame_image)
            for _ in range(duration_frames):
                writer.append_data(frame_array)
            total_frames += duration_frames

    report = {
        "episode_code": render_plan["episode_code"],
        "render_mode": "mp4",
        "output_path": str(output_path),
        "report_path": str(report_path),
        "shot_count": render_plan["shot_count"],
        "total_frames": total_frames,
        "fps": fps,
        "used_placeholder_count": sum(1 for shot in render_plan["shots"] if shot["has_image"] is False),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

