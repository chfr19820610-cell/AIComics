from __future__ import annotations

import subprocess
import sys
from typing import Any

from web.backend.settings import WebSettings
from web.backend.services.edition_policy import EditionPolicy, load_edition_policy


COMMAND_DESCRIPTIONS = {
    "status": "读取系统当前状态",
    "dashboard-export": "刷新批量生产 Dashboard 报告",
    "review-metrics": "刷新复盘统计报告",
    "build-navigator": "生成单集导航页",
}


def load_command_catalog(settings: WebSettings, policy: EditionPolicy | None = None) -> dict[str, Any]:
    active_policy = policy or load_edition_policy(settings)
    return {
        "command_execution_enabled": settings.command_execution_enabled,
        "command_console_enabled": active_policy.command_console_enabled,
        "edition_allowed": active_policy.command_console_enabled,
        "edition_name": active_policy.edition_name,
        "edition_display_name": active_policy.display_name,
        "edition_block_reason": "" if active_policy.command_console_enabled else active_policy.command_console_reason,
        "requires_confirmation": True,
        "items": [
            {
                "command": command,
                "description": COMMAND_DESCRIPTIONS.get(command, "暂未补充命令说明"),
                "allowed": command in settings.allowed_commands,
                "runnable": command in settings.runnable_commands,
                "enabled": (
                    active_policy.command_console_enabled
                    and settings.command_execution_enabled
                    and command in settings.runnable_commands
                ),
                "requires_confirmation": command in settings.runnable_commands,
                "command_preview": f"{sys.executable} -m aicomic.cli.main {command}",
                "reason": (
                    "已允许在显式确认后从 Web 控制台执行"
                    if (
                        active_policy.command_console_enabled
                        and settings.command_execution_enabled
                        and command in settings.runnable_commands
                    )
                    else active_policy.command_console_reason
                    if not active_policy.command_console_enabled
                    else "当前仅开放目录与命令白名单展示，执行仍受安全开关限制。"
                ),
            }
            for command in settings.allowed_commands
        ],
        "count": len(settings.allowed_commands),
    }


def execute_whitelisted_command(
    settings: WebSettings,
    command: str,
    confirm_execution: bool = False,
    policy: EditionPolicy | None = None,
) -> dict[str, Any]:
    active_policy = policy or load_edition_policy(settings)
    if not active_policy.command_console_enabled:
        return {
            "command": command,
            "status": "blocked_edition_not_allowed",
            "exit_code": -1,
            "stdout": "",
            "stderr": active_policy.command_console_reason,
            "edition_name": active_policy.edition_name,
        }

    if command not in settings.allowed_commands:
        return {
            "command": command,
            "status": "rejected_not_allowed",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command is not in the allowed whitelist.",
        }

    if command not in settings.runnable_commands:
        return {
            "command": command,
            "status": "rejected_not_runnable",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command requires parameters or has not been enabled for Web execution yet.",
        }

    if not settings.command_execution_enabled:
        return {
            "command": command,
            "status": "blocked_command_execution_disabled",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command execution is disabled by safety policy.",
        }

    if not confirm_execution:
        return {
            "command": command,
            "status": "blocked_confirmation_required",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command execution requires explicit confirmation in the Web UI.",
        }

    try:
        process = subprocess.run(
            [sys.executable, "-m", "aicomic.cli.main", command],
            cwd=settings.project_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "confirmed": confirm_execution,
            "status": "timeout",
            "exit_code": -1,
            "stdout": "",
            "stderr": "命令执行超时（300秒），请稍后重试。",
        }
    return {
        "command": command,
        "confirmed": confirm_execution,
        "status": "completed" if process.returncode == 0 else "failed",
        "exit_code": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }
