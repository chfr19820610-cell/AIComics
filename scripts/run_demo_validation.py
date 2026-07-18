from __future__ import annotations

from dataclasses import asdict
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.batch.coordinator import build_batch_payload, build_batch_record, run_batch_payload, write_batch_payload
from aicomic.batch.reporter import build_batch_summary, write_batch_summary
from aicomic.batch.retry_manager import retry_batch_jobs, write_retry_batch_report
from aicomic.core.config import ProjectPaths
from aicomic.core.database import (
    collect_job_status_by_episode,
    collect_statistics,
    connect_database,
    initialize_schema,
    insert_batch,
    insert_batch_runs,
    insert_episodes,
    insert_episode_states,
    insert_jobs,
    insert_provider_requests,
    insert_project,
    insert_season,
)
from aicomic.core.dispatcher import dispatch_jobs, write_dispatch_report
from aicomic.core.episode_lifecycle import advance_status
from aicomic.core.job_control import filter_jobs, retry_jobs, write_job_payload
from aicomic.core.job_builder import build_jobs_from_episode_manifest, serialize_jobs
from aicomic.core.manifest import load_json, write_json
from aicomic.core.models import EpisodeRecord, EpisodeStateRecord, JobRecord, ProjectRecord, SeasonRecord
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
from aicomic.providers.manual_importer import import_manual_outputs, write_manual_import_report
from aicomic.providers.provider_planner import build_provider_plan, write_provider_plan
from aicomic.providers.readiness import build_provider_readiness_report, write_provider_readiness_report
from aicomic.providers.request_builder import build_provider_requests, extract_request_records, write_provider_requests
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
from aicomic.security.production_rehearsal import (
    build_rehearsal_environment,
    prepare_comfyui_fixture_models,
    run_mock_comfyui_server,
    temporary_environment,
)

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None


def reset_demo_tables(connection) -> None:
    connection.execute("DELETE FROM batch_runs")
    connection.execute("DELETE FROM batches")
    connection.execute("DELETE FROM provider_requests")
    connection.execute("DELETE FROM jobs")
    connection.execute("DELETE FROM episodes")
    connection.execute("DELETE FROM seasons")
    connection.execute("DELETE FROM projects")
    connection.commit()


def build_demo_payload() -> tuple[ProjectRecord, SeasonRecord, list[EpisodeRecord], list[JobRecord]]:
    project = ProjectRecord(
        project_id="aicomic_system",
        project_name="AI漫剧自动生成系统",
        genre="现代职场逆袭",
        status="mvp_bootstrap",
    )
    season = SeasonRecord("aicomic_system", 1, "职场逆袭第一季", "planning")
    episodes = [
        EpisodeRecord("E01", "被当众刁难的实习生", "script_ready", 4),
        EpisodeRecord("E02", "总裁第一次公开撑腰", "shotlist_ready", 3),
    ]
    episode_manifest = load_json(ProjectPaths.manifest_dir() / "episode_manifest.json")
    jobs = build_jobs_from_episode_manifest(episode_manifest)
    for index, job in enumerate(jobs):
        if index < 4:
            job.status = "succeeded"
    return project, season, episodes, jobs


def create_demo_image(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if Image is None or ImageDraw is None:
        path.write_bytes(b"")
        return
    canvas = Image.new("RGB", (720, 1280), "#202020")
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 80), label, fill="#ffffff")
    canvas.save(path)


def build_demo_assets(manifest: dict[str, object], asset_root: Path, episode_code: str) -> None:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    for shot in episode.get("shots", []):
        shot_id = str(shot["shot_id"])
        image_path = asset_root / episode_code / "images" / f"{episode_code}_{shot_id}_key.png"
        create_demo_image(image_path, f"{episode_code} {shot_id}")


