from __future__ import annotations

from typing import Any


def build_execution_queue_summary(queue_history: list[dict[str, Any]]) -> dict[str, Any]:
    priority_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    execution_status_counts: dict[str, int] = {}
    approval_required_count = 0
    completed_count = 0
    failed_count = 0
    running_count = 0
    for item in queue_history:
        priority = str(item.get("priority", "unknown"))
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        queue_status = str(item.get("queue_status", "unknown"))
        status_counts[queue_status] = status_counts.get(queue_status, 0) + 1
        execution_status = str(item.get("execution_status", "unknown"))
        execution_status_counts[execution_status] = execution_status_counts.get(execution_status, 0) + 1
        if bool(item.get("requires_manual_approval", False)):
            approval_required_count += 1
        if queue_status == "completed" or execution_status == "completed":
            completed_count += 1
        if queue_status == "failed" or execution_status == "failed":
            failed_count += 1
        if queue_status in {"queued", "running"} or execution_status in {"ready", "running", "waiting_for_approval"}:
            running_count += 1
    latest_item = queue_history[0] if queue_history else {}
    queue_count = len(queue_history)
    return {
        "queued_count": queue_count,
        "running_count": running_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "approval_required_count": approval_required_count,
        "priority_counts": priority_counts,
        "status_counts": status_counts,
        "execution_status_counts": execution_status_counts,
        "completion_rate": round((completed_count / max(1, queue_count)) * 100, 1),
        "failure_rate": round((failed_count / max(1, queue_count)) * 100, 1),
        "latest_queue_run_id": str(latest_item.get("queue_run_id", "")),
        "latest_plan_key": str(latest_item.get("plan_key", "")),
        "latest_priority": str(latest_item.get("priority", "")),
        "latest_queue_status": str(latest_item.get("queue_status", "")),
    }


def build_execution_failure_breakdown(queue_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in queue_history:
        queue_status = str(item.get("queue_status", ""))
        execution_status = str(item.get("execution_status", ""))
        if queue_status != "failed" and execution_status != "failed":
            continue
        result_note = str(item.get("result_note", "")).strip()
        failure_reason = result_note if result_note else "unknown_failure"
        bucket = buckets.setdefault(
            failure_reason,
            {
                "dimension": "result_note",
                "name": failure_reason,
                "failed_count": 0,
                "priorities": set(),
                "targets": set(),
                "latest_queue_run_id": "",
                "latest_completed_at": "",
            },
        )
        bucket["failed_count"] += 1
        priority = str(item.get("priority", ""))
        if priority:
            bucket["priorities"].add(priority)
        target = str(item.get("target", ""))
        if target:
            bucket["targets"].add(target)
        completed_at = str(item.get("completed_at", "")) or str(item.get("updated_at", ""))
        if completed_at >= str(bucket.get("latest_completed_at", "")):
            bucket["latest_queue_run_id"] = str(item.get("queue_run_id", ""))
            bucket["latest_completed_at"] = completed_at

    total_failed = sum(int(item.get("failed_count", 0)) for item in buckets.values())
    items = []
    for bucket in buckets.values():
        items.append(
            {
                "dimension": str(bucket.get("dimension", "")),
                "name": str(bucket.get("name", "")),
                "failed_count": int(bucket.get("failed_count", 0)),
                "share_rate": round((int(bucket.get("failed_count", 0)) / max(1, total_failed)) * 100, 1),
                "priority_count": len(bucket.get("priorities", set())),
                "target_count": len(bucket.get("targets", set())),
                "latest_queue_run_id": str(bucket.get("latest_queue_run_id", "")),
                "latest_completed_at": str(bucket.get("latest_completed_at", "")),
            }
        )
    items.sort(
        key=lambda item: (
            -int(item.get("failed_count", 0)),
            str(item.get("name", "")),
        )
    )
    return items[:10]


def build_execution_operations_report(
    queue_summary: dict[str, Any],
    queue_history: list[dict[str, Any]],
    failure_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    queued_count = int(queue_summary.get("queued_count", 0))
    running_count = int(queue_summary.get("running_count", 0))
    completed_count = int(queue_summary.get("completed_count", 0))
    failed_count = int(queue_summary.get("failed_count", 0))
    completion_rate = float(queue_summary.get("completion_rate", 0.0))
    failure_rate = float(queue_summary.get("failure_rate", 0.0))
    approval_required_count = int(queue_summary.get("approval_required_count", 0))
    latest_item = queue_history[0] if queue_history else {}

    if failure_rate >= 30:
        health_status = "critical"
    elif failure_rate > 0 or approval_required_count > max(1, queued_count // 2):
        health_status = "warning"
    else:
        health_status = "healthy"

    recommendations: list[str] = []
    if failure_breakdown:
        recommendations.append(f"Prioritize fixing failure reason: {failure_breakdown[0]['name']}.")
    if approval_required_count > 0:
        recommendations.append(f"Resolve {approval_required_count} approval-gated queue items.")
    if running_count > completed_count:
        recommendations.append("Increase execution throughput for running queue items.")
    if not recommendations:
        recommendations.append("Queue is stable. Continue monitoring execution throughput.")

    return {
        "health_status": health_status,
        "summary_cards": [
            {"key": "queued_count", "title": "Queued", "value": queued_count},
            {"key": "completed_count", "title": "Completed", "value": completed_count},
            {"key": "failed_count", "title": "Failed", "value": failed_count},
            {"key": "completion_rate", "title": "Completion Rate", "value": completion_rate},
            {"key": "failure_rate", "title": "Failure Rate", "value": failure_rate},
            {"key": "approval_required_count", "title": "Approval Required", "value": approval_required_count},
        ],
        "recommendations": recommendations,
        "top_failure_reason": (failure_breakdown[0] if failure_breakdown else {}).get("name", ""),
        "latest_queue_run_id": str(queue_summary.get("latest_queue_run_id", "")),
        "latest_queue_status": str(queue_summary.get("latest_queue_status", "")),
        "latest_execution_status": str(latest_item.get("execution_status", "")),
    }


def build_execution_operations_report_rows(
    queue_summary: dict[str, Any],
    failure_breakdown: list[dict[str, Any]],
    operations_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in list(operations_report.get("summary_cards", [])):
        rows.append(
            {
                "section": "summary_cards",
                "metric": str(card.get("title", "")),
                "value": str(card.get("value", "")),
                "extra": str(card.get("key", "")),
            }
        )
    rows.append(
        {
            "section": "health",
            "metric": "health_status",
            "value": str(operations_report.get("health_status", "")),
            "extra": str(operations_report.get("top_failure_reason", "")),
        }
    )
    for item in failure_breakdown:
        rows.append(
            {
                "section": "failure_breakdown",
                "metric": str(item.get("name", "")),
                "value": str(item.get("failed_count", 0)),
                "extra": f"share={item.get('share_rate', 0)}%; targets={item.get('target_count', 0)}",
            }
        )
    for recommendation in list(operations_report.get("recommendations", [])):
        rows.append(
            {
                "section": "recommendations",
                "metric": "recommendation",
                "value": recommendation,
                "extra": str(queue_summary.get("latest_queue_run_id", "")),
            }
        )
    return rows
