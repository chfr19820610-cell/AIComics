from __future__ import annotations

from typing import Any

from aicomic.core.config import ProjectPaths
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema
from web.backend.services.batch_history_service import (
    ensure_batch_execution_preview_schema,
    ensure_batch_execution_queue_schema,
    write_batch_execution_preview_run,
    write_batch_execution_queue_run,
)
from web.backend.settings import WebSettings


def make_plan_key(prefix: str, value: str) -> str:
    safe_value = "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")
    return f"{prefix}_{safe_value or 'all'}"


def build_execution_steps(source_type: str, target: str, command: str) -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "step_key": "validate_target",
            "title": "Validate target scope",
            "action": f"Confirm target exists before running {command}.",
        },
        {
            "order": 2,
            "step_key": "dry_run",
            "title": "Run dry-run preview",
            "action": f"Preview {source_type} action for {target}.",
        },
        {
            "order": 3,
            "step_key": "record_result",
            "title": "Record execution result",
            "action": "Write execution summary and audit note after preview.",
        },
    ]


def build_execution_plan_templates(
    auto_disposition_templates: list[dict[str, Any]],
    dispatch_priority_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for template in auto_disposition_templates:
        template_key = str(template.get("template_key", "auto_disposition"))
        target = str(template.get("target", "all"))
        suggested_command = str(template.get("suggested_command", "continue_monitoring"))
        execution_command = f"{suggested_command} --target {target} --dry-run"
        steps = build_execution_steps("auto_disposition", target, suggested_command)
        plans.append(
            {
                "plan_key": make_plan_key("execute", f"{template_key}_{target}"),
                "source_type": "auto_disposition_template",
                "source_key": template_key,
                "title": f"Dry-run {template.get('title', 'Auto Disposition')}",
                "priority": str(template.get("priority", "P2")),
                "target": target,
                "mode": "dry_run",
                "execution_command": execution_command,
                "estimated_step_count": len(steps),
                "requires_manual_approval": str(template.get("priority", "P2")) in {"P0", "P1"},
                "steps": steps,
            }
        )

    for item in dispatch_priority_plan[:3]:
        target = str(item.get("target", "all"))
        priority = str(item.get("recommended_priority", "P2"))
        execution_command = f"preview_dispatch_priority --target {target} --priority {priority} --dry-run"
        steps = build_execution_steps("dispatch_priority", target, "preview_dispatch_priority")
        plans.append(
            {
                "plan_key": make_plan_key("dispatch", target),
                "source_type": "dispatch_priority",
                "source_key": str(item.get("dimension", "dispatch")),
                "title": f"Dry-run dispatch for {target}",
                "priority": priority,
                "target": target,
                "mode": "dry_run",
                "execution_command": execution_command,
                "estimated_step_count": len(steps),
                "requires_manual_approval": priority in {"P0", "P1"},
                "steps": steps,
            }
        )

    if not plans:
        steps = build_execution_steps("monitor", "all", "continue_monitoring")
        plans.append(
            {
                "plan_key": "execute_monitor_only",
                "source_type": "monitor",
                "source_key": "monitor_only",
                "title": "Dry-run monitor only",
                "priority": "P3",
                "target": "all",
                "mode": "dry_run",
                "execution_command": "continue_monitoring --dry-run",
                "estimated_step_count": len(steps),
                "requires_manual_approval": False,
                "steps": steps,
            }
        )
    return plans[:8]


def resolve_execution_plan_template(
    execution_plan_templates: list[dict[str, Any]],
    plan_key: str,
    target: str = "",
) -> dict[str, Any]:
    selected_plan = next((item for item in execution_plan_templates if str(item.get("plan_key", "")) == plan_key), None)
    if selected_plan is None and target:
        selected_plan = next((item for item in execution_plan_templates if str(item.get("target", "")) == target), None)
    if selected_plan is None:
        raise ValueError(f"Execution plan `{plan_key}` not found.")
    return selected_plan


def load_execution_plan_templates(settings: WebSettings) -> list[dict[str, Any]]:
    from web.backend.services.report_service import load_batch_summary

    batches_payload = load_batch_summary(settings, include_history=False)
    return list(batches_payload.get("multi_batch_summary", {}).get("execution_plan_templates", []))


def preview_batch_execution_plan(
    settings: WebSettings,
    plan_key: str,
    user_id: str,
    target: str = "",
    mode: str = "dry_run",
) -> dict[str, Any]:
    execution_plan_templates = load_execution_plan_templates(settings)
    selected_plan = resolve_execution_plan_template(execution_plan_templates, plan_key, target)
    effective_plan = {
        **selected_plan,
        "target": target or str(selected_plan.get("target", "")),
        "mode": mode or str(selected_plan.get("mode", "dry_run")),
    }
    preview_summary = (
        f"mode={effective_plan['mode']};"
        f" priority={effective_plan.get('priority', '')};"
        f" target={effective_plan['target']};"
        f" estimated_steps={effective_plan.get('estimated_step_count', 0)}"
    )
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_preview_schema(connection)
    preview_run = write_batch_execution_preview_run(
        connection,
        user_id,
        effective_plan,
        "preview_ready",
        preview_summary,
    )
    connection.close()
    return {
        "status": "preview_ready",
        "preview_run_id": preview_run["preview_run_id"],
        "created_at": preview_run["created_at"],
        "plan_key": str(effective_plan.get("plan_key", "")),
        "source_type": str(effective_plan.get("source_type", "")),
        "source_key": str(effective_plan.get("source_key", "")),
        "title": str(effective_plan.get("title", "")),
        "priority": str(effective_plan.get("priority", "")),
        "target": str(effective_plan.get("target", "")),
        "mode": str(effective_plan.get("mode", "dry_run")),
        "execution_command": str(effective_plan.get("execution_command", "")),
        "estimated_step_count": int(effective_plan.get("estimated_step_count", 0)),
        "requires_manual_approval": bool(effective_plan.get("requires_manual_approval", False)),
        "steps": list(effective_plan.get("steps", [])),
        "preview_summary": preview_summary,
    }


def queue_batch_execution_plan(
    settings: WebSettings,
    plan_key: str,
    user_id: str,
    target: str = "",
    mode: str = "queued",
) -> dict[str, Any]:
    execution_plan_templates = load_execution_plan_templates(settings)
    selected_plan = resolve_execution_plan_template(execution_plan_templates, plan_key, target)
    effective_plan = {
        **selected_plan,
        "target": target or str(selected_plan.get("target", "")),
        "mode": mode or "queued",
    }
    queue_summary = (
        f"mode={effective_plan['mode']};"
        f" priority={effective_plan.get('priority', '')};"
        f" target={effective_plan['target']};"
        f" estimated_steps={effective_plan.get('estimated_step_count', 0)};"
        f" requires_manual_approval={effective_plan.get('requires_manual_approval', False)}"
    )
    connection = connect_auth_database(ProjectPaths.default_database_path())
    ensure_auth_schema(connection)
    ensure_batch_execution_queue_schema(connection)
    queue_run = write_batch_execution_queue_run(
        connection,
        user_id,
        effective_plan,
        "queued",
        "waiting_for_approval" if bool(effective_plan.get("requires_manual_approval", False)) else "ready",
        queue_summary,
    )
    connection.close()
    return {
        "status": "queued",
        "queue_run_id": queue_run["queue_run_id"],
        "created_at": queue_run["created_at"],
        "updated_at": queue_run["updated_at"],
        "plan_key": str(effective_plan.get("plan_key", "")),
        "source_type": str(effective_plan.get("source_type", "")),
        "source_key": str(effective_plan.get("source_key", "")),
        "title": str(effective_plan.get("title", "")),
        "priority": str(effective_plan.get("priority", "")),
        "target": str(effective_plan.get("target", "")),
        "mode": str(effective_plan.get("mode", "queued")),
        "execution_command": str(effective_plan.get("execution_command", "")),
        "estimated_step_count": int(effective_plan.get("estimated_step_count", 0)),
        "requires_manual_approval": bool(effective_plan.get("requires_manual_approval", False)),
        "queue_status": "queued",
        "execution_status": "waiting_for_approval" if bool(effective_plan.get("requires_manual_approval", False)) else "ready",
        "steps": list(effective_plan.get("steps", [])),
        "queue_summary": queue_summary,
    }
