# -*- coding: utf-8 -*-
"""
keyframe_engine.py — 关键帧引擎

蒸馏自 BigBanana-AI-Director 的 "先画后动" 理念:
  1. 为每个 shot 生成首帧/尾帧 SDXL 提示词
  2. 用 ffmpeg 在首尾帧之间做插值过渡 (morph/zoom/pan)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import os
import subprocess


@dataclass
class KeyframeConfig:
    mode: str = "morph"       # morph | zoom | pan
    duration: int = 3          # 过渡时长(秒)
    fps: int = 24
    width: int = 1024
    height: int = 1024
    ffmpeg_bin: str = "/Users/eric/.hermes/bin/ffmpeg"


# 运镜 → 首尾帧变化映射
_CAMERA_START = {
    "特写": "extreme close-up shot",
    "近景": "close-up shot",
    "中景": "medium shot",
    "远景": "wide shot",
    "全景": "establishing wide shot",
    "俯视": "high angle bird's eye view",
    "仰视": "low angle looking up",
    "侧视": "side profile view",
    "正面": "frontal facing view",
    "背面": "back view silhouette",
}

_CAMERA_END = {
    "特写": "extreme close-up, pulled back slightly",
    "近景": "close-up, slightly wider",
    "中景": "medium shot, pushed in closer",
    "远景": "wide shot, zoomed in to medium",
    "全景": "medium shot, zoomed in from wide",
    "俯视": "eye level, tilted up from high angle",
    "仰视": "eye level, tilted down from low angle",
    "侧视": "frontal turn from side profile",
    "正面": "three-quarter turn from frontal",
    "背面": "over-the-shoulder turn from back",
}

_EMOTION_LIGHT = {
    "压低": "dim moody lighting, dark shadows",
    "禁忌": "eerie cold lighting, unsettling atmosphere",
    "悬念": "mysterious half-light, ambiguous shadows",
    "温暖": "warm golden hour lighting, soft glow",
    "心动": "soft pink-tinted lighting, gentle bokeh",
    "甜蜜": "bright warm lighting, dreamy atmosphere",
    "紧张": "high contrast dramatic lighting, sharp shadows",
    "悲伤": "cold blue-grey lighting, overcast mood",
    "愤怒": "harsh red-tinted lighting, aggressive contrast",
    "平静": "even natural lighting, calm atmosphere",
}


def generate_keyframe_prompts(shot: dict[str, Any]) -> dict[str, str]:
    """为 shot 生成首帧和尾帧的 SDXL 提示词。

    Returns: {"start_prompt": "...", "end_prompt": "..."}
    """
    visual = shot.get("visual", "")
    camera = shot.get("camera", "")
    emotion = shot.get("emotion", "")
    scene = shot.get("scene", "")
    characters = "、".join(shot.get("characters", []))

    # 解析运镜关键词
    cam_start = "cinematic shot"
    cam_end = "cinematic shot"
    for key in _CAMERA_START:
        if key in camera:
            cam_start = _CAMERA_START[key]
            cam_end = _CAMERA_END[key]
            break

    # 解析情绪关键词
    light = "cinematic lighting"
    for key in _EMOTION_LIGHT:
        if key in emotion:
            light = _EMOTION_LIGHT[key]
            break

    base = f"anime illustration style, {scene}, {characters}"
    suffix = "high quality, detailed, 2D animated illustration, no text, no watermark"

    start_prompt = f"{base}, {visual}, {cam_start}, {light}, {suffix}"
    end_prompt = f"{base}, {visual}, {cam_end}, {light}, {suffix}"

    return {"start_prompt": start_prompt, "end_prompt": end_prompt}


def render_keyframe_transition(
    start_img: str,
    end_img: str,
    output_path: str,
    mode: str = "morph",
    duration: int = 3,
    fps: int = 24,
    width: int = 1024,
    height: int = 1024,
    ffmpeg_bin: str = "/Users/eric/.hermes/bin/ffmpeg",
) -> bool:
    """用 ffmpeg 在首尾帧之间做插值过渡。

    mode: morph (帧混合) | zoom (推拉) | pan (平移)
    Returns: True if success
    """
    if not os.path.exists(start_img) or not os.path.exists(end_img):
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    total_frames = duration * fps

    if mode == "morph":
        # 交叉淡入淡出: start → fade → end
        cmd = [
            ffmpeg_bin, "-y",
            "-loop", "1", "-i", start_img,
            "-loop", "1", "-i", end_img,
            "-filter_complex",
            f"[0:v]scale={width}:{height},fps={fps},trim=duration={duration}[a];"
            f"[1:v]scale={width}:{height},fps={fps},trim=duration={duration}[b];"
            f"[a][b]xfade=transition=fade:duration={duration}:offset=0[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    elif mode == "zoom":
        # 推拉: 从start图缓慢推近, 末尾切到end图
        mid_path = output_path.replace(".mp4", "_mid.mp4")
        # Part 1: zoom in on start (2/3 duration)
        dur1 = duration * 2 // 3
        cmd1 = [
            ffmpeg_bin, "-y",
            "-loop", "1", "-i", start_img,
            "-vf", f"scale={width}:{height},zoompan=z='min(zoom+{0.3/(dur1*fps)},1.3)':d={dur1*fps}:s={width}x{height}:fps={fps},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(dur1), mid_path,
        ]
        subprocess.run(cmd1, capture_output=True, timeout=60)

        # Part 2: zoom out to end (1/3 duration)
        dur2 = duration - dur1
        end_path = output_path.replace(".mp4", "_end.mp4")
        cmd2 = [
            ffmpeg_bin, "-y",
            "-loop", "1", "-i", end_img,
            "-vf", f"scale={width}:{height},zoompan=z='1.3+0':d=1:s={width}x{height}:fps={fps},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(dur2), end_path,
        ]
        subprocess.run(cmd2, capture_output=True, timeout=60)

        # Concat
        concat_list = output_path.replace(".mp4", "_concat.txt")
        with open(concat_list, "w") as f:
            f.write(f"file '{mid_path}'\nfile '{end_path}'\n")
        cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c", "copy", output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        for tmp in [mid_path, end_path, concat_list]:
            if os.path.exists(tmp):
                os.remove(tmp)
        return os.path.exists(output_path)

    elif mode == "pan":
        # 平移: 从左到右扫过start, 末尾切到end
        cmd = [
            ffmpeg_bin, "-y",
            "-loop", "1", "-i", start_img,
            "-vf", f"scale={width*2}:{height},crop={width}:{height}:x='t/{duration}*{width}':y=0,fps={fps},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(duration), output_path,
        ]
    else:
        return False

    result = subprocess.run(cmd, capture_output=True, timeout=120)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
