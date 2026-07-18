from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_json


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_dashboard_payload(
    validation_report_path: Path,
    batch_summary_path: Path,
    season_summary_path: Path,
    manual_import_report_path: Path,
    retry_batch_report_path: Path,
) -> dict[str, Any]:
    validation_report = load_optional_json(validation_report_path)
    batch_summary = load_optional_json(batch_summary_path)
    season_summary = load_optional_json(season_summary_path)
    manual_import_report = load_optional_json(manual_import_report_path)
    retry_batch_report = load_optional_json(retry_batch_report_path)

    return {
        "title": "AI漫剧批量生产 Dashboard",
        "status": resolve_dashboard_status(validation_report),
        "source_reports": {
            "validation": str(validation_report_path),
            "batch_summary": str(batch_summary_path),
            "season_summary": str(season_summary_path),
            "manual_import": str(manual_import_report_path),
            "retry_batch": str(retry_batch_report_path),
        },
        "overview": {
            "projects": int(validation_report.get("projects_count", 0)),
            "seasons": int(validation_report.get("seasons_count", 0)),
            "episodes": int(validation_report.get("episodes_count", 0)),
            "jobs": int(validation_report.get("jobs_count", 0)),
            "succeeded_jobs": int(validation_report.get("succeeded_jobs_count", 0)),
            "batches": int(validation_report.get("batches_count", 0)),
            "batch_runs": int(validation_report.get("batch_runs_count", 0)),
        },
        "batch": {
            "batch_id": str(batch_summary.get("batch_id", validation_report.get("batch_file_path", ""))),
            "status": str(batch_summary.get("status", "unknown")),
            "step_count": int(batch_summary.get("step_count", validation_report.get("batch_step_count", 0))),
            "completed_step_count": int(batch_summary.get("completed_step_count", validation_report.get("batch_simulated_step_count", 0))),
        },
        "season": {
            "episode_count": int(season_summary.get("episode_count", validation_report.get("episodes_count", 0))),
            "job_count": int(season_summary.get("job_count", validation_report.get("jobs_count", 0))),
            "ready_episode_count": int(season_summary.get("ready_episode_count", validation_report.get("season_ready_episode_count", 0))),
            "rendered_episode_count": int(season_summary.get("rendered_episode_count", validation_report.get("season_rendered_episode_count", 0))),
        },
        "provider": {
            "provider_count": int(validation_report.get("provider_count", 0)),
            "request_count": int(validation_report.get("provider_request_count", 0)),
            "ready_request_count": int(validation_report.get("provider_ready_request_count", 0)),
            "openai_dry_run_count": int(validation_report.get("provider_execution_dry_run_count", 0)),
            "local_dry_run_count": int(validation_report.get("provider_execution_local_dry_run_count", 0)),
            "local_provider_ready_count": int(validation_report.get("provider_execution_local_ready_count", 0)),
            "readiness_status": str(validation_report.get("provider_readiness_status", "unknown")),
            "readiness_blocking_count": int(validation_report.get("provider_readiness_blocking_count", 0)),
            "production_fallback_ready": bool(validation_report.get("production_fallback_ready", False)),
            "production_live_provider_ready": bool(validation_report.get("production_live_provider_ready", False)),
            "production_local_provider_ready": bool(validation_report.get("production_local_provider_ready", False)),
            "production_local_video_ready": bool(validation_report.get("provider_readiness_local_video_ready", False)),
            "production_risk_register_status": str(validation_report.get("production_risk_register_status", "unknown")),
            "production_risk_blocking_count": int(validation_report.get("production_risk_blocking_count", 0)),
            "production_risk_warning_count": int(validation_report.get("production_risk_warning_count", 0)),
        },
        "manual_import": {
            "imported_count": int(manual_import_report.get("imported_count", validation_report.get("manual_import_imported_count", 0))),
            "missing_count": int(manual_import_report.get("missing_count", validation_report.get("manual_import_missing_count", 0))),
            "succeeded_after_import": int(validation_report.get("manual_import_succeeded_count", 0)),
            "manual_required_after_import": int(validation_report.get("manual_import_manual_required_count", 0)),
        },
        "retry": {
            "retried_count": int(retry_batch_report.get("retried_count", validation_report.get("retry_batch_retried_count", 0))),
            "scoped_job_count": int(retry_batch_report.get("scoped_job_count", validation_report.get("retry_batch_scoped_job_count", 0))),
        },
        "episode_states": validation_report.get("episode_states", {}),
        "job_status_by_episode": validation_report.get("job_status_by_episode", {}),
        "next_actions": build_dashboard_next_actions(validation_report),
    }


def resolve_dashboard_status(validation_report: dict[str, Any]) -> str:
    retry_count = int(validation_report.get("retry_batch_retried_count", 0))
    manual_required = int(validation_report.get("manual_import_manual_required_count", 0))
    if retry_count > 0 or manual_required > 0:
        return "needs_attention"
    return "ready"


