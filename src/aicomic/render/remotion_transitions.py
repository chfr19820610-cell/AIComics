# -*- coding: utf-8 -*-
"""
remotion_transitions.py — Remotion转场效果蒸馏版

从Remotion源码蒸馏6种转场效果，用Python+ffmpeg实现：
  1. fade     — 淡入淡出 (opacity)
  2. slide    — 滑入 (translateX/Y)
  3. wipe     — 擦除 (clip-path polygon)
  4. clock_wipe — 时钟擦除 (径向遮罩)
  5. flip     — 翻转 (rotateY/X)
  6. cross_zoom — 交叉缩放 (scale+fade)

原理: Remotion用React组件在Chromium里渲染每一帧。
蒸馏版: 用ffmpeg的xfade filter直接在视频帧之间做转场，零React依赖。

参考: remotion-dev/remotion/packages/transitions/src/presentations/
"""

from __future__ import annotations
import subprocess
import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "/Users/eric/.hermes/bin/ffmpeg")


@dataclass
class TransitionConfig:
    """转场配置"""
    transition_type: str = "fade"       # fade/slide/wipe/flip/clock_wipe/cross_zoom
    duration: float = 0.5               # 转场持续秒数
    direction: str = "from-left"        # slide/wipe方向
    width: int = 1024
    height: int = 1024
    fps: int = 24


# ffmpeg xfade filter名称映射
XFARE_MAP = {
    "fade": "fade",
    "slide": "slideleft",   # 方向后续处理
    "wipe": "wipeleft",     # 方向后续处理
    "flip": "smoothup",     # 近似
    "clock_wipe": "circleopen",
    "cross_zoom": "zoomin",
    "dissolve": "dissolve",
    "pixelize": "pixelize",
}

DIRECTION_MAP = {
    "from-left": "slideleft",
    "from-right": "slideright",
    "from-top": "slideup",
    "from-bottom": "slidedown",
    "from-left-wipe": "wipeleft",
    "from-right-wipe": "wiperight",
    "from-top-wipe": "wipeup",
    "from-bottom-wipe": "wipedown",
}


def build_xfade_filter(
    transition_type: str,
    duration: float = 0.5,
    direction: str = "from-left",
    offset: float = 0.0,
) -> str:
    """
    构建ffmpeg xfade filter字符串。
    蒸馏自Remotion的fade/slide/wipe/clock_wipe/flip/cross_zoom presentations。
    """
    if transition_type == "slide":
        xfade_type = DIRECTION_MAP.get(direction, "slideleft")
    elif transition_type == "wipe":
        xfade_type = DIRECTION_MAP.get(f"{direction}-wipe", "wipeleft")
    elif transition_type == "flip":
        xfade_type = "smoothup"  # 近似Remotion的flip
    else:
        xfade_type = XFARE_MAP.get(transition_type, "fade")

    return f"xfade=transition={xfade_type}:duration={duration}:offset={offset}"


