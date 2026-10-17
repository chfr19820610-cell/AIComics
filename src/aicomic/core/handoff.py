"""交接包（handoff）— SOP 第 8 章/§7.6 的工程化落地。

- 数据层：build_handoff_record() 把信控级机的真实状态（含审批、门禁需求）折叠成
  可序列化的 handoff dict——不读渲染文件系统，全部来自 PipelineCoordinator 状态；
- render_handoff_markdown() 把 record 渲染成可直接发到微信群/飞书群的 markdown 文本；
- write_handoff() 原子写 handoff 目录（默认 <state>/handoff/<episode>_handoff.md），
  供人工续作无缝衔接。

语义约定：
- completed 非门禁阶段视作"放行"（human_approved=True），不要求每阶段都过卡点；
- failed_stage 登记责任断点：该阶段标记 failed 并把 notes 挂在其备注里（附录 J 续作语义）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_text


def build_handoff_record(
    episode_code: str,
    coordinator: Any,
    *,
    budget: dict[str, Any] | None = None,
    failed_stage: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for stage_id in coordinator.step_ids:
        requires = bool(coordinator.manifest.stage(stage_id).requires_human_approval)
        raw_status = coordinator.stage_status(episode_code, stage_id)
        status = "pending" if raw_status == "not_started" else raw_status
        approved = False
        if status == "completed":
            approved = coordinator.stage_approved(episode_code, stage_id) or not requires
        row: dict[str, Any] = {
            "stage_id": stage_id,
            "status": status,
            "requires_human_approval": requires,
            "human_approved": approved,
            "notes": None,
        }
        if failed_stage and stage_id == failed_stage:
            row["status"] = "failed"
            row["notes"] = notes
        rows.append(row)
    return {
        "schema_version": 1,
        "episode": episode_code,
        "stages": rows,
        "budget": dict(budget) if budget else {"status": "unlimited"},
    }


def render_handoff_markdown(record: dict[str, Any]) -> str:
    lines: list[str] = [f"# 交接包：{record['episode']}", ""]
    budget = record.get("budget") or {}
    if record.get("failed_stage"):
        lines += [f"- 责任断点：`{record['failed_stage']}`（续作入口：begin_stage 该阶段直接重跑）", ""]
    lines += [f"- budget 汇报：status={budget.get('status')}", ""]
    lines += ["| 标志 | 阶段 | 状态 | 需人工 | 已批准 |", "| --- | --- | --- | --- | --- |"]
    for row in record.get("stages", []):
        flag = "⚠" if (
            row["status"] == "failed"
            or row["status"] == "awaiting_human"
            or (row["requires_human_approval"] and not row["human_approved"])
        ) else "　"
        lines.append(
            f"| {flag} | {row['stage_id']} | {row['status']} | {row['requires_human_approval']} | {row['human_approved']} |"
        )
    lines += [
        "",
        "## 交接要点（定稿文案，直接落入实现）",
        "",
        "- 中文文档用全角标点；代码与命令用半角（《中文文案排版指北》口径）。",
        "- 引用 SOP 章节保留 `§x.y` 原编号；示例命令须可直接执行。",
        "- 本文件由 show-handoff / ShowAgent 出口自动生成；人工续作以上表 ⚠ 行为准。",
        "",
        "## 续作指引",
        "",
        "- 续作入口：`acomic show-run <episode> --confirm-live`（预算哨兵默认读 `AICOMIC_BUDGET_CENTS`）。",
        "- checkpoint status=failed 的阶段：begin_stage 该阶段即可重跑（CHECKPOINT_FAILED 语义）。",
        "- 平台发布当前 disabled：SOP §10 #2 逐平台手动入审，shim 留给发布阶段实现。",
        "",
    ]
    return "\n".join(lines) + "\n"


def handoff_path(episode_code: str, handoff_dir: Path | None = None) -> Path:
    if handoff_dir is None:
        from aicomic.core.config import ProjectPaths

        handoff_dir = ProjectPaths.state_dir() / "handoff"
    return Path(handoff_dir) / f"{episode_code}_handoff.md"


def write_handoff(markdown: str, episode_code: str, *, handoff_dir: Path | None = None) -> Path:
    target = handoff_path(episode_code, handoff_dir)
    atomic_write_text(target, markdown)
    return target
