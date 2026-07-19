"""
Subtitle generation for the video synthesis pipeline.

Supports:
- SRT format (simple, widely compatible)
- ASS format (styled: larger font, stroke/outline, centered position)
"""

from pathlib import Path
from typing import Any

from aicomic.video_synthesis.config import (
    SUBTITLE_BORDER_SIZE,
    SUBTITLE_FONT,
    SUBTITLE_FONT_SIZE,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _srt_ts(sec: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_ts(sec: float) -> str:
    """Format seconds as ASS timestamp: H:MM:SS.mm"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ── SRT generation ────────────────────────────────────────────────────────

def build_srt(
    scene_durations: list[float],
    subtitles: list[str],
) -> str:
    """
    Build SRT subtitle content from scene durations and subtitle texts.

    Args:
        scene_durations: Duration in seconds for each scene.
        subtitles: Subtitle text for each scene (empty string = no subtitle).

    Returns:
        Complete SRT file content as a string.
    """
    lines: list[str] = []
    current_time = 0.0
    sub_idx = 0

    for dur, text in zip(scene_durations, subtitles):
        if not text:
            current_time += dur
            continue

        sub_idx += 1
        lines.append(str(sub_idx))
        lines.append(f"{_srt_ts(current_time)} --> {_srt_ts(current_time + dur)}")
        lines.append(text)
        lines.append("")
        current_time += dur

    return "\n".join(lines)


def write_srt(path: Path, scene_durations: list[float], subtitles: list[str]) -> Path:
    """Write SRT file and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_srt(scene_durations, subtitles)
    path.write_text(content, encoding="utf-8")
    return path


# ── ASS (Advanced SSA/SubStation Alpha) generation ────────────────────────

def build_ass(
    scene_durations: list[float],
    subtitles: list[str],
    video_width: int = 1920,
    video_height: int = 1080,
    font_size: int = SUBTITLE_FONT_SIZE,
    border_size: int = SUBTITLE_BORDER_SIZE,
    font_name: str | None = None,
) -> str:
    """
    Build ASS subtitle content with styled formatting.

    ASS provides better control over:
    - Font size (28px for readability)
    - Border/outline (2px black stroke)
    - Position (bottom-center)
    - Shadow and colors

    Args:
        scene_durations: Duration in seconds for each scene.
        subtitles: Subtitle text for each scene.
        video_width, video_height: Output video dimensions.
        font_size: Subtitle font size.
        border_size: Black outline thickness.

    Returns:
        Complete ASS file content as a string.
    """
    margin_v = int(video_height * 0.05)  # 5% from bottom
    margin_h = int(video_width * 0.02)

    lines: list[str] = []
    lines.append("[Script Info]")
    lines.append("Title: AIComics Subtitles")
    lines.append("ScriptType: v4.00+")
    lines.append(f"PlayResX: {video_width}")
    lines.append(f"PlayResY: {video_height}")
    lines.append("ScaledBorderAndShadow: yes")
    lines.append("")

    # Style definitions
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,
    #         OutlineColour, BackColour, Bold, Italic, Underline,
    #         StrikeOut, ScaleX, ScaleY, Spacing, Angle,
    #         BorderStyle, Outline, Shadow, Alignment, MarginL,
    #         MarginR, MarginV, Encoding
    lines.append("[V4+ Styles]")
    lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    # Style: white text, black outline, no shadow, centered bottom
    primary = "&H00FFFFFF"    # white
    outline = "&H00000000"     # black
    # Choose font: explicit > config > auto-detect
    chosen_font = font_name or SUBTITLE_FONT or _FontResolver._font_name()
    lines.append(
        f"Style: Default,{chosen_font},{font_size},"
        f"{primary},{primary},"
        f"{outline},{outline},"
        f"0,0,0,0,"    # bold, italic, underline, strikeout
        f"100,100,0,0,"  # scaleX, scaleY, spacing, angle
        f"1,{border_size},0,"  # border_style, outline, shadow
        f"2,"           # alignment (2 = bottom center)
        f"{margin_h},{margin_h},{margin_v},"
        f"1"            # encoding
    )
    lines.append("")

    # Events
    lines.append("[Events]")
    lines.append(
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text"
    )

    current_time = 0.0
    for dur, text in zip(scene_durations, subtitles):
        if not text:
            current_time += dur
            continue
        escaped = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(
            f"Dialogue: 0,{_ass_ts(current_time)},{_ass_ts(current_time + dur)},"
            f"Default,,0,0,0,,{escaped}"
        )
        current_time += dur

    return "\n".join(lines)


def write_ass(path: Path, scene_durations: list[float], subtitles: list[str],
              video_width: int = 1920, video_height: int = 1080) -> Path:
    """Write ASS file and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_ass(scene_durations, subtitles, video_width, video_height)
    path.write_text(content, encoding="utf-8")
    return path


# ── Shared ────────────────────────────────────────────────────────────────

class _FontResolver:
    """Resolve a font name for ASS. Tries common Chinese fonts on macOS."""

    _font_cache: str | None = None

    @classmethod
    def _font_name(cls) -> str:
        if cls._font_cache is not None:
            return cls._font_cache

        import subprocess
        # Probe for a readable Chinese font
        candidates = [
            "PingFang SC",        # macOS system Chinese font
            "Noto Sans CJK SC",   # Google Noto
            "Source Han Sans SC", # Adobe Source Han
            "STHeiti",            # macOS alternative
            "Arial Unicode MS",   # fallback
        ]
        for name in candidates:
            try:
                result = subprocess.run(
                    ["fc-list", f":lang=zh"],
                    capture_output=True, text=True, timeout=3,
                )
                if name.lower() in result.stdout.lower():
                    cls._font_cache = name
                    return name
            except Exception:
                pass

        # Final fallback
        cls._font_cache = "PingFang SC"
        return cls._font_cache
