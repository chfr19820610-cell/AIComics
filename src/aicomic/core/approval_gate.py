"""人类审核门硬门禁 — ACOM-0.6.0 P0-2.

分镜（shot_breakdown）与素材（asset_generation）两个高成本创意节点设
human_approval_default: true。未人工批准前，该阶段 checkpoint 锁
awaiting_human，任何路径都无法推进到下一阶段；每门独立批准。

核心不变量（grep 验证）：
  - 门禁阶段 status 未 approved → advance_stage 抛 HumanApprovalRequiredError
  - 每门独立批准（approved_gate 只影响当前门，不覆盖后续门）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aicomic.core.checkpoint_store import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    read_checkpoint,
    write_checkpoint,
)
from aicomic.core.pipeline_manifest import (
    PipelineManifest,
    PipelineManifestError,
)


@dataclass(frozen=True)
class ApprovalRecord:
    stage_id: str
    approved: bool
    reviewer: str
    approved_at: str


class HumanApprovalRequiredError(PipelineManifestError):
    """门禁阶段尚未人工批准，禁止推进到下一阶段。"""


def _approved_flag(checkpoint: dict[str, object] | None) -> bool:
    if not checkpoint:
        return False
    self_review = checkpoint.get("self_review")
    if isinstance(self_review, dict):
        if self_review.get("human_approved") is True:
            return True
    metadata = checkpoint.get("metadata")
    if isinstance(metadata, dict):
        if metadata.get("human_approved") is True:
            return True
    return False


def is_stage_approved(state_dir: Path, episode_code: str, stage_id: str) -> bool:
    return _approved_flag(read_checkpoint(state_dir, episode_code, stage_id))


def stage_holds_human_approval(manifest: PipelineManifest, stage_id: str) -> bool:
    try:
        return manifest.requires_human_approval(stage_id)
    except PipelineManifestError:
        return False


def require_stage_approved(
    state_dir: Path, episode_code: str, stage_id: str, manifest: PipelineManifest
) -> None:
    """硬门禁：若阶段是门禁阶段且尚未批准，抛 HumanApprovalRequiredError。"""
    if not stage_holds_human_approval(manifest, stage_id):
        return
    if not is_stage_approved(state_dir, episode_code, stage_id):
        raise HumanApprovalRequiredError(
            f"阶段 {stage_id} 为人类审核门禁，未人工批准前禁止推进（episode={episode_code}）"
        )


def mark_awaiting_human(
    state_dir: Path,
    episode_code: str,
    stage_id: str,
    *,
    manifest: PipelineManifest,
    self_review: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> Path:
    """阶段完成后若需人工审核，把状态落为 awaiting_human（锁死，不可推进）。"""
    review_focus: list[str] = []
    try:
        review_focus = manifest.stage(stage_id).review_focus
    except PipelineManifestError:
        review_focus = []
    return write_checkpoint(
        state_dir,
        episode_code,
        stage_id,
        CHECKPOINT_AWAITING_HUMAN,
        review_focus=review_focus,
        self_review=dict(self_review or {}),
        metadata=dict(metadata or {}),
    )


def approve_stage(
    state_dir: Path,
    episode_code: str,
    stage_id: str,
    *,
    reviewer: str,
    approved_at: str | None = None,
    notes: str = "",
) -> Path:
    """人工批准一个门禁阶段；批准后该门放行，断点续跑可推进到下一阶段。

    每门独立批准：本函数只更新当前阶段，不触碰任何后续阶段。
    """
    existing = read_checkpoint(state_dir, episode_code, stage_id) or {}
    self_review = dict(existing.get("self_review") or {})
    self_review["human_approved"] = True
    self_review["human_approved_at"] = approved_at or existing.get("updated_at", "")
    self_review["reviewer"] = reviewer
    self_review["approval_notes"] = notes

    metadata = dict(existing.get("metadata") or {})
    metadata["human_approved"] = True
    metadata["approval_notes"] = notes

    return write_checkpoint(
        state_dir,
        episode_code,
        stage_id,
        CHECKPOINT_COMPLETED,
        review_focus=existing.get("review_focus"),
        self_review=self_review,
        success_criteria_met=True,
        metadata=metadata,
    )


def complete_stage(
    state_dir: Path,
    episode_code: str,
    stage_id: str,
    *,
    manifest: PipelineManifest,
    self_review: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> Path:
    """普通阶段完成写 checkpoint（completed）。

    若阶段是门禁阶段，则落 awaiting_human 并抛 HumanApprovalRequiredError，
    强制人工审核后才放行（P0-2 硬门禁）。
    """
    if stage_holds_human_approval(manifest, stage_id):
        path = mark_awaiting_human(
            state_dir,
            episode_code,
            stage_id,
            manifest=manifest,
            self_review=self_review,
            metadata=metadata,
        )
        raise HumanApprovalRequiredError(
            f"阶段 {stage_id} 为人类审核门禁，已锁定 awaiting_human，"
            f"请调用 approve_stage 批准后推进（episode={episode_code}）"
        )
    review_focus: list[str] = []
    try:
        review_focus = manifest.stage(stage_id).review_focus
    except PipelineManifestError:
        review_focus = []
    return write_checkpoint(
        state_dir,
        episode_code,
        stage_id,
        CHECKPOINT_COMPLETED,
        review_focus=review_focus,
        self_review=dict(self_review or {}),
        metadata=dict(metadata or {}),
    )
