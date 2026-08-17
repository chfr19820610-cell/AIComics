"""Subtitle styler — 字体/颜色/大小/描边/背景 全可配.

Distilled from MoneyPrinterTurbo video.py subtitle functions.
Wraps FFmpeg subtitles filter with configurable styling.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aicomic.video_synthesis.config import FFMPEG


@dataclass
class SubtitleStyle:
    """Subtitle styling configuration."""
    font_name: str = "PingFang SC"
    font_size: int = 36
    primary_color: str = "&H00FFFFFF"  # White (ASS format: &H00BBGGRR)
    outline_color: str = "&H00000000"  # Black
    outline_width: int = 3
    shadow: bool = True
    shadow_color: str = "&H80000000"
    position: str = "bottom"  # bottom / center / top
    margin_v: int = 40  # Vertical margin from bottom/top
    bold: bool = True

    def to_ass_style(self) -> str:
        """Convert to ASS style string."""
        alignment = {"bottom": 2, "center": 5, "top": 8}.get(self.position, 2)
        outline = self.outline_width if self.outline_width > 0 else 1
        shadow_val = 3 if self.shadow else 0
        bold_flag = -1 if self.bold else 0
        return (
            f"Style: Default,{self.font_name},{self.font_size},"
            f"{self.primary_color},{self.primary_color},"
            f"{self.outline_color},{self.shadow_color},"
            f"{bold_flag},0,0,0,{alignment},{self.margin_v},{outline},{shadow_val},1"
        )


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    style: SubtitleStyle | None = None,
) -> bool:
    """Burn subtitles into video with styling.

    Args:
        video_path: Input video.
        subtitle_path: SRT or ASS subtitle file.
        output_path: Output video with burned subtitles.
        style: Subtitle styling configuration.

    Returns True if burn succeeded.
    """
    style = style or SubtitleStyle()

    # Escape special chars in path for FFmpeg filter
    safe_path = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    if subtitle_path.suffix == ".srt":
        force_style = (
            f"FontName={style.font_name},"
            f"FontSize={style.font_size},"
            f"PrimaryColour={style.primary_color},"
            f"OutlineColour={style.outline_color},"
            f"Outline={style.outline_width},"
            f"Shadow={3 if style.shadow else 0},"
            f"Bold={1 if style.bold else 0},"
            f"MarginV={style.margin_v}"
        )
        subtitle_filter = f"subtitles='{safe_path}':force_style='{force_style}'"
    else:
        subtitle_filter = f"ass='{safe_path}'"

    cmd = [
        FFMPEG, "-y",
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:a", "copy",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        str(output_path),
    ]

    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False


def create_ass_file(
    subtitle_entries: list[dict],
    output_path: Path,
    style: SubtitleStyle | None = None,
) -> bool:
    """Create ASS subtitle file from entries with styling.

    Args:
        subtitle_entries: List of {start, end, text} dicts (seconds).
        output_path: Output .ass file path.
        style: Subtitle styling configuration.

    Returns True if file was created.
    """
    style = style or SubtitleStyle()

    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        cs = int((s % 1) * 100)
        return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"

    header = f"""[Script Info]
Title: AIComics Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style.to_ass_style()}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for entry in subtitle_entries:
        start = fmt_time(entry["start"])
        end = fmt_time(entry["end"])
        text = entry["text"].replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    content = header + "\n".join(events) + "\n"
    try:
        output_path.write_text(content, encoding="utf-8")
        return output_path.exists()
    except Exception:
        return False
