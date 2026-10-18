"""任务级交接契约（SOP §6.3：输入→输出→工具→边界→验收→失败策略，机器可读）。"""
from __future__ import annotations

from typing import Any

MAX_SHOT_DURATION_S = 8.0  # §4④ 一镜一动作/时长红线


def build_task_contract(
    *,
    from_agent: str,
    to_agent: str,
    artifact: str,
    shot_id: str,
    duration_s: float,
    refs: dict[str, str],
    style_tokens: str,
    motion_prompt: str,
    max_roll: int,
    model_route: str,
    acceptance: list[str],
    failure_policy: str,
    audio_line: str = "",
) -> dict[str, Any]:
    return {
        "from": from_agent,
        "to": to_agent,
        "artifact": artifact,
        "payload": {
            "shot_id": shot_id,
            "duration_s": duration_s,
            "refs": dict(refs),
            "style_tokens": style_tokens,
            "motion_prompt": motion_prompt,
            "audio_line": audio_line,
            "budget": {"max_roll": max_roll, "model_route": model_route},
        },
        "acceptance": list(acceptance),
        "failure_policy": failure_policy,
    }


def validate_task_contract(contract: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    for key in ("from", "to", "artifact", "payload", "acceptance", "failure_policy"):
        if key not in contract:
            violations.append(f"missing top-level field: {key}")
    payload = contract.get("payload") if isinstance(contract, dict) else None
    if not isinstance(payload, dict):
        violations.append("payload must be dict")
    else:
        for key in ("shot_id", "duration_s", "refs", "style_tokens", "motion_prompt", "budget"):
            if key not in payload:
                violations.append(f"missing payload field: {key}")
        duration = payload.get("duration_s")
        if isinstance(duration, (int, float)) and duration > MAX_SHOT_DURATION_S:
            violations.append(f"duration_s={duration} 超红线 {MAX_SHOT_DURATION_S}s（一镜一动作）")
        budget = payload.get("budget")
        if isinstance(budget, dict):
            if "max_roll" not in budget:
                violations.append("missing payload.budget.max_roll（预算哨兵参数）")
            if "model_route" not in budget:
                violations.append("missing payload.budget.model_route（路由）")
        elif budget is not None:
            violations.append("budget must be dict")
    acceptance = contract.get("acceptance")
    if isinstance(acceptance, list) and not acceptance:
        violations.append("acceptance 不允许为空（gate 不可自夸）")
    return {"ok": not violations, "violations": violations}
