"""Batch coordinator — pipeline orchestration for multi-step batch execution."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Callable

from aicomic.batch.preflight_gate import build_batch_preflight_gate, ensure_batch_preflight_gate
from aicomic.core.models import BatchRecord, BatchRunRecord
from aicomic.core.season_jobs import build_season_job_bundle
from aicomic.qc.asset_scanner import scan_episode_assets
from aicomic.providers.request_builder import build_provider_requests
from aicomic.providers.executor import execute_provider_requests
from aicomic.render.season_renderer import render_season
from aicomic.publish.publish_pack import build_enhanced_publish_pack
from aicomic.publish.season_summary import build_season_summary
from aicomic.utils.atomic_io import atomic_write_json

DEFAULT_BATCH_STEPS = (
    "build_season_jobs",
    "scan_season_assets",
    "build_provider_requests",
    "apply_provider_results",
    "render_season",
    "build_season_summary",
)


def parse_steps(raw_steps: str) -> list[str]:
    steps = [s.strip() for s in raw_steps.split(",") if s.strip()]
    return steps or list(DEFAULT_BATCH_STEPS)


def build_batch_record(
    batch_id: str, batch_type: str, scope_type: str, scope_value: str,
    steps: list[str], provider_filter: str, summary_path: Path,
) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id, batch_type=batch_type,
        scope_type=scope_type, scope_value=scope_value,
        target_steps=",".join(steps), provider_filter=provider_filter,
        status="planned", summary_path=str(summary_path),
    )


def build_batch_payload(record: BatchRecord) -> dict[str, object]:
    return {
        "batch": asdict(record),
        "steps": [{"step_name": s, "status": "planned"} for s in record.target_steps.split(",") if s],
    }


def apply_batch_preflight_gate(
    payload: dict[str, object],
    enabled: bool = True, auto_run: bool = True, providers_raw: str = "",
    max_age_minutes: int = 240, image_workflow_mode: str = "smoke",
    video_workflow_mode: str = "smoke", report_path: Path | None = None,
) -> dict[str, object]:
    batch = payload.get("batch", {})
    if not isinstance(batch, dict):
        return payload
    updated = dict(payload)
    updated["preflight_gate"] = build_batch_preflight_gate(
        batch_id=str(batch.get("batch_id", "batch")),
        provider_filter=str(batch.get("provider_filter", "")),
        enabled=enabled, auto_run=auto_run, providers_raw=providers_raw,
        max_age_minutes=max_age_minutes, image_workflow_mode=image_workflow_mode,
        video_workflow_mode=video_workflow_mode, report_path=report_path,
    )
    return updated


def write_batch_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_batch_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_output_path(reports_dir: Path, batch_id: str, step_name: str) -> Path:
    return reports_dir / f"{batch_id}_{step_name}.json"


class BatchStepError(Exception):
    """Raised when a real batch step fails."""

    def __init__(self, step_name: str, original_error: Exception) -> None:
        self.step_name = step_name
        self.original_error = original_error
        super().__init__(f"[{step_name}] {original_error}")


# ---------------------------------------------------------------------------
#  Step engines  (thin calls into library functions)
# ---------------------------------------------------------------------------

def _build_season_jobs(season_manifest: dict[str, Any], episode_manifest: dict[str, Any]) -> dict[str, Any]:
    """Step 1: build jobs from manifests."""
    return build_season_job_bundle(season_manifest, episode_manifest)


def _scan_season_assets(season_manifest: dict[str, Any], episode_manifest: dict[str, Any], asset_root: Path) -> dict[str, Any]:
    """Step 2: scan assets for every episode."""
    reports: list[dict[str, Any]] = []
    agg = {"expected_count": 0, "existing_count": 0, "missing_required_count": 0, "missing_optional_count": 0, "ready_episode_count": 0}
    for ep in season_manifest.get("episodes", []):
        r = scan_episode_assets(episode_manifest, str(ep["episode_code"]), asset_root)
        reports.append(r)
        for k in ("expected_count", "existing_count", "missing_required_count", "missing_optional_count"):
            agg[k] += r[k]
        if r["ready_for_preview"]:
            agg["ready_episode_count"] += 1
    return {"asset_root": str(asset_root), "episode_count": len(reports), **agg,
            "missing_required_total": agg["missing_required_count"],
            "episode_reports": reports, "ready_for_preview": agg["missing_required_count"] == 0}


def _build_provider_requests_step(season_manifest, episode_manifest, season_jobs_bundle, providers_config_path, output_root):
    """Step 3: build provider requests from jobs."""
    from aicomic.core.models import JobRecord
    jobs = [JobRecord(job_id=str(j["job_id"]), episode_code=str(j["episode_code"]),
                      job_type=str(j["job_type"]), provider=str(j["provider"]), status=str(j["status"]))
            for j in season_jobs_bundle.get("jobs", [])]
    return build_provider_requests(manifest=episode_manifest, jobs=jobs, providers_config_path=providers_config_path, output_root=output_root)


def _render_season_step(season_manifest, episode_manifest, asset_root, output_dir, report_path, mode="preview"):
    """Step 5: render the season."""
    return render_season(season_manifest=season_manifest, episode_manifest=episode_manifest, asset_root=asset_root, output_dir=output_dir, report_path=report_path, mode=mode)


def _generate_publish_pack_for_season(episode_manifest):
    """Step 6: publish packs."""
    packs = [build_enhanced_publish_pack(episode_manifest, str(ep["episode_code"])) for ep in episode_manifest.get("episodes", [])]
    return {"episode_count": len(packs), "packs": packs}


# ---------------------------------------------------------------------------
#  Step dispatch  (step_name → (engine_fn, needed_ctx_keys, summariser_fn))
# ---------------------------------------------------------------------------

def _msg(result: dict, key: str, default: Any = 0) -> Any:
    return result.get(key, default)


_STEP_DISPATCH: dict[str, tuple[Callable, tuple[str, ...], Callable]] = {
    "build_season_jobs": (
        _build_season_jobs,
        ("season_manifest", "episode_manifest"),
        lambda r: f"Built {_msg(r, 'job_count')} jobs across {_msg(r, 'episode_count')} episodes",
    ),
    "scan_season_assets": (
        _scan_season_assets,
        ("season_manifest", "episode_manifest", "asset_root"),
        lambda r: f"Scanned {_msg(r, 'episode_count')} episodes: {_msg(r, 'existing_count')} assets found, {_msg(r, 'missing_required_count')} required missing",
    ),
    "build_provider_requests": (
        _build_provider_requests_step,
        ("season_manifest", "episode_manifest", "season_jobs_bundle", "providers_config_path"),
        lambda r: f"Built {_msg(r, 'request_count')} provider requests ({_msg(r, 'ready_count')} ready, {_msg(r, 'blocked_count')} blocked)",
    ),
    "apply_provider_results": (
        execute_provider_requests,
        ("provider_requests_payload", "providers_config_path"),
        lambda r: f"Executed provider requests: {_msg(r, 'success_count')} succeeded, {_msg(r, 'failed_count')} failed, {_msg(r, 'skipped_count')} skipped",
    ),
    "render_season": (
        _render_season_step,
        ("season_manifest", "episode_manifest", "asset_root", "render_output_dir"),
        lambda r: f"Rendered {_msg(r, 'episode_count')} episodes",
    ),
    "generate_publish_pack": (
        _generate_publish_pack_for_season,
        ("episode_manifest",),
        lambda r: f"Generated publish packs for {_msg(r, 'episode_count')} episodes",
    ),
    "build_season_summary": (
        build_season_summary,
        ("season_manifest", "season_jobs_bundle", "season_scan_report", "render_report"),
        lambda r: "Season summary built",
    ),
}

_STEP_INTERMEDIATE: dict[str, str] = {
    "build_season_jobs": "season_jobs_bundle",
    "scan_season_assets": "season_scan_report",
    "build_provider_requests": "provider_requests_payload",
    "render_season": "render_report",
    "generate_publish_pack": "publish_pack_result",
}


def _build_step_context(*, season_manifest, episode_manifest, providers_config_path, asset_root, render_output_dir, render_mode, execute_dry_run, execute_confirm_live, execute_max_failures, execute_skip_existing) -> dict[str, Any]:
    return {"season_manifest": season_manifest, "episode_manifest": episode_manifest,
            "season_jobs_bundle": None, "season_scan_report": None,
            "provider_requests_payload": None, "render_report": None,
            "providers_config_path": providers_config_path, "asset_root": asset_root,
            "render_output_dir": render_output_dir, "render_mode": render_mode,
            "apply_provider_results__dry_run": execute_dry_run,
            "apply_provider_results__confirm_live": execute_confirm_live,
            "apply_provider_results__max_failures": execute_max_failures,
            "apply_provider_results__skip_existing": execute_skip_existing,
            "batch_id": ""}


def _extract_step_kwargs(ctx: dict[str, Any], step_name: str, needs: tuple[str, ...]) -> dict[str, Any]:
    kwargs = {}
    for k in needs:
        v = ctx.get(k)
        if v is None:
            raise ValueError(f"'{step_name}' requires '{k}' but it is None")
        kwargs[k] = v
    if step_name == "apply_provider_results":
        kwargs.update(dry_run=ctx["apply_provider_results__dry_run"], confirm_live=ctx["apply_provider_results__confirm_live"], max_failures=ctx["apply_provider_results__max_failures"], skip_existing=ctx["apply_provider_results__skip_existing"])
    if step_name == "render_season":
        kwargs["mode"] = ctx["render_mode"]
        kwargs["report_path"] = ctx["render_output_dir"] / f"{ctx['batch_id']}_render.json"
    if step_name == "build_provider_requests":
        kwargs["output_root"] = ctx["providers_config_path"].parent
    return kwargs


def _execute_real_step(step_name: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Execute one real step, returning result dict with status."""
    entry = _STEP_DISPATCH.get(step_name)
    if entry is None:
        return {"status": "simulated", "message": f"No real handler for step '{step_name}', recorded as simulated"}
    engine_fn, needs, summariser = entry
    try:
        kwargs = _extract_step_kwargs(ctx, step_name, needs)
        result = engine_fn(**kwargs)
        return {"status": "completed", **result, "message": summariser(result)}
    except Exception as exc:
        raise BatchStepError(step_name, exc) from exc


