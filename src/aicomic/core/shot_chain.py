"""镜头承接 —— 把上一镜的**真实尾帧**直拷为本镜首帧（参考 ai-comic-studio 语义）。

为什么需要它
------------
让模型为下一镜"重新想象"衔接，几乎必然出现跳变。可靠做法是取**已生成视频的
真实最后一帧**作为下一镜的首帧输入（image-to-video 的 start frame），
这样跨镜构图/光影/角色朝向天然连续。

与现有 `prev_shot` 的区别
-------------------------
`request_builder` 里的 `prev_shot/next_shot` 只把**文本**上下文传给 prompt 构建器，
属于"提示词层面"的连续性；本模块提供"像素层面"的连续性，两者互补。

设计要点
--------
- 只依赖 ffmpeg（本机 ffprobe 因架构问题不可用，ffmpeg 正常，故一律走 ffmpeg）
- 失败返回结构化 error，不抛异常、不假绿
- `_run_ffmpeg` seam 可 monkeypatch，便于单测
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def _ffmpeg_bin(ffmpeg_bin: str | Path | None = None) -> str:
    if ffmpeg_bin:
        return str(ffmpeg_bin)
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _run_ffmpeg(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, capture_output=True, text=True).returncode
    except OSError:
        return 127


def extract_last_frame(
    video_path: str | Path,
    output_path: str | Path,
    *,
    ffmpeg_bin: str | Path | None = None,
) -> dict[str, Any]:
    """把视频的最后一帧抽成 PNG。

    用 `-sseof -0.3` 从结尾前 0.3 秒开始解码，再取 1 帧 —— 比 `-vframes 1`
    配合全片解码快得多，且能避开尾部的黑场补帧。
    """
    src = Path(video_path)
    dst = Path(output_path)
    if not src.is_file():
        return {"ok": False, "error": f"video not found: {src}", "path": str(dst)}
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_bin(ffmpeg_bin), "-y", "-sseof", "-0.3", "-i", str(src),
        "-frames:v", "1", "-q:v", "1", str(dst),
    ]
    rc = _run_ffmpeg(cmd)
    if rc != 0 or not dst.is_file() or dst.stat().st_size == 0:
        return {"ok": False, "error": f"ffmpeg rc={rc}", "path": str(dst)}
    return {"ok": True, "path": str(dst), "bytes": dst.stat().st_size}


def extract_first_frame(
    video_path: str | Path,
    output_path: str | Path,
    *,
    ffmpeg_bin: str | Path | None = None,
) -> dict[str, Any]:
    """把视频的第一帧抽成 PNG（用于承接后的连续性校验）。"""
    src = Path(video_path)
    dst = Path(output_path)
    if not src.is_file():
        return {"ok": False, "error": f"video not found: {src}", "path": str(dst)}
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg_bin(ffmpeg_bin), "-y", "-i", str(src),
        "-frames:v", "1", "-q:v", "1", str(dst),
    ]
    rc = _run_ffmpeg(cmd)
    if rc != 0 or not dst.is_file() or dst.stat().st_size == 0:
        return {"ok": False, "error": f"ffmpeg rc={rc}", "path": str(dst)}
    return {"ok": True, "path": str(dst), "bytes": dst.stat().st_size}


def carry_last_frame(
    prev_video_path: str | Path,
    next_start_frame_path: str | Path,
    *,
    ffmpeg_bin: str | Path | None = None,
) -> dict[str, Any]:
    """承接：上一镜视频的尾帧 → 本镜的首帧文件。

    Returns:
        {"ok": bool, "source": prev_video, "target": next_frame, "error": str}
    """
    result = extract_last_frame(prev_video_path, next_start_frame_path, ffmpeg_bin=ffmpeg_bin)
    return {
        "ok": bool(result.get("ok")),
        "source": str(prev_video_path),
        "target": str(next_start_frame_path),
        "bytes": result.get("bytes", 0),
        "error": result.get("error", ""),
    }


def chain_shots(
    video_paths: list[str | Path],
    output_dir: str | Path,
    *,
    ffmpeg_bin: str | Path | None = None,
) -> dict[str, Any]:
    """对一整串镜头做承接：第 i 镜尾帧 → 第 i+1 镜首帧。

    输出到 `output_dir/S{i+1:02d}_start.png`，并返回逐条明细。
    少于 2 个镜头时无承接可做，返回 ok=True 且 chains 为空。
    """
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    chains: list[dict[str, Any]] = []
    for idx in range(len(video_paths) - 1):
        prev_video = Path(video_paths[idx])
        target = out_root / f"S{idx + 2:02d}_start.png"
        chains.append(carry_last_frame(prev_video, target, ffmpeg_bin=ffmpeg_bin))
    failed = [c for c in chains if not c.get("ok")]
    return {
        "ok": not failed,
        "chain_count": len(chains),
        "failed_count": len(failed),
        "chains": chains,
    }
