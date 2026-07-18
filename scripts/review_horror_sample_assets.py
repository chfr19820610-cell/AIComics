from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def inspect_image(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    return {
        "path": str(path),
        "exists": True,
        "bytes": file_size(path),
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height else 0,
        "format_valid": width > 0 and height > 0 and file_size(path) > 10_000,
    }


def inspect_audio(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        frame_rate = audio.getframerate()
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
    duration_seconds = frames / frame_rate if frame_rate else 0
    return {
        "path": str(path),
        "exists": True,
        "bytes": file_size(path),
        "duration_seconds": round(duration_seconds, 2),
        "frame_rate": frame_rate,
        "channels": channels,
        "sample_width": sample_width,
        "format_valid": duration_seconds > 0 and channels > 0 and file_size(path) > 1_000,
    }


def inspect_binary_video(path: Path) -> dict[str, Any]:
    header = path.read_bytes()[:16]
    return {
        "path": str(path),
        "exists": True,
        "bytes": file_size(path),
        "looks_like_mp4": b"ftyp" in header,
        "format_valid": b"ftyp" in header and file_size(path) > 1_000,
    }


def build_review(project_id: str, episode_code: str = "E01") -> dict[str, Any]:
    project_root = PROJECT_ROOT / "state" / "generated_projects" / project_id
    asset_root = project_root / "state" / "demo_assets" / episode_code
    images = [inspect_image(path) for path in sorted((asset_root / "images").glob("*.png"))]
    audio = [inspect_audio(path) for path in sorted((asset_root / "audio").glob("*.wav"))]
    videos = [inspect_binary_video(path) for path in sorted((asset_root / "videos").glob("*.mp4"))]
    manual_findings = [
        {
            "severity": "review_required",
            "category": "visual_text",
            "detail": "S01-S08 were regenerated after the horror visual prompt fix. Inspect the latest contact sheet before scaling live batches beyond the current staged limit.",
        }
    ]
    return {
        "project_id": project_id,
        "episode_code": episode_code,
        "asset_root": str(asset_root),
        "counts": {
            "image_count": len(images),
            "audio_count": len(audio),
            "video_count": len(videos),
            "valid_image_count": sum(1 for item in images if item["format_valid"]),
            "valid_audio_count": sum(1 for item in audio if item["format_valid"]),
            "valid_video_count": sum(1 for item in videos if item["format_valid"]),
        },
        "images": images,
        "audio": audio,
        "videos": videos,
        "manual_findings": manual_findings,
        "recommendations": [
            "Use the latest contact sheet as the visual gate before raising AICOMIC_HORROR_LIVE_LIMIT.",
            "Keep live batches at limit 6-10 while ComfyUI is running in CPU mode.",
            "Move to limit 20 only after the first 8-shot visual style is accepted.",
        ],
    }


def main() -> int:
    state_file = PROJECT_ROOT / "state" / "horror_real_sample_project_id.txt"
    project_id = state_file.read_text(encoding="utf-8").strip()
    report = build_review(project_id)
    output_path = PROJECT_ROOT / "state" / "generated_projects" / project_id / "reports" / "horror_asset_quality_review_E01.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"project_id={project_id}")
    print(f"image_count={report['counts']['image_count']}")
    print(f"audio_count={report['counts']['audio_count']}")
    print(f"video_count={report['counts']['video_count']}")
    print(f"blocking_findings={sum(1 for item in report['manual_findings'] if item['severity'] == 'blocking')}")
    print(f"review_required_findings={sum(1 for item in report['manual_findings'] if item['severity'] == 'review_required')}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
