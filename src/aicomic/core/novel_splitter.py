# -*- coding: utf-8 -*-
"""
novel_splitter.py — 小说拆分

蒸馏自 BigBanana-AI-Director 的小说导入拆分功能:
  将整篇小说文本拆分成多集 manifest, 每集 6-10 个 shot。
"""

from __future__ import annotations
from typing import Any
import re


# 场景转换关键词
_SCENE_BREAKS = [
    r"第[一二三四五六七八九十百千]+章",
    r"第\d+章",
    r"Chapter\s+\d+",
    r"【.+?】",
    r"---",
    r"\n{3,}",
]

# 对白正则
_DIALOGUE_RE = re.compile(r'[""「」『』].+?[""「」『』]')

# 地点关键词
_LOCATION_PATTERNS = [
    r"在(.+?)(?:里|中|上|前|后|旁|内|下)",
    r"(.+?)(?:里|中|上|前|后|旁|内|下)",
    r"(\w+路|\w+街|\w+巷|\w+楼|\w+店|\w+站|\w+园|\w+场|\w+室)",
]

# 情绪关键词
_EMOTION_MAP = {
    "笑": "温暖",
    "哭": "悲伤",
    "怒": "愤怒",
    "惊": "紧张",
    "怕": "压低",
    "爱": "心动",
    "甜": "甜蜜",
    "冷": "平静",
    "急": "紧张",
}


def split_novel_to_episodes(
    novel_text: str,
    target_shots_per_ep: int = 6,
    chars_per_shot: int = 300,
) -> list[dict[str, Any]]:
    """将整篇小说拆分成多集。

    Args:
        novel_text: 小说全文
        target_shots_per_ep: 每集目标 shot 数
        chars_per_shot: 每个 shot 的平均字数
    Returns: list of episode dicts, each with shots
    """
    # 1. 按章节/分隔符切分段落
    chunks = _split_by_markers(novel_text)

    # 2. 每段按字数切分成 shot 级片段
    episodes = []
    current_shots = []
    ep_num = 1

    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 20:
            continue

        # 切成 ~chars_per_shot 字的小段
        segments = _split_by_length(chunk, chars_per_shot)

        for seg in segments:
            shot = _parse_segment_to_shot(seg, f"S{len(current_shots) + 1:02d}")
            current_shots.append(shot)

            if len(current_shots) >= target_shots_per_ep:
                episodes.append({
                    "episode_code": f"E{ep_num:02d}",
                    "title": _extract_title(current_shots),
                    "shots": current_shots,
                })
                current_shots = []
                ep_num += 1

    # 剩余 shot 组成最后一集
    if current_shots:
        episodes.append({
            "episode_code": f"E{ep_num:02d}",
            "title": _extract_title(current_shots),
            "shots": current_shots,
        })

    return episodes


def build_manifest_from_episodes(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    """将多集数据构建成 AlComics manifest 格式。"""
    return {"episodes": episodes}


def _split_by_markers(text: str) -> list[str]:
    """按章节标记切分。"""
    # 先按 \n{3,} 切
    chunks = re.split(r"\n{3,}", text)

    # 再按章节标记切
    result = []
    for chunk in chunks:
        parts = re.split(r"(?=第[一二三四五六七八九十百千]+章|第\d+章|Chapter\s+\d+)", chunk)
        result.extend(parts)

    return [c for c in result if c.strip()]


def _split_by_length(text: str, length: int) -> list[str]:
    """按字数切分, 尽量在句号/换行处断。"""
    if len(text) <= length:
        return [text]

    segments = []
    start = 0
    while start < len(text):
        end = min(start + length, len(text))
        # 尝试在句号/换行处断
        if end < len(text):
            for break_char in ["。", "！", "？", "\n", "，"]:
                last_break = text.rfind(break_char, start, end)
                if last_break > start + length // 2:
                    end = last_break + 1
                    break
        segments.append(text[start:end])
        start = end

    return segments


def _parse_segment_to_shot(seg: str, shot_id: str) -> dict[str, Any]:
    """从文本片段提取 shot 字段。"""
    # 场景: 查找地点关键词
    scene = "室内场景"
    for pattern in _LOCATION_PATTERNS:
        match = re.search(pattern, seg)
        if match:
            scene = match.group(1)[:20]
            break

    # 对白: 提取引号内内容
    dialogue_match = _DIALOGUE_RE.search(seg)
    dialogue = dialogue_match.group(0).strip('""「」『』') if dialogue_match else ""

    # 情绪: 关键词检测
    emotion = "平静"
    for keyword, emo in _EMOTION_MAP.items():
        if keyword in seg:
            emotion = emo
            break

    # 画面: 取前80字作为画面描述
    visual = seg.replace("\n", " ").strip()[:80]

    return {
        "shot_id": shot_id,
        "duration": 6,
        "scene": scene,
        "characters": [],
        "visual": visual,
        "action": "",
        "dialogue": dialogue,
        "emotion": emotion,
        "camera": "中景，缓慢推进",
        "ai_video": False,
    }


def _extract_title(shots: list[dict]) -> str:
    """从 shots 提取标题。"""
    if not shots:
        return "未命名"
    first_dialogue = shots[0].get("dialogue", "")
    if first_dialogue:
        return first_dialogue[:30]
    return shots[0].get("visual", "未命名")[:30]