def build_dashboard_next_actions(validation_report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if int(validation_report.get("retry_batch_retried_count", 0)) > 0:
        actions.append("继续执行 retry-batch 生成的新任务包，补齐 queued 任务产物。")
    openai_required = bool(validation_report.get("production_live_provider_required", True))
    if openai_required and int(validation_report.get("provider_openai_blocked_count", 0)) > 0 and not bool(validation_report.get("production_fallback_ready", False)):
        actions.append("配置 OPENAI_API_KEY 后可执行真实 OpenAI 图片/TTS 请求。")
    elif openai_required and int(validation_report.get("provider_openai_blocked_count", 0)) > 0:
        actions.append("OpenAI live run 尚未启用；当前本地 fallback 产物已补齐，上线前再做真实 Provider 验证。")
    if int(validation_report.get("provider_execution_local_dry_run_count", 0)) > 0 and not bool(validation_report.get("production_local_provider_ready", False)):
        actions.append(build_local_provider_action(validation_report))
    if int(validation_report.get("production_risk_blocking_count", 0)) > 0:
        actions.append("上线前必须处理 `production_risk_register.json` 中的 blocking 风险；OpenAI live provider 已按本轮范围排除。")
    elif int(validation_report.get("production_risk_warning_count", 0)) > 0:
        actions.append("生产演练闸门已无 blocking 项；继续处理 `production_risk_register.json` 中的 warning 项并做真实 ComfyUI 验收。")
    if int(validation_report.get("manual_import_missing_count", 0)) > 0:
        actions.append("将网页生成产物按目标文件名放入 manual_import_sources 后再次导入。")
    if not actions:
        actions.append("当前批量链路已完成，可进入正式渲染与发布包阶段。")
    return actions


def build_local_provider_action(validation_report: dict[str, Any]) -> str:
    piper_ready = bool(validation_report.get("provider_readiness_local_piper_tts_ready", False))
    comfyui_image_ready = bool(validation_report.get("provider_readiness_local_comfyui_image_ready", False))
    comfyui_video_ready = bool(validation_report.get("provider_readiness_local_comfyui_video_ready", False))
    if piper_ready and not (comfyui_image_ready and comfyui_video_ready):
        return "Piper TTS 已可本地执行；ComfyUI 图片/视频仍需启动服务并补齐 `model_requirements.json` 中的模型权重后做小批量验证。"
    if comfyui_image_ready and piper_ready and not comfyui_video_ready:
        return "本地图片与 TTS 路线已就绪；ComfyUI 视频仍需补齐模型/服务并先跑低分辨率单镜头验证。"
    return "本地 Provider 仍需补齐 ComfyUI workflow/模型/服务与 Piper 模型配置后，再执行小批量本地验证。"


def write_dashboard_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def render_dashboard_html(payload: dict[str, Any]) -> str:
    cards = [
        ("项目", payload["overview"]["projects"]),
        ("剧集", payload["overview"]["episodes"]),
        ("任务", payload["overview"]["jobs"]),
        ("成功任务", payload["overview"]["succeeded_jobs"]),
        ("批次", payload["overview"]["batches"]),
        ("批次步骤", payload["batch"]["completed_step_count"]),
        ("导入成功", payload["manual_import"]["imported_count"]),
        ("重试任务", payload["retry"]["retried_count"]),
    ]
    card_html = "\n".join(
        f"<section class='card'><div class='value'>{escape(str(value))}</div><div class='label'>{escape(label)}</div></section>"
        for label, value in cards
    )
    actions_html = "\n".join(f"<li>{escape(action)}</li>" for action in payload["next_actions"])
    episode_rows = render_table_rows(payload.get("episode_states", {}))
    job_rows = render_table_rows(payload.get("job_status_by_episode", {}))
    source_rows = "\n".join(
        f"<tr><td>{escape(label)}</td><td>{escape(path)}</td></tr>"
        for label, path in payload["source_reports"].items()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{escape(str(payload["title"]))}</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: #111827; color: #f9fafb; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    .status {{ color: #fbbf24; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 24px 0; }}
    .card {{ background: #1f2937; border: 1px solid #374151; border-radius: 14px; padding: 18px; }}
    .value {{ font-size: 30px; font-weight: 800; }}
    .label {{ color: #9ca3af; margin-top: 6px; }}
    section.panel {{ background: #111827; border: 1px solid #374151; border-radius: 14px; padding: 18px; margin: 18px 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ border-bottom: 1px solid #374151; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: #93c5fd; }}
    code {{ color: #bfdbfe; }}
    li {{ margin: 8px 0; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(str(payload["title"]))}</h1>
  <div class="status">当前状态：<strong>{escape(str(payload["status"]))}</strong></div>
  <div class="grid">{card_html}</div>
  <section class="panel">
    <h2>下一步建议</h2>
    <ul>{actions_html}</ul>
  </section>
  <section class="panel">
    <h2>剧集状态</h2>
    <table><tr><th>剧集</th><th>状态</th><th>完成任务</th><th>总任务</th></tr>{episode_rows}</table>
  </section>
  <section class="panel">
    <h2>任务分布</h2>
    <table><tr><th>剧集</th><th>状态分布</th></tr>{job_rows}</table>
  </section>
  <section class="panel">
    <h2>来源报告</h2>
    <table><tr><th>类型</th><th>路径</th></tr>{source_rows}</table>
  </section>
</main>
</body>
</html>
"""


def render_table_rows(payload: dict[str, Any]) -> str:
    rows: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict) and {"status", "completed_jobs", "total_jobs"}.issubset(value.keys()):
            rows.append(
                "<tr>"
                f"<td>{escape(str(key))}</td>"
                f"<td>{escape(str(value['status']))}</td>"
                f"<td>{escape(str(value['completed_jobs']))}</td>"
                f"<td>{escape(str(value['total_jobs']))}</td>"
                "</tr>"
            )
        else:
            rows.append(
                "<tr>"
                f"<td>{escape(str(key))}</td>"
                f"<td colspan='3'><code>{escape(json.dumps(value, ensure_ascii=False))}</code></td>"
                "</tr>"
            )
    return "\n".join(rows)


def write_dashboard_html(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard_html(payload), encoding="utf-8")