def create_manual_import_placeholder(path: Path, label: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        create_demo_image(path, label)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".wav":
        path.write_bytes(b"demo wav from production fallback import")
    elif suffix == ".mp4":
        path.write_bytes(b"demo mp4 from production fallback import")
    else:
        path.write_text(f"demo output for {label}", encoding="utf-8")


def build_manual_import_samples(import_root: Path, provider_requests: dict[str, object]) -> list[Path]:
    import_root.mkdir(parents=True, exist_ok=True)
    sample_files: list[Path] = []
    seen_filenames: set[str] = set()
    for request in provider_requests.get("requests", []):
        payload = request.get("payload", {}) if isinstance(request, dict) else {}
        output_path = Path(str(payload.get("output_path", "")))
        if not output_path.name:
            continue
        normalized_name = output_path.name.lower()
        if normalized_name in seen_filenames:
            continue
        seen_filenames.add(normalized_name)
        source_path = import_root / output_path.name
        create_manual_import_placeholder(source_path, output_path.stem)
        sample_files.append(source_path)
    return sample_files


def reset_manual_import_targets(asset_root: Path) -> None:
    target_paths = [
        asset_root / "E01" / "audio" / "E01_S01_tts.wav",
        asset_root / "E01" / "videos" / "E01_S02_motion.mp4",
    ]
    for target_path in target_paths:
        if target_path.exists():
            target_path.unlink()


def main() -> int:
    database_path = ProjectPaths.default_database_path()
    reports_dir = ProjectPaths.reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    state_dir = ProjectPaths.state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    asset_root = ProjectPaths.demo_assets_dir()
    asset_root.mkdir(parents=True, exist_ok=True)

    connection = connect_database(database_path)
    initialize_schema(connection)
    reset_demo_tables(connection)

    project, season, episodes, jobs = build_demo_payload()
    insert_project(connection, project)
    insert_season(connection, season)
    insert_episodes(connection, episodes)
    insert_jobs(connection, jobs)

    jobs_payload_path = PROJECT_ROOT / "jobs" / "episode_jobs.json"
    write_json(jobs_payload_path, serialize_jobs(jobs))

    episode_manifest = load_json(ProjectPaths.manifest_dir() / "episode_manifest.json")
    season_manifest = load_json(ProjectPaths.manifest_dir() / "season_manifest.json")
    build_demo_assets(episode_manifest, asset_root, "E01")
    reset_manual_import_targets(asset_root)

    asset_scan_report_path = reports_dir / "asset_scan_E01.json"
    asset_scan_report = scan_episode_assets(episode_manifest, "E01", asset_root)
    write_asset_scan_report(asset_scan_report_path, asset_scan_report)

    episode_states = [summarize_episode_state(episode.episode_code, jobs) for episode in episodes]
    state_records = [
        EpisodeStateRecord(
            episode_code=item.episode_code,
            status=item.status,
            completed_jobs=item.completed_jobs,
            total_jobs=item.total_jobs,
        )
        for item in episode_states
    ]
    insert_episode_states(connection, state_records)

    state_snapshot_path = state_dir / "episode_state_snapshot.json"
    write_state_snapshot(state_snapshot_path, episode_states)

    dispatch_report_path = reports_dir / "dispatch_report.json"
    dispatch_decisions = dispatch_jobs(jobs)
    write_dispatch_report(dispatch_report_path, dispatch_decisions)

    initialized_project = initialize_project(
        ProjectPaths.generated_projects_dir(),
        "批量量产演示项目",
        "现代职场逆袭",
        "动漫漫剧",
        "batch_demo_project",
    )

    provider_plan_path = reports_dir / "provider_plan.json"
    provider_plan = build_provider_plan(jobs, ProjectPaths.providers_config_path())
    write_provider_plan(provider_plan_path, provider_plan)

    provider_requests_path = reports_dir / "provider_requests.json"
    provider_requests = build_provider_requests(
        episode_manifest,
        jobs,
        ProjectPaths.providers_config_path(),
        asset_root,
    )
    write_provider_requests(provider_requests_path, provider_requests)
    insert_provider_requests(connection, extract_request_records(provider_requests))

    provider_requests_openai_path = reports_dir / "provider_requests_openai.json"
    provider_requests_openai = build_provider_requests(
        episode_manifest,
        jobs,
        ProjectPaths.providers_config_path(),
        asset_root,
        {"image": "openai_image", "tts": "openai_tts"},
    )
    write_provider_requests(provider_requests_openai_path, provider_requests_openai)

    provider_execution_dry_run_path = reports_dir / "provider_execution_openai_dry_run.json"
    provider_execution_dry_run = execute_provider_requests(
        provider_requests_openai,
        ProjectPaths.providers_config_path(),
        {"openai_image", "openai_tts"},
        dry_run=True,
    )
    write_provider_execution_report(provider_execution_dry_run_path, provider_execution_dry_run)

    provider_execution_safe_block_path = reports_dir / "provider_execution_openai_safe_block.json"
    provider_execution_safe_block = execute_provider_requests(
        provider_requests_openai,
        ProjectPaths.providers_config_path(),
        {"openai_image", "openai_tts"},
        dry_run=False,
        confirm_live=False,
        limit=1,
        max_failures=1,
    )
    write_provider_execution_report(provider_execution_safe_block_path, provider_execution_safe_block)

    provider_requests_local_path = reports_dir / "provider_requests_local.json"
    provider_requests_local = build_provider_requests(
        episode_manifest,
        jobs,
        ProjectPaths.providers_config_path(),
        asset_root,
        {"image": "local_comfyui_image", "video": "local_comfyui_video", "tts": "local_piper_tts"},
    )
    write_provider_requests(provider_requests_local_path, provider_requests_local)

    provider_readiness_path = reports_dir / "provider_readiness_report.json"
    provider_readiness_report = build_provider_readiness_report(
        ProjectPaths.providers_config_path(),
        provider_requests_local_path,
    )
    write_provider_readiness_report(provider_readiness_path, provider_readiness_report)

    dependency_audit_path = reports_dir / "dependency_audit_report.json"
    dependency_audit_report = build_dependency_audit_report(PROJECT_ROOT)
    write_dependency_audit_report(dependency_audit_path, dependency_audit_report)

    production_risk_register_path = reports_dir / "production_risk_register.json"
    production_risk_register = build_production_risk_register(
        PROJECT_ROOT,
        web_config_path=PROJECT_ROOT / "config" / "web.yaml",
        edition_config_path=PROJECT_ROOT / "config" / "edition.yaml",
        providers_config_path=ProjectPaths.providers_config_path(),
        provider_readiness_path=provider_readiness_path,
        dependency_audit_path=dependency_audit_path,
        require_openai_live=False,
        deployment_mode="production",
    )
    write_production_risk_register(production_risk_register_path, production_risk_register)

    rehearsal_model_root = state_dir / "production_rehearsal" / "comfyui_models"
    comfyui_fixture_report = prepare_comfyui_fixture_models(
        rehearsal_model_root,
        PROJECT_ROOT / "local_providers" / "comfyui" / "model_requirements.json",
    )
    with run_mock_comfyui_server() as mock_comfyui:
        rehearsal_env = build_rehearsal_environment(PROJECT_ROOT, str(mock_comfyui["base_url"]), rehearsal_model_root)
        with temporary_environment(rehearsal_env):
            provider_execution_local_dry_run_path = reports_dir / "provider_execution_local_dry_run.json"
            provider_execution_local_dry_run = execute_provider_requests(
                provider_requests_local,
                ProjectPaths.providers_config_path(),
                {"local_comfyui_image", "local_comfyui_video", "local_piper_tts"},
                dry_run=True,
            )
            write_provider_execution_report(provider_execution_local_dry_run_path, provider_execution_local_dry_run)

            rehearsal_provider_readiness_path = reports_dir / "provider_readiness_rehearsal_report.json"
            rehearsal_provider_readiness_report = build_provider_readiness_report(
                ProjectPaths.providers_config_path(),
                provider_requests_local_path,
            )
            write_provider_readiness_report(rehearsal_provider_readiness_path, rehearsal_provider_readiness_report)

            rehearsal_production_risk_register_path = reports_dir / "production_risk_register_rehearsal.json"
            rehearsal_production_risk_register = build_production_risk_register(
                PROJECT_ROOT,
                web_config_path=PROJECT_ROOT / "config" / "web.production.example.yaml",
                providers_config_path=ProjectPaths.providers_config_path(),
                provider_readiness_path=rehearsal_provider_readiness_path,
                dependency_audit_path=dependency_audit_path,
                require_openai_live=False,
                deployment_mode="rehearsal",
            )
            write_production_risk_register(rehearsal_production_risk_register_path, rehearsal_production_risk_register)
            production_rehearsal_env_summary = {
                key: ("<configured>" if key == "AICOMIC_JWT_SECRET" else value)
                for key, value in rehearsal_env.items()
            }
            production_rehearsal_comfyui = dict(mock_comfyui)

    batch_file_path = reports_dir / "season1_batch.json"
    batch_record = build_batch_record(
        "season1_batch_demo",
        "season_pipeline",
        "season",
        "S01",
        ["build_season_jobs", "scan_season_assets", "build_provider_requests", "render_season"],
        "manual_web,windows_tts",
        reports_dir / "season1_batch_summary.json",
    )
    batch_payload = build_batch_payload(batch_record)
    write_batch_payload(batch_file_path, batch_payload)
    insert_batch(connection, batch_record)

    batch_report_path = reports_dir / "season1_batch_report.json"
    batch_report, batch_run_records = run_batch_payload(batch_payload, reports_dir)
    write_batch_payload(batch_report_path, batch_report)
    insert_batch_runs(connection, batch_run_records)
    batch_summary_path = reports_dir / "season1_batch_summary.json"
    batch_summary = build_batch_summary(batch_report)
    write_batch_summary(batch_summary_path, batch_summary)

    provider_writeback_report_path = reports_dir / "provider_writeback_report.json"
    provider_synced_jobs_path = PROJECT_ROOT / "jobs" / "episode_jobs_provider_synced.json"
    provider_writeback_report, provider_synced_jobs = build_provider_result_writeback(provider_requests, jobs)
    write_provider_writeback_report(provider_writeback_report_path, provider_writeback_report)
    write_job_payload(provider_synced_jobs_path, provider_synced_jobs)
    insert_jobs(connection, provider_synced_jobs)

    manual_import_root = state_dir / "manual_import_sources" / "season1_batch_demo"
    manual_import_samples = build_manual_import_samples(manual_import_root, provider_requests)
    manual_import_report_path = reports_dir / "manual_import_report.json"
    manual_import_report = import_manual_outputs(provider_requests, manual_import_root, overwrite=True)
    write_manual_import_report(manual_import_report_path, manual_import_report)

    manual_import_writeback_report_path = reports_dir / "manual_import_writeback_report.json"
    manual_import_jobs_path = PROJECT_ROOT / "jobs" / "episode_jobs_manual_import_synced.json"
    manual_import_writeback_report, manual_import_jobs = build_provider_result_writeback(provider_requests, provider_synced_jobs)
    write_provider_writeback_report(manual_import_writeback_report_path, manual_import_writeback_report)
    write_job_payload(manual_import_jobs_path, manual_import_jobs)
    insert_jobs(connection, manual_import_jobs)

    retry_batch_report_path = reports_dir / "retry_batch_report.json"
    retry_batch_jobs_path = PROJECT_ROOT / "jobs" / "episode_jobs_batch_retried.json"
    retry_batch_report, retry_batch_updated_jobs = retry_batch_jobs(
        manual_import_jobs,
        {"manual_required", "failed"},
    )
    write_retry_batch_report(retry_batch_report_path, retry_batch_report)
    write_job_payload(retry_batch_jobs_path, retry_batch_updated_jobs)
    insert_jobs(connection, retry_batch_updated_jobs)

    episode_states = [summarize_episode_state(episode.episode_code, retry_batch_updated_jobs) for episode in episodes]
    state_records = [
        EpisodeStateRecord(
            episode_code=item.episode_code,
            status=item.status,
            completed_jobs=item.completed_jobs,
            total_jobs=item.total_jobs,
        )
        for item in episode_states
    ]
    insert_episode_states(connection, state_records)
    write_state_snapshot(state_snapshot_path, episode_states)

    subtitle_entries = build_subtitle_entries(episode_manifest, "E01")
    subtitle_output_path = state_dir / "subtitles" / "E01.srt"
    write_srt(subtitle_output_path, subtitle_entries)
    audio_plan = build_audio_plan(episode_manifest, "E01")
    audio_plan_path = reports_dir / "audio_plan_E01.json"
    write_audio_plan(audio_plan_path, audio_plan)
    placeholder_wav_path = state_dir / "audio" / "E01_placeholder.wav"
    total_subtitle_duration = int(subtitle_entries[-1]["end"]) if subtitle_entries else 1
    write_silence_wav(placeholder_wav_path, max(1, total_subtitle_duration))

    preview_output_path = ProjectPaths.preview_outputs_dir() / "E01_preview.mp4"
    preview_report_path = reports_dir / "render_preview_E01.json"
    render_plan = build_render_plan(episode_manifest, "E01", asset_root)
    preview_report = render_preview_video(render_plan, preview_output_path, preview_report_path)

    release_output_path = ProjectPaths.preview_outputs_dir() / "E01_release.mp4"
    release_report_path = reports_dir / "render_release_E01.json"
    release_plan = build_release_plan(episode_manifest, "E01", asset_root)
    release_report = render_release_video(release_plan, release_output_path, release_report_path)

    filtered_jobs_path = reports_dir / "filtered_pending_E01_jobs.json"
    filtered_jobs = filter_jobs(retry_batch_updated_jobs, episode_code="E01", statuses={"pending"})
    write_job_payload(filtered_jobs_path, filtered_jobs)

    retried_jobs_path = PROJECT_ROOT / "jobs" / "episode_jobs_retried.json"
    retried_jobs, retry_summary = retry_jobs(retry_batch_updated_jobs, {"pending"})
    write_job_payload(retried_jobs_path, retried_jobs)

    resume_report_path = reports_dir / "resume_report.json"
    resume_report = build_resume_report(
        load_json(state_snapshot_path),
        load_json(retry_batch_jobs_path),
        load_json(dispatch_report_path),
    )
    write_resume_report(resume_report_path, resume_report)

    publish_pack_path = reports_dir / "publish_pack_E01.json"
    publish_pack = build_publish_pack(episode_manifest, "E01")
    write_publish_pack(publish_pack_path, publish_pack)

    enhanced_publish_pack_path = reports_dir / "publish_pack_E01_enhanced.json"
    enhanced_publish_pack = build_enhanced_publish_pack(episode_manifest, "E01")
    write_publish_pack(enhanced_publish_pack_path, enhanced_publish_pack)

    repair_suggestions_path = reports_dir / "asset_repair_E01.json"
    repair_suggestions = build_repair_suggestions(asset_scan_report)
    write_repair_suggestions(repair_suggestions_path, repair_suggestions)

    rework_jobs = select_rework_jobs(jobs, "E01", {"S02", "S03"})
    rework_report = build_rework_report(episode_manifest, "E01", {"S02", "S03"}, rework_jobs)
    rework_report_path = reports_dir / "rework_E01.json"
    write_rework_report(rework_report_path, rework_report)
    rework_jobs_path = PROJECT_ROOT / "jobs" / "E01_rework_jobs.json"
    write_job_payload(rework_jobs_path, rework_jobs)

    navigator_output_path = reports_dir / "E01_navigator.html"
    navigator_html = build_episode_navigator(
        "E01",
        [
            {"label": "预览视频", "path": str(preview_output_path), "status": "存在" if preview_output_path.exists() else "缺失"},
            {"label": "正式版视频", "path": str(release_output_path), "status": "存在" if release_output_path.exists() else "缺失"},
            {"label": "字幕", "path": str(subtitle_output_path), "status": "存在" if subtitle_output_path.exists() else "缺失"},
            {"label": "发布包", "path": str(publish_pack_path), "status": "存在" if publish_pack_path.exists() else "缺失"},
        ],
    )
    write_navigator(navigator_output_path, navigator_html)

    season_jobs_path = PROJECT_ROOT / "jobs" / "season1_jobs.json"
    season_jobs_payload = build_season_job_bundle(season_manifest, episode_manifest)
    write_season_job_bundle(season_jobs_path, season_jobs_payload)

    season_scan_report_path = reports_dir / "season1_asset_scan.json"
    season_scan_report = scan_season_assets(season_manifest, episode_manifest, asset_root)
    write_season_scan_report(season_scan_report_path, season_scan_report)

    season_render_report_path = reports_dir / "season1_render_report.json"
    season_render_payload = render_season(
        season_manifest,
        episode_manifest,
        asset_root,
        ProjectPaths.preview_outputs_dir() / "season1",
        season_render_report_path,
        mode="preview",
    )

    season_summary_path = reports_dir / "season1_summary.json"
    season_summary_payload = build_season_summary(
        season_manifest,
        season_jobs_payload,
        season_scan_report,
        season_render_payload,
    )
    write_season_summary(season_summary_path, season_summary_payload)

    lifecycle_result = advance_status("script_ready", "shotlist_ready")

    statistics = collect_statistics(connection)
    statistics["generated_jobs_count"] = len(jobs)
    statistics["episode_states"] = {
        item.episode_code: asdict(item) for item in episode_states
    }
    statistics["job_status_by_episode"] = collect_job_status_by_episode(connection)
    statistics["jobs_payload_path"] = str(jobs_payload_path)
    statistics["state_snapshot_path"] = str(state_snapshot_path)
    statistics["dispatch_report_path"] = str(dispatch_report_path)
    statistics["dispatch_count"] = len(dispatch_decisions)
    statistics["initialized_project_root"] = str(initialized_project["project_root"])
    statistics["initialized_project_id"] = str(initialized_project["project_id"])
    statistics["initialized_project_directory_count"] = int(initialized_project["created_directory_count"])
    statistics["provider_plan_path"] = str(provider_plan_path)
    statistics["provider_count"] = int(provider_plan["provider_count"])
    statistics["provider_job_route_count"] = int(provider_plan["job_route_count"])
    statistics["provider_unresolved_count"] = int(provider_plan["unresolved_provider_count"])
    statistics["provider_requests_path"] = str(provider_requests_path)
    statistics["provider_request_count"] = int(provider_requests["request_count"])
    statistics["provider_ready_request_count"] = int(provider_requests["ready_count"])
    statistics["provider_blocked_request_count"] = int(provider_requests["blocked_count"])
    statistics["provider_requests_openai_path"] = str(provider_requests_openai_path)
    statistics["provider_openai_request_count"] = int(provider_requests_openai["request_count"])
    statistics["provider_openai_blocked_count"] = int(provider_requests_openai["blocked_count"])
    statistics["provider_execution_dry_run_path"] = str(provider_execution_dry_run_path)
    statistics["provider_execution_dry_run_count"] = int(provider_execution_dry_run["dry_run_count"])
    statistics["provider_execution_skipped_count"] = int(provider_execution_dry_run["skipped_count"])
    statistics["provider_execution_safe_block_path"] = str(provider_execution_safe_block_path)
    statistics["provider_execution_safe_blocked_count"] = int(provider_execution_safe_block["blocked_count"])
    statistics["provider_execution_confirm_live"] = bool(provider_execution_safe_block["confirm_live"])
    statistics["provider_execution_limit"] = int(provider_execution_safe_block["limit"])
    statistics["provider_execution_attempt_count"] = int(provider_execution_safe_block["execution_attempt_count"])
    statistics["provider_execution_stopped_by_failure_guard"] = bool(provider_execution_safe_block["stopped_by_failure_guard"])
    statistics["provider_requests_local_path"] = str(provider_requests_local_path)
    statistics["provider_local_request_count"] = int(provider_requests_local["request_count"])
    statistics["provider_local_blocked_count"] = int(provider_requests_local["blocked_count"])
    statistics["provider_execution_local_dry_run_path"] = str(provider_execution_local_dry_run_path)
    statistics["provider_execution_local_dry_run_count"] = int(provider_execution_local_dry_run["dry_run_count"])
    statistics["provider_execution_local_ready_count"] = int(provider_execution_local_dry_run["provider_ready_count"])
    statistics["provider_execution_local_not_ready_count"] = int(provider_execution_local_dry_run["provider_not_ready_count"])
    statistics["provider_readiness_path"] = str(provider_readiness_path)
    statistics["provider_readiness_status"] = str(provider_readiness_report["status"])
    statistics["provider_readiness_blocking_count"] = len(provider_readiness_report["blocking_reasons"])
    statistics["provider_readiness_full_local_ready"] = bool(provider_readiness_report["full_local_ready"])
    statistics["provider_readiness_local_video_ready"] = bool(provider_readiness_report["local_video_ready"])
    statistics["provider_readiness_rehearsal_path"] = str(rehearsal_provider_readiness_path)
    statistics["provider_readiness_rehearsal_status"] = str(rehearsal_provider_readiness_report["status"])
    statistics["provider_readiness_rehearsal_blocking_count"] = len(rehearsal_provider_readiness_report["blocking_reasons"])
    statistics["production_rehearsal_runtime_mode"] = "mock_comfyui_with_fixture_models"
    statistics["production_rehearsal_env"] = production_rehearsal_env_summary
    statistics["production_rehearsal_comfyui"] = production_rehearsal_comfyui
    statistics["production_rehearsal_comfyui_fixture_model_count"] = int(comfyui_fixture_report["fixture_model_count"])
    statistics["production_rehearsal_comfyui_fixture_model_root"] = str(rehearsal_model_root)
    readiness_items = {
        str(item.get("provider", "")): item
        for item in provider_readiness_report.get("items", [])
        if isinstance(item, dict) and item.get("provider")
    }
    for provider_name in ("local_comfyui_image", "local_comfyui_video", "local_piper_tts"):
        provider_item = readiness_items.get(provider_name, {})
        readiness = provider_item.get("readiness", {}) if isinstance(provider_item, dict) else {}
        key_prefix = f"provider_readiness_{provider_name}"
        statistics[f"{key_prefix}_ready"] = bool(provider_item.get("ready", False))
        statistics[f"{key_prefix}_missing_required_model_count"] = int(readiness.get("missing_required_model_count", 0))
        statistics[f"{key_prefix}_license_status"] = str(readiness.get("license_status", ""))
        statistics[f"{key_prefix}_server_available"] = bool(readiness.get("comfyui_server_available", False))
    statistics["dependency_audit_path"] = str(dependency_audit_path)
    statistics["dependency_lock_status"] = str(dependency_audit_report["lock_status"])
    statistics["dependency_cve_audit_status"] = str(dependency_audit_report["cve_audit_status"])
    statistics["dependency_audit_tool_status"] = str(dependency_audit_report["audit_tool_status"])
    statistics["dependency_transitive_lock_status"] = str(dependency_audit_report["transitive_lock_status"])
    statistics["dependency_known_vulnerability_count"] = int(dependency_audit_report["known_vulnerability_count"])
    statistics["production_risk_register_path"] = str(production_risk_register_path)
    statistics["production_risk_register_status"] = str(production_risk_register["status"])
    statistics["production_risk_blocking_count"] = int(production_risk_register["blocking_count"])
    statistics["production_risk_warning_count"] = int(production_risk_register["warning_count"])
    statistics["production_risk_deployment_mode"] = str(production_risk_register["deployment_mode"])
    statistics["production_risk_register_rehearsal_path"] = str(rehearsal_production_risk_register_path)
    statistics["production_risk_register_rehearsal_status"] = str(rehearsal_production_risk_register["status"])
    statistics["production_risk_rehearsal_blocking_count"] = int(rehearsal_production_risk_register["blocking_count"])
    statistics["production_risk_rehearsal_warning_count"] = int(rehearsal_production_risk_register["warning_count"])
    statistics["production_risk_rehearsal_deployment_mode"] = str(rehearsal_production_risk_register["deployment_mode"])
    statistics["batch_file_path"] = str(batch_file_path)
    statistics["batch_report_path"] = str(batch_report_path)
    statistics["batch_summary_path"] = str(batch_summary_path)
    statistics["batch_step_count"] = int(batch_report["step_count"])
    statistics["batch_simulated_step_count"] = int(batch_report["simulated_step_count"])
    statistics["provider_writeback_report_path"] = str(provider_writeback_report_path)
    statistics["provider_synced_jobs_path"] = str(provider_synced_jobs_path)
    statistics["provider_writeback_changed_count"] = int(provider_writeback_report["changed_count"])
    statistics["provider_writeback_succeeded_count"] = int(provider_writeback_report["succeeded_count"])
    statistics["provider_writeback_manual_required_count"] = int(provider_writeback_report["manual_required_count"])
    statistics["manual_import_root"] = str(manual_import_root)
    statistics["manual_import_sample_count"] = len(manual_import_samples)
    statistics["manual_import_report_path"] = str(manual_import_report_path)
    statistics["manual_import_imported_count"] = int(manual_import_report["imported_count"])
    statistics["manual_import_missing_count"] = int(manual_import_report["missing_count"])
    statistics["manual_import_writeback_report_path"] = str(manual_import_writeback_report_path)
    statistics["manual_import_jobs_path"] = str(manual_import_jobs_path)
    statistics["manual_import_succeeded_count"] = int(manual_import_writeback_report["succeeded_count"])
    statistics["manual_import_manual_required_count"] = int(manual_import_writeback_report["manual_required_count"])
    statistics["retry_batch_report_path"] = str(retry_batch_report_path)
    statistics["retry_batch_jobs_path"] = str(retry_batch_jobs_path)
    statistics["retry_batch_retried_count"] = int(retry_batch_report["retried_count"])
    statistics["retry_batch_scoped_job_count"] = int(retry_batch_report["scoped_job_count"])
    production_fallback_ready = (
        int(manual_import_report["missing_count"]) == 0
        and int(manual_import_writeback_report["manual_required_count"]) == 0
        and int(retry_batch_report["retried_count"]) == 0
    )
    statistics["production_fallback_ready"] = production_fallback_ready
    production_local_provider_ready = (
        int(provider_execution_local_dry_run["execution_attempt_count"]) > 0
        and int(provider_execution_local_dry_run["provider_not_ready_count"]) == 0
    )
    statistics["production_readiness_status"] = (
        "ready_with_local_provider"
        if production_fallback_ready and production_local_provider_ready
        else "ready_with_local_fallback"
        if production_fallback_ready
        else "needs_production_inputs"
    )
    statistics["production_live_provider_ready"] = bool(provider_execution_dry_run.get("api_key_ready", False))
    statistics["production_local_provider_ready"] = production_local_provider_ready
    statistics["production_local_provider_rehearsal_ready"] = bool(rehearsal_provider_readiness_report["full_local_ready"])
    statistics["production_live_provider_required"] = False
    statistics["production_batch_failure_rate"] = 0.0 if str(batch_summary.get("status", "")) == "completed" else 100.0
    statistics["asset_scan_ready_for_preview"] = bool(asset_scan_report["ready_for_preview"])
    statistics["asset_scan_missing_required_count"] = int(asset_scan_report["missing_required_count"])
    statistics["asset_scan_report_path"] = str(asset_scan_report_path)
    statistics["preview_render_mode"] = str(preview_report["render_mode"])
    statistics["preview_output_path"] = str(preview_output_path)
    statistics["preview_report_path"] = str(preview_report_path)
    statistics["release_render_profile"] = str(release_report["render_profile"])
    statistics["release_output_path"] = str(release_output_path)
    statistics["release_report_path"] = str(release_report_path)
    statistics["subtitle_count"] = len(subtitle_entries)
    statistics["subtitle_output_path"] = str(subtitle_output_path)
    statistics["audio_plan_path"] = str(audio_plan_path)
    statistics["placeholder_wav_path"] = str(placeholder_wav_path)
    statistics["filtered_pending_e01_jobs_count"] = len(filtered_jobs)
    statistics["filtered_pending_jobs_report_path"] = str(filtered_jobs_path)
    statistics["retried_count"] = int(retry_summary["retried_count"])
    statistics["retried_jobs_path"] = str(retried_jobs_path)
    statistics["resume_report_path"] = str(resume_report_path)
    statistics["resume_unfinished_episode_count"] = int(resume_report.unfinished_episode_count)
    statistics["resume_unfinished_job_count"] = int(resume_report.unfinished_job_count)
    statistics["publish_pack_path"] = str(publish_pack_path)
    statistics["publish_title"] = str(publish_pack["publish_title"])
    statistics["enhanced_publish_pack_path"] = str(enhanced_publish_pack_path)
    statistics["enhanced_title_candidate_count"] = len(enhanced_publish_pack["title_candidates"])
    statistics["repair_suggestions_path"] = str(repair_suggestions_path)
    statistics["repair_suggestion_count"] = int(repair_suggestions["suggestion_count"])
    statistics["rework_job_count"] = len(rework_jobs)
    statistics["rework_report_path"] = str(rework_report_path)
    statistics["rework_jobs_path"] = str(rework_jobs_path)
    statistics["navigator_output_path"] = str(navigator_output_path)
    statistics["season_jobs_path"] = str(season_jobs_path)
    statistics["season_job_count"] = int(season_jobs_payload["job_count"])
    statistics["season_scan_report_path"] = str(season_scan_report_path)
    statistics["season_ready_episode_count"] = int(season_scan_report["ready_episode_count"])
    statistics["season_render_report_path"] = str(season_render_report_path)
    statistics["season_rendered_episode_count"] = int(season_render_payload["episode_count"])
    statistics["season_summary_path"] = str(season_summary_path)
    statistics["lifecycle_transition"] = lifecycle_result
    statistics["database_path"] = str(database_path)
    statistics["project_root"] = str(ProjectPaths.project_root())

    report_path = reports_dir / "demo_validation_report.json"
    report_path.write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")

    dashboard_json_path = reports_dir / "dashboard.json"
    dashboard_html_path = reports_dir / "dashboard.html"
    dashboard_payload = build_dashboard_payload(
        report_path,
        batch_summary_path,
        season_summary_path,
        manual_import_report_path,
        retry_batch_report_path,
    )
    write_dashboard_json(dashboard_json_path, dashboard_payload)
    write_dashboard_html(dashboard_html_path, dashboard_payload)
    statistics["dashboard_json_path"] = str(dashboard_json_path)
    statistics["dashboard_html_path"] = str(dashboard_html_path)
    statistics["dashboard_status"] = str(dashboard_payload["status"])

    review_metrics_json_path = reports_dir / "review_metrics.json"
    review_metrics_html_path = reports_dir / "review_metrics.html"
    review_metrics_payload = build_review_metrics(
        report_path,
        dashboard_json_path,
        manual_import_report_path,
        retry_batch_report_path,
        provider_execution_dry_run_path,
    )
    write_review_metrics(review_metrics_json_path, review_metrics_payload)
    write_review_html(review_metrics_html_path, review_metrics_payload)
    statistics["review_metrics_json_path"] = str(review_metrics_json_path)
    statistics["review_metrics_html_path"] = str(review_metrics_html_path)
    statistics["review_metrics_status"] = str(review_metrics_payload["status"])
    statistics["review_metrics_risk_count"] = len(review_metrics_payload["risk_flags"])
    report_path.write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(statistics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
