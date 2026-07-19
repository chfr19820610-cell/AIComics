from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_batch_summary(batch_report: dict[str, Any]) -> dict[str, object]:
    step_results = batch_report.get("step_results", [])
    return {
        "batch_id": str(batch_report.get("batch_id", "")),
        "status": str(batch_report.get("status", "unknown")),
        "scope_type": str(batch_report.get("scope_type", "")),
        "scope_value": str(batch_report.get("scope_value", "")),
        "step_count": len(step_results),
        "completed_step_count": sum(
            1 for item in step_results
            if str(item.get("status")) not in ("failed", "planned")
        ),
        "real_step_count": sum(
            1 for item in step_results
            if str(item.get("status")) not in ("simulated", "failed", "planned")
        ),
        "failed_step_count": sum(
            1 for item in step_results
            if str(item.get("status")) == "failed"
        ),
        "next_actions": [],
    }


def write_batch_summary(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
