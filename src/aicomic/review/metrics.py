from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def build_review_metrics(
    validation_report_path: Path,
    dashboard_path: Path,
    manual_import_report_path: Path,
    retry_batch_report_path: Path,
    provider_execution_report_path: Path,
) -> dict[str, Any]:
    validation = load_optional_json(validation_report_path)
    dashboard = load_optional_json(dashboard_path)
    manual_import = load_optional_json(manual_import_report_path)
    retry_batch = load_optional_json(retry_batch_report_path)
    provider_execution = load_optional_json(provider_execution_report_path)

    jobs_count = int(validation.get("jobs_count", dashboard.get("overview", {}).get("jobs", 0)))
    succeeded_jobs = int(validation.get("succeeded_jobs_count", dashboard.get("overview", {}).get("succeeded_jobs", 0)))
    episodes_count = int(validation.get("episodes_count", dashboard.get("overview", {}).get("episodes", 0)))
    ready_episode_count = int(validation.get("season_ready_episode_count", dashboard.get("season", {}).get("ready_episode_count", 0)))
    manual_imported = int(manual_import.get("imported_count", validation.get("manual_import_imported_count", 0)))
    manual_missing = int(manual_import.get("missing_count", validation.get("manual_import_missing_count", 0)))
    retry_count = int(retry_batch.get("retried_count", validation.get("retry_batch_retried_count", 0)))
    retry_scope = int(retry_batch.get("scoped_job_count", validation.get("retry_batch_scoped_job_count", 0)))
    dry_run_count = int(provider_execution.get("dry_run_count", validation.get("provider_execution_dry_run_count", 0)))
    local_dry_run_count = int(validation.get("provider_execution_local_dry_run_count", 0))
    local_ready_count = int(validation.get("provider_execution_local_ready_count", 0))
    provider_request_count = int(validation.get("provider_request_count", 0))
    production_fallback_ready = bool(validation.get("production_fallback_ready", False))
    production_live_provider_ready = bool(validation.get("production_live_provider_ready", False))
    production_local_provider_ready = bool(validation.get("production_local_provider_ready", False))
    production_local_video_ready = bool(validation.get("provider_readiness_local_video_ready", False))

    metrics = {
        "job_success_rate": safe_ratio(succeeded_jobs, jobs_count),
        "episode_ready_rate": safe_ratio(ready_episode_count, episodes_count),
        "manual_import_rate": safe_ratio(manual_imported, manual_imported + manual_missing),
        "retry_rate": safe_ratio(retry_count, retry_scope),
        "provider_dry_run_rate": safe_ratio(dry_run_count, provider_request_count),
    }
    risk_flags = build_risk_flags(metrics, validation)
    blocking_risk_flags = [item for item in risk_flags if item.get("level") != "info"]
    return {
        "title": "AI漫剧批量生产数据复盘",
        "status": "needs_optimization" if blocking_risk_flags else "healthy",
        "source_reports": {
            "validation": str(validation_report_path),
            "dashboard": str(dashboard_path),
            "manual_import": str(manual_import_report_path),
            "retry_batch": str(retry_batch_report_path),
            "provider_execution": str(provider_execution_report_path),
        },
        "metrics": metrics,
        "counts": {
            "jobs_count": jobs_count,
            "succeeded_jobs": succeeded_jobs,
            "episodes_count": episodes_count,
            "ready_episode_count": ready_episode_count,
            "manual_imported": manual_imported,
            "manual_missing": manual_missing,
            "retry_count": retry_count,
            "retry_scope": retry_scope,
            "dry_run_count": dry_run_count,
            "local_dry_run_count": local_dry_run_count,
            "local_ready_count": local_ready_count,
            "provider_request_count": provider_request_count,
            "production_fallback_ready": production_fallback_ready,
            "production_live_provider_ready": production_live_provider_ready,
            "production_local_provider_ready": production_local_provider_ready,
            "production_local_video_ready": production_local_video_ready,
            "provider_readiness_status": str(validation.get("provider_readiness_status", "unknown")),
            "production_risk_register_status": str(validation.get("production_risk_register_status", "unknown")),
            "production_risk_blocking_count": int(validation.get("production_risk_blocking_count", 0)),
            "production_risk_warning_count": int(validation.get("production_risk_warning_count", 0)),
        },
        "risk_flags": risk_flags,
        "recommendations": build_recommendations(metrics, validation),
    }


