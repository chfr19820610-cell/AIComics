"""字幕烧制（SOP tts_subtitle 渲染层）——PIL 通路，绕开 imageio-ffmpeg 的 fontconfig 框框坑。

排查实录：imageio-ffmpeg 静态 build 启用 fontconfig，但 macOS 无 /etc/fonts/fonts.conf
→ drawtext 初始化失败回退，中文渲染成 □ 框。本模块用 Pillow（内建 freetype，不走
fontconfig）先渲染字幕条/卡片 PNG，再 ffmpeg overlay，字形可单测。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES: list[Path] = [
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
]

DEFAULT_BAR_FONT_SIZE = 26
DEFAULT_BAR_WIDTH = 448
BAR_BOTTOM_MARGIN = 28
BAR_BG_ALPHA = 90


def load_cjk_font(size: int = DEFAULT_BAR_FONT_SIZE, index: int = 0) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        path = Path(path)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size, index=index)
            except OSError:
                continue
    raise FileNotFoundError(f"无可用的 CJK 字体，候选缺失: {_FONT_CANDIDATES}")


def render_subtitle_bar(
    text: str,
    *,
    width: int = DEFAULT_BAR_WIDTH,
    font_size: int = DEFAULT_BAR_FONT_SIZE,
    output: str | Path,
) -> Path:
    """黑底半透明 + 白字居中的一行字幕条（PNG RGBA）。"""
    font = load_cjk_font(font_size)
    pad = 14
    bbox = font.getbbox(text)
    text_w = max(1, bbox[2] - bbox[0])
    text_h_ = max(1, bbox[3] - bbox[1])
    bar_h = text_h_ + pad * 2
    img = Image.new("RGBA", (width, bar_h), (0, 0, 0, BAR_BG_ALPHA))
    draw = ImageDraw.Draw(img)
    x = max(0, (width - text_w) // 2 - bbox[0])
    y = pad - bbox[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def render_title_card(
    background: str | Path,
    lines: list[str],
    *,
    size: tuple[int, int] | None = None,
    font_sizes: list[int] | None = None,
    colors: list[tuple[int, int, int]] | None = None,
    y_fractions: list[float] | None = None,
    output: str | Path,
    border_px: int = 3,
) -> Path:
    """在底图上叠多行文字（片头/片尾卡）。默认标题白+描边、副行黄、页脚灰。"""
    bg = Image.open(background).convert("RGBA")
    if size is not None:
        bg = bg.resize(size, Image.LANCZOS)
    sizes = font_sizes or [52, 30, 20]
    colors_ = colors or [(255, 255, 255), (255, 214, 102), (187, 187, 187)]
    ys = y_fractions or [0.52, 0.62, 0.70]
    draw = ImageDraw.Draw(bg)
    for i, text in enumerate(lines):
        size = sizes[i] if i < len(sizes) else sizes[-1]
        color = colors_[i] if i < len(colors_) else colors_[-1]
        yf = ys[i] if i < len(ys) else ys[-1]
        font = load_cjk_font(size)
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        x = max(0, (bg.width - text_w) // 2 - bbox[0])
        y = int(bg.height * yf) - bbox[1]
        if border_px:
            for dx in (-border_px, 0, border_px):
                for dy in (-border_px, 0, border_px):
                    if dx or dy:
                        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), text, font=font, fill=color + (255,))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out)
    return out


def _run_ffmpeg(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, capture_output=True, text=True).returncode
    except OSError:
        return 127


def ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def burn_subtitle(
    video_path: str | Path,
    subtitle_png: str | Path,
    *,
    output: str | Path,
    ff_bin: str | None = None,
    position: str = "bottom",
    margin_px: int = BAR_BOTTOM_MARGIN,
) -> int:
    """把字幕条 overlay 到视频底部，返回 ffmpeg rc（0=成功）。"""
    video = Path(video_path)
    bar = Path(subtitle_png)
    if not video.exists():
        return 1
    if not bar.exists():
        return 2
    if position == "bottom":
        overlay_expr = f"(main_w-overlay_w)/2:main_h-overlay_h-{margin_px}"
    elif position == "top":
        overlay_expr = f"(main_w-overlay_w)/2:{margin_px}"
    else:
        overlay_expr = "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    ff = ff_bin or ffmpeg_bin()
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ff, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-i", str(bar),
        "-filter_complex",
        f"[1:v]format=yuva420p[b1];[0:v][b1]overlay={overlay_expr}:alpha=straight,format=yuv420p[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
        "-c:a", "copy",
        str(out),
    ]
    return _run_ffmpeg(cmd)


def make_card_video(
    card_png: str | Path,
    *,
    seconds: float = 4.0,
    output: str | Path,
    ff_bin: str | None = None,
    fps: int = 24,
    silent_audio: bool = True,
    sample_rate: int = 24000,
) -> int:
    """静帧 PNG → 定长 mp4（可选 mono 静音轨，保证 concat 流一致）。"""
    png = Path(card_png)
    if not png.exists():
        return 2
    ff = ff_bin or ffmpeg_bin()
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", f"{seconds}", "-i", str(png)]
    if silent_audio:
        cmd += ["-f", "lavfi", "-t", f"{seconds}", "-i", f"anullsrc=channel_layout=mono:sample_rate={sample_rate}"]
        cmd += ["-c:a", "aac", "-b:a", "96k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
    return _run_ffmpeg(cmd)


def bar_stats(png: str | Path) -> dict[str, Any]:
    """自检：字幕条白像素数与尺寸（防 tofu 框）。"""
    import numpy as np

    arr = np.asarray(Image.open(png).convert("L"))
    return {"size": [int(arr.shape[1]), int(arr.shape[0])], "white_px": int((arr > 180).sum())}
