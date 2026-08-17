# -*- coding: utf-8 -*-
"""
storyboard_grid.py — 九宫格分镜

蒸馏自 BigBanana-AI-Director 的九宫格分镜功能:
  为每个 shot 生成 9 个不同视角/构图的 SDXL 候选提示词,
  拼成 3x3 网格供创作者选最佳构图。
"""

from __future__ import annotations
from typing import Any
import os

try:
    from PIL import Image
except ImportError:
    Image = None


# 9 个视角/构图
_GRID_ANGLES = [
    ("extreme_close_up", "extreme close-up shot, face filling frame, intense detail"),
    ("close_up", "close-up shot, head and shoulders, shallow depth of field"),
    ("medium_shot", "medium shot, waist up, natural framing"),
    ("wide_shot", "wide establishing shot, full body, environment visible"),
    ("high_angle", "high angle bird's eye view, looking down at subject"),
    ("low_angle", "low angle hero shot, looking up at subject"),
    ("side_profile", "side profile view, dramatic silhouette edge lighting"),
    ("three_quarter", "three-quarter frontal view, classic portrait angle"),
    ("dynamic_dutch", "dynamic Dutch angle, tilted composition, action energy"),
]


def generate_grid_prompts(shot: dict[str, Any]) -> list[str]:
    """为 shot 生成 9 个不同视角的 SDXL 提示词。

    Returns: list of 9 prompt strings
    """
    visual = shot.get("visual", "")
    scene = shot.get("scene", "")
    emotion = shot.get("emotion", "")
    characters = "、".join(shot.get("characters", []))
    style = "anime illustration style, 2D animated, high quality, detailed, no text, no watermark"

    prompts = []
    for angle_name, angle_desc in _GRID_ANGLES:
        prompt = f"{style}, {scene}, {characters}, {visual}, {angle_desc}, {emotion} mood"
        prompts.append(prompt)

    return prompts


def compose_grid_image(
    images: list[str],
    output_path: str,
    cell_size: int = 1024,
    padding: int = 20,
    bg_color: str = "#1a1a1a",
    labels: bool = True,
) -> bool:
    """将 9 张图片拼成 3x3 网格。

    Args:
        images: list of 9 image file paths
        output_path: output grid image path
        cell_size: each cell size in pixels
        padding: padding between cells
    Returns: True if success
    """
    if Image is None:
        return False
    if len(images) < 9:
        return False

    cols, rows = 3, 3
    total_w = cols * cell_size + (cols + 1) * padding
    total_h = rows * cell_size + (rows + 1) * padding + (rows * 30 if labels else 0)

    canvas = Image.new("RGB", (total_w, total_h), bg_color)
    draw = None
    if labels:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)

    angle_names = [a[0] for a in _GRID_ANGLES]

    for idx in range(9):
        row = idx // 3
        col = idx % 3
        x = padding + col * (cell_size + padding)
        y = padding + row * (cell_size + padding + (30 if labels else 0))

        img_path = images[idx]
        if os.path.exists(img_path):
            try:
                img = Image.open(img_path).convert("RGB").resize((cell_size, cell_size))
                canvas.paste(img, (x, y))
            except Exception:
                _draw_placeholder(draw, x, y, cell_size, angle_names[idx])
        else:
            _draw_placeholder(draw, x, y, cell_size, angle_names[idx])

        if labels and draw:
            draw.text((x + 5, y + cell_size + 5), angle_names[idx], fill="#888888")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    canvas.save(output_path, "PNG")
    return os.path.exists(output_path)


def _draw_placeholder(draw, x, y, size, label):
    """Draw a placeholder rectangle for missing images."""
    if draw is None:
        return
    from PIL import ImageDraw
    draw.rectangle([x, y, x + size, y + size], outline="#444444", width=2)
    draw.text((x + size // 3, y + size // 2), label, fill="#666666")
