"""ShowAgent — SOP 第 6 章『多 Agent 编排（Transformer 闭环）』的工程化落地。

定位：把编排者+执行器收敛成单个 CLI 可驱动的入口：用 PipelineCoordinator 的
状态机逐阶段推进，直到人工卡点（awaiting_human）、输入缺失（needs_input）、
预算拦截（budget_stopped）、失败（failed）或全部完成（all_completed）。

- 不越过任何现有守门人（budget_sentinel/quality_gate/drift_gate 原样调用）；
- gate-protection（规格 §8 红线4）：checkpoint status=awaiting_human 或 门禁阶段
  completed-未批准时**不得 begin_stage 重放**（重复烧成本/重复人工）；
- 异常路径与 budget kill 必须显式写 checkpoint=failed，不得静默吞错（红线5）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.config import ProjectPaths
from aicomic.core.pipeline_coordinator import PipelineCoordinator
from aicomic.core.pipeline_manifest import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    CHECKPOINT_FAILED,
)
from aicomic.core.checkpoint_store import write_checkpoint
from aicomic.providers.executor import execute_provider_requests

PASSTHROUGH_STAGES = {"project_setup", "story_bible", "episode_outline"}


class ShowRunResult:
    def __init__(self, stop_reason: str, current_stage: str = "", message: str = "") -> None:
        self.stop_reason = stop_reason
        self.current_stage = current_stage
        self.message = message
        self.body: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"ShowRunResult(stop_reason={self.stop_reason!r}, current_stage={self.current_stage!r})"


class _NeedsInput(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class ShowAgent:
    def __init__(
        self,
        state_dir: str | Path = "",
        *,
        coordinator: PipelineCoordinator | None = None,
        budget_sentinel: Any | None = None,
        budget: dict[str, Any] | None = None,
        providers_config_path: Any | None = None,
        output_root: Any | None = None,
        handoff_writer: Any | None = None,
        self_reviewer: Any | None = None,
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir else ProjectPaths.state_dir()
        self.coordinator = coordinator if coordinator is not None else PipelineCoordinator(self.state_dir)
        self.budget_sentinel = budget_sentinel
        self.budget = budget if budget is not None else self._budget_snapshot()
        self.providers_config_path = providers_config_path
        self.output_root = output_root
        self.handoff_writer = handoff_writer
        self.self_reviewer = self_reviewer
        self.last_self_review: dict[str, Any] | None = None
        self._last_budget_stop = False
        self._stage_results: dict[str, dict[str, Any]] = {}

    def _budget_snapshot(self) -> dict[str, Any]:
        if self.budget_sentinel is None:
            return {"status": "unlimited"}
        status = self.budget_sentinel.dashboard.get_budget_status()
        return {
            "status": getattr(status, "status", "unknown"),
            "total_spent_cents": getattr(status, "total_spent_cents", 0),
            "total_budget_cents": getattr(status, "total_budget_cents", 0),
            "generation_count": getattr(status, "generation_count", 0),
        }

    # ---- 主循环 ----

    def run_until_human(self, episode_code: str, inputs: dict[str, Any], *, live: bool = False) -> ShowRunResult:
        try:
            for stage_id in self.coordinator.step_ids:
                requires = bool(self.coordinator.manifest.stage(stage_id).requires_human_approval)
                status = self.coordinator.stage_status(episode_code, stage_id)

                if status == CHECKPOINT_COMPLETED:
                    if requires and not self.coordinator.stage_approved(episode_code, stage_id):
                        return self._exit(episode_code, "awaiting_human", stage_id, "gate-unapproved")
                    continue
                if status == CHECKPOINT_AWAITING_HUMAN:
                    return self._exit(episode_code, "awaiting_human", stage_id, "checkpoint-awaiting")

                self.coordinator.begin_stage(episode_code, stage_id)
                try:
                    dispatch_out = self._dispatch(stage_id, episode_code, inputs, live)
                except _NeedsInput as exc:
                    return self._exit(episode_code, "needs_input", stage_id, exc.key)
                except Exception as exc:  # noqa: BLE001 — 任何失败必须显式落账（红线5）
                    write_checkpoint(
                        self.state_dir, episode_code, stage_id, CHECKPOINT_FAILED,
                        metadata={"error": repr(exc), "budget_status": self.budget},
                    )
                    return self._exit(episode_code, "failed", stage_id, repr(exc), failed_stage=stage_id, notes=repr(exc))
                self._stage_results[stage_id] = dispatch_out
                self.coordinator.complete_stage(episode_code, stage_id)

                if live and stage_id == "asset_generation" and self._last_budget_stop:
                    write_checkpoint(
                        self.state_dir, episode_code, stage_id, CHECKPOINT_FAILED,
                        metadata={"error": "budget_stopped", "budget_status": self.budget},
                    )
                    return self._exit(episode_code, "budget_stopped", stage_id, "live-provider-budget-kill")

                if self.coordinator.stage_status(episode_code, stage_id) == CHECKPOINT_AWAITING_HUMAN:
                    return self._exit(episode_code, "awaiting_human", stage_id)
            return self._exit(episode_code, "all_completed")
        except Exception as exc:  # noqa: BLE001 — 兜底：终态必须收敛
            return ShowRunResult("failed", "", repr(exc))

    # ---- 分发 ----

    def _dispatch(self, stage_id: str, episode_code: str, inputs: dict[str, Any], live: bool) -> dict[str, Any]:
        stage_inputs = inputs.get(stage_id, {}) if isinstance(inputs, dict) else {}
        manifest = self._episode_manifest(stage_inputs, inputs)

        if stage_id in PASSTHROUGH_STAGES:
            return {"status": "passed_through"}

        if stage_id == "shot_breakdown":
            blueprint = stage_inputs.get("blueprint") if isinstance(stage_inputs, dict) else None
            if not isinstance(blueprint, dict) or not blueprint:
                raise _NeedsInput("shot_breakdown.blueprint")
            return dict(
                self.coordinator.execute_shot_breakdown(
                    episode_code, blueprint,
                    template_name=str(stage_inputs.get("template_name", "")),
                    project_id=str(stage_inputs.get("project_id", "")),
                )
            )

        if stage_id == "asset_generation":
            if not isinstance(manifest, dict):
                raise _NeedsInput("asset_generation.episode_manifest")
            providers_config_path = str(stage_inputs.get("providers_config_path", "") or self.providers_config_path or "")
            output_root = str(stage_inputs.get("output_root", "") or self.output_root or "")
            built = dict(
                self.coordinator.execute_asset_generation(episode_code, manifest, providers_config_path, output_root)
            )
            if live:
                provider_requests = built.get("provider_requests")
                if isinstance(provider_requests, dict):
                    report = execute_provider_requests(
                        provider_requests,
                        Path(providers_config_path),
                        confirm_live=True,
                        budget_sentinel=self.budget_sentinel,
                    )
                    self._last_budget_stop = bool(report.get("stopped_by_budget_guard"))
                    built["execution_report"] = {k: v for k, v in report.items() if k != "results"}
            return built

        if stage_id == "tts_subtitle":
            if not isinstance(manifest, dict):
                raise _NeedsInput("tts_subtitle.episode_manifest")
            return dict(self.coordinator.execute_tts_subtitle(episode_code, manifest))

        if stage_id == "preview_render":
            render_plan = stage_inputs.get("render_plan") if isinstance(stage_inputs, dict) else None
            if not isinstance(render_plan, dict) or not render_plan:
                raise _NeedsInput("preview_render.render_plan")
            output_path = str(stage_inputs.get("output_path", "") or self.output_root or "")
            report_path = str(stage_inputs.get("report_path", "") or self.output_root or "")
            result = dict(
                self.coordinator.execute_preview_render(episode_code, render_plan, output_path, report_path)
            )
            # SOP §8.1：审片 Agent 审完 preview 才算闸门过（self_reviewer 注入点；失败 fail-soft）
            shots = render_plan.get("shots") if isinstance(render_plan.get("shots"), list) else []
            self.last_self_review = self._safe_self_review(shots)
            if self.last_self_review is not None:
                result["self_review"] = self.last_self_review
            return result

        if stage_id == "publish_pack":
            if not isinstance(manifest, dict):
                raise _NeedsInput("publish_pack.episode_manifest")
            return dict(self.coordinator.execute_publish_pack(episode_code, manifest))

        return {"status": "skipped_unknown_stage"}

    def _safe_self_review(self, shots: list[Any]) -> dict[str, Any] | None:
        if self.self_reviewer is None:
            return None
        try:
            raw = self.self_reviewer(list(shots))
            return raw if isinstance(raw, dict) else {"verdict": "error", "issues": [], "model": ""}
        except Exception as exc:  # noqa: BLE001 — 自审失败不反噬主流程
            return {"verdict": "error", "issues": [{"code": "self_review_failed", "message": repr(exc)}], "model": ""}

    def _episode_manifest(self, stage_inputs: dict[str, Any], inputs: dict[str, Any]) -> Any:
        if isinstance(stage_inputs, dict) and isinstance(stage_inputs.get("episode_manifest"), dict):
            return stage_inputs["episode_manifest"]
        if isinstance(inputs, dict) and isinstance(inputs.get("episode_manifest"), dict):
            return inputs["episode_manifest"]
        shot_result = self._stage_results.get("shot_breakdown", {})
        return shot_result.get("shot_manifest")

    def _budget_status(self) -> dict[str, Any]:
        return self.budget

    # ---- 出口（统一写交接包）----

    def _exit(self, episode_code: str, stop_reason: str, current_stage: str = "", message: str = "", *, failed_stage: str | None = None, notes: str | None = None) -> ShowRunResult:
        result = ShowRunResult(stop_reason, current_stage, message)
        try:
            from aicomic.core.handoff import build_handoff_record, render_handoff_markdown, write_handoff

            record = build_handoff_record(
                episode_code, self.coordinator, budget=self.budget, failed_stage=failed_stage, notes=notes,
            )
            text = render_handoff_markdown(record)
            if self.handoff_writer is not None:
                self.handoff_writer(text, episode_code)
            else:
                write_handoff(text, episode_code, handoff_dir=self.state_dir / "handoff")
        except Exception:
            pass  # 交接包写失败不反噬主流程
        return result
