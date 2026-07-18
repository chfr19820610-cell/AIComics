from __future__ import annotations

import argparse
from pathlib import Path

from aicomic.batch.coordinator import (
    apply_batch_preflight_gate,
    build_batch_payload,
    build_batch_record,
    load_batch_payload,
    parse_steps,
    run_batch_payload,
    write_batch_payload,
)
from aicomic.batch.reporter import build_batch_summary, write_batch_summary
from aicomic.batch.retry_manager import retry_batch_jobs, write_retry_batch_report
from aicomic.core.config import ProjectPaths
from aicomic.core.dispatcher import dispatch_jobs, write_dispatch_report
from aicomic.core.episode_lifecycle import advance_status
from aicomic.core.horror_pipeline import (
    DEFAULT_HORROR_HOOK,
    build_horror_episode_manifest,
    build_horror_story_blueprint,
    write_horror_blueprint,
    write_horror_episode_manifest,
)
from aicomic.core.job_control import filter_jobs, retry_jobs, write_job_payload
from aicomic.core.job_builder import build_jobs_from_episode_manifest, serialize_jobs
from aicomic.core.manifest import load_json, write_json
from aicomic.core.models import JobRecord
from aicomic.core.project_initializer import initialize_project
from aicomic.core.rework import build_rework_report, select_rework_jobs, write_rework_report
from aicomic.core.resume import build_resume_report, write_resume_report
from aicomic.core.season_jobs import build_season_job_bundle, write_season_job_bundle
from aicomic.core.state_store import write_state_snapshot
from aicomic.core.status import summarize_episode_state
from aicomic.publish.dashboard import build_dashboard_payload, write_dashboard_html, write_dashboard_json
from aicomic.publish.navigator import build_episode_navigator, write_navigator
from aicomic.publish.publish_pack import build_enhanced_publish_pack, build_publish_pack, write_publish_pack
from aicomic.publish.season_summary import build_season_summary, write_season_summary
from aicomic.providers.executor import execute_provider_requests, write_provider_execution_report
from aicomic.providers.comfyui_service import run_comfyui_service_action, write_comfyui_service_report
from aicomic.providers.live_smoke import run_local_provider_live_smoke, write_local_provider_live_smoke_report
from aicomic.providers.manual_importer import import_manual_outputs, write_manual_import_report
from aicomic.providers.provider_planner import build_provider_plan, write_provider_plan
from aicomic.providers.readiness import build_provider_readiness_report, write_provider_readiness_report
from aicomic.providers.request_builder import build_provider_requests, write_provider_requests
from aicomic.providers.result_writer import build_provider_result_writeback, write_provider_writeback_report
from aicomic.qc.asset_scanner import scan_episode_assets, write_asset_scan_report
from aicomic.qc.repair_advisor import build_repair_suggestions, write_repair_suggestions
from aicomic.qc.season_scanner import scan_season_assets, write_season_scan_report
from aicomic.render.preview_renderer import build_render_plan, render_preview_video
from aicomic.render.release_renderer import build_release_plan, render_release_video
from aicomic.render.season_renderer import render_season
from aicomic.render.subtitle_audio import build_audio_plan, build_subtitle_entries, write_audio_plan, write_silence_wav, write_srt
from aicomic.review.metrics import build_review_metrics, write_review_html, write_review_metrics
from aicomic.security.dependency_audit import build_dependency_audit_report, write_dependency_audit_report
from aicomic.security.production_readiness import build_production_risk_register, write_production_risk_register


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI漫剧自动生成系统 CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="查看项目骨架状态")

    build_jobs_parser = subparsers.add_parser("build-jobs", help="从 episode_manifest 构建任务包")
    build_jobs_parser.add_argument(
        "--episode-manifest",
        type=Path,
        default=ProjectPaths.manifest_dir() / "episode_manifest.json",
        help="Episode Manifest 路径",
    )
    build_jobs_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json",
        help="任务包输出路径",
    )

    sync_states_parser = subparsers.add_parser("sync-states", help="根据任务包生成剧集状态快照")
    sync_states_parser.add_argument(
        "--jobs-file",
        type=Path,
        default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json",
        help="任务包路径",
    )
    sync_states_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.state_dir() / "episode_state_snapshot.json",
        help="状态快照输出路径",
    )

    dispatch_parser = subparsers.add_parser("dispatch-jobs", help="生成任务调度报告")
    dispatch_parser.add_argument(
        "--jobs-file",
        type=Path,
        default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json",
        help="任务包路径",
    )
    dispatch_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.reports_dir() / "dispatch_report.json",
        help="调度报告输出路径",
    )

    lifecycle_parser = subparsers.add_parser("advance-episode", help="验证剧集状态流转")
    lifecycle_parser.add_argument("--current", required=True, help="当前状态")
    lifecycle_parser.add_argument("--next", required=True, help="目标状态")

    scan_assets_parser = subparsers.add_parser("scan-assets", help="扫描单集素材完整性")
    scan_assets_parser.add_argument(
        "--episode-manifest",
        type=Path,
        default=ProjectPaths.manifest_dir() / "episode_manifest.json",
        help="Episode Manifest 路径",
    )
    scan_assets_parser.add_argument(
        "--episode-code",
        default="E01",
        help="剧集编号",
    )
    scan_assets_parser.add_argument(
        "--asset-root",
        type=Path,
        default=ProjectPaths.demo_assets_dir(),
        help="素材根目录",
    )
    scan_assets_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.reports_dir() / "asset_scan_E01.json",
        help="扫描报告输出路径",
    )

    render_preview_parser = subparsers.add_parser("render-preview", help="渲染单集预览视频")
    render_preview_parser.add_argument(
        "--episode-manifest",
        type=Path,
        default=ProjectPaths.manifest_dir() / "episode_manifest.json",
        help="Episode Manifest 路径",
    )
    render_preview_parser.add_argument(
        "--episode-code",
        default="E01",
        help="剧集编号",
    )
    render_preview_parser.add_argument(
        "--asset-root",
        type=Path,
        default=ProjectPaths.demo_assets_dir(),
        help="素材根目录",
    )
    render_preview_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.preview_outputs_dir() / "E01_preview.mp4",
        help="预览视频输出路径",
    )
    render_preview_parser.add_argument(
        "--report-output",
        type=Path,
        default=ProjectPaths.reports_dir() / "render_preview_E01.json",
        help="渲染报告输出路径",
    )

    subtitle_audio_parser = subparsers.add_parser("prepare-subtitles-audio", help="生成字幕和音轨占位计划")
    subtitle_audio_parser.add_argument(
        "--episode-manifest",
        type=Path,
        default=ProjectPaths.manifest_dir() / "episode_manifest.json",
        help="Episode Manifest 路径",
    )
    subtitle_audio_parser.add_argument("--episode-code", default="E01", help="剧集编号")
    subtitle_audio_parser.add_argument(
        "--srt-output",
        type=Path,
        default=ProjectPaths.state_dir() / "subtitles" / "E01.srt",
        help="字幕输出路径",
    )
    subtitle_audio_parser.add_argument(
        "--audio-plan-output",
        type=Path,
        default=ProjectPaths.reports_dir() / "audio_plan_E01.json",
        help="音轨计划输出路径",
    )

    horror_blueprint_parser = subparsers.add_parser("horror-blueprint", help="生成玄学/民俗恐怖样片故事蓝图")
    horror_blueprint_parser.add_argument("--hook", default=DEFAULT_HORROR_HOOK, help="故事钩子")
    horror_blueprint_parser.add_argument("--episode-code", default="E01", help="剧集编号")
    horror_blueprint_parser.add_argument("--target-seconds", type=int, default=360, help="目标时长，限制为 300-420 秒")
    horror_blueprint_parser.add_argument("--max-shots", type=int, default=60, help="镜头上限，限制为 40-60")
    horror_blueprint_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.project_root() / "docs" / "horror_story_blueprint.json",
        help="故事蓝图输出路径",
    )

    horror_episode_parser = subparsers.add_parser("build-horror-episode", help="根据玄学/民俗恐怖蓝图生成 Episode Manifest")
    horror_episode_parser.add_argument(
        "--blueprint",
        type=Path,
        default=ProjectPaths.project_root() / "docs" / "horror_story_blueprint.json",
        help="故事蓝图路径",
    )
    horror_episode_parser.add_argument("--project-id", default="aicomic_system", help="项目编号")
    horror_episode_parser.add_argument("--season", type=int, default=1, help="季编号")
    horror_episode_parser.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths.manifest_dir() / "episode_manifest.json",
        help="Episode Manifest 输出路径",
    )
    subtitle_audio_parser.add_argument(
        "--wav-output",
        type=Path,
        default=ProjectPaths.state_dir() / "audio" / "E01_placeholder.wav",
        help="占位音频输出路径",
    )

    filter_jobs_parser = subparsers.add_parser("filter-jobs", help="按条件筛选任务")
    filter_jobs_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json")
    filter_jobs_parser.add_argument("--episode-code", default=None)
    filter_jobs_parser.add_argument("--job-type", default=None)
    filter_jobs_parser.add_argument("--statuses", default=None, help="逗号分隔，如 pending,failed")
    filter_jobs_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "filtered_jobs.json")

    retry_jobs_parser = subparsers.add_parser("retry-jobs", help="重置可重试任务状态")
    retry_jobs_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json")
    retry_jobs_parser.add_argument("--statuses", default="pending,failed,manual_required")
    retry_jobs_parser.add_argument("--output", type=Path, default=ProjectPaths.project_root() / "jobs" / "episode_jobs_retried.json")

    retry_batch_parser = subparsers.add_parser("retry-batch", help="批量重试指定范围任务")
    retry_batch_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs_provider_synced.json")
    retry_batch_parser.add_argument("--statuses", default="failed,manual_required")
    retry_batch_parser.add_argument("--episode-code", default=None)
    retry_batch_parser.add_argument("--provider", default=None)
    retry_batch_parser.add_argument("--report-output", type=Path, default=ProjectPaths.reports_dir() / "retry_batch_report.json")
    retry_batch_parser.add_argument("--jobs-output", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs_batch_retried.json")

    resume_parser = subparsers.add_parser("resume-report", help="生成断点续跑建议报告")
    resume_parser.add_argument("--state-snapshot", type=Path, default=ProjectPaths.state_dir() / "episode_state_snapshot.json")
    resume_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json")
    resume_parser.add_argument("--dispatch-report", type=Path, default=ProjectPaths.reports_dir() / "dispatch_report.json")
    resume_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "resume_report.json")

    init_project_parser = subparsers.add_parser("init-project", help="初始化新项目模板目录")
    init_project_parser.add_argument("--project-name", required=True)
    init_project_parser.add_argument("--genre", default="现代职场逆袭")
    init_project_parser.add_argument("--style", default="动漫漫剧")
    init_project_parser.add_argument("--project-id", default=None)
    init_project_parser.add_argument("--logline", default="一个普通人被卷入高压环境后，靠连续反转赢回主动权。")
    init_project_parser.add_argument("--protagonist-name", default="女主")
    init_project_parser.add_argument("--target-audience", default="短剧用户 / 二次元短视频观众")
    init_project_parser.add_argument("--tone", default="强钩子")
    init_project_parser.add_argument("--season-hook", default="结尾必须留下身份、关系或真相反转。")
    init_project_parser.add_argument("--episode-target-count", type=int, default=12)
    init_project_parser.add_argument("--output-root", type=Path, default=ProjectPaths.generated_projects_dir())

    render_release_parser = subparsers.add_parser("render-release", help="渲染单集正式版视频")
    render_release_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    render_release_parser.add_argument("--episode-code", default="E01")
    render_release_parser.add_argument("--asset-root", type=Path, default=ProjectPaths.demo_assets_dir())
    render_release_parser.add_argument("--output", type=Path, default=ProjectPaths.preview_outputs_dir() / "E01_release.mp4")
    render_release_parser.add_argument("--report-output", type=Path, default=ProjectPaths.reports_dir() / "render_release_E01.json")

    publish_pack_parser = subparsers.add_parser("build-publish-pack", help="生成单集发布包")
    publish_pack_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    publish_pack_parser.add_argument("--episode-code", default="E01")
    publish_pack_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "publish_pack_E01.json")

    enhanced_publish_parser = subparsers.add_parser("enhance-publish-pack", help="生成增强版单集发布包")
    enhanced_publish_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    enhanced_publish_parser.add_argument("--episode-code", default="E01")
    enhanced_publish_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "publish_pack_E01_enhanced.json")

    repair_parser = subparsers.add_parser("suggest-asset-repairs", help="基于扫描报告生成素材修复建议")
    repair_parser.add_argument("--scan-report", type=Path, default=ProjectPaths.reports_dir() / "asset_scan_E01.json")
    repair_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "asset_repair_E01.json")

    provider_plan_parser = subparsers.add_parser("plan-providers", help="生成多 Provider 路由规划报告")
    provider_plan_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs.json")
    provider_plan_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    provider_plan_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "provider_plan.json")

    provider_requests_parser = subparsers.add_parser("build-provider-requests", help="生成 Provider 任务请求包")
    provider_requests_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    provider_requests_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs.json")
    provider_requests_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    provider_requests_parser.add_argument("--output-root", type=Path, default=ProjectPaths.demo_assets_dir())
    provider_requests_parser.add_argument("--provider-overrides", default="", help="按 job_type 覆盖 Provider，如 image=openai_image,tts=openai_tts")
    provider_requests_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "provider_requests.json")

    provider_results_parser = subparsers.add_parser("apply-provider-results", help="扫描 Provider 产物并回写任务状态")
    provider_results_parser.add_argument("--requests-report", type=Path, default=ProjectPaths.reports_dir() / "provider_requests.json")
    provider_results_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs.json")
    provider_results_parser.add_argument("--report-output", type=Path, default=ProjectPaths.reports_dir() / "provider_writeback_report.json")
    provider_results_parser.add_argument("--jobs-output", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs_provider_synced.json")

    manual_import_parser = subparsers.add_parser("manual-import-batch", help="从手工网页导出目录批量导入产物并同步任务状态")
    manual_import_parser.add_argument("--requests-report", type=Path, default=ProjectPaths.reports_dir() / "provider_requests.json")
    manual_import_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs_provider_synced.json")
    manual_import_parser.add_argument("--import-root", type=Path, required=True)
    manual_import_parser.add_argument("--import-report-output", type=Path, default=ProjectPaths.reports_dir() / "manual_import_report.json")
    manual_import_parser.add_argument("--writeback-report-output", type=Path, default=ProjectPaths.reports_dir() / "manual_import_writeback_report.json")
    manual_import_parser.add_argument("--jobs-output", type=Path, default=ProjectPaths.jobs_output_dir() / "episode_jobs_manual_import_synced.json")
    manual_import_parser.add_argument("--overwrite", action="store_true")

    provider_execute_parser = subparsers.add_parser("execute-provider-requests", help="执行支持的 Provider 请求")
    provider_execute_parser.add_argument("--requests-report", type=Path, default=ProjectPaths.reports_dir() / "provider_requests.json")
    provider_execute_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    provider_execute_parser.add_argument("--providers", default="", help="只执行指定 Provider，逗号分隔")
    provider_execute_parser.add_argument("--dry-run", action="store_true", help="仅生成请求预览，不发起真实网络调用")
    provider_execute_parser.add_argument("--confirm-live", action="store_true", help="确认允许发起真实 Provider 网络调用")
    provider_execute_parser.add_argument("--limit", type=int, default=0, help="最多执行或预演的支持类请求数量，0 表示不限")
    provider_execute_parser.add_argument("--max-failures", type=int, default=1, help="真实执行时达到失败次数后停止后续请求，0 表示不限")
    provider_execute_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "provider_execution_report.json")

    provider_readiness_parser = subparsers.add_parser("provider-readiness", help="检查 OpenAI/本地 Provider 上线前就绪状态")
    provider_readiness_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    provider_readiness_parser.add_argument("--requests-report", type=Path, default=ProjectPaths.reports_dir() / "provider_requests_local.json")
    provider_readiness_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "provider_readiness_report.json")

    comfyui_service_parser = subparsers.add_parser("comfyui-service", help="管理项目内 ComfyUI 服务")
    comfyui_service_parser.add_argument("action", choices=("status", "start", "stop", "restart"))
    comfyui_service_parser.add_argument("--host", default="127.0.0.1")
    comfyui_service_parser.add_argument("--port", type=int, default=8188)
    comfyui_service_parser.add_argument("--wait-timeout-seconds", type=float, default=120.0)
    comfyui_service_parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    comfyui_service_parser.add_argument("--force", action="store_true", help="stop/restart 时必要时使用强制退出")
    comfyui_service_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "comfyui_service_report.json")

    local_provider_live_smoke_parser = subparsers.add_parser("local-provider-live-smoke", help="执行本地 Provider 一键 live smoke")
    local_provider_live_smoke_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    local_provider_live_smoke_parser.add_argument("--providers", default="", help="只执行指定 Provider，逗号分隔")
    local_provider_live_smoke_parser.add_argument("--output-root", type=Path, default=ProjectPaths.state_dir() / "live_smoke")
    local_provider_live_smoke_parser.add_argument("--image-workflow-mode", choices=("configured", "smoke", "full"), default="smoke")
    local_provider_live_smoke_parser.add_argument("--video-workflow-mode", choices=("configured", "smoke", "full"), default="smoke")
    local_provider_live_smoke_parser.add_argument("--skip-comfyui-start", action="store_true")
    local_provider_live_smoke_parser.add_argument("--restart-comfyui", action="store_true")
    local_provider_live_smoke_parser.add_argument(
        "--no-retry-comfyui-on-failure",
        action="store_false",
        dest="retry_comfyui_on_failure",
        help="ComfyUI 请求失败后不自动重启并重试失败项",
    )
    local_provider_live_smoke_parser.set_defaults(retry_comfyui_on_failure=True)
    local_provider_live_smoke_parser.add_argument("--max-failures", type=int, default=1)
    local_provider_live_smoke_parser.add_argument("--comfyui-host", default="127.0.0.1")
    local_provider_live_smoke_parser.add_argument("--comfyui-port", type=int, default=8188)
    local_provider_live_smoke_parser.add_argument("--wait-timeout-seconds", type=float, default=120.0)
    local_provider_live_smoke_parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    local_provider_live_smoke_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "local_provider_live_smoke_report.json")

    dependency_audit_parser = subparsers.add_parser("dependency-audit", help="生成依赖锁定与 CVE 审计状态报告")
    dependency_audit_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "dependency_audit_report.json")

    production_risk_parser = subparsers.add_parser("production-risk-register", help="生成生产上线风险闸门报告")
    production_risk_parser.add_argument("--web-config", type=Path, default=ProjectPaths.config_dir() / "web.yaml")
    production_risk_parser.add_argument("--edition-config", type=Path, default=None)
    production_risk_parser.add_argument("--providers-config", type=Path, default=ProjectPaths.providers_config_path())
    production_risk_parser.add_argument("--provider-readiness", type=Path, default=ProjectPaths.reports_dir() / "provider_readiness_report.json")
    production_risk_parser.add_argument("--dependency-audit", type=Path, default=ProjectPaths.reports_dir() / "dependency_audit_report.json")
    production_risk_parser.add_argument("--require-openai-live", action="store_true")
    production_risk_parser.add_argument("--deployment-mode", choices=("production", "rehearsal"), default="production")
    production_risk_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "production_risk_register.json")

    build_batch_parser = subparsers.add_parser("build-batch", help="构建批次定义文件")
    build_batch_parser.add_argument("--batch-id", default="season1_batch_demo")
    build_batch_parser.add_argument("--batch-type", default="season_pipeline")
    build_batch_parser.add_argument("--scope-type", default="season")
    build_batch_parser.add_argument("--scope-value", default="S01")
    build_batch_parser.add_argument("--steps", default="")
    build_batch_parser.add_argument("--providers", default="")
    build_batch_parser.add_argument("--skip-local-provider-preflight", action="store_true")
    build_batch_parser.add_argument("--no-auto-run-local-provider-preflight", action="store_true")
    build_batch_parser.add_argument(
        "--local-provider-preflight-providers",
        default="local_comfyui_image,local_comfyui_video,local_piper_tts",
    )
    build_batch_parser.add_argument("--local-provider-preflight-max-age-minutes", type=int, default=240)
    build_batch_parser.add_argument("--local-provider-preflight-image-workflow-mode", choices=("configured", "smoke", "full"), default="smoke")
    build_batch_parser.add_argument("--local-provider-preflight-video-workflow-mode", choices=("configured", "smoke", "full"), default="smoke")
    build_batch_parser.add_argument("--local-provider-preflight-report", type=Path, default=None)
    build_batch_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "season1_batch.json")

    run_batch_parser = subparsers.add_parser("run-batch", help="执行批次定义并生成批次报告")
    run_batch_parser.add_argument("--batch-file", type=Path, default=ProjectPaths.reports_dir() / "season1_batch.json")
    run_batch_parser.add_argument("--report-output", type=Path, default=ProjectPaths.reports_dir() / "season1_batch_report.json")
    run_batch_parser.add_argument("--summary-output", type=Path, default=ProjectPaths.reports_dir() / "season1_batch_summary.json")

    dashboard_parser = subparsers.add_parser("dashboard-export", help="导出批量生产 Dashboard")
    dashboard_parser.add_argument("--validation-report", type=Path, default=ProjectPaths.reports_dir() / "demo_validation_report.json")
    dashboard_parser.add_argument("--batch-summary", type=Path, default=ProjectPaths.reports_dir() / "season1_batch_summary.json")
    dashboard_parser.add_argument("--season-summary", type=Path, default=ProjectPaths.reports_dir() / "season1_summary.json")
    dashboard_parser.add_argument("--manual-import-report", type=Path, default=ProjectPaths.reports_dir() / "manual_import_report.json")
    dashboard_parser.add_argument("--retry-batch-report", type=Path, default=ProjectPaths.reports_dir() / "retry_batch_report.json")
    dashboard_parser.add_argument("--json-output", type=Path, default=ProjectPaths.reports_dir() / "dashboard.json")
    dashboard_parser.add_argument("--html-output", type=Path, default=ProjectPaths.reports_dir() / "dashboard.html")

    review_parser = subparsers.add_parser("review-metrics", help="导出批量生产数据复盘统计")
    review_parser.add_argument("--validation-report", type=Path, default=ProjectPaths.reports_dir() / "demo_validation_report.json")
    review_parser.add_argument("--dashboard", type=Path, default=ProjectPaths.reports_dir() / "dashboard.json")
    review_parser.add_argument("--manual-import-report", type=Path, default=ProjectPaths.reports_dir() / "manual_import_report.json")
    review_parser.add_argument("--retry-batch-report", type=Path, default=ProjectPaths.reports_dir() / "retry_batch_report.json")
    review_parser.add_argument("--provider-execution-report", type=Path, default=ProjectPaths.reports_dir() / "provider_execution_openai_dry_run.json")
    review_parser.add_argument("--json-output", type=Path, default=ProjectPaths.reports_dir() / "review_metrics.json")
    review_parser.add_argument("--html-output", type=Path, default=ProjectPaths.reports_dir() / "review_metrics.html")

    rework_parser = subparsers.add_parser("plan-rework", help="为指定镜头生成增量返工任务")
    rework_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    rework_parser.add_argument("--jobs-file", type=Path, default=ProjectPaths.project_root() / "jobs" / "episode_jobs.json")
    rework_parser.add_argument("--episode-code", default="E01")
    rework_parser.add_argument("--shot-ids", required=True, help="逗号分隔，如 S02,S03")
    rework_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "rework_E01.json")
    rework_parser.add_argument("--jobs-output", type=Path, default=ProjectPaths.project_root() / "jobs" / "E01_rework_jobs.json")

    navigator_parser = subparsers.add_parser("build-navigator", help="生成单集导航页")
    navigator_parser.add_argument("--episode-code", default="E01")
    navigator_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "E01_navigator.html")

    season_jobs_parser = subparsers.add_parser("build-season-jobs", help="生成整季任务包")
    season_jobs_parser.add_argument("--season-manifest", type=Path, default=ProjectPaths.manifest_dir() / "season_manifest.json")
    season_jobs_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    season_jobs_parser.add_argument("--output", type=Path, default=ProjectPaths.jobs_output_dir() / "season1_jobs.json")

    season_scan_parser = subparsers.add_parser("scan-season-assets", help="扫描整季素材状态")
    season_scan_parser.add_argument("--season-manifest", type=Path, default=ProjectPaths.manifest_dir() / "season_manifest.json")
    season_scan_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    season_scan_parser.add_argument("--asset-root", type=Path, default=ProjectPaths.demo_assets_dir())
    season_scan_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "season1_asset_scan.json")

    season_render_parser = subparsers.add_parser("render-season", help="渲染整季视频产物")
    season_render_parser.add_argument("--season-manifest", type=Path, default=ProjectPaths.manifest_dir() / "season_manifest.json")
    season_render_parser.add_argument("--episode-manifest", type=Path, default=ProjectPaths.manifest_dir() / "episode_manifest.json")
    season_render_parser.add_argument("--asset-root", type=Path, default=ProjectPaths.demo_assets_dir())
    season_render_parser.add_argument("--mode", default="preview", choices=["preview", "release"])
    season_render_parser.add_argument("--output-dir", type=Path, default=ProjectPaths.preview_outputs_dir() / "season1")
    season_render_parser.add_argument("--report-output", type=Path, default=ProjectPaths.reports_dir() / "season1_render_report.json")

    season_summary_parser = subparsers.add_parser("build-season-summary", help="生成整季总报告")
    season_summary_parser.add_argument("--season-manifest", type=Path, default=ProjectPaths.manifest_dir() / "season_manifest.json")
    season_summary_parser.add_argument("--jobs-report", type=Path, default=ProjectPaths.jobs_output_dir() / "season1_jobs.json")
    season_summary_parser.add_argument("--scan-report", type=Path, default=ProjectPaths.reports_dir() / "season1_asset_scan.json")
    season_summary_parser.add_argument("--render-report", type=Path, default=ProjectPaths.reports_dir() / "season1_render_report.json")
    season_summary_parser.add_argument("--output", type=Path, default=ProjectPaths.reports_dir() / "season1_summary.json")

    init_demo_parser = subparsers.add_parser("init-demo-db", help="初始化演示数据库")
    init_demo_parser.add_argument(
        "--database",
        type=Path,
        default=ProjectPaths.default_database_path(),
        help="SQLite 数据库路径",
    )
    return parser


