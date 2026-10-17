"""规则层质检（SOP §8.1 规则层：黑帧/时长/分辨率/可读性）。

- ffprobe stdout json 拿 streams；ffprobe 不可用 → ffmetadata 探针兜底不可行（拿不到 streams），
  直接报 probe_unavailable 结构化 issue，不静默假绿；
- 黑帧用 ffmpeg blackdetect stderr 解析（video:0 s / 占比>阈值 → black_frames_excess）；
  不可用 → blackdetect_unavailable 单列 issue（检查缺失可见）；
- 与 ai_label 同族：_run_probe/_run_ffmpeg seam 可 monkeypatch。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

BLACK_FRACTION_MAX = 0.20
MIN_DURATION_FALLBACK = 2.5


def _run_probe(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout
    except OSError:
        return 127, ""


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


def _ffprobe_bin() -> str:
    try:
        candidate = Path(_ffmpeg_bin()).with_name("ffprobe")
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return "ffprobe"


def _probe_streams(video: Path) -> tuple[int, str]:
    rc, stdout = _run_probe([_ffprobe_bin(), "-v", "quiet", "-show_streams", "-of", "json", str(video)])
    if rc == 0 and stdout.strip():
        return 0, stdout
    # ffprobe 不可用 / 坏架构 → ffmpeg banner 兜底（Duration + Video 行），不静默假绿
    return _run_ffmpeg_banner(video)


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")
_VIDEO_RE = re.compile(r"Stream #\d+:\d+.*: Video:.*?(\d{2,5})x(\d{2,5})")


def _run_ffmpeg_banner(video: Path) -> tuple[int, str]:
    """ffmpeg -i 输出 stderr banner；规整为与 ffprobe 同形 json streams。"""
    try:
        proc = subprocess.run([_ffmpeg_bin(), "-hide_banner", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
        banner = str(proc.stderr)
    except OSError:
        return 127, ""
    if proc.returncode != 0:
        return proc.returncode, banner
    duration = 0.0
    m = _DURATION_RE.search(banner)
    if m:
        duration = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 100
    width = height = 0
    m = _VIDEO_RE.search(banner)
    if m:
        width, height = int(m[1]), int(m[2])
    streams = [{"codec_type": "video", "width": width, "height": height, "duration": str(round(duration, 2))}]
    return 0, json.dumps({"streams": streams})


def _issues_add(issues: list[dict[str, Any]], code: str, message: str) -> None:
    issues.append({"code": code, "message": message})


def _parse_black_lines(text: str) -> float | None:
    matched = re.findall(r"black_start:[\d.]+\s+black_end:[\d.]+\s+black_duration:([\d.]+)", text)
    if not matched:
        return None
    return sum(float(m) for m in matched)


def _run_blackdetect(video: Path) -> tuple[int, str]:
    """黑帧探测：返回 (rc, stderr)。ffdetect 不可用 → rc!=0（调用方单列 issue 不静默）。"""
    cmd = [
        _ffmpeg_bin(),
        "-v",
        "info",
        "-i",
        str(video),
        "-vf",
        "blackdetect=d=0.1:pix_th=0.10",
        "-an",
        "-f",
        "null",
        "-y",
        os.devnull,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stderr
    except OSError:
        return 127, ""


def check_asset(
    video_path: str | Path,
    *,
    min_duration: float = MIN_DURATION_FALLBACK,
    min_width: int = 720,
    min_height: int = 1280,
) -> dict[str, Any]:
    """产出规则层质检报告：{ok, issues:[{code,message}], black_fraction?}。"""
    video = Path(video_path)
    issues: list[dict[str, Any]] = []
    if not video.exists():
        _issues_add(issues, "not_found", f"文件不存在: {video}")
        return {"ok": False, "issues": issues}
    rc, stdout = _probe_streams(video)
    if rc != 0 or not stdout.strip():
        _issues_add(issues, "probe_unavailable", f"ffprobe 不可用（rc={rc}），规则层质检无法执行")
        return {"ok": False, "issues": issues}
    try:
        streams = json.loads(stdout).get("streams", [])
    except json.JSONDecodeError:
        _issues_add(issues, "probe_unavailable", "ffprobe 输出不可解析")
        return {"ok": False, "issues": issues}
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        _issues_add(issues, "no_video_stream", "未检出视频流")
        return {"ok": False, "issues": issues}
    duration = float(video_stream.get("duration") or 0.0)
    if duration < min_duration:
        _issues_add(issues, "duration_too_short", f"时长 {duration:.2f}s 低于红线 {min_duration}s")
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width < min_width or height < min_height:
        _issues_add(issues, "resolution_too_small", f"分辨率 {width}x{height} 低于 {min_width}x{min_height}")
    black_rc, black_text = _run_blackdetect(video)
    black_fraction = None
    if black_rc != 0:
        _issues_add(issues, "blackdetect_unavailable", "黑帧检查工具不可用（blackdetect 未运行）")
    else:
        black_total = _parse_black_lines(black_text)
        black_fraction = ((black_total or 0.0) / duration) if duration > 0 else None
        if black_fraction is not None and black_fraction > BLACK_FRACTION_MAX:
            _issues_add(issues, "black_frames_excess", f"黑帧占比 {black_fraction:.0%} 超阈 {BLACK_FRACTION_MAX:.0%}")
    return {"ok": not issues, "issues": issues, "black_fraction": black_fraction}
