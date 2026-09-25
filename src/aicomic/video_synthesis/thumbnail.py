"""Video thumbnail extractor — extract key frames from MP4 for web preview.

Uses FFmpeg to extract frames at specified timestamps.  Generates a
thumbnail grid image for quick visual scanning.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def extract_key_frames(
    video_path: Path | str,
    output_dir: Path | str,
    num_frames: int = 4,
    quality: int = 2,
) -> list[str]:
    """Extract key frames from a video file.

    Extracts ``num_frames`` evenly-spaced frames as JPEG images.

    Args:
        video_path: Path to the source video.
        output_dir: Directory to write thumbnails.
        num_frames: Number of frames to extract (default 4).
        quality: JPEG quality (1=best, 31=worst).

    Returns:
        List of thumbnail file paths.
    """
    if not shutil.which("ffmpeg"):
        return []

    path = Path(video_path)
    if not path.exists():
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Get duration first
    duration = _get_duration(path)
    if duration <= 0:
        return []

    timestamps = [
        duration * (i + 1) / (num_frames + 1)
        for i in range(num_frames)
    ]

    results: list[str] = []
    for i, ts in enumerate(timestamps):
        thumb_path = out / f"{path.stem}_thumb_{i+1:02d}.jpg"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss", f"{ts:.2f}",
                    "-i", str(path),
                    "-frames:v", "1",
                    "-q:v", str(quality),
                    str(thumb_path),
                ],
                capture_output=True,
                timeout=15,
            )
            if thumb_path.exists():
                results.append(str(thumb_path))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return results


def _get_duration(video_path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return 0.0


def build_thumbnail_grid(
    thumbnail_paths: list[str],
    output_path: Path | str,
    columns: int = 2,
    cell_width: int = 320,
) -> str | None:
    """Build a grid image from thumbnail paths.

    Uses Pillow if available; falls back to returning None.

    Args:
        thumbnail_paths: List of thumbnail image paths.
        output_path: Output grid image path.
        columns: Number of columns in the grid.
        cell_width: Width of each cell in pixels.

    Returns:
        Path to the grid image, or None if Pillow is unavailable.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    if not thumbnail_paths:
        return None

    # Load images
    images: list[Image.Image] = []
    for p in thumbnail_paths:
        try:
            img = Image.open(p)
            ratio = cell_width / img.width
            img = img.resize((cell_width, int(img.height * ratio)))
            images.append(img)
        except Exception:
            continue

    if not images:
        return None

    # Calculate grid dimensions
    rows = (len(images) + columns - 1) // columns
    cell_height = max(img.height for img in images)
    grid = Image.new("RGB", (columns * cell_width, rows * cell_height), (20, 20, 20))

    for i, img in enumerate(images):
        x = (i % columns) * cell_width
        y = (i // columns) * cell_height
        grid.paste(img, (x, y))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.save(str(out), quality=85)
    return str(out)
