"""缺陷看板（SOP §12：缺陷反哺——checkpoint failed/awaiting_human 汇总）。

扫描 state/checkpoints/*.json；坏文件 → skipped 计数（不静默）；markdown 简版给交接。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_json, atomic_write_text


def _entries_from(state_dir: Path) -> tuple[list[dict[str, Any]], int]:
    cp_dir = state_dir / "checkpoints"
    entries: list[dict[str, Any]] = []
    skipped = 0
    if not cp_dir.is_dir():
        return entries, 0
    for path in sorted(cp_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        status = str(data.get("status", ""))
        if status not in {"failed", "awaiting_human"}:
            continue
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        entries.append({
            "episode": str(data.get("episode_code", "")),
            "stage_id": str(data.get("stage_id", "")),
            "status": status,
            "failures": [metadata.get("error", "")] if metadata.get("error") else [],
        })
    return entries, skipped


def build_defect_board(state_dir: Path) -> dict[str, Any]:
    entries, skipped = _entries_from(Path(state_dir))
    by_stage: dict[str, int] = {}
    for item in entries:
        by_stage[item["stage_id"]] = by_stage.get(item["stage_id"], 0) + 1
    return {
        "total_defects": len(entries),
        "skipped": skipped,
        "entries": entries,
        "by_stage": by_stage,
    }


def render_defect_board_markdown(board: dict[str, Any]) -> str:
    lines = ["# 缺陷看板", "", f"- 待反哺缺陷总数：{board['total_defects']}（跳过坏文件 {board['skipped']} 个）", ""]
    lines.append("| 阶段 | 数量 |")
    lines.append("| --- | --- |")
    for stage, count in sorted(board.get("by_stage", {}).items(), key=lambda kv: -kv[1]):
        lines.append(f"| {stage} | {count} |")
    lines.append("")
    for item in board.get("entries", []):
        note = "; ".join(str(f) for f in item["failures"]) or "-"
        lines.append(f"- {item['episode']} {item['stage_id']} [{item['status']}] {note}")
    lines.append("")
    return "\n".join(lines)


def write_defect_board(state_dir: str | Path, out_path: str | Path) -> tuple[Path, dict[str, Any]]:
    state = Path(state_dir)
    board = build_defect_board(state)
    target = Path(out_path)
    atomic_write_json(target, board)
    md_target = target.with_suffix(".md")
    atomic_write_text(md_target, render_defect_board_markdown(board))
    return target, board
