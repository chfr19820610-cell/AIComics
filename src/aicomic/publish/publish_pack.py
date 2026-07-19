from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_publish_pack(manifest: dict[str, Any], episode_code: str) -> dict[str, Any]:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    subtitle_lines = [str(shot.get("dialogue", "")).strip() for shot in episode.get("shots", []) if str(shot.get("dialogue", "")).strip()]
    summary = subtitle_lines[0] if subtitle_lines else episode["title"]
    return {
        "episode_code": episode_code,
        "title": episode["title"],
        "publish_title": episode["publish_title"],
        "cover_text": episode["cover_text"],
        "description": f"{episode['title']}：{summary}",
        "hashtags": ["#AI漫剧", "#职场逆袭", "#短剧"],
        "comment_seed": "你们觉得她的真实身份会是什么？",
    }


def build_enhanced_publish_pack(manifest: dict[str, Any], episode_code: str) -> dict[str, Any]:
    base_pack = build_publish_pack(manifest, episode_code)
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    base_title = str(episode["publish_title"])
    cover_text = str(episode["cover_text"])
    base_pack["title_candidates"] = [
        base_title,
        f"{cover_text}，全公司都沉默了",
        "她刚被羞辱，总裁就亲自撑腰",
        "一个实习生，凭什么让总裁护着？",
        "没人知道，她才是这场局的关键",
    ]
    base_pack["cover_text_candidates"] = [
        cover_text,
        "总裁亲自来接她",
        "她不是普通实习生",
        "开除她？你们不配",
        "她的身份藏不住了",
    ]
    base_pack["platform_copy"] = {
        "douyin": f"{base_title}。{base_pack['description']} #AI漫剧 #职场逆袭",
        "kuaishou": f"{cover_text}，这次她不忍了。",
        "xiaohongshu": f"职场爽文照进现实：{base_pack['description']}",
        "bilibili": f"AI漫剧短篇｜{episode['title']}｜身份反转开局",
    }
    base_pack["publish_checklist"] = [
        "确认封面图无文字错误",
        "确认字幕不遮挡人物脸部",
        "确认前 3 秒冲突明确",
        "确认结尾保留追更钩子",
        "确认发布标题与封面文案一致",
    ]
    return base_pack


def write_publish_pack(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
