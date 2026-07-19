"""CLI for aicomic — declarative command registry."""

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jobs(path: Path) -> list[JobRecord]:
    payload = load_json(path)
    return [
        JobRecord(job_id=str(j["job_id"]), episode_code=str(j["episode_code"]),
                  job_type=str(j["job_type"]), provider=str(j["provider"]), status=str(j["status"]))
        for j in payload.get("jobs", [])
    ]


def parse_overrides(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in raw.strip().split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                result[k] = v
    return result


def parse_filter(raw: str) -> set[str]:
    return {s.strip() for s in raw.split(",") if s.strip()}


def P(path_expr: str) -> Path:
    """Resolve a dotted path expression like 'ProjectPaths.manifest_dir() / ...'."""
    return eval(path_expr, {"ProjectPaths": ProjectPaths, "Path": Path})


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

def handle_status() -> int:
    print(f"project_root={ProjectPaths.project_root()}\nconfig_dir={ProjectPaths.config_dir()}\nmanifest_dir={ProjectPaths.manifest_dir()}\nstate_dir={ProjectPaths.state_dir()}")
    return 0


def handle_build_jobs(ep: Path, out: Path) -> int:
    manifest = load_json(ep)
    write_json(out, serialize_jobs(build_jobs_from_episode_manifest(manifest)))
    print(f"jobs_count={len(build_jobs_from_episode_manifest(manifest))}\noutput={out}")
    return 0


def handle_sync_states(jf: Path, out: Path) -> int:
    jobs = load_jobs(jf)
    states = [summarize_episode_state(code, jobs) for code in sorted({j.episode_code for j in jobs})]
    write_state_snapshot(out, states)
    print(f"episode_states={len(states)}\noutput={out}")
    return 0


def handle_dispatch_jobs(jf: Path, out: Path) -> int:
    decisions = dispatch_jobs(load_jobs(jf))
    write_dispatch_report(out, decisions)
    print(f"dispatch_count={len(decisions)}\noutput={out}")
    return 0


def handle_advance_episode(cur: str, nxt: str) -> int:
    print(f"transition={cur}->{advance_status(cur, nxt)}")
    return 0


def handle_scan_assets(ep: Path, code: str, root: Path, out: Path) -> int:
    report = scan_episode_assets(load_json(ep), code, root)
    write_asset_scan_report(out, report)
    print(f"ready_for_preview={report['ready_for_preview']}\nmissing_required_count={report['missing_required_count']}\noutput={out}")
    return 0


def handle_render_preview(ep: Path, code: str, root: Path, vid: Path, ro: Path) -> int:
    report = render_preview_video(build_render_plan(load_json(ep), code, root), vid, ro)
    print(f"render_mode={report['render_mode']}\noutput={vid}")
    return 0


def handle_prepare_subtitles_audio(ep: Path, code: str, srt_p: Path, ap_p: Path, wav_p: Path) -> int:
    mf = load_json(ep)
    entries = build_subtitle_entries(mf, code)
    write_srt(srt_p, entries)
    write_audio_plan(ap_p, build_audio_plan(mf, code))
    dur = int(entries[-1]["end"]) if entries else sum(int(s["duration"]) for s in mf.get("episodes", [{}])[0].get("shots", []))
    write_silence_wav(wav_p, max(1, dur))
    print(f"subtitle_count={len(entries)}\nsrt_output={srt_p}\naudio_plan_output={ap_p}\nwav_output={wav_p}")
    return 0


def handle_horror_blueprint(hook: str, code: str, sec: int, shots: int, out: Path) -> int:
    p = build_horror_story_blueprint(hook, episode_code=code, target_seconds=sec, max_shots=shots)
    write_horror_blueprint(out, p)
    print(f"episode_code={p['episode_code']}\ntarget_seconds={p['target_seconds']}\nshot_count={p['shot_count']}\noutput={out}")
    return 0


def handle_build_horror_episode(bp: Path, pid: str, season: int, out: Path) -> int:
    p = build_horror_episode_manifest(load_json(bp), project_id=pid, season=season)
    write_horror_episode_manifest(out, p)
    ep = p["episodes"][0]
    print(f"episode_code={ep['episode_code']}\nshot_count={len(ep.get('shots', []))}\ntotal_duration={sum(int(s.get('duration', 0)) for s in ep.get('shots', []))}\noutput={out}")
    return 0


def handle_filter_jobs(jf: Path, ep: str | None, jt: str | None, sr: str | None, out: Path) -> int:
    s = {x.strip() for x in sr.split(",")} if sr else None
    filtered = filter_jobs(load_jobs(jf), episode_code=ep, job_type=jt, statuses=s)
    write_job_payload(out, filtered)
    print(f"filtered_count={len(filtered)}\noutput={out}")
    return 0


def handle_retry_jobs(jf: Path, sr: str, out: Path) -> int:
    s = {x.strip() for x in sr.split(",") if x.strip()}
    jobs, sm = retry_jobs(load_jobs(jf), s)
    write_job_payload(out, jobs)
    print(f"retried_count={sm['retried_count']}\noutput={out}")
    return 0


def handle_retry_batch(jf: Path, sr: str, ep: str | None, prov: str | None, ro: Path, jo: Path) -> int:
    s = {x.strip() for x in sr.split(",") if x.strip()}
    rpt, jobs = retry_batch_jobs(load_jobs(jf), s, ep, prov)
    write_retry_batch_report(ro, rpt)
    write_job_payload(jo, jobs)
    print(f"retried_count={rpt['retried_count']}\nscoped_job_count={rpt['scoped_job_count']}\noutput={ro}")
    return 0


def handle_resume_report(ss: Path, jf: Path, dr: Path, out: Path) -> int:
    rpt = build_resume_report(load_json(ss), load_json(jf), load_json(dr))
    write_resume_report(out, rpt)
    print(f"unfinished_episode_count={rpt.unfinished_episode_count}\nunfinished_job_count={rpt.unfinished_job_count}\noutput={out}")
    return 0


def handle_init_project(name: str, genre: str, style: str, pid: str | None, logline: str, proto: str, aud: str, tone: str, hook: str, ept: int, root: Path) -> int:
    p = initialize_project(root, name, genre, style, pid, logline=logline, protagonist_name=proto, target_audience=aud, tone=tone, season_hook=hook, episode_target_count=ept)
    print(f"project_id={p['project_id']}\nproject_root={p['project_root']}\ncreated_directory_count={p['created_directory_count']}\nstory_bible={p['bootstrap_paths']['story_bible']}")
    return 0


def handle_render_release(ep: Path, code: str, root: Path, out: Path, ro: Path) -> int:
    rpt = render_release_video(build_release_plan(load_json(ep), code, root), out, ro)
    print(f"render_profile={rpt['render_profile']}\noutput={out}")
    return 0


def handle_build_publish_pack(ep: Path, code: str, out: Path) -> int:
    p = build_publish_pack(load_json(ep), code)
    write_publish_pack(out, p)
    print(f"publish_title={p['publish_title']}\noutput={out}")
    return 0


def handle_enhance_publish_pack(ep: Path, code: str, out: Path) -> int:
    p = build_enhanced_publish_pack(load_json(ep), code)
    write_publish_pack(out, p)
    print(f"title_candidates={len(p['title_candidates'])}\noutput={out}")
    return 0


def handle_suggest_asset_repairs(sr: Path, out: Path) -> int:
    p = build_repair_suggestions(load_json(sr))
    write_repair_suggestions(out, p)
    print(f"suggestion_count={p['suggestion_count']}\noutput={out}")
    return 0


def handle_plan_providers(jf: Path, pc: Path, out: Path) -> int:
    p = build_provider_plan(load_jobs(jf), pc)
    write_provider_plan(out, p)
    print(f"provider_count={p['provider_count']}\nunresolved_provider_count={p['unresolved_provider_count']}\noutput={out}")
    return 0


def handle_build_provider_requests(ep: Path, jf: Path, pc: Path, oroot: Path, ov: str, out: Path) -> int:
    mf = load_json(ep)
    jobs = load_jobs(jf)
    p = build_provider_requests(mf, jobs, pc, oroot, parse_overrides(ov))
    write_provider_requests(out, p)
    print(f"request_count={p['request_count']}\nready_count={p['ready_count']}\nblocked_count={p['blocked_count']}\noutput={out}")
    return 0


def handle_apply_provider_results(rr: Path, jf: Path, ro: Path, jo: Path) -> int:
    rpt, jobs = build_provider_result_writeback(load_json(rr), load_jobs(jf))
    write_provider_writeback_report(ro, rpt)
    write_job_payload(jo, jobs)
    print(f"changed_count={rpt['changed_count']}\nsucceeded_count={rpt['succeeded_count']}\nmanual_required_count={rpt['manual_required_count']}\noutput={ro}")
    return 0


def handle_manual_import_batch(rr: Path, jf: Path, ir: Path, iro: Path, wro: Path, jo: Path, ow: bool) -> int:
    pr = load_json(rr)
    imp = import_manual_outputs(pr, ir, overwrite=ow)
    write_manual_import_report(iro, imp)
    rpt, jobs = build_provider_result_writeback(pr, load_jobs(jf))
    write_provider_writeback_report(wro, rpt)
    write_job_payload(jo, jobs)
    print(f"imported_count={imp['imported_count']}\nmissing_count={imp['missing_count']}\nwriteback_succeeded_count={rpt['succeeded_count']}\noutput={iro}")
    return 0


def handle_execute_provider_requests(rr: Path, pc: Path, pr: str, dry: bool, cl: bool, lim: int, mf: int, out: Path) -> int:
    p = execute_provider_requests(load_json(rr), pc, parse_filter(pr) or None, dry_run=dry, confirm_live=cl, limit=lim, max_failures=mf)
    write_provider_execution_report(out, p)
    for k in ("request_count", "success_count", "failed_count", "dry_run_count", "blocked_count", "stopped_by_failure_guard"):
        print(f"{k}={p[k]}")
    print(f"output={out}")
    return 0


def handle_provider_readiness(pc: Path, rr: Path, out: Path) -> int:
    p = build_provider_readiness_report(pc, rr)
    write_provider_readiness_report(out, p)
    for k in ("status", "provider_count", "manual_fallback_ready", "openai_core_ready", "local_core_ready", "local_video_ready"):
        print(f"{k}={p[k]}")
    print(f"output={out}")
    return 0


def handle_comfyui_service(act: str, host: str, port: int, wto: float, pio: float, force: bool, out: Path) -> int:
    p = run_comfyui_service_action(act, project_root=ProjectPaths.project_root(), host=host, port=port, wait_timeout_seconds=wto, poll_interval_seconds=pio, force=force)
    write_comfyui_service_report(out, p)
    print(f"action={p['action']}\nbase_url={p['base_url']}\nstatus_before={p['status_before']['status']}\nstatus_after={p['status_after']['status']}\nruntime_error_count={len(p['runtime_errors'])}\noutput={out}")
    return 0


def handle_local_provider_live_smoke(pc: Path, pr: str, oroot: Path, img_m: str, vid_m: str, skip: bool, restart: bool, retry: bool, mf: int, ch: str, cp: int, wto: float, pio: float, out: Path) -> int:
    sp = parse_filter(pr) or None
    p = run_local_provider_live_smoke(providers_config_path=pc, selected_providers=sp, output_root=oroot, image_workflow_mode=img_m, video_workflow_mode=vid_m, skip_comfyui_start=skip, restart_comfyui=restart, retry_comfyui_on_failure=retry, max_failures=mf, comfyui_host=ch, comfyui_port=cp, wait_timeout_seconds=wto, poll_interval_seconds=pio)
    write_local_provider_live_smoke_report(out, p)
    print(f"status={p['status']}\nselected_provider_count={len(p['selected_providers'])}\npreflight_ready_count={p['preflight_summary']['ready_count']}\nsuccess_count={p['final_summary']['success_count']}\nfailed_count={p['final_summary']['failed_count']}\noutput={out}")
    return 0 if p["status"] == "passed" else 1


def handle_dependency_audit(out: Path) -> int:
    p = build_dependency_audit_report(ProjectPaths.project_root())
    write_dependency_audit_report(out, p)
    for k in ("lock_status", "cve_audit_status", "blocking_count", "warning_count"):
        print(f"{k}={p[k]}")
    print(f"output={out}")
    return 0


def handle_production_risk_register(wc: Path, ec: Path | None, pc: Path, prp: Path, da: Path, rol: bool, dm: str, out: Path) -> int:
    p = build_production_risk_register(ProjectPaths.project_root(), web_config_path=wc, edition_config_path=ec, providers_config_path=pc, provider_readiness_path=prp, dependency_audit_path=da, require_openai_live=rol, deployment_mode=dm)
    write_production_risk_register(out, p)
    for k in ("status", "risk_count", "blocking_count", "warning_count"):
        print(f"{k}={p[k]}")
    print(f"output={out}")
    return 0


def handle_build_batch(bid: str, bt: str, st: str, sv: str, sr: str, prov: str, skip: bool, noauto: bool, lpp: str, lpma: int, lpi: str, lpv: str, lpr: Path | None, out: Path) -> int:
    steps = parse_steps(sr)
    rec = build_batch_record(bid, bt, st, sv, steps, prov, out.with_name(f"{bid}_summary.json"))
    p = build_batch_payload(rec)
    p = apply_batch_preflight_gate(p, enabled=not skip, auto_run=not noauto, providers_raw=lpp, max_age_minutes=lpma, image_workflow_mode=lpi, video_workflow_mode=lpv, report_path=lpr)
    write_batch_payload(out, p)
    print(f"batch_id={rec.batch_id}\nstep_count={len(steps)}\nlocal_provider_preflight_enabled={p.get('preflight_gate', {}).get('enabled', False)}\noutput={out}")
    return 0


def handle_run_batch(bf: Path, ro: Path, so: Path) -> int:
    p = load_batch_payload(bf)
    rpt, _ = run_batch_payload(p, ro.parent)
    write_batch_payload(ro, rpt)
    write_batch_summary(so, build_batch_summary(rpt))
    print(f"batch_id={rpt['batch_id']}\nstep_count={rpt['step_count']}\nstatus={rpt['status']}")
    if "preflight_gate" in rpt:
        print(f"preflight_status={rpt['preflight_gate'].get('status', '')}\npreflight_mode={rpt['preflight_gate'].get('mode', '')}")
    print(f"report_output={ro}")
    return 0


def handle_dashboard_export(vr: Path, bs: Path, ss: Path, mir: Path, rbr: Path, jo: Path, ho: Path) -> int:
    p = build_dashboard_payload(vr, bs, ss, mir, rbr)
    write_dashboard_json(jo, p)
    write_dashboard_html(ho, p)
    print(f"status={p['status']}\njson_output={jo}\nhtml_output={ho}")
    return 0


def handle_review_metrics(vr: Path, d: Path, mir: Path, rbr: Path, per: Path, jo: Path, ho: Path) -> int:
    p = build_review_metrics(vr, d, mir, rbr, per)
    write_review_metrics(jo, p)
    write_review_html(ho, p)
    print(f"status={p['status']}\nrisk_count={len(p['risk_flags'])}\njson_output={jo}\nhtml_output={ho}")
    return 0


def handle_plan_rework(ep: Path, jf: Path, code: str, sid: str, out: Path, jo: Path) -> int:
    sids = {x.strip() for x in sid.split(",") if x.strip()}
    jobs = select_rework_jobs(load_jobs(jf), code, sids)
    write_rework_report(out, build_rework_report(load_json(ep), code, sids, jobs))
    write_job_payload(jo, jobs)
    print(f"rework_job_count={len(jobs)}\noutput={out}")
    return 0


def handle_build_navigator(code: str, out: Path) -> int:
    paths = [
        ("预览视频", ProjectPaths.preview_outputs_dir() / f"{code}_preview.mp4"),
        ("正式版视频", ProjectPaths.preview_outputs_dir() / f"{code}_release.mp4"),
        ("字幕", ProjectPaths.state_dir() / "subtitles" / f"{code}.srt"),
        ("占位音频", ProjectPaths.state_dir() / "audio" / f"{code}_placeholder.wav"),
        ("发布包", ProjectPaths.reports_dir() / f"publish_pack_{code}.json"),
        ("扫描报告", ProjectPaths.reports_dir() / f"asset_scan_{code}.json"),
        ("渲染报告", ProjectPaths.reports_dir() / f"render_preview_{code}.json"),
    ]
    html = build_episode_navigator(code, [{"label": l, "path": str(p), "status": "存在" if p.exists() else "缺失"} for l, p in paths])
    write_navigator(out, html)
    print(f"output={out}")
    return 0


def handle_build_season_jobs(sm: Path, em: Path, out: Path) -> int:
    p = build_season_job_bundle(load_json(sm), load_json(em))
    write_season_job_bundle(out, p)
    print(f"job_count={p['job_count']}\noutput={out}")
    return 0


def handle_scan_season_assets(sm: Path, em: Path, root: Path, out: Path) -> int:
    rpt = scan_season_assets(load_json(sm), load_json(em), root)
    write_season_scan_report(out, rpt)
    print(f"ready_episode_count={rpt['ready_episode_count']}\noutput={out}")
    return 0


def handle_render_season(sm: Path, em: Path, root: Path, od: Path, ro: Path, mode: str) -> int:
    rpt = render_season(load_json(sm), load_json(em), root, od, ro, mode=mode)
    print(f"episode_count={rpt['episode_count']}\noutput={ro}")
    return 0


def handle_build_season_summary(sm: Path, jr: Path, sr: Path, rr: Path, out: Path) -> int:
    p = build_season_summary(load_json(sm), load_json(jr), load_json(sr), load_json(rr))
    write_season_summary(out, p)
    print(f"episode_count={p['episode_count']}\noutput={out}")
    return 0


# ---------------------------------------------------------------------------
# Declarative command registry
# ---------------------------------------------------------------------------

COMMANDS: dict[str, dict] = {
    "status": {"help": "查看项目骨架状态", "args": [], "handler": lambda a: handle_status()},
    "build-jobs": {"help": "从 episode_manifest 构建任务包", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")})],
        "handler": lambda a: handle_build_jobs(a.episode_manifest, a.output)},
    "sync-states": {"help": "根据任务包生成剧集状态快照", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.state_dir() / 'episode_state_snapshot.json'")})],
        "handler": lambda a: handle_sync_states(a.jobs_file, a.output)},
    "dispatch-jobs": {"help": "生成任务调度报告", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dispatch_report.json'")})],
        "handler": lambda a: handle_dispatch_jobs(a.jobs_file, a.output)},
    "advance-episode": {"help": "验证剧集状态流转", "args": [
        (["--current"], {"required": True}), (["--next"], {"required": True})],
        "handler": lambda a: handle_advance_episode(a.current, a.next)},
    "scan-assets": {"help": "扫描单集素材完整性", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}),
        (["--asset-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'asset_scan_E01.json'")})],
        "handler": lambda a: handle_scan_assets(a.episode_manifest, a.episode_code, a.asset_root, a.output)},
    "render-preview": {"help": "渲染单集预览视频", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}),
        (["--asset-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.preview_outputs_dir() / 'E01_preview.mp4'")}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'render_preview_E01.json'")})],
        "handler": lambda a: handle_render_preview(a.episode_manifest, a.episode_code, a.asset_root, a.output, a.report_output)},
    "prepare-subtitles-audio": {"help": "生成字幕和音轨占位计划", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}),
        (["--srt-output"], {"type": Path, "default": P("ProjectPaths.state_dir() / 'subtitles' / 'E01.srt'")}),
        (["--audio-plan-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'audio_plan_E01.json'")}),
        (["--wav-output"], {"type": Path, "default": P("ProjectPaths.state_dir() / 'audio' / 'E01_placeholder.wav'")})],
        "handler": lambda a: handle_prepare_subtitles_audio(a.episode_manifest, a.episode_code, a.srt_output, a.audio_plan_output, a.wav_output)},
    "horror-blueprint": {"help": "生成玄学/民俗恐怖样片故事蓝图", "args": [
        (["--hook"], {"default": DEFAULT_HORROR_HOOK}), (["--episode-code"], {"default": "E01"}),
        (["--target-seconds"], {"type": int, "default": 360}), (["--max-shots"], {"type": int, "default": 60}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.project_root() / 'docs' / 'horror_story_blueprint.json'")})],
        "handler": lambda a: handle_horror_blueprint(a.hook, a.episode_code, a.target_seconds, a.max_shots, a.output)},
    "build-horror-episode": {"help": "根据恐怖蓝图生成 Episode Manifest", "args": [
        (["--blueprint"], {"type": Path, "default": P("ProjectPaths.project_root() / 'docs' / 'horror_story_blueprint.json'")}),
        (["--project-id"], {"default": "aicomic_system"}), (["--season"], {"type": int, "default": 1}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")})],
        "handler": lambda a: handle_build_horror_episode(a.blueprint, a.project_id, a.season, a.output)},
    "filter-jobs": {"help": "按条件筛选任务", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--episode-code"], {"default": None}), (["--job-type"], {"default": None}),
        (["--statuses"], {"default": None}), (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'filtered_jobs.json'")})],
        "handler": lambda a: handle_filter_jobs(a.jobs_file, a.episode_code, a.job_type, a.statuses, a.output)},
    "retry-jobs": {"help": "重置可重试任务状态", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--statuses"], {"default": "pending,failed,manual_required"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs_retried.json'")})],
        "handler": lambda a: handle_retry_jobs(a.jobs_file, a.statuses, a.output)},
    "retry-batch": {"help": "批量重试指定范围任务", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs_provider_synced.json'")}),
        (["--statuses"], {"default": "failed,manual_required"}), (["--episode-code"], {"default": None}),
        (["--provider"], {"default": None}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'retry_batch_report.json'")}),
        (["--jobs-output"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs_batch_retried.json'")})],
        "handler": lambda a: handle_retry_batch(a.jobs_file, a.statuses, a.episode_code, a.provider, a.report_output, a.jobs_output)},
    "resume-report": {"help": "生成断点续跑建议报告", "args": [
        (["--state-snapshot"], {"type": Path, "default": P("ProjectPaths.state_dir() / 'episode_state_snapshot.json'")}),
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--dispatch-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dispatch_report.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'resume_report.json'")})],
        "handler": lambda a: handle_resume_report(a.state_snapshot, a.jobs_file, a.dispatch_report, a.output)},
    "init-project": {"help": "初始化新项目模板目录", "args": [
        (["--project-name"], {"required": True}), (["--genre"], {"default": "现代职场逆袭"}),
        (["--style"], {"default": "动漫漫剧"}), (["--project-id"], {"default": None}),
        (["--logline"], {"default": "一个普通人被卷入高压环境后，靠连续反转赢回主动权。"}),
        (["--protagonist-name"], {"default": "女主"}), (["--target-audience"], {"default": "短剧用户 / 二次元短视频观众"}),
        (["--tone"], {"default": "强钩子"}), (["--season-hook"], {"default": "结尾必须留下身份、关系或真相反转。"}),
        (["--episode-target-count"], {"type": int, "default": 12}),
        (["--output-root"], {"type": Path, "default": P("ProjectPaths.generated_projects_dir()")})],
        "handler": lambda a: handle_init_project(a.project_name, a.genre, a.style, a.project_id, a.logline, a.protagonist_name, a.target_audience, a.tone, a.season_hook, a.episode_target_count, a.output_root)},
    "render-release": {"help": "渲染单集正式版视频", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}), (["--asset-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.preview_outputs_dir() / 'E01_release.mp4'")}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'render_release_E01.json'")})],
        "handler": lambda a: handle_render_release(a.episode_manifest, a.episode_code, a.asset_root, a.output, a.report_output)},
    "build-publish-pack": {"help": "生成单集发布包", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'publish_pack_E01.json'")})],
        "handler": lambda a: handle_build_publish_pack(a.episode_manifest, a.episode_code, a.output)},
    "enhance-publish-pack": {"help": "生成增强版单集发布包", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--episode-code"], {"default": "E01"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'publish_pack_E01_enhanced.json'")})],
        "handler": lambda a: handle_enhance_publish_pack(a.episode_manifest, a.episode_code, a.output)},
    "suggest-asset-repairs": {"help": "基于扫描报告生成素材修复建议", "args": [
        (["--scan-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'asset_scan_E01.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'asset_repair_E01.json'")})],
        "handler": lambda a: handle_suggest_asset_repairs(a.scan_report, a.output)},
    "plan-providers": {"help": "生成多 Provider 路由规划报告", "args": [
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs.json'")}),
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_plan.json'")})],
        "handler": lambda a: handle_plan_providers(a.jobs_file, a.providers_config, a.output)},
    "build-provider-requests": {"help": "生成 Provider 任务请求包", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs.json'")}),
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--output-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--provider-overrides"], {"default": "", "help": "按 job_type 覆盖 Provider"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_requests.json'")})],
        "handler": lambda a: handle_build_provider_requests(a.episode_manifest, a.jobs_file, a.providers_config, a.output_root, a.provider_overrides, a.output)},
    "apply-provider-results": {"help": "扫描 Provider 产物并回写任务状态", "args": [
        (["--requests-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_requests.json'")}),
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs.json'")}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_writeback_report.json'")}),
        (["--jobs-output"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs_provider_synced.json'")})],
        "handler": lambda a: handle_apply_provider_results(a.requests_report, a.jobs_file, a.report_output, a.jobs_output)},
    "manual-import-batch": {"help": "从手工网页导出目录批量导入产物", "args": [
        (["--requests-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_requests.json'")}),
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs_provider_synced.json'")}),
        (["--import-root"], {"type": Path, "required": True}),
        (["--import-report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'manual_import_report.json'")}),
        (["--writeback-report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'manual_import_writeback_report.json'")}),
        (["--jobs-output"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'episode_jobs_manual_import_synced.json'")}),
        (["--overwrite"], {"action": "store_true"})],
        "handler": lambda a: handle_manual_import_batch(a.requests_report, a.jobs_file, a.import_root, a.import_report_output, a.writeback_report_output, a.jobs_output, a.overwrite)},
    "execute-provider-requests": {"help": "执行支持的 Provider 请求", "args": [
        (["--requests-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_requests.json'")}),
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--providers"], {"default": "", "help": "只执行指定 Provider，逗号分隔"}),
        (["--dry-run"], {"action": "store_true"}), (["--confirm-live"], {"action": "store_true"}),
        (["--limit"], {"type": int, "default": 0}), (["--max-failures"], {"type": int, "default": 1}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_execution_report.json'")})],
        "handler": lambda a: handle_execute_provider_requests(a.requests_report, a.providers_config, a.providers, a.dry_run, a.confirm_live, a.limit, a.max_failures, a.output)},
    "provider-readiness": {"help": "检查 Provider 上线前就绪状态", "args": [
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--requests-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_requests_local.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_readiness_report.json'")})],
        "handler": lambda a: handle_provider_readiness(a.providers_config, a.requests_report, a.output)},
    "comfyui-service": {"help": "管理项目内 ComfyUI 服务", "args": [
        (["action"], {"choices": ("status", "start", "stop", "restart")}),
        (["--host"], {"default": "127.0.0.1"}), (["--port"], {"type": int, "default": 8188}),
        (["--wait-timeout-seconds"], {"type": float, "default": 120.0}),
        (["--poll-interval-seconds"], {"type": float, "default": 2.0}),
        (["--force"], {"action": "store_true"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'comfyui_service_report.json'")})],
        "handler": lambda a: handle_comfyui_service(a.action, a.host, a.port, a.wait_timeout_seconds, a.poll_interval_seconds, a.force, a.output)},
    "local-provider-live-smoke": {"help": "执行本地 Provider 一键 live smoke", "args": [
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--providers"], {"default": "", "help": "只执行指定 Provider，逗号分隔"}),
        (["--output-root"], {"type": Path, "default": P("ProjectPaths.state_dir() / 'live_smoke'")}),
        (["--image-workflow-mode"], {"choices": ("configured", "smoke", "full"), "default": "smoke"}),
        (["--video-workflow-mode"], {"choices": ("configured", "smoke", "full"), "default": "smoke"}),
        (["--skip-comfyui-start"], {"action": "store_true"}), (["--restart-comfyui"], {"action": "store_true"}),
        (["--no-retry-comfyui-on-failure"], {"action": "store_false", "dest": "retry_comfyui_on_failure"}),
        (["--max-failures"], {"type": int, "default": 1}), (["--comfyui-host"], {"default": "127.0.0.1"}),
        (["--comfyui-port"], {"type": int, "default": 8188}), (["--wait-timeout-seconds"], {"type": float, "default": 120.0}),
        (["--poll-interval-seconds"], {"type": float, "default": 2.0}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'local_provider_live_smoke_report.json'")})],
        "handler": lambda a: handle_local_provider_live_smoke(a.providers_config, a.providers, a.output_root, a.image_workflow_mode, a.video_workflow_mode, a.skip_comfyui_start, a.restart_comfyui, a.retry_comfyui_on_failure, a.max_failures, a.comfyui_host, a.comfyui_port, a.wait_timeout_seconds, a.poll_interval_seconds, a.output)},
    "dependency-audit": {"help": "生成依赖锁定与 CVE 审计状态报告", "args": [
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dependency_audit_report.json'")})],
        "handler": lambda a: handle_dependency_audit(a.output)},
    "production-risk-register": {"help": "生成生产上线风险闸门报告", "args": [
        (["--web-config"], {"type": Path, "default": P("ProjectPaths.config_dir() / 'web.yaml'")}),
        (["--edition-config"], {"type": Path, "default": None}),
        (["--providers-config"], {"type": Path, "default": P("ProjectPaths.providers_config_path()")}),
        (["--provider-readiness"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_readiness_report.json'")}),
        (["--dependency-audit"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dependency_audit_report.json'")}),
        (["--require-openai-live"], {"action": "store_true"}),
        (["--deployment-mode"], {"choices": ("production", "rehearsal"), "default": "production"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'production_risk_register.json'")})],
        "handler": lambda a: handle_production_risk_register(a.web_config, a.edition_config, a.providers_config, a.provider_readiness, a.dependency_audit, a.require_openai_live, a.deployment_mode, a.output)},
    "build-batch": {"help": "构建批次定义文件", "args": [
        (["--batch-id"], {"default": "season1_batch_demo"}), (["--batch-type"], {"default": "season_pipeline"}),
        (["--scope-type"], {"default": "season"}), (["--scope-value"], {"default": "S01"}),
        (["--steps"], {"default": ""}), (["--providers"], {"default": ""}),
        (["--skip-local-provider-preflight"], {"action": "store_true"}),
        (["--no-auto-run-local-provider-preflight"], {"action": "store_true"}),
        (["--local-provider-preflight-providers"], {"default": "local_comfyui_image,local_comfyui_video,local_piper_tts"}),
        (["--local-provider-preflight-max-age-minutes"], {"type": int, "default": 240}),
        (["--local-provider-preflight-image-workflow-mode"], {"choices": ("configured", "smoke", "full"), "default": "smoke"}),
        (["--local-provider-preflight-video-workflow-mode"], {"choices": ("configured", "smoke", "full"), "default": "smoke"}),
        (["--local-provider-preflight-report"], {"type": Path, "default": None}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_batch.json'")})],
        "handler": lambda a: handle_build_batch(a.batch_id, a.batch_type, a.scope_type, a.scope_value, a.steps, a.providers, a.skip_local_provider_preflight, a.no_auto_run_local_provider_preflight, a.local_provider_preflight_providers, a.local_provider_preflight_max_age_minutes, a.local_provider_preflight_image_workflow_mode, a.local_provider_preflight_video_workflow_mode, a.local_provider_preflight_report, a.output)},
    "run-batch": {"help": "执行批次定义并生成批次报告", "args": [
        (["--batch-file"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_batch.json'")}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_batch_report.json'")}),
        (["--summary-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_batch_summary.json'")})],
        "handler": lambda a: handle_run_batch(a.batch_file, a.report_output, a.summary_output)},
    "dashboard-export": {"help": "导出批量生产 Dashboard", "args": [
        (["--validation-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'demo_validation_report.json'")}),
        (["--batch-summary"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_batch_summary.json'")}),
        (["--season-summary"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_summary.json'")}),
        (["--manual-import-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'manual_import_report.json'")}),
        (["--retry-batch-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'retry_batch_report.json'")}),
        (["--json-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dashboard.json'")}),
        (["--html-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dashboard.html'")})],
        "handler": lambda a: handle_dashboard_export(a.validation_report, a.batch_summary, a.season_summary, a.manual_import_report, a.retry_batch_report, a.json_output, a.html_output)},
    "review-metrics": {"help": "导出批量生产数据复盘统计", "args": [
        (["--validation-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'demo_validation_report.json'")}),
        (["--dashboard"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'dashboard.json'")}),
        (["--manual-import-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'manual_import_report.json'")}),
        (["--retry-batch-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'retry_batch_report.json'")}),
        (["--provider-execution-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'provider_execution_openai_dry_run.json'")}),
        (["--json-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'review_metrics.json'")}),
        (["--html-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'review_metrics.html'")})],
        "handler": lambda a: handle_review_metrics(a.validation_report, a.dashboard, a.manual_import_report, a.retry_batch_report, a.provider_execution_report, a.json_output, a.html_output)},
    "plan-rework": {"help": "为指定镜头生成增量返工任务", "args": [
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--jobs-file"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'episode_jobs.json'")}),
        (["--episode-code"], {"default": "E01"}), (["--shot-ids"], {"required": True}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'rework_E01.json'")}),
        (["--jobs-output"], {"type": Path, "default": P("ProjectPaths.project_root() / 'jobs' / 'E01_rework_jobs.json'")})],
        "handler": lambda a: handle_plan_rework(a.episode_manifest, a.jobs_file, a.episode_code, a.shot_ids, a.output, a.jobs_output)},
    "build-navigator": {"help": "生成单集导航页", "args": [
        (["--episode-code"], {"default": "E01"}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'E01_navigator.html'")})],
        "handler": lambda a: handle_build_navigator(a.episode_code, a.output)},
    "build-season-jobs": {"help": "生成整季任务包", "args": [
        (["--season-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'season_manifest.json'")}),
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'season1_jobs.json'")})],
        "handler": lambda a: handle_build_season_jobs(a.season_manifest, a.episode_manifest, a.output)},
    "scan-season-assets": {"help": "扫描整季素材状态", "args": [
        (["--season-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'season_manifest.json'")}),
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--asset-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_asset_scan.json'")})],
        "handler": lambda a: handle_scan_season_assets(a.season_manifest, a.episode_manifest, a.asset_root, a.output)},
    "render-season": {"help": "渲染整季视频产物", "args": [
        (["--season-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'season_manifest.json'")}),
        (["--episode-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'episode_manifest.json'")}),
        (["--asset-root"], {"type": Path, "default": P("ProjectPaths.demo_assets_dir()")}),
        (["--mode"], {"default": "preview", "choices": ["preview", "release"]}),
        (["--output-dir"], {"type": Path, "default": P("ProjectPaths.preview_outputs_dir() / 'season1'")}),
        (["--report-output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_render_report.json'")})],
        "handler": lambda a: handle_render_season(a.season_manifest, a.episode_manifest, a.asset_root, a.output_dir, a.report_output, a.mode)},
    "build-season-summary": {"help": "生成整季总报告", "args": [
        (["--season-manifest"], {"type": Path, "default": P("ProjectPaths.manifest_dir() / 'season_manifest.json'")}),
        (["--jobs-report"], {"type": Path, "default": P("ProjectPaths.jobs_output_dir() / 'season1_jobs.json'")}),
        (["--scan-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_asset_scan.json'")}),
        (["--render-report"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_render_report.json'")}),
        (["--output"], {"type": Path, "default": P("ProjectPaths.reports_dir() / 'season1_summary.json'")})],
        "handler": lambda a: handle_build_season_summary(a.season_manifest, a.jobs_report, a.scan_report, a.render_report, a.output)},
    "init-demo-db": {"help": "初始化演示数据库", "args": [
        (["--database"], {"type": Path, "default": P("ProjectPaths.default_database_path()")})],
        "handler": lambda a: print(f"database={a.database}") or 0},
}


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser from declarative COMMANDS registry."""
    parser = argparse.ArgumentParser(description="AI漫剧自动生成系统 CLI")
    subparsers = parser.add_subparsers(dest="command")
    for name, cmd in COMMANDS.items():
        sp = subparsers.add_parser(name, help=cmd["help"])
        for args_spec, kwargs in cmd["args"]:
            sp.add_argument(*args_spec, **kwargs)
    return parser


def main() -> int:
    """Dispatch parsed args to registered handler."""
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    cmd = COMMANDS.get(args.command)
    if cmd is None:
        parser.print_help()
        return 0
    return cmd["handler"](args)


if __name__ == "__main__":
    raise SystemExit(main())
