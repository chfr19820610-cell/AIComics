"""管线协调器 — ACOM-0.6.0 P0-1/2/3.

把"管线是什么"从 Python 硬编码提升为声明式清单（config/pipelines/*.yaml），
阶段流转、人工审核门、checkpoint 自检、断点续跑全部由本协调器统一驱动。
episode_lifecycle / 外部调用方通过本协调器读清单决定下一步，改管线只改 YAML。

不变量：
  - 阶段顺序来自清单（stages 数组顺序），非硬编码。
  - 门禁阶段（human_approval_default=true）未批准前无法推进。
  - 每阶段完成写 checkpoint；断点续跑基于 checkpoint。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aicomic.core.approval_gate import (
    HumanApprovalRequiredError,
    approve_stage,
    complete_stage,
    is_stage_approved,
    mark_awaiting_human,
    require_stage_approved,
)
from aicomic.core.checkpoint_store import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    checkpoint_status,
    write_checkpoint,
)
from aicomic.core.pipeline_manifest import (
    CHECKPOINT_IN_PROGRESS,
    PipelineManifest,
    PipelineManifestError,
    get_pipeline_manifest,
)


@dataclass
class StageAdvanceResult:
    episode_code: str
    current_stage: str
    next_stage: str | None
    status: str
    required_human_approval: bool = False
    warnings: list[str] = field(default_factory=list)


class PipelineCoordinator:
    """基于声明式清单的漫剧单集管线协调器。"""

    def __init__(self, state_dir: Path, manifest: PipelineManifest | None = None) -> None:
        self.state_dir = state_dir
        self.manifest = manifest or get_pipeline_manifest()
        self.step_ids = self.manifest.step_ids

    # ---- 查询 ----

    def stage_status(self, episode_code: str, stage_id: str) -> str:
        return checkpoint_status(self.state_dir, episode_code, stage_id) or "not_started"

    def stage_approved(self, episode_code: str, stage_id: str) -> bool:
        return is_stage_approved(self.state_dir, episode_code, stage_id)

    def current_stage(self, episode_code: str) -> str | None:
        """返回下一个应处理的阶段（第一个非 completed，或 completed 但门禁未批准的阶段）。全完成返回 None。"""
        for stage_id in self.step_ids:
            status = self.stage_status(episode_code, stage_id)
            if status != CHECKPOINT_COMPLETED:
                return stage_id
            # 门禁阶段 completed 但 human_approved 未置位 → 视为未完成（防直写绕过）
            if (
                self.manifest.stage(stage_id).requires_human_approval
                and not self.stage_approved(episode_code, stage_id)
            ):
                return stage_id
        return None

    # ---- 推进 ----

    def begin_stage(self, episode_code: str, stage_id: str) -> StageAdvanceResult:
        """标记阶段开始（in_progress）。"""
        stage = self.manifest.stage(stage_id)
        write_checkpoint(
            self.state_dir,
            episode_code,
            stage_id,
            CHECKPOINT_IN_PROGRESS,
            review_focus=stage.review_focus,
            success_criteria_met=None,
            metadata={"pipeline": self.manifest.pipeline_id},
        )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_IN_PROGRESS,
        )

    def complete_stage(
        self,
        episode_code: str,
        stage_id: str,
        *,
        self_review: dict[str, object] | None = None,
    ) -> StageAdvanceResult:
        """完成一个阶段（写 checkpoint）。门禁阶段自动锁 awaiting_human。"""
        try:
            complete_stage(
                self.state_dir,
                episode_code,
                stage_id,
                manifest=self.manifest,
                self_review=self_review,
            )
        except HumanApprovalRequiredError as exc:
            return StageAdvanceResult(
                episode_code=episode_code,
                current_stage=stage_id,
                next_stage=None,
                status=CHECKPOINT_AWAITING_HUMAN,
                required_human_approval=True,
                warnings=[str(exc)],
            )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_COMPLETED,
        )

    def approve_stage(
        self,
        episode_code: str,
        stage_id: str,
        *,
        reviewer: str,
        notes: str = "",
    ) -> StageAdvanceResult:
        """人工批准门禁阶段，放行到下一阶段。每门独立批准。"""
        approve_stage(
            self.state_dir,
            episode_code,
            stage_id,
            reviewer=reviewer,
            notes=notes,
        )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_COMPLETED,
        )

    def advance(self, episode_code: str) -> StageAdvanceResult:
        """自动推进：校验门禁并给出下一步。

        若当前阶段已被锁定为 awaiting_human（门禁阶段完成但未人工批准），
        抛 HumanApprovalRequiredError（硬门禁：未批准任何路径都无法推进）。
        若当前阶段是尚未开始的下一阶段，直接放行进入。
        """
        current = self.current_stage(episode_code)
        if current is None:
            return StageAdvanceResult(
                episode_code=episode_code,
                current_stage="",
                next_stage=None,
                status="all_completed",
            )
        status = self.stage_status(episode_code, current)
        # 硬门禁：门禁阶段若已产出（awaiting_human 或 被直写 completed 绕过），
        # 只要 human_approved 标志未置位即拦截——不依赖 status 值（防 B3/R2 绕过）。
        if self.manifest.stage(current).requires_human_approval and status in (
            CHECKPOINT_AWAITING_HUMAN,
            CHECKPOINT_COMPLETED,
        ) and not self.stage_approved(episode_code, current):
            require_stage_approved(self.state_dir, episode_code, current, self.manifest)
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=current,
            next_stage=self._next_of(current),
            status=status,
        )

    def require_ready_to_proceed(self, episode_code: str, stage_id: str) -> None:
        """外部调用：试图进入/处理某阶段前，校验前置门禁已放行。"""
        require_stage_approved(self.state_dir, episode_code, stage_id, self.manifest)

    # ---- 内部 ----

    def _next_of(self, stage_id: str) -> str | None:
        index = self.step_ids.index(stage_id)
        return self.step_ids[index + 1] if index + 1 < len(self.step_ids) else None
