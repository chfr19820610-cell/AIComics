"""Scheduled publish — 定时发布任务管理."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ScheduledTask:
    task_id: str
    video_path: str
    platforms: list[str]
    scheduled_at: str  # ISO datetime
    title: str
    status: str = "pending"  # pending / done / failed


def create_scheduled_task(video_path: str, platforms: list[str], scheduled_at: str, title: str = "") -> ScheduledTask:
    return ScheduledTask(
        task_id=str(uuid.uuid4())[:8],
        video_path=video_path,
        platforms=platforms,
        scheduled_at=scheduled_at,
        title=title,
    )


def save_tasks(tasks: list[ScheduledTask], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(t) for t in tasks], ensure_ascii=False, indent=2), encoding="utf-8")


def load_tasks(path: Path) -> list[ScheduledTask]:
    if not path.exists():
        return []
    return [ScheduledTask(**t) for t in json.loads(path.read_text(encoding="utf-8"))]


def list_pending_tasks(path: Path) -> list[ScheduledTask]:
    return [t for t in load_tasks(path) if t.status == "pending"]


def mark_task_done(path: Path, task_id: str) -> None:
    tasks = load_tasks(path)
    for t in tasks:
        if t.task_id == task_id:
            t.status = "done"
            break
    save_tasks(tasks, path)
