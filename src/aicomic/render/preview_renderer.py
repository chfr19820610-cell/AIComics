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


def _fit_image_to_canvas(img: "Image.Image", target_w: int, target_h: int) -> "Image.Image":
    """Resize image preserving aspect ratio, pad to target canvas with black bars."""
    orig_w, orig_h = img.size
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), "#000000")
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas


def render_preview_video(
    render_plan: dict[str, Any],
    output_path: Path,
    report_path: Path,
    width: int = 1024,
    height: int = 1024,
    fps: int = 24,
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
    with imageio.get_writer(output_path, fps=fps, codec="libx264") as writer:
        for shot in render_plan["shots"]:
            duration_frames = max(1, int(shot["duration"]) * fps)
            if shot["has_image"] is True:
                raw = Image.open(shot["image_path"]).convert("RGB")
                frame_image = _fit_image_to_canvas(raw, width, height)
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



# ---- Audio mixing (added v0.2.0) ----
import subprocess as _sp
import os as _os


def _mix_audio_into_video(video_path: str, audio_dir: str, episode_code: str, shots: list, output_path: str, ffmpeg_bin: str = "ffmpeg") -> bool:
    """Mix per-shot TTS audio into the rendered video using ffmpeg."""
    # 1. Concatenate all TTS wav files in shot order
    concat_list = _os.path.join(_os.path.dirname(output_path), f"{episode_code}_audio_concat.txt")
    with open(concat_list, "w") as f:
        for shot in shots:
            shot_id = shot.get("shot_id", "")
            wav_path = _os.path.join(audio_dir, episode_code, "audio", f"{episode_code}_{shot_id}_tts.wav")
            if not _os.path.exists(wav_path):
                # Try local_provider_output path
                wav_path = _os.path.join(audio_dir, episode_code, "audio", f"{episode_code}_{shot_id}_tts.wav")
            if _os.path.exists(wav_path):
                f.write(f"file '{wav_path}'\n")
            else:
                # Generate 1s silence placeholder
                silence_path = _os.path.join(_os.path.dirname(output_path), f"{episode_code}_{shot_id}_silence.wav")
                _sp.run([ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", str(shot.get("duration", 4)), "-q:a", "9", "-acodec", "pcm_s16le", silence_path], capture_output=True, timeout=10)
                f.write(f"file '{silence_path}'\n")

    # 2. Concat audio
    concat_wav = _os.path.join(_os.path.dirname(output_path), f"{episode_code}_audio_full.wav")
    _sp.run([ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", concat_wav], capture_output=True, timeout=30)

    # 3. Mix audio into video
    mixed_path = output_path.replace(".mp4", "_mixed.mp4")
    _sp.run([ffmpeg_bin, "-y", "-i", output_path, "-i", concat_wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", mixed_path], capture_output=True, timeout=60)

    # 4. Replace original
    if _os.path.exists(mixed_path) and _os.path.getsize(mixed_path) > _os.path.getsize(output_path):
        _os.replace(mixed_path, output_path)

    # 5. Cleanup
    for tmp in [concat_list, concat_wav]:
        if _os.path.exists(tmp):
            _os.remove(tmp)

    return True


def render_preview_video_with_audio(render_plan: dict, output_path: Path, report_path: Path, asset_root: Path = None, **kwargs) -> dict:
    """Render preview video with TTS audio mixed in."""
    report = render_preview_video(render_plan, output_path, report_path, **kwargs)

    # Find audio directory
    if asset_root is None:
        asset_root = Path("state/local_provider_output")

    audio_base = str(asset_root) if asset_root else "state/local_provider_output"
    # Also check demo_assets
    demo_base = str(asset_root).replace("local_provider_output", "demo_assets") if "local_provider_output" in str(asset_root) else audio_base

    ffmpeg_bin = "/Users/eric/.hermes/bin/ffmpeg"
    if not _os.path.exists(ffmpeg_bin):
        import shutil as _sh
        ffmpeg_bin = _sh.which("ffmpeg") or "ffmpeg"

    try:
        _mix_audio_into_video(str(output_path), audio_base, render_plan["episode_code"], render_plan["shots"], str(output_path), ffmpeg_bin)
        report["audio_mixed"] = True
    except Exception as e:
        report["audio_mixed"] = False
        report["audio_error"] = str(e)

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