def handle_status() -> int:
    print(f"project_root={ProjectPaths.project_root()}")
    print(f"config_dir={ProjectPaths.config_dir()}")
    print(f"manifest_dir={ProjectPaths.manifest_dir()}")
    print(f"state_dir={ProjectPaths.state_dir()}")
    return 0


def handle_build_jobs(episode_manifest_path: Path, output_path: Path) -> int:
    manifest = load_json(episode_manifest_path)
    jobs = build_jobs_from_episode_manifest(manifest)
    write_json(output_path, serialize_jobs(jobs))
    print(f"jobs_count={len(jobs)}")
    print(f"output={output_path}")
    return 0


def load_jobs_from_file(path: Path) -> list[JobRecord]:
    payload = load_json(path)
    jobs = []
    for item in payload.get("jobs", []):
        jobs.append(
            JobRecord(
                job_id=str(item["job_id"]),
                episode_code=str(item["episode_code"]),
                job_type=str(item["job_type"]),
                provider=str(item["provider"]),
                status=str(item["status"]),
            )
        )
    return jobs


def parse_provider_overrides(raw_value: str) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if not raw_value.strip():
        return overrides
    for item in raw_value.split(","):
        chunk = item.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key_clean = key.strip()
        value_clean = value.strip()
        if key_clean and value_clean:
            overrides[key_clean] = value_clean
    return overrides