def build_risk_flags(metrics: dict[str, float], validation: dict[str, Any]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if metrics["job_success_rate"] < 0.8:
        flags.append({"level": "high", "name": "任务成功率偏低", "detail": "成功任务未达到 80%，需要继续补素材或执行 API。"})
    if metrics["manual_import_rate"] < 0.5:
        flags.append({"level": "medium", "name": "手工导入率偏低", "detail": "网页生成产物导入不足，建议优先补齐缺失文件。"})
    if metrics["retry_rate"] > 0.3:
        flags.append({"level": "medium", "name": "重试占比较高", "detail": "大量任务进入 queued，说明批量生产仍依赖补产物。"})
    openai_required = bool(validation.get("production_live_provider_required", True))
    if openai_required and int(validation.get("provider_openai_blocked_count", 0)) > 0 and not bool(validation.get("production_fallback_ready", False)):
        flags.append({"level": "medium", "name": "OpenAI 请求未真实执行", "detail": "存在 blocked/dry-run 请求，需配置密钥或继续网页模式。"})
    if int(validation.get("provider_execution_local_dry_run_count", 0)) > 0 and not bool(validation.get("production_local_provider_ready", False)):
        flags.append({"level": "info", "name": "本地 Provider 未完全就绪", "detail": build_local_provider_detail(validation)})
    if int(validation.get("production_risk_blocking_count", 0)) > 0:
        flags.append(
            {
                "level": "high",
                "name": "生产风险闸门未通过",
                "detail": "除 OpenAI live provider 外，仍存在上线 blocking 风险；详见 production_risk_register.json。",
            }
        )
    elif int(validation.get("production_risk_warning_count", 0)) > 0:
        flags.append(
            {
                "level": "info",
                "name": "生产演练存在非阻断提醒",
                "detail": "生产风险闸门已无 blocking 项；仍需查看 warning 项确认真实 ComfyUI 和供应链接受标准。",
            }
        )
    return flags


def build_recommendations(metrics: dict[str, float], validation: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    if metrics["job_success_rate"] < 1:
        recommendations.append("先按 `retry_batch_report.json` 补齐 queued 任务，再重新执行 manual-import-batch。")
    if int(validation.get("manual_import_missing_count", 0)) > 0:
        recommendations.append("把缺失文件按目标文件名放入 `state/manual_import_sources/season1_batch_demo`。")
    openai_required = bool(validation.get("production_live_provider_required", True))
    if openai_required and int(validation.get("provider_openai_blocked_count", 0)) > 0 and not bool(validation.get("production_fallback_ready", False)):
        recommendations.append("如要减少人工导入，配置 `OPENAI_API_KEY` 后执行真实 OpenAI Provider。")
    elif openai_required and int(validation.get("provider_openai_blocked_count", 0)) > 0:
        recommendations.append("OpenAI live run 尚未启用，但本地 fallback 产物已补齐；上线前再配置 `OPENAI_API_KEY` 做真实 Provider 验证。")
    if int(validation.get("provider_execution_local_dry_run_count", 0)) > 0 and not bool(validation.get("production_local_provider_ready", False)):
        recommendations.append(build_local_provider_recommendation(validation))
    if int(validation.get("production_risk_blocking_count", 0)) > 0:
        recommendations.append("按 `reports/production_risk_register.json` 逐项处理生产 blocking 风险；OpenAI live provider 已按本轮范围排除。")
    elif int(validation.get("production_risk_warning_count", 0)) > 0:
        recommendations.append("生产演练闸门已通过 blocking 检查；继续按 `production_risk_register.json` 处理 warning 项并做真实 ComfyUI 验收。")
    if not recommendations:
        recommendations.append("当前批量生产指标健康，可以进入正式版渲染和发布包阶段。")
    return recommendations


def build_local_provider_detail(validation: dict[str, Any]) -> str:
    piper_ready = bool(validation.get("provider_readiness_local_piper_tts_ready", False))
    image_ready = bool(validation.get("provider_readiness_local_comfyui_image_ready", False))
    video_ready = bool(validation.get("provider_readiness_local_comfyui_video_ready", False))
    if piper_ready and not (image_ready and video_ready):
        return "Piper TTS 已可本地执行；ComfyUI 图片/视频仍缺服务或模型权重验证。"
    if image_ready and piper_ready and not video_ready:
        return "ComfyUI 图片与 Piper TTS 已就绪；ComfyUI 视频仍缺服务或模型权重验证。"
    return "ComfyUI/Piper 已进入 dry-run 路由，但当前环境仍未满足全部本地执行条件。"


def build_local_provider_recommendation(validation: dict[str, Any]) -> str:
    piper_ready = bool(validation.get("provider_readiness_local_piper_tts_ready", False))
    if piper_ready:
        return "本地替代 OpenAI 的 TTS 路线已可执行；继续启动 ComfyUI、补齐 `local_providers/comfyui/model_requirements.json` 中的模型权重，再跑小批量图片/视频 Provider。"
    return "如要本地替代 OpenAI，先补齐 ComfyUI workflow/模型/服务与 Piper `.onnx` 配置，再跑小批量本地 Provider。"


def write_review_metrics(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_review_html(payload: dict[str, Any]) -> str:
    metric_cards = "\n".join(
        f"<section class='card'><div class='value'>{escape(format_percent(value))}</div><div class='label'>{escape(label)}</div></section>"
        for label, value in payload["metrics"].items()
    )
    risk_rows = "\n".join(
        f"<tr><td>{escape(item['level'])}</td><td>{escape(item['name'])}</td><td>{escape(item['detail'])}</td></tr>"
        for item in payload["risk_flags"]
    )
    recommendation_items = "\n".join(f"<li>{escape(item)}</li>" for item in payload["recommendations"])
    count_rows = "\n".join(
        f"<tr><td>{escape(key)}</td><td>{escape(str(value))}</td></tr>"
        for key, value in payload["counts"].items()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{escape(str(payload["title"]))}</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: #0f172a; color: #e5e7eb; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px; }}
    .grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 24px 0; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 16px; }}
    .value {{ font-size: 24px; font-weight: 800; color: #facc15; }}
    .label {{ color: #94a3b8; margin-top: 6px; font-size: 13px; }}
    section {{ background: #111827; border: 1px solid #334155; border-radius: 14px; padding: 18px; margin: 18px 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ border-bottom: 1px solid #334155; padding: 10px; text-align: left; }}
    th {{ color: #93c5fd; }}
    li {{ margin: 8px 0; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(str(payload["title"]))}</h1>
  <p>复盘状态：<strong>{escape(str(payload["status"]))}</strong></p>
  <div class="grid">{metric_cards}</div>
  <section><h2>风险项</h2><table><tr><th>等级</th><th>名称</th><th>说明</th></tr>{risk_rows}</table></section>
  <section><h2>建议动作</h2><ul>{recommendation_items}</ul></section>
  <section><h2>原始计数</h2><table><tr><th>指标</th><th>数值</th></tr>{count_rows}</table></section>
</main>
</body>
</html>
"""


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def write_review_html(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_review_html(payload), encoding="utf-8")
