"""Publish analytics — 发布后数据回收（播放量/点赞/评论）."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AnalyticsRecord:
    platform: str
    video_id: str
    title: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


def create_analytics_record(platform: str, video_id: str, title: str = "") -> AnalyticsRecord:
    return AnalyticsRecord(platform=platform, video_id=video_id, title=title)


def save_analytics(records: list[AnalyticsRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2), encoding="utf-8")


def load_analytics(path: Path) -> list[AnalyticsRecord]:
    if not path.exists():
        return []
    return [AnalyticsRecord(**r) for r in json.loads(path.read_text(encoding="utf-8"))]


def update_analytics(path: Path, video_id: str, **kwargs: int) -> None:
    records = load_analytics(path)
    for r in records:
        if r.video_id == video_id:
            for k, v in kwargs.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            break
    save_analytics(records, path)


def get_summary(path: Path) -> dict[str, int]:
    records = load_analytics(path)
    return {
        "total_views": sum(r.views for r in records),
        "total_likes": sum(r.likes for r in records),
        "total_comments": sum(r.comments for r in records),
        "total_shares": sum(r.shares for r in records),
        "total_videos": len(records),
    }
