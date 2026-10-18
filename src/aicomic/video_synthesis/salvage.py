"""废片截帧自动入库（SOP §4⑤：废片截帧自动入库 salvage/）。

坏镜头不算白烧钱：均匀抽帧入 runs/{ep}/shots/{shot}/salvage/；失败结构化不假绿。
fps 抽帧（select/nb_frames 表达式在部分容器上不可靠——真机 rc=234 教训）。
"""
from __future__ import annotations

import json
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


def _probe_duration(video: Path) -> float | None:
    """复用 quality_check._probe_streams 底座（含 ffprobe banner 兜底）；拿不到 → None（不假绿）。"""
    try:
        from aicomic.video_synthesis.quality_check import _probe_streams

        rc, stdout = _probe_streams(video)
        if rc != 0 or not stdout.strip():
            return None
        streams = json.loads(stdout).get("streams", [])
        vs = next((s for s in streams if s.get("codec_type") == "video"), None)
        if vs is None:
            return None
        return float(vs.get("duration") or 0.0) or None
    except Exception:
        return None


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
    duration = _probe_duration(video)
    if duration is None or duration <= 0:
        return {"saved": [], "error": "probe_unavailable: 时长探针不可得，抽帧中止（不假绿）"}
    fps = count / duration
    target.mkdir(parents=True, exist_ok=True)
    pattern = str(target / "frame_%02d.png")
    cmd = [
        _ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"fps={fps:.6f}",
        "-frames:v", str(count),
        "-q:v", "3",
        "-y", pattern,
    ]
    rc = _run_ffmpeg(cmd)
    if rc != 0:
        return {"saved": [], "error": f"ffmpeg salvage failed rc={rc}"}
    saved = [p for p in sorted(target.glob("frame_*.png")) if p.is_file()]
    return {"saved": saved, "error": ""}