def _build_run_record(batch_id: str, step_name: str, status: str, output_path: Path) -> BatchRunRecord:
    return BatchRunRecord(run_id=f"RUN_{batch_id}_{step_name}", batch_id=batch_id, step_name=step_name, status=status, output_path=str(output_path))


def _build_final_report(batch: dict[str, Any], batch_id: str, step_results: list[dict[str, object]], failed_steps: int, preflight_result: dict[str, Any]) -> dict[str, object]:
    simulated_count = sum(1 for r in step_results if str(r.get("status")) == "simulated")
    real_count = sum(1 for r in step_results if str(r.get("status")) not in ("simulated", "failed"))
    total = len(step_results)
    if failed_steps > 0 and total == failed_steps:
        status = "failed"
    elif failed_steps > 0:
        status = "partial"
    else:
        status = "completed"
    return {
        "batch_id": batch_id, "scope_type": str(batch["scope_type"]),
        "scope_value": str(batch["scope_value"]), "step_count": total,
        "simulated_step_count": simulated_count, "real_step_count": real_count,
        "failed_step_count": failed_steps, "status": status,
        "step_results": step_results, "preflight_gate": preflight_result,
    }


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def run_batch_payload(
    batch_payload: dict[str, Any],
    reports_dir: Path,
    *,
    mode: str = "simulated",
    max_workers: int = 1,
    progress_callback: Callable[[str, int, int], None] | None = None,
    season_manifest: dict[str, Any] | None = None,
    episode_manifest: dict[str, Any] | None = None,
    providers_config_path: Path | None = None,
    asset_root: Path | None = None,
    render_output_dir: Path | None = None,
    render_mode: str = "preview",
    execute_dry_run: bool = False,
    execute_confirm_live: bool = False,
    execute_max_failures: int = 1,
    execute_skip_existing: bool = False,
) -> tuple[dict[str, object], list[BatchRunRecord]]:
    batch = batch_payload["batch"]
    batch_id = str(batch["batch_id"])
    run_records: list[BatchRunRecord] = []
    step_results: list[dict[str, object]] = []
    steps = batch_payload.get("steps", [])

    # ---- preflight gate -------------------------------------------------
    preflight_gate = batch_payload.get("preflight_gate", {})
    if isinstance(preflight_gate, dict):
        preflight_result = ensure_batch_preflight_gate(preflight_gate)
    else:
        preflight_result = {"status": "disabled", "reason": "", "report_path": "", "mode": "disabled", "report": {}}

    if str(preflight_result["status"]) not in {"disabled", "passed"}:
        report = {
            "batch_id": batch_id, "scope_type": str(batch["scope_type"]),
            "scope_value": str(batch["scope_value"]), "step_count": 0,
            "simulated_step_count": 0, "real_step_count": 0,
            "failed_step_count": 0, "status": "blocked_preflight_failed",
            "step_results": [], "preflight_gate": preflight_result,
        }
        return report, []

    # ---- step loop ------------------------------------------------------
    if mode not in ("simulated", "real"):
        raise ValueError(f"Unknown batch execution mode: {mode!r}. Use 'simulated' or 'real'.")

    is_real = mode == "real"
    ctx = _build_step_context(
        season_manifest=season_manifest, episode_manifest=episode_manifest,
        providers_config_path=providers_config_path, asset_root=asset_root,
        render_output_dir=render_output_dir, render_mode=render_mode,
        execute_dry_run=execute_dry_run, execute_confirm_live=execute_confirm_live,
        execute_max_failures=execute_max_failures, execute_skip_existing=execute_skip_existing,
    )
    ctx["batch_id"] = batch_id
    failed_steps = 0

    for idx, step in enumerate(steps):
        step_name = str(step["step_name"])
        output_path = build_run_output_path(reports_dir, batch_id, step_name)

        try:
            if is_real:
                step_result = _execute_real_step(step_name, ctx)
                # Store intermediate for downstream steps
                intermediate_key = _STEP_INTERMEDIATE.get(step_name)
                if intermediate_key:
                    ctx[intermediate_key] = step_result
            else:
                step_result = {
                    "batch_id": batch_id, "step_name": step_name,
                    "status": "simulated", "output_path": str(output_path),
                    "message": "MVP 阶段记录批次步骤，实际生产动作由既有 CLI 命令执行",
                }
        except BatchStepError as exc:
            step_result = {
                "batch_id": batch_id, "step_name": step_name,
                "status": "failed", "output_path": str(output_path),
                "error": str(exc), "error_detail": str(exc.original_error),
            }
            failed_steps += 1

        # Write output
        step_status = str(step_result.get("status", "unknown"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_path, step_result)

        run_records.append(_build_run_record(batch_id, step_name, step_status, output_path))
        step_results.append({
            "batch_id": batch_id, "step_name": step_name,
            "status": step_status, "output_path": str(output_path),
            "message": step_result.get("message", ""),
            "error": step_result.get("error", ""),
        })

        if progress_callback is not None:
            progress_callback(step_name, idx + 1, len(steps))

    return _build_final_report(batch, batch_id, step_results, failed_steps, preflight_result), run_records
