from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RETRYABLE_REASONS = {"missing_output", "empty_output", "provider_execution_failed", "provider_blocked"}


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_horror_regeneration_queue(
    episode_manifest: dict[str, Any],
    provider_writeback_report: dict[str, Any],
    provider_execution_report: dict[str, Any] | None = None,
    episode_code: str = "E01",
) -> dict[str, Any]:
    execution_by_job_id = {
        str(item.get("job_id", "")): item
        for item in (provider_execution_report or {}).get("results", [])
        if isinstance(item, dict)
    }
    shots_by_id = {}
    for episode in episode_manifest.get("episodes", []):
        if str(episode.get("episode_code", "")) != episode_code:
            continue
        shots_by_id = {
            str(shot.get("shot_id", "")): shot
            for shot in episode.get("shots", [])
            if isinstance(shot, dict)
        }
        break

    queue: list[dict[str, Any]] = []
    for update in provider_writeback_report.get("updates", []):
        if not isinstance(update, dict):
            continue
        next_status = str(update.get("next_status", ""))
        reason = str(update.get("reason", ""))
        job_id = str(update.get("job_id", ""))
        if next_status != "manual_required" and reason not in RETRYABLE_REASONS:
            continue
        shot_id = parse_shot_id_from_job_id(job_id)
        shot = shots_by_id.get(shot_id, {})
        execution = execution_by_job_id.get(job_id, {})
        queue.append(
            {
                "queue_id": f"REGEN_{job_id}",
                "job_id": job_id,
                "episode_code": str(update.get("episode_code", episode_code)),
                "shot_id": shot_id,
                "job_type": str(update.get("job_type", "")),
                "provider": str(update.get("provider", "")),
                "reason": reason,
                "next_status": next_status,
                "output_path": str(update.get("output_path", "")),
                "execution_status": str(execution.get("status", "")),
                "execution_error": str(execution.get("error", "")),
                "priority": str(shot.get("priority", "medium")),
                "horror_beat": str(shot.get("horror_beat", "")),
                "avoidance_strategy": str(shot.get("avoidance_strategy", "")),
                "continuity_anchor": str(shot.get("continuity_anchor", "")),
                "suggested_action": suggested_regeneration_action(update, execution),
            }
        )

    high_priority_count = sum(1 for item in queue if item["priority"] == "high")
    return {
        "episode_code": episode_code,
        "queue_count": len(queue),
        "high_priority_count": high_priority_count,
        "items": queue,
        "recommendations": build_regeneration_recommendations(len(queue), high_priority_count),
    }


def parse_shot_id_from_job_id(job_id: str) -> str:
    parts = job_id.split("_")
    if len(parts) >= 4:
        return parts[2]
    return ""


def suggested_regeneration_action(update: dict[str, Any], execution: dict[str, Any]) -> str:
    if str(execution.get("status", "")) == "failed":
        return "检查 Provider 错误后重试该镜头。"
    reason = str(update.get("reason", ""))
    if reason == "missing_output":
        return "重新执行该 Provider 请求，或手工补齐对应产物。"
    if reason == "empty_output":
        return "删除空文件后重新生成，避免状态误判。"
    if reason == "provider_blocked":
        return "先处理 Provider preflight 阻塞，再重试。"
    return "加入下一轮镜头重生成队列。"


def build_regeneration_recommendations(queue_count: int, high_priority_count: int) -> list[str]:
    if queue_count == 0:
        return ["没有发现需要重生成的镜头，可以进入样片审核和正式导出。"]
    recommendations = [f"当前有 {queue_count} 个任务需要重生成或手工处理。"]
    if high_priority_count:
        recommendations.append(f"优先处理 {high_priority_count} 个 high priority 镜头，它们通常影响开场钩子或幕尾反转。")
    recommendations.append("先重试图片和 TTS，再处理视频动效；正式样片可以先用静态镜头过审。")
    return recommendations


def write_horror_regeneration_queue(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