def render_shots_with_transitions(
    shots: list[dict[str, Any]],
    output_path: str,
    config: TransitionConfig | None = None,
) -> str:
    """
    用ffmpeg xfade filter在shot之间添加转场效果。

    蒸馏自Remotion TransitionSeries:
      Remotion: <TransitionSeries>
                   <Sequence><Img src={shot1}/></Sequence>
                   <Transition presentation={fade()}/>
                   <Sequence><Img src={shot2}/></Sequence>
                 </TransitionSeries>

    蒸馏版: ffmpeg -i shot1 -i shot2 -filter_complex "xfade=fade:d=0.5:o=3" out.mp4

    Args:
        shots: [{"image": "/path/to/img.png", "audio": "/path/to/tts.wav", "duration": 6}]
        output_path: 输出mp4路径
        config: 转场配置
    """
    if config is None:
        config = TransitionConfig()

    if len(shots) < 2:
        # 单个shot直接渲染
        return _render_single_shot(shots[0], output_path, config)

    FFMPEG = FFMPEG_BIN
    tmp_dir = os.path.dirname(output_path)
    os.makedirs(tmp_dir, exist_ok=True)

    # Step 1: 为每个shot生成单独的视频片段（图片+音频）
    segments = []
    for i, shot in enumerate(shots):
        seg_path = os.path.join(tmp_dir, f"_seg_{i:03d}.mp4")
        img = shot.get("image", "")
        audio = shot.get("audio", "")
        duration = shot.get("duration", 4)

        if not os.path.exists(img):
            print(f"  ⚠️ 图片不存在: {img}, 用占位")
            img = _create_placeholder(config.width, config.height, os.path.join(tmp_dir, f"_placeholder_{i}.png"))

        # Ken Burns效果 + 音频
        vf = (
            f"scale={config.width}:{config.height}:force_original_aspect_ratio=decrease,"
            f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"zoompan=z='min(zoom+0.002,1.3)':d=1:s={config.width}x{config.height}:fps={config.fps},"
            f"format=yuv420p"
        )

        cmd = [FFMPEG, "-y", "-loop", "1", "-i", img]
        if audio and os.path.exists(audio):
            cmd += ["-i", audio]
        cmd += [
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-t", str(duration),
        ]
        if audio and os.path.exists(audio):
            cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd += [seg_path]

        subprocess.run(cmd, capture_output=True, timeout=60)
        if os.path.exists(seg_path):
            segments.append(seg_path)
            print(f"  ✅ seg_{i:03d}: {os.path.getsize(seg_path)//1024}KB")
        else:
            print(f"  ❌ seg_{i:03d} 生成失败")

    if len(segments) < 2:
        if len(segments) == 1:
            subprocess.run(["cp", segments[0], output_path])
            return output_path
        return ""

    # Step 2: 用xfade filter拼接片段，加转场
    # 交替使用不同转场效果
    transition_types = ["fade", "slide", "wipe", "cross_zoom", "clock_wipe", "flip"]

    # 逐个拼接
    current = segments[0]
    for i in range(1, len(segments)):
        transition = transition_types[(i - 1) % len(transition_types)]
        # 获取current时长
        r = subprocess.run([FFMPEG, "-i", current], capture_output=True, text=True, timeout=5)
        dur_line = [l for l in r.stderr.split("\n") if "Duration" in l]
        if dur_line:
            dur_str = dur_line[0].split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur_str.split(":")
            total_sec = float(h) * 3600 + float(m) * 60 + float(s)
            offset = max(0, total_sec - config.duration)
        else:
            offset = 3.0

        xfade = build_xfade_filter(transition, config.duration, "from-left", offset)
        next_path = os.path.join(tmp_dir, f"_xfade_{i:03d}.mp4")

        cmd = [
            FFMPEG, "-y", "-i", current, "-i", segments[i],
            "-filter_complex", f"[0:v][1:v]{xfade}[v]",
            "-map", "[v]",
        ]
        # 音频: 取第二个片段的音频
        if os.path.exists(shots[i].get("audio", "")):
            cmd += ["-map", "1:a?",]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k", next_path]

        subprocess.run(cmd, capture_output=True, timeout=60)
        if os.path.exists(next_path) and os.path.getsize(next_path) > 1000:
            current = next_path
            print(f"  ✅ xfade_{i:03d} ({transition}): {os.path.getsize(next_path)//1024}KB")
        else:
            # fallback: 简单concat
            print(f"  ⚠️ xfade失败, 用concat")
            concat_path = os.path.join(tmp_dir, f"_concat_{i:03d}.mp4")
            subprocess.run([FFMPEG, "-y", "-i", current, "-i", segments[i],
                          "-c", "copy", concat_path], capture_output=True, timeout=30)
            if os.path.exists(concat_path):
                current = concat_path

    # Step 3: 输出最终视频
    subprocess.run(["cp", current, output_path])

    # Cleanup
    for f in os.listdir(tmp_dir):
        if f.startswith("_seg_") or f.startswith("_xfade_") or f.startswith("_concat_") or f.startswith("_placeholder_"):
            try:
                os.remove(os.path.join(tmp_dir, f))
            except:
                pass

    return output_path


