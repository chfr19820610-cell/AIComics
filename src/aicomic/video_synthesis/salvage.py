"""废片截帧自动入库（SOP §4⑤：废片截帧自动入库 salvage/）。

坏镜头不算白烧钱：均匀抽帧入 runs/{ep}/shots/{shot}/salvage/；失败结构化不假绿。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run_ffmpeg(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, capture_output=True, text=True).returncode
    except OSError:
        return 127


def _ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def salvage_frames(
    video_path: str | Path,
    out_dir: str | Path,
    *,
    count: int = 3,
) -> dict[str, Any]:
    video = Path(video_path)
    target = Path(out_dir)
    if not video.exists():
        return {"saved": [], "error": f"not_found: {video}"}
    if count < 1:
        return {"saved": [], "error": "count must be >= 1"}
    target.mkdir(parents=True, exist_ok=True)
    pattern = str(target / "frame_%02d.png")
    cmd = [
        _ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"select=not(mod(n\\,max(1\\,floor(nb_frames/{count}))))",
        "-frames:v", str(count),
        "-q:v", "3",
        "-y", pattern,
    ]
    rc = _run_ffmpeg(cmd)
    if rc != 0:
        return {"saved": [], "error": f"ffmpeg salvage failed rc={rc}"}
    saved = sorted(target.glob("frame_*.png"))
    return {"saved": saved, "error": ""}
