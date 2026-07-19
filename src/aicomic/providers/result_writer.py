from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.core.models import JobRecord
from aicomic.utils.atomic_io import atomic_write_json


COMPLETED_STATUSES = {"succeeded", "cached", "skipped"}


def resolve_next_status(request: dict[str, Any]) -> tuple[str, str, bool, int]:
    request_status = str(request.get("request_status", "ready"))
    payload = request.get("payload", {})
    output_path = Path(str(payload.get("output_path", "")))
    output_exists = output_path.exists()
    output_size = output_path.stat().st_size if output_exists else 0

    if request_status == "blocked":
        return "manual_required", "provider_blocked", output_exists, output_size
    if output_exists and output_size > 0:
        return "succeeded", "output_ready", output_exists, output_size
    if output_exists and output_size == 0:
        return "manual_required", "empty_output", output_exists, output_size
    return "manual_required", "missing_output", output_exists, output_size


def build_provider_result_writeback(
    provider_requests: dict[str, Any],
    jobs: list[JobRecord],
) -> tuple[dict[str, Any], list[JobRecord]]:
    requests_by_job_id = {
        str(request.get("payload", {}).get("job_id")): request
        for request in provider_requests.get("requests", [])
    }
    updated_jobs: list[JobRecord] = []
    updates: list[dict[str, Any]] = []

    for job in jobs:
        request = requests_by_job_id.get(job.job_id)
        if request is None:
            updated_jobs.append(job)
            updates.append(
                {
                    "job_id": job.job_id,
                    "episode_code": job.episode_code,
                    "job_type": job.job_type,
                    "provider": job.provider,
                    "previous_status": job.status,
                    "next_status": job.status,
                    "reason": "request_not_found",
                    "output_exists": False,
                    "output_size": 0,
                    "output_path": "",
                }
            )
            continue

        next_status, reason, output_exists, output_size = resolve_next_status(request)
        payload = request.get("payload", {})
        updated_jobs.append(
            JobRecord(
                job_id=job.job_id,
                episode_code=job.episode_code,
                job_type=job.job_type,
                provider=job.provider,
                status=next_status,
            )
        )
        updates.append(
            {
                "job_id": job.job_id,
                "episode_code": job.episode_code,
                "job_type": job.job_type,
                "provider": job.provider,
                "previous_status": job.status,
                "next_status": next_status,
                "reason": reason,
                "output_exists": output_exists,
                "output_size": output_size,
                "output_path": str(payload.get("output_path", "")),
            }
        )

    succeeded_count = sum(1 for item in updated_jobs if item.status in COMPLETED_STATUSES)
    manual_required_count = sum(1 for item in updated_jobs if item.status == "manual_required")
    changed_count = sum(1 for item in updates if item["previous_status"] != item["next_status"])
    report = {
        "request_count": len(requests_by_job_id),
        "job_count": len(jobs),
        "changed_count": changed_count,
        "succeeded_count": succeeded_count,
        "manual_required_count": manual_required_count,
        "updates": updates,
        "recommendations": build_writeback_recommendations(manual_required_count, changed_count),
    }
    return report, updated_jobs


def build_writeback_recommendations(manual_required_count: int, changed_count: int) -> list[str]:
    recommendations: list[str] = []
    if manual_required_count > 0:
        recommendations.append("仍有任务缺少实际产物，需要继续网页生成或补充 API 调用结果。")
    if changed_count > 0:
        recommendations.append("任务状态已根据产物扫描结果刷新，建议后续使用同步后的任务包续跑。")
    if manual_required_count == 0:
        recommendations.append("Provider 产物已全部到位，可进入预览/正式渲染。")
    return recommendations


def write_provider_writeback_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, report)
