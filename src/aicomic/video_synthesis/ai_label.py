"""AI 合规标识（SOP §10 监管合规 #7）。默认不可见元数据，可选可见水印。

- 不重编码地改写 mp4 元数据：ffmpeg -c copy -map_metadata 0 + -metadata（追加语义）；
- 不清原生 metadata（`-map_metadata 0` 全保留，AI 三标签覆盖式写入）；
- ai_generated=true 是机检锚点（ai_label_present / 平台 shim），comment 是人读一句；
- ffmpeg 失败 → RuntimeError（调用方决定 fail-soft），tmp 清理后重命名，永不假绿。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

AI_METADATA_TAGS = {
    "ai_generated": "true",
    "comment": "本内容由AI生成（AIComics）",
    "ai_generator": "AIComics",
}
DEFAULT_WATERMARK_TEXT = "本内容为AI生成"


def _run_ffmpeg(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _run_probe(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _ffmpeg_bin(ffmpeg_bin: str | Path | None = None) -> str:
    if ffmpeg_bin:
        return str(ffmpeg_bin)
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _ffprobe_bin(ffprobe_bin: str | Path | None = None) -> str:
    if ffprobe_bin:
        return str(ffprobe_bin)
    try:
        return str(Path(_ffmpeg_bin(None)).with_name("ffprobe"))
    except Exception:
        return "ffprobe"


def embed_ai_label(
    video_path: str | Path,
    output_path: str | Path | None = None,
    *,
    watermark: bool = False,
    watermark_text: str = DEFAULT_WATERMARK_TEXT,
    ffmpeg_bin: str | Path | None = None,
) -> Path:
    src = Path(video_path)
    if not src.exists():
        raise RuntimeError(f"input video 不存在: {src}")
    target = Path(output_path) if output_path is not None else src
    tmp_out = target.with_name(f".{target.name}.ailabel.tmp.mp4")
    cmd: list[str] = [_ffmpeg_bin(ffmpeg_bin), "-y", "-i", str(src)]
    if watermark:
        text = watermark_text.replace(":", "\\:")
        cmd += [
            "-vf",
            f"drawtext=text='{text}':fontsize=28:fontcolor=white@0.8:box=1:boxcolor=black@0.35:boxborderw=12:x=(w-tw)/2:y=h-th-56",
        ]
    cmd += ["-map", "0", "-map_metadata", "0"]
    for key, value in AI_METADATA_TAGS.items():
        cmd += ["-metadata", f"{key}={value}"]
    cmd += ["-c", "copy", "-movflags", "+faststart", str(tmp_out)]
    rc = _run_ffmpeg(cmd)
    if rc != 0:
        tmp_out.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg 写 AI 标识失败（rc={rc}）")
    tmp_out.replace(target)
    return target


def ai_label_present(video_path: str | Path, *, ffprobe_bin: str | Path | None = None) -> bool:
    video = Path(video_path)
    if not video.exists():
        return False
    probe_out = video.with_name(f".{video.name}.ailabel.probe.json")
    try:
        cmd = [str(_ffprobe_bin(ffprobe_bin)), "-show_format", "-of", "json", str(video), "-o", str(probe_out)]
        rc = _run_probe(cmd)
        data: dict[str, Any] = {}
        if rc == 0 and probe_out.exists():
            data = json.loads(probe_out.read_text(encoding="utf-8"))
        tags = ((data.get("format") or {}).get("tags") or {})
        return str(tags.get("ai_generated", "")).lower() == "true"
    except Exception:
        return False
    finally:
        try:
            if probe_out.exists():
                probe_out.unlink()
        except OSError:
            pass
