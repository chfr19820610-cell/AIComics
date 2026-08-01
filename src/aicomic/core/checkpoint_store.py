"""阶段 checkpoint 存储 — ACOM-0.6.0 P0-3.

每阶段完成写 state/checkpoints/<episode>_<stage>.json，记录 status
(in_progress / awaiting_human / completed / failed) 与自检结论，供
断点续跑（resume）基于 checkpoint 而非全量重跑。

合规：独立 Apache-2.0 自建。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aicomic.core.pipeline_manifest import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    CHECKPOINT_FAILED,
    CHECKPOINT_IN_PROGRESS,
    CHECKPOINT_STATUSES,
    CHECKPOINT_TERMINAL_STATUSES,
    PipelineManifestError,
)
from aicomic.utils.atomic_io import atomic_write_json


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def checkpoint_dir(state_dir: Path) -> Path:
    return state_dir / "checkpoints"


def checkpoint_path(state_dir: Path, episode_code: str, stage_id: str) -> Path:
    safe_stage = stage_id.replace("/", "_").replace("\\", "_")
    return checkpoint_dir(state_dir) / f"{episode_code}_{safe_stage}.json"


def _validate_status(status: str) -> None:
    if status not in CHECKPOINT_STATUSES:
        raise PipelineManifestError(
            f"非法 checkpoint status: {status}; 允许: {sorted(CHECKPOINT_STATUSES)}"
        )


def build_checkpoint(
    episode_code: str,
    stage_id: str,
    status: str,
    *,
    review_focus: list[str] | None = None,
    self_review: dict[str, Any] | None = None,
    success_criteria_met: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_status(status)
    return {
        "episode_code": episode_code,
        "stage_id": stage_id,
        "status": status,
        "updated_at": _now_iso(),
        "review_focus": list(review_focus or []),
        "self_review": dict(self_review or {}),
        "success_criteria_met": success_criteria_met,
        "metadata": dict(metadata or {}),
    }


def write_checkpoint(
    state_dir: Path,
    episode_code: str,
    stage_id: str,
    status: str,
    *,
    review_focus: list[str] | None = None,
    self_review: dict[str, Any] | None = None,
    success_criteria_met: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    payload = build_checkpoint(
        episode_code,
        stage_id,
        status,
        review_focus=review_focus,
        self_review=self_review,
        success_criteria_met=success_criteria_met,
        metadata=metadata,
    )
    path = checkpoint_path(state_dir, episode_code, stage_id)
    atomic_write_json(path, payload)
    return path


def read_checkpoint(state_dir: Path, episode_code: str, stage_id: str) -> dict[str, Any] | None:
    path = checkpoint_path(state_dir, episode_code, stage_id)
    if not path.is_file():
        return None
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else None


def _load_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint_status(state_dir: Path, episode_code: str, stage_id: str) -> str | None:
    checkpoint = read_checkpoint(state_dir, episode_code, stage_id)
    if checkpoint is None:
        return None
    status = checkpoint.get("status")
    return status if isinstance(status, str) else None


def stage_is_completed(state_dir: Path, episode_code: str, stage_id: str) -> bool:
    return checkpoint_status(state_dir, episode_code, stage_id) == CHECKPOINT_COMPLETED


def is_stage_terminal(state_dir: Path, episode_code: str, stage_id: str) -> bool:
    status = checkpoint_status(state_dir, episode_code, stage_id)
    return status in CHECKPOINT_TERMINAL_STATUSES


def resume_from(state_dir: Path, episode_code: str, step_ids: list[str]) -> str | None:
    """返回应从哪个阶段开始续跑。

    规则：从第一个 status 不是 completed 的阶段开始。若全部 completed 返回 None。
    """
    for stage_id in step_ids:
        status = checkpoint_status(state_dir, episode_code, stage_id)
        if status != CHECKPOINT_COMPLETED:
            return stage_id
    return None