def _render_single_shot(
    shot: dict[str, Any],
    output_path: str,
    config: TransitionConfig,
) -> str:
    """渲染单个shot（无转场）"""
    FFMPEG = FFMPEG_BIN
    img = shot.get("image", "")
    audio = shot.get("audio", "")
    duration = shot.get("duration", 4)

    vf = (
        f"scale={config.width}:{config.height}:force_original_aspect_ratio=decrease,"
        f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"zoompan=z='min(zoom+0.002,1.3)':d=1:s={config.width}x{config.height}:fps={config.fps},"
        f"format=yuv420p"
    )

    cmd = [FFMPEG, "-y", "-loop", "1", "-i", img]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-t", str(duration)]
    if audio and os.path.exists(audio):
        cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += [output_path]

    subprocess.run(cmd, capture_output=True, timeout=60)
    return output_path


def _create_placeholder(width: int, height: int, path: str) -> str:
    """创建占位图"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), "#141414")
    d = ImageDraw.Draw(img)
    d.text((40, height // 2), "Placeholder", fill="#ffffff")
    img.save(path)
    return path


# === 字幕功能 (蒸馏自Remotion captions包) ===

def generate_srt_from_shots(shots: list[dict[str, Any]], output_path: str) -> str:
    """
    从shot列表生成SRT字幕文件。
    蒸馏自Remotion captions包的parseSrt/serializeSrt。
    """
    lines = []
    current_time = 0.0

    for i, shot in enumerate(shots):
        dialogue = shot.get("dialogue", "")
        if not dialogue:
            continue

        duration = shot.get("duration", 4)
        start_time = current_time
        end_time = current_time + duration

        lines.append(str(i + 1))
        lines.append(f"{_format_srt_time(start_time)} --> {_format_srt_time(end_time)}")
        lines.append(dialogue)
        lines.append("")

        current_time = end_time

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def _format_srt_time(seconds: float) -> str:
    """格式化SRT时间戳 00:00:00,000"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# === 字幕烧录 (蒸馏自Remotion Caption组件) ===

def burn_subtitles_into_video(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_name: str = "Arial",
    font_size: int = 24,
    font_color: str = "white",
    border_color: str = "black",
    border_width: int = 2,
    margin_v: int = 60,
) -> str:
    """
    将SRT字幕烧录到视频中。
    蒸馏自Remotion <Caption>组件的渲染效果。

    使用ffmpeg subtitles filter:
      subtitles=filename=xxx.srt:force_style='FontName=Arial,Fontsize=24,...'
    """
    FFMPEG = FFMPEG_BIN
    style = (
        f"FontName={font_name},Fontsize={font_size},"
        f"PrimaryColour=&H{ _color_to_ass(font_color)},"
        f"OutlineColour=&H{_color_to_ass(border_color)},"
        f"Outline={border_width},Alignment=2,MarginV={margin_v}"
    )

    # 转义路径中的特殊字符
    escaped_srt = srt_path.replace("'", "\\'").replace(":", "\\:")
    filter_str = f"subtitles='{escaped_srt}':force_style='{style}'"

    cmd = [
        FFMPEG, "-y", "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        output_path,
    ]

    subprocess.run(cmd, capture_output=True, timeout=120)
    return output_path


def _color_to_ass(color: str) -> str:
    """将颜色名转ASS颜色代码 (BBGGRR)"""
    color_map = {
        "white": "FFFFFF",
        "black": "000000",
        "yellow": "FFFF00",
        "red": "0000FF",
        "green": "00FF00",
        "blue": "FF0000",
    }
    rgb = color_map.get(color.lower(), "FFFFFF")
    # ASS用BBGGRR格式
    r = rgb[0:2]
    g = rgb[2:4]
    b = rgb[4:6]
    return f"&H{b}{g}{r}"


if __name__ == "__main__":
    # Demo: 演示转场效果
    print("Remotion转场蒸馏版 — 可用转场:")
    for t in XFARE_MAP:
        print(f"  - {t}")
    print(f"\n方向: {list(DIRECTION_MAP.keys())}")