def parse_provider_filter(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def handle_sync_states(jobs_file: Path, output_path: Path) -> int:
    jobs = load_jobs_from_file(jobs_file)
    episode_codes = sorted({job.episode_code for job in jobs})
    states = [summarize_episode_state(episode_code, jobs) for episode_code in episode_codes]
    write_state_snapshot(output_path, states)
    print(f"episode_states={len(states)}")
    print(f"output={output_path}")
    return 0


def handle_dispatch_jobs(jobs_file: Path, output_path: Path) -> int:
    jobs = load_jobs_from_file(jobs_file)
    decisions = dispatch_jobs(jobs)
    write_dispatch_report(output_path, decisions)
    print(f"dispatch_count={len(decisions)}")
    print(f"output={output_path}")
    return 0


def handle_advance_episode(current_status: str, next_status: str) -> int:
    updated_status = advance_status(current_status, next_status)
    print(f"transition={current_status}->{updated_status}")
    return 0


def handle_scan_assets(
    episode_manifest_path: Path,
    episode_code: str,
    asset_root: Path,
    output_path: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    report = scan_episode_assets(manifest, episode_code, asset_root)
    write_asset_scan_report(output_path, report)
    print(f"ready_for_preview={report['ready_for_preview']}")
    print(f"missing_required_count={report['missing_required_count']}")
    print(f"output={output_path}")
    return 0


def handle_render_preview(
    episode_manifest_path: Path,
    episode_code: str,
    asset_root: Path,
    output_path: Path,
    report_output_path: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    render_plan = build_render_plan(manifest, episode_code, asset_root)
    report = render_preview_video(render_plan, output_path, report_output_path)
    print(f"render_mode={report['render_mode']}")
    print(f"output={output_path}")
    return 0


def handle_prepare_subtitles_audio(
    episode_manifest_path: Path,
    episode_code: str,
    srt_output: Path,
    audio_plan_output: Path,
    wav_output: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    entries = build_subtitle_entries(manifest, episode_code)
    write_srt(srt_output, entries)
    audio_plan = build_audio_plan(manifest, episode_code)
    write_audio_plan(audio_plan_output, audio_plan)
    total_duration = 0
    if entries:
        total_duration = int(entries[-1]["end"])
    else:
        episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
        total_duration = sum(int(shot["duration"]) for shot in episodes[episode_code].get("shots", []))
    write_silence_wav(wav_output, max(1, total_duration))
    print(f"subtitle_count={len(entries)}")
    print(f"srt_output={srt_output}")
    print(f"audio_plan_output={audio_plan_output}")
    print(f"wav_output={wav_output}")
    return 0


def handle_horror_blueprint(
    hook: str,
    episode_code: str,
    target_seconds: int,
    max_shots: int,
    output_path: Path,
) -> int:
    payload = build_horror_story_blueprint(
        hook,
        episode_code=episode_code,
        target_seconds=target_seconds,
        max_shots=max_shots,
    )
    write_horror_blueprint(output_path, payload)
    print(f"episode_code={payload['episode_code']}")
    print(f"target_seconds={payload['target_seconds']}")
    print(f"shot_count={payload['shot_count']}")
    print(f"output={output_path}")
    return 0


def handle_build_horror_episode(
    blueprint_path: Path,
    project_id: str,
    season: int,
    output_path: Path,
) -> int:
    blueprint = load_json(blueprint_path)
    payload = build_horror_episode_manifest(blueprint, project_id=project_id, season=season)
    write_horror_episode_manifest(output_path, payload)
    episode = payload["episodes"][0]
    print(f"episode_code={episode['episode_code']}")
    print(f"shot_count={len(episode.get('shots', []))}")
    print(f"total_duration={sum(int(shot.get('duration', 0)) for shot in episode.get('shots', []))}")
    print(f"output={output_path}")
    return 0


def handle_filter_jobs(
    jobs_file: Path,
    episode_code: str | None,
    job_type: str | None,
    statuses_raw: str | None,
    output_path: Path,
) -> int:
    jobs = load_jobs_from_file(jobs_file)
    statuses = set(status.strip() for status in statuses_raw.split(",")) if statuses_raw else None
    filtered = filter_jobs(jobs, episode_code=episode_code, job_type=job_type, statuses=statuses)
    write_job_payload(output_path, filtered)
    print(f"filtered_count={len(filtered)}")
    print(f"output={output_path}")
    return 0


def handle_retry_jobs(jobs_file: Path, statuses_raw: str, output_path: Path) -> int:
    jobs = load_jobs_from_file(jobs_file)
    retryable_statuses = {item.strip() for item in statuses_raw.split(",") if item.strip()}
    updated_jobs, summary = retry_jobs(jobs, retryable_statuses)
    write_job_payload(output_path, updated_jobs)
    print(f"retried_count={summary['retried_count']}")
    print(f"output={output_path}")
    return 0


def handle_retry_batch(
    jobs_file: Path,
    statuses_raw: str,
    episode_code: str | None,
    provider: str | None,
    report_output_path: Path,
    jobs_output_path: Path,
) -> int:
    jobs = load_jobs_from_file(jobs_file)
    retryable_statuses = {item.strip() for item in statuses_raw.split(",") if item.strip()}
    report, updated_jobs = retry_batch_jobs(jobs, retryable_statuses, episode_code, provider)
    write_retry_batch_report(report_output_path, report)
    write_job_payload(jobs_output_path, updated_jobs)
    print(f"retried_count={report['retried_count']}")
    print(f"scoped_job_count={report['scoped_job_count']}")
    print(f"output={report_output_path}")
    return 0


def handle_resume_report(state_snapshot_path: Path, jobs_file: Path, dispatch_report_path: Path, output_path: Path) -> int:
    state_snapshot = load_json(state_snapshot_path)
    jobs_payload = load_json(jobs_file)
    dispatch_report = load_json(dispatch_report_path)
    report = build_resume_report(state_snapshot, jobs_payload, dispatch_report)
    write_resume_report(output_path, report)
    print(f"unfinished_episode_count={report.unfinished_episode_count}")
    print(f"unfinished_job_count={report.unfinished_job_count}")
    print(f"output={output_path}")
    return 0


def handle_init_project(
    project_name: str,
    genre: str,
    style: str,
    project_id: str | None,
    logline: str,
    protagonist_name: str,
    target_audience: str,
    tone: str,
    season_hook: str,
    episode_target_count: int,
    output_root: Path,
) -> int:
    payload = initialize_project(
        output_root,
        project_name,
        genre,
        style,
        project_id,
        logline=logline,
        protagonist_name=protagonist_name,
        target_audience=target_audience,
        tone=tone,
        season_hook=season_hook,
        episode_target_count=episode_target_count,
    )
    print(f"project_id={payload['project_id']}")
    print(f"project_root={payload['project_root']}")
    print(f"created_directory_count={payload['created_directory_count']}")
    print(f"story_bible={payload['bootstrap_paths']['story_bible']}")
    return 0


def handle_render_release(
    episode_manifest_path: Path,
    episode_code: str,
    asset_root: Path,
    output_path: Path,
    report_output_path: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    release_plan = build_release_plan(manifest, episode_code, asset_root)
    report = render_release_video(release_plan, output_path, report_output_path)
    print(f"render_profile={report['render_profile']}")
    print(f"output={output_path}")
    return 0


def handle_build_publish_pack(episode_manifest_path: Path, episode_code: str, output_path: Path) -> int:
    manifest = load_json(episode_manifest_path)
    payload = build_publish_pack(manifest, episode_code)
    write_publish_pack(output_path, payload)
    print(f"publish_title={payload['publish_title']}")
    print(f"output={output_path}")
    return 0


def handle_enhance_publish_pack(episode_manifest_path: Path, episode_code: str, output_path: Path) -> int:
    manifest = load_json(episode_manifest_path)
    payload = build_enhanced_publish_pack(manifest, episode_code)
    write_publish_pack(output_path, payload)
    print(f"title_candidates={len(payload['title_candidates'])}")
    print(f"output={output_path}")
    return 0


def handle_suggest_asset_repairs(scan_report_path: Path, output_path: Path) -> int:
    scan_report = load_json(scan_report_path)
    payload = build_repair_suggestions(scan_report)
    write_repair_suggestions(output_path, payload)
    print(f"suggestion_count={payload['suggestion_count']}")
    print(f"output={output_path}")
    return 0


def handle_plan_providers(jobs_file: Path, providers_config_path: Path, output_path: Path) -> int:
    jobs = load_jobs_from_file(jobs_file)
    payload = build_provider_plan(jobs, providers_config_path)
    write_provider_plan(output_path, payload)
    print(f"provider_count={payload['provider_count']}")
    print(f"unresolved_provider_count={payload['unresolved_provider_count']}")
    print(f"output={output_path}")
    return 0


def handle_build_provider_requests(
    episode_manifest_path: Path,
    jobs_file: Path,
    providers_config_path: Path,
    output_root: Path,
    provider_overrides_raw: str,
    output_path: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    jobs = load_jobs_from_file(jobs_file)
    provider_overrides = parse_provider_overrides(provider_overrides_raw)
    payload = build_provider_requests(manifest, jobs, providers_config_path, output_root, provider_overrides)
    write_provider_requests(output_path, payload)
    print(f"request_count={payload['request_count']}")
    print(f"ready_count={payload['ready_count']}")
    print(f"blocked_count={payload['blocked_count']}")
    print(f"output={output_path}")
    return 0


def handle_apply_provider_results(
    requests_report_path: Path,
    jobs_file: Path,
    report_output_path: Path,
    jobs_output_path: Path,
) -> int:
    provider_requests = load_json(requests_report_path)
    jobs = load_jobs_from_file(jobs_file)
    report, updated_jobs = build_provider_result_writeback(provider_requests, jobs)
    write_provider_writeback_report(report_output_path, report)
    write_job_payload(jobs_output_path, updated_jobs)
    print(f"changed_count={report['changed_count']}")
    print(f"succeeded_count={report['succeeded_count']}")
    print(f"manual_required_count={report['manual_required_count']}")
    print(f"output={report_output_path}")
    return 0


def handle_manual_import_batch(
    requests_report_path: Path,
    jobs_file: Path,
    import_root: Path,
    import_report_output_path: Path,
    writeback_report_output_path: Path,
    jobs_output_path: Path,
    overwrite: bool,
) -> int:
    provider_requests = load_json(requests_report_path)
    import_report = import_manual_outputs(provider_requests, import_root, overwrite=overwrite)
    write_manual_import_report(import_report_output_path, import_report)
    jobs = load_jobs_from_file(jobs_file)
    writeback_report, updated_jobs = build_provider_result_writeback(provider_requests, jobs)
    write_provider_writeback_report(writeback_report_output_path, writeback_report)
    write_job_payload(jobs_output_path, updated_jobs)
    print(f"imported_count={import_report['imported_count']}")
    print(f"missing_count={import_report['missing_count']}")
    print(f"writeback_succeeded_count={writeback_report['succeeded_count']}")
    print(f"output={import_report_output_path}")
    return 0


def handle_execute_provider_requests(
    requests_report_path: Path,
    providers_config_path: Path,
    providers_raw: str,
    dry_run: bool,
    confirm_live: bool,
    limit: int,
    max_failures: int,
    output_path: Path,
) -> int:
    provider_requests = load_json(requests_report_path)
    selected_providers = parse_provider_filter(providers_raw)
    payload = execute_provider_requests(
        provider_requests,
        providers_config_path,
        selected_providers if selected_providers else None,
        dry_run=dry_run,
        confirm_live=confirm_live,
        limit=limit,
        max_failures=max_failures,
    )
    write_provider_execution_report(output_path, payload)
    print(f"request_count={payload['request_count']}")
    print(f"success_count={payload['success_count']}")
    print(f"failed_count={payload['failed_count']}")
    print(f"dry_run_count={payload['dry_run_count']}")
    print(f"blocked_count={payload['blocked_count']}")
    print(f"stopped_by_failure_guard={payload['stopped_by_failure_guard']}")
    print(f"output={output_path}")
    return 0


def handle_provider_readiness(
    providers_config_path: Path,
    requests_report_path: Path,
    output_path: Path,
) -> int:
    payload = build_provider_readiness_report(providers_config_path, requests_report_path)
    write_provider_readiness_report(output_path, payload)
    print(f"status={payload['status']}")
    print(f"provider_count={payload['provider_count']}")
    print(f"manual_fallback_ready={payload['manual_fallback_ready']}")
    print(f"openai_core_ready={payload['openai_core_ready']}")
    print(f"local_core_ready={payload['local_core_ready']}")
    print(f"local_video_ready={payload['local_video_ready']}")
    print(f"output={output_path}")
    return 0


def handle_comfyui_service(
    action: str,
    host: str,
    port: int,
    wait_timeout_seconds: float,
    poll_interval_seconds: float,
    force: bool,
    output_path: Path,
) -> int:
    payload = run_comfyui_service_action(
        action,
        project_root=ProjectPaths.project_root(),
        host=host,
        port=port,
        wait_timeout_seconds=wait_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        force=force,
    )
    write_comfyui_service_report(output_path, payload)
    print(f"action={payload['action']}")
    print(f"base_url={payload['base_url']}")
    print(f"status_before={payload['status_before']['status']}")
    print(f"status_after={payload['status_after']['status']}")
    print(f"runtime_error_count={len(payload['runtime_errors'])}")
    print(f"output={output_path}")
    return 0


def handle_local_provider_live_smoke(
    providers_config_path: Path,
    providers_raw: str,
    output_root: Path,
    image_workflow_mode: str,
    video_workflow_mode: str,
    skip_comfyui_start: bool,
    restart_comfyui: bool,
    retry_comfyui_on_failure: bool,
    max_failures: int,
    comfyui_host: str,
    comfyui_port: int,
    wait_timeout_seconds: float,
    poll_interval_seconds: float,
    output_path: Path,
) -> int:
    selected_providers = parse_provider_filter(providers_raw)
    payload = run_local_provider_live_smoke(
        providers_config_path=providers_config_path,
        selected_providers=selected_providers if selected_providers else None,
        output_root=output_root,
        image_workflow_mode=image_workflow_mode,
        video_workflow_mode=video_workflow_mode,
        skip_comfyui_start=skip_comfyui_start,
        restart_comfyui=restart_comfyui,
        retry_comfyui_on_failure=retry_comfyui_on_failure,
        max_failures=max_failures,
        comfyui_host=comfyui_host,
        comfyui_port=comfyui_port,
        wait_timeout_seconds=wait_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    write_local_provider_live_smoke_report(output_path, payload)
    print(f"status={payload['status']}")
    print(f"selected_provider_count={len(payload['selected_providers'])}")
    print(f"preflight_ready_count={payload['preflight_summary']['ready_count']}")
    print(f"success_count={payload['final_summary']['success_count']}")
    print(f"failed_count={payload['final_summary']['failed_count']}")
    print(f"output={output_path}")
    return 0 if payload["status"] == "passed" else 1


def handle_dependency_audit(output_path: Path) -> int:
    payload = build_dependency_audit_report(ProjectPaths.project_root())
    write_dependency_audit_report(output_path, payload)
    print(f"lock_status={payload['lock_status']}")
    print(f"cve_audit_status={payload['cve_audit_status']}")
    print(f"blocking_count={payload['blocking_count']}")
    print(f"warning_count={payload['warning_count']}")
    print(f"output={output_path}")
    return 0


def handle_production_risk_register(
    web_config_path: Path,
    edition_config_path: Path | None,
    providers_config_path: Path,
    provider_readiness_path: Path,
    dependency_audit_path: Path,
    require_openai_live: bool,
    deployment_mode: str,
    output_path: Path,
) -> int:
    payload = build_production_risk_register(
        ProjectPaths.project_root(),
        web_config_path=web_config_path,
        edition_config_path=edition_config_path,
        providers_config_path=providers_config_path,
        provider_readiness_path=provider_readiness_path,
        dependency_audit_path=dependency_audit_path,
        require_openai_live=require_openai_live,
        deployment_mode=deployment_mode,
    )
    write_production_risk_register(output_path, payload)
    print(f"status={payload['status']}")
    print(f"risk_count={payload['risk_count']}")
    print(f"blocking_count={payload['blocking_count']}")
    print(f"warning_count={payload['warning_count']}")
    print(f"output={output_path}")
    return 0


def handle_build_batch(
    batch_id: str,
    batch_type: str,
    scope_type: str,
    scope_value: str,
    steps_raw: str,
    providers: str,
    skip_local_provider_preflight: bool,
    no_auto_run_local_provider_preflight: bool,
    local_provider_preflight_providers: str,
    local_provider_preflight_max_age_minutes: int,
    local_provider_preflight_image_workflow_mode: str,
    local_provider_preflight_video_workflow_mode: str,
    local_provider_preflight_report: Path | None,
    output_path: Path,
) -> int:
    steps = parse_steps(steps_raw)
    record = build_batch_record(
        batch_id,
        batch_type,
        scope_type,
        scope_value,
        steps,
        providers,
        output_path.with_name(f"{batch_id}_summary.json"),
    )
    payload = build_batch_payload(record)
    payload = apply_batch_preflight_gate(
        payload,
        enabled=not skip_local_provider_preflight,
        auto_run=not no_auto_run_local_provider_preflight,
        providers_raw=local_provider_preflight_providers,
        max_age_minutes=local_provider_preflight_max_age_minutes,
        image_workflow_mode=local_provider_preflight_image_workflow_mode,
        video_workflow_mode=local_provider_preflight_video_workflow_mode,
        report_path=local_provider_preflight_report,
    )
    write_batch_payload(output_path, payload)
    print(f"batch_id={record.batch_id}")
    print(f"step_count={len(steps)}")
    print(f"local_provider_preflight_enabled={payload.get('preflight_gate', {}).get('enabled', False)}")
    print(f"output={output_path}")
    return 0


def handle_run_batch(batch_file: Path, report_output_path: Path, summary_output_path: Path) -> int:
    batch_payload = load_batch_payload(batch_file)
    report, _run_records = run_batch_payload(batch_payload, report_output_path.parent)
    write_batch_payload(report_output_path, report)
    summary = build_batch_summary(report)
    write_batch_summary(summary_output_path, summary)
    print(f"batch_id={report['batch_id']}")
    print(f"step_count={report['step_count']}")
    print(f"status={report['status']}")
    if "preflight_gate" in report:
        preflight_gate = report["preflight_gate"]
        print(f"preflight_status={preflight_gate.get('status', '')}")
        print(f"preflight_mode={preflight_gate.get('mode', '')}")
    print(f"report_output={report_output_path}")
    return 0


def handle_dashboard_export(
    validation_report_path: Path,
    batch_summary_path: Path,
    season_summary_path: Path,
    manual_import_report_path: Path,
    retry_batch_report_path: Path,
    json_output_path: Path,
    html_output_path: Path,
) -> int:
    payload = build_dashboard_payload(
        validation_report_path,
        batch_summary_path,
        season_summary_path,
        manual_import_report_path,
        retry_batch_report_path,
    )
    write_dashboard_json(json_output_path, payload)
    write_dashboard_html(html_output_path, payload)
    print(f"status={payload['status']}")
    print(f"json_output={json_output_path}")
    print(f"html_output={html_output_path}")
    return 0


def handle_review_metrics(
    validation_report_path: Path,
    dashboard_path: Path,
    manual_import_report_path: Path,
    retry_batch_report_path: Path,
    provider_execution_report_path: Path,
    json_output_path: Path,
    html_output_path: Path,
) -> int:
    payload = build_review_metrics(
        validation_report_path,
        dashboard_path,
        manual_import_report_path,
        retry_batch_report_path,
        provider_execution_report_path,
    )
    write_review_metrics(json_output_path, payload)
    write_review_html(html_output_path, payload)
    print(f"status={payload['status']}")
    print(f"risk_count={len(payload['risk_flags'])}")
    print(f"json_output={json_output_path}")
    print(f"html_output={html_output_path}")
    return 0


def handle_plan_rework(
    episode_manifest_path: Path,
    jobs_file: Path,
    episode_code: str,
    shot_ids_raw: str,
    output_path: Path,
    jobs_output_path: Path,
) -> int:
    manifest = load_json(episode_manifest_path)
    jobs = load_jobs_from_file(jobs_file)
    shot_ids = {item.strip() for item in shot_ids_raw.split(",") if item.strip()}
    rework_jobs = select_rework_jobs(jobs, episode_code, shot_ids)
    report = build_rework_report(manifest, episode_code, shot_ids, rework_jobs)
    write_rework_report(output_path, report)
    write_job_payload(jobs_output_path, rework_jobs)
    print(f"rework_job_count={len(rework_jobs)}")
    print(f"output={output_path}")
    return 0


def handle_build_navigator(episode_code: str, output_path: Path) -> int:
    outputs = []
    candidate_paths = [
        ("预览视频", ProjectPaths.preview_outputs_dir() / f"{episode_code}_preview.mp4"),
        ("正式版视频", ProjectPaths.preview_outputs_dir() / f"{episode_code}_release.mp4"),
        ("字幕", ProjectPaths.state_dir() / "subtitles" / f"{episode_code}.srt"),
        ("占位音频", ProjectPaths.state_dir() / "audio" / f"{episode_code}_placeholder.wav"),
        ("发布包", ProjectPaths.reports_dir() / f"publish_pack_{episode_code}.json"),
        ("扫描报告", ProjectPaths.reports_dir() / f"asset_scan_{episode_code}.json"),
        ("渲染报告", ProjectPaths.reports_dir() / f"render_preview_{episode_code}.json"),
    ]
    for label, path in candidate_paths:
        outputs.append(
            {
                "label": label,
                "path": str(path),
                "status": "存在" if path.exists() else "缺失",
            }
        )
    html = build_episode_navigator(episode_code, outputs)
    write_navigator(output_path, html)
    print(f"output={output_path}")
    return 0


def handle_build_season_jobs(season_manifest_path: Path, episode_manifest_path: Path, output_path: Path) -> int:
    season_manifest = load_json(season_manifest_path)
    episode_manifest = load_json(episode_manifest_path)
    payload = build_season_job_bundle(season_manifest, episode_manifest)
    write_season_job_bundle(output_path, payload)
    print(f"job_count={payload['job_count']}")
    print(f"output={output_path}")
    return 0


def handle_scan_season_assets(
    season_manifest_path: Path,
    episode_manifest_path: Path,
    asset_root: Path,
    output_path: Path,
) -> int:
    season_manifest = load_json(season_manifest_path)
    episode_manifest = load_json(episode_manifest_path)
    report = scan_season_assets(season_manifest, episode_manifest, asset_root)
    write_season_scan_report(output_path, report)
    print(f"ready_episode_count={report['ready_episode_count']}")
    print(f"output={output_path}")
    return 0


def handle_render_season(
    season_manifest_path: Path,
    episode_manifest_path: Path,
    asset_root: Path,
    output_dir: Path,
    report_output_path: Path,
    mode: str,
) -> int:
    season_manifest = load_json(season_manifest_path)
    episode_manifest = load_json(episode_manifest_path)
    report = render_season(season_manifest, episode_manifest, asset_root, output_dir, report_output_path, mode=mode)
    print(f"episode_count={report['episode_count']}")
    print(f"output={report_output_path}")
    return 0


def handle_build_season_summary(
    season_manifest_path: Path,
    jobs_report_path: Path,
    scan_report_path: Path,
    render_report_path: Path,
    output_path: Path,
) -> int:
    season_manifest = load_json(season_manifest_path)
    jobs_report = load_json(jobs_report_path)
    scan_report = load_json(scan_report_path)
    render_report = load_json(render_report_path)
    payload = build_season_summary(season_manifest, jobs_report, scan_report, render_report)
    write_season_summary(output_path, payload)
    print(f"episode_count={payload['episode_count']}")
    print(f"output={output_path}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        return handle_status()

    if args.command == "build-jobs":
        return handle_build_jobs(args.episode_manifest, args.output)

    if args.command == "sync-states":
        return handle_sync_states(args.jobs_file, args.output)

    if args.command == "dispatch-jobs":
        return handle_dispatch_jobs(args.jobs_file, args.output)

    if args.command == "advance-episode":
        return handle_advance_episode(args.current, args.next)

    if args.command == "scan-assets":
        return handle_scan_assets(args.episode_manifest, args.episode_code, args.asset_root, args.output)

    if args.command == "render-preview":
        return handle_render_preview(
            args.episode_manifest,
            args.episode_code,
            args.asset_root,
            args.output,
            args.report_output,
        )

    if args.command == "prepare-subtitles-audio":
        return handle_prepare_subtitles_audio(
            args.episode_manifest,
            args.episode_code,
            args.srt_output,
            args.audio_plan_output,
            args.wav_output,
        )

    if args.command == "horror-blueprint":
        return handle_horror_blueprint(
            args.hook,
            args.episode_code,
            args.target_seconds,
            args.max_shots,
            args.output,
        )

    if args.command == "build-horror-episode":
        return handle_build_horror_episode(
            args.blueprint,
            args.project_id,
            args.season,
            args.output,
        )

    if args.command == "filter-jobs":
        return handle_filter_jobs(args.jobs_file, args.episode_code, args.job_type, args.statuses, args.output)

    if args.command == "retry-jobs":
        return handle_retry_jobs(args.jobs_file, args.statuses, args.output)

    if args.command == "retry-batch":
        return handle_retry_batch(
            args.jobs_file,
            args.statuses,
            args.episode_code,
            args.provider,
            args.report_output,
            args.jobs_output,
        )

    if args.command == "resume-report":
        return handle_resume_report(args.state_snapshot, args.jobs_file, args.dispatch_report, args.output)

    if args.command == "init-project":
        return handle_init_project(
            args.project_name,
            args.genre,
            args.style,
            args.project_id,
            args.logline,
            args.protagonist_name,
            args.target_audience,
            args.tone,
            args.season_hook,
            args.episode_target_count,
            args.output_root,
        )

    if args.command == "render-release":
        return handle_render_release(
            args.episode_manifest,
            args.episode_code,
            args.asset_root,
            args.output,
            args.report_output,
        )

    if args.command == "build-publish-pack":
        return handle_build_publish_pack(args.episode_manifest, args.episode_code, args.output)

    if args.command == "enhance-publish-pack":
        return handle_enhance_publish_pack(args.episode_manifest, args.episode_code, args.output)

    if args.command == "suggest-asset-repairs":
        return handle_suggest_asset_repairs(args.scan_report, args.output)

    if args.command == "plan-providers":
        return handle_plan_providers(args.jobs_file, args.providers_config, args.output)

    if args.command == "build-provider-requests":
        return handle_build_provider_requests(
            args.episode_manifest,
            args.jobs_file,
            args.providers_config,
            args.output_root,
            args.provider_overrides,
            args.output,
        )

    if args.command == "apply-provider-results":
        return handle_apply_provider_results(
            args.requests_report,
            args.jobs_file,
            args.report_output,
            args.jobs_output,
        )

    if args.command == "manual-import-batch":
        return handle_manual_import_batch(
            args.requests_report,
            args.jobs_file,
            args.import_root,
            args.import_report_output,
            args.writeback_report_output,
            args.jobs_output,
            args.overwrite,
        )

    if args.command == "execute-provider-requests":
        return handle_execute_provider_requests(
            args.requests_report,
            args.providers_config,
            args.providers,
            args.dry_run,
            args.confirm_live,
            args.limit,
            args.max_failures,
            args.output,
        )

    if args.command == "provider-readiness":
        return handle_provider_readiness(
            args.providers_config,
            args.requests_report,
            args.output,
        )

    if args.command == "comfyui-service":
        return handle_comfyui_service(
            args.action,
            args.host,
            args.port,
            args.wait_timeout_seconds,
            args.poll_interval_seconds,
            args.force,
            args.output,
        )

    if args.command == "local-provider-live-smoke":
        return handle_local_provider_live_smoke(
            args.providers_config,
            args.providers,
            args.output_root,
            args.image_workflow_mode,
            args.video_workflow_mode,
            args.skip_comfyui_start,
            args.restart_comfyui,
            args.retry_comfyui_on_failure,
            args.max_failures,
            args.comfyui_host,
            args.comfyui_port,
            args.wait_timeout_seconds,
            args.poll_interval_seconds,
            args.output,
        )

    if args.command == "dependency-audit":
        return handle_dependency_audit(args.output)

    if args.command == "production-risk-register":
        return handle_production_risk_register(
            args.web_config,
            args.edition_config,
            args.providers_config,
            args.provider_readiness,
            args.dependency_audit,
            args.require_openai_live,
            args.deployment_mode,
            args.output,
        )

    if args.command == "build-batch":
        return handle_build_batch(
            args.batch_id,
            args.batch_type,
            args.scope_type,
            args.scope_value,
            args.steps,
            args.providers,
            args.skip_local_provider_preflight,
            args.no_auto_run_local_provider_preflight,
            args.local_provider_preflight_providers,
            args.local_provider_preflight_max_age_minutes,
            args.local_provider_preflight_image_workflow_mode,
            args.local_provider_preflight_video_workflow_mode,
            args.local_provider_preflight_report,
            args.output,
        )

    if args.command == "run-batch":
        return handle_run_batch(args.batch_file, args.report_output, args.summary_output)

    if args.command == "dashboard-export":
        return handle_dashboard_export(
            args.validation_report,
            args.batch_summary,
            args.season_summary,
            args.manual_import_report,
            args.retry_batch_report,
            args.json_output,
            args.html_output,
        )

    if args.command == "review-metrics":
        return handle_review_metrics(
            args.validation_report,
            args.dashboard,
            args.manual_import_report,
            args.retry_batch_report,
            args.provider_execution_report,
            args.json_output,
            args.html_output,
        )

    if args.command == "plan-rework":
        return handle_plan_rework(
            args.episode_manifest,
            args.jobs_file,
            args.episode_code,
            args.shot_ids,
            args.output,
            args.jobs_output,
        )

    if args.command == "build-navigator":
        return handle_build_navigator(args.episode_code, args.output)

    if args.command == "build-season-jobs":
        return handle_build_season_jobs(args.season_manifest, args.episode_manifest, args.output)

    if args.command == "scan-season-assets":
        return handle_scan_season_assets(args.season_manifest, args.episode_manifest, args.asset_root, args.output)

    if args.command == "render-season":
        return handle_render_season(
            args.season_manifest,
            args.episode_manifest,
            args.asset_root,
            args.output_dir,
            args.report_output,
            args.mode,
        )

    if args.command == "build-season-summary":
        return handle_build_season_summary(
            args.season_manifest,
            args.jobs_report,
            args.scan_report,
            args.render_report,
            args.output,
        )

    if args.command == "init-demo-db":
        print(f"database={args.database}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
