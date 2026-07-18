from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Callable

from aicomic.batch.preflight_gate import build_batch_preflight_gate, ensure_batch_preflight_gate
from aicomic.core.models import BatchRecord, BatchRunRecord, JobRecord
from aicomic.core.season_jobs import build_season_job_bundle
from aicomic.qc.asset_scanner import scan_episode_assets, write_asset_scan_report
from aicomic.providers.request_builder import (
    build_provider_requests,
    extract_request_records,
    write_provider_requests,
)
from aicomic.providers.executor import execute_provider_requests, write_provider_execution_report
from aicomic.providers.result_writer import build_provider_result_writeback, write_provider_writeback_report
from aicomic.render.season_renderer import render_season
from aicomic.publish.publish_pack import build_enhanced_publish_pack, write_publish_pack
from aicomic.publish.season_summary import build_season_summary, write_season_summary
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
    steps = [item.strip() for item in raw_steps.split(",") if item.strip()]
    if steps:
        return steps
    return list(DEFAULT_BATCH_STEPS)


def build_batch_record(
    batch_id: str,
    batch_type: str,
    scope_type: str,
    scope_value: str,
    steps: list[str],
    provider_filter: str,
    summary_path: Path,
) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        batch_type=batch_type,
        scope_type=scope_type,
        scope_value=scope_value,
        target_steps=",".join(steps),
        provider_filter=provider_filter,
        status="planned",
        summary_path=str(summary_path),
    )


def build_batch_payload(record: BatchRecord) -> dict[str, object]:
    return {
        "batch": asdict(record),
        "steps": [
            {
                "step_name": step_name,
                "status": "planned",
            }
            for step_name in record.target_steps.split(",")
            if step_name
        ],
    }


def apply_batch_preflight_gate(
    payload: dict[str, object],
    enabled: bool = True,
    auto_run: bool = True,
    providers_raw: str = "",
    max_age_minutes: int = 240,
    image_workflow_mode: str = "smoke",
    video_workflow_mode: str = "smoke",
    report_path: Path | None = None,
) -> dict[str, object]:
    batch = payload.get("batch", {})
    if not isinstance(batch, dict):
        return payload
    batch_id = str(batch.get("batch_id", "batch"))
    provider_filter = str(batch.get("provider_filter", ""))
    updated = dict(payload)
    updated["preflight_gate"] = build_batch_preflight_gate(
        batch_id=batch_id,
        provider_filter=provider_filter,
        enabled=enabled,
        auto_run=auto_run,
        providers_raw=providers_raw,
        max_age_minutes=max_age_minutes,
        image_workflow_mode=image_workflow_mode,
        video_workflow_mode=video_workflow_mode,
        report_path=report_path,
    )
    return updated


def write_batch_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_batch_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_output_path(reports_dir: Path, batch_id: str, step_name: str) -> Path:
    return reports_dir / f"{batch_id}_{step_name}.json"


# ---------------------------------------------------------------------------
#  Real-mode helpers  (step wrappers for the batch pipeline)
# ---------------------------------------------------------------------------

def _build_season_jobs(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Step 1: build jobs from manifests."""
    return build_season_job_bundle(season_manifest, episode_manifest)


def _scan_season_assets(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
    asset_root: Path,
) -> dict[str, Any]:
    """Step 2: scan assets for every episode in the season."""
    episode_reports: list[dict[str, Any]] = []
    aggregated = {
        "expected_count": 0,
        "existing_count": 0,
        "missing_required_count": 0,
        "missing_optional_count": 0,
        "ready_episode_count": 0,
    }
    for episode in season_manifest.get("episodes", []):
        episode_code = str(episode["episode_code"])
        report = scan_episode_assets(episode_manifest, episode_code, asset_root)
        episode_reports.append(report)
        aggregated["expected_count"] += report["expected_count"]
        aggregated["existing_count"] += report["existing_count"]
        aggregated["missing_required_count"] += report["missing_required_count"]
        aggregated["missing_optional_count"] += report["missing_optional_count"]
        if report["ready_for_preview"]:
            aggregated["ready_episode_count"] += 1

    return {
        "asset_root": str(asset_root),
        "episode_count": len(episode_reports),
        **aggregated,
        "missing_required_total": aggregated["missing_required_count"],
        "episode_reports": episode_reports,
        "ready_for_preview": aggregated["missing_required_count"] == 0,
    }


def _build_provider_requests_step(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
    season_jobs_bundle: dict[str, Any],
    providers_config_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Step 3: build provider requests from jobs."""
    jobs = [
        JobRecord(
            job_id=str(item["job_id"]),
            episode_code=str(item["episode_code"]),
            job_type=str(item["job_type"]),
            provider=str(item["provider"]),
            status=str(item["status"]),
        )
        for item in season_jobs_bundle.get("jobs", [])
    ]
    return build_provider_requests(
        manifest=episode_manifest,
        jobs=jobs,
        providers_config_path=providers_config_path,
        output_root=output_root,
    )


def _apply_provider_results_step(
    provider_requests_payload: dict[str, Any],
    providers_config_path: Path,
    *,
    dry_run: bool = False,
    confirm_live: bool = False,
    max_failures: int = 1,
    skip_existing: bool = False,
) -> dict[str, Any]:
    """Step 4: execute provider requests and write back results."""
    execution_result = execute_provider_requests(
        provider_requests=provider_requests_payload,
        providers_config_path=providers_config_path,
        dry_run=dry_run,
        confirm_live=confirm_live,
        max_failures=max_failures,
        skip_existing=skip_existing,
    )
    return execution_result


def _render_season_step(
    season_manifest: dict[str, Any],
    episode_manifest: dict[str, Any],
    asset_root: Path,
    output_dir: Path,
    report_path: Path,
    mode: str = "preview",
) -> dict[str, Any]:
    """Step 5: render the season."""
    return render_season(
        season_manifest=season_manifest,
        episode_manifest=episode_manifest,
        asset_root=asset_root,
        output_dir=output_dir,
        report_path=report_path,
        mode=mode,
    )


def _generate_publish_pack_for_season(
    episode_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Step 6: generate publish packs for every episode."""
    packs: list[dict[str, Any]] = []
    for episode in episode_manifest.get("episodes", []):
        episode_code = str(episode["episode_code"])
        pack = build_enhanced_publish_pack(episode_manifest, episode_code)
        packs.append(pack)
    return {
        "episode_count": len(packs),
        "packs": packs,
    }


def _build_season_summary_step(
    season_manifest: dict[str, Any],
    season_jobs_bundle: dict[str, Any],
    season_scan_report: dict[str, Any],
    season_render_report: dict[str, Any],
) -> dict[str, Any]:
    """Step 7: build consolidated season summary."""
    return build_season_summary(
        season_manifest=season_manifest,
        season_jobs=season_jobs_bundle,
        season_scan=season_scan_report,
        season_render=season_render_report,
    )


# ---------------------------------------------------------------------------
#  Step registry: maps step name → (callable, needs_run_context)
# ---------------------------------------------------------------------------

_REAL_STEP_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "build_season_jobs": _build_season_jobs,
    "scan_season_assets": _scan_season_assets,
    "build_provider_requests": _build_provider_requests_step,
    "apply_provider_results": _apply_provider_results_step,
    "render_season": _render_season_step,
    "generate_publish_pack": _generate_publish_pack_for_season,
    "build_season_summary": _build_season_summary_step,
}


# ---------------------------------------------------------------------------
#  Custom exception for batch execution errors
# ---------------------------------------------------------------------------

class BatchStepError(Exception):
    """Raised when a real batch step fails. Carries the wrapped error for diagnostics."""

    def __init__(self, step_name: str, original_error: Exception) -> None:
        self.step_name = step_name
        self.original_error = original_error
        super().__init__(f"[{step_name}] {original_error}")


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def run_batch_payload(
    batch_payload: dict[str, Any],
    reports_dir: Path,
    *,
    # execution mode
    mode: str = "simulated",
    # parallelism
    max_workers: int = 1,
    # progress reporting
    progress_callback: Callable[[str, int, int], None] | None = None,
    # context for real mode
    season_manifest: dict[str, Any] | None = None,
    episode_manifest: dict[str, Any] | None = None,
    providers_config_path: Path | None = None,
    asset_root: Path | None = None,
    render_output_dir: Path | None = None,
    render_mode: str = "preview",
    # executor options
    execute_dry_run: bool = False,
    execute_confirm_live: bool = False,
    execute_max_failures: int = 1,
    execute_skip_existing: bool = False,
) -> tuple[dict[str, object], list[BatchRunRecord]]:
    """Execute a batch payload.

    Parameters
    ----------
    batch_payload : dict
        The batch payload dict produced by build_batch_payload().
    reports_dir : Path
        Directory to write per-step output reports.
    mode : str
        ``"simulated"`` (default, MVP stub) or ``"real"`` (actual execution).
    max_workers : int
        Maximum parallel workers for independent steps in real mode.
    progress_callback : Callable[[str, int, int], None] | None
        Called after each step with ``(step_name, completed, total)``.
    season_manifest : dict | None
        Required in real mode. Season-level manifest dict.
    episode_manifest : dict | None
        Required in real mode. Episode-level manifest dict.
    providers_config_path : Path | None
        Required for provider-related steps in real mode.
    asset_root : Path | None
        Required for asset scanning in real mode.
    render_output_dir : Path | None
        Required for render step in real mode.
    render_mode : str
        Render mode (``"preview"`` or ``"release"``). Default ``"preview"``.
    execute_dry_run : bool
        When true, executor dry-runs instead of sending live requests.
    execute_confirm_live : bool
        Must be true for executor to perform live API calls.
    execute_max_failures : int
        Max failures before executor stops (default 1).
    execute_skip_existing : bool
        When true, executor skips requests whose output already exists.

    Returns
    -------
    (report, run_records)
    """
    batch = batch_payload["batch"]
    batch_id = str(batch["batch_id"])
    run_records: list[BatchRunRecord] = []
    step_results: list[dict[str, object]] = []
    steps = batch_payload.get("steps", [])

    # ---- preflight gate -------------------------------------------------
    preflight_gate = batch_payload.get("preflight_gate", {})
    preflight_result = (
        ensure_batch_preflight_gate(preflight_gate)
        if isinstance(preflight_gate, dict)
        else {
            "status": "disabled",
            "reason": "",
            "report_path": "",
            "mode": "disabled",
            "report": {},
        }
    )

    if str(preflight_result["status"]) not in {"disabled", "passed"}:
        report = {
            "batch_id": batch_id,
            "scope_type": str(batch["scope_type"]),
            "scope_value": str(batch["scope_value"]),
            "step_count": 0,
            "simulated_step_count": 0,
            "real_step_count": 0,
            "failed_step_count": 0,
            "status": "blocked_preflight_failed",
            "step_results": [],
            "preflight_gate": preflight_result,
        }
        return report, run_records

    # ---- route to mode --------------------------------------------------
    if mode == "simulated":
        return _run_simulated(batch_payload, reports_dir, batch, batch_id, preflight_result)
    elif mode == "real":
        return _run_real(
            batch_payload,
            reports_dir,
            batch,
            batch_id,
            preflight_result,
            season_manifest=season_manifest,
            episode_manifest=episode_manifest,
            providers_config_path=providers_config_path,
            asset_root=asset_root,
            render_output_dir=render_output_dir,
            render_mode=render_mode,
            execute_dry_run=execute_dry_run,
            execute_confirm_live=execute_confirm_live,
            execute_max_failures=execute_max_failures,
            execute_skip_existing=execute_skip_existing,
            max_workers=max_workers,
            progress_callback=progress_callback,
        )
    else:
        raise ValueError(f"Unknown batch execution mode: {mode!r}. Use 'simulated' or 'real'.")


# ---------------------------------------------------------------------------
#  Simulated mode  (unchanged behaviour)
# ---------------------------------------------------------------------------

def _run_simulated(
    batch_payload: dict[str, Any],
    reports_dir: Path,
    batch: dict[str, Any],
    batch_id: str,
    preflight_result: dict[str, Any],
) -> tuple[dict[str, object], list[BatchRunRecord]]:
    run_records: list[BatchRunRecord] = []
    step_results: list[dict[str, object]] = []

    for step in batch_payload.get("steps", []):
        step_name = str(step["step_name"])
        output_path = build_run_output_path(reports_dir, batch_id, step_name)
        step_result: dict[str, object] = {
            "batch_id": batch_id,
            "step_name": step_name,
            "status": "simulated",
            "output_path": str(output_path),
            "message": "MVP 阶段记录批次步骤，实际生产动作由既有 CLI 命令执行",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(step_result, ensure_ascii=False, indent=2), encoding="utf-8")
        run_id = f"RUN_{batch_id}_{step_name}"
        run_records.append(
            BatchRunRecord(
                run_id=run_id,
                batch_id=batch_id,
                step_name=step_name,
                status="simulated",
                output_path=str(output_path),
            )
        )
        step_results.append(step_result)

    report: dict[str, object] = {
        "batch_id": batch_id,
        "scope_type": str(batch["scope_type"]),
        "scope_value": str(batch["scope_value"]),
        "step_count": len(step_results),
        "simulated_step_count": len(step_results),
        "real_step_count": 0,
        "failed_step_count": 0,
        "status": "completed",
        "step_results": step_results,
        "preflight_gate": preflight_result,
    }
    return report, run_records


# ---------------------------------------------------------------------------
#  Real mode
# ---------------------------------------------------------------------------

def _run_real(
    batch_payload: dict[str, Any],
    reports_dir: Path,
    batch: dict[str, Any],
    batch_id: str,
    preflight_result: dict[str, Any],
    *,
    season_manifest: dict[str, Any] | None,
    episode_manifest: dict[str, Any] | None,
    providers_config_path: Path | None,
    asset_root: Path | None,
    render_output_dir: Path | None,
    render_mode: str,
    execute_dry_run: bool,
    execute_confirm_live: bool,
    execute_max_failures: int,
    execute_skip_existing: bool,
    max_workers: int,
    progress_callback: Callable[[str, int, int], None] | None,
) -> tuple[dict[str, object], list[BatchRunRecord]]:
    step_results: list[dict[str, object]] = []
    run_records: list[BatchRunRecord] = []
    total_steps = len(batch_payload.get("steps", []))
    failed_steps = 0

    # Intermediate results that steps may consume
    season_jobs_bundle: dict[str, Any] | None = None
    season_scan_report: dict[str, Any] | None = None
    provider_requests_payload: dict[str, Any] | None = None
    render_report: dict[str, Any] | None = None
    publish_pack_result: dict[str, Any] | None = None

    # Build run context for steps that need it
    run_ctx: dict[str, Any] = {
        "batch_id": batch_id,
        "mode": "real",
    }

    for step_index, step in enumerate(batch_payload.get("steps", [])):
        step_name = str(step["step_name"])
        output_path = build_run_output_path(reports_dir, batch_id, step_name)

        try:
            step_result = _execute_real_step(
                step_name=step_name,
                season_manifest=season_manifest,
                episode_manifest=episode_manifest,
                season_jobs_bundle=season_jobs_bundle,
                season_scan_report=season_scan_report,
                provider_requests_payload=provider_requests_payload,
                render_report=render_report,
                providers_config_path=providers_config_path,
                asset_root=asset_root,
                render_output_dir=render_output_dir,
                render_mode=render_mode,
                execute_dry_run=execute_dry_run,
                execute_confirm_live=execute_confirm_live,
                execute_max_failures=execute_max_failures,
                execute_skip_existing=execute_skip_existing,
                run_ctx=run_ctx,
            )

            # Update intermediate results
            if step_name == "build_season_jobs":
                season_jobs_bundle = step_result
            elif step_name == "scan_season_assets":
                season_scan_report = step_result
            elif step_name == "build_provider_requests":
                provider_requests_payload = step_result
            elif step_name == "render_season":
                render_report = step_result
            elif step_name == "generate_publish_pack":
                publish_pack_result = step_result

        except BatchStepError as exc:
            # Record failure but continue to next step
            step_result = {
                "batch_id": batch_id,
                "step_name": step_name,
                "status": "failed",
                "output_path": str(output_path),
                "error": str(exc),
                "error_detail": str(exc.original_error),
            }
            failed_steps += 1

        # Write step output
        step_status = str(step_result.get("status", "unknown"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_path, step_result)

        run_id = f"RUN_{batch_id}_{step_name}"
        run_records.append(
            BatchRunRecord(
                run_id=run_id,
                batch_id=batch_id,
                step_name=step_name,
                status=step_status,
                output_path=str(output_path),
            )
        )
        step_results.append(
            {
                "batch_id": batch_id,
                "step_name": step_name,
                "status": step_status,
                "output_path": str(output_path),
                "message": step_result.get("message", ""),
                "error": step_result.get("error", ""),
            }
        )

        if progress_callback is not None:
            progress_callback(step_name, step_index + 1, total_steps)

    simulated_count = sum(
        1 for r in step_results if str(r.get("status")) == "simulated"
    )
    real_count = sum(
        1 for r in step_results if str(r.get("status")) not in ("simulated", "failed")
    )

    overall_status = "completed"
    if failed_steps > 0 and len(step_results) == failed_steps:
        overall_status = "failed"
    elif failed_steps > 0:
        overall_status = "partial"

    report: dict[str, object] = {
        "batch_id": batch_id,
        "scope_type": str(batch["scope_type"]),
        "scope_value": str(batch["scope_value"]),
        "step_count": len(step_results),
        "simulated_step_count": simulated_count,
        "real_step_count": real_count,
        "failed_step_count": failed_steps,
        "status": overall_status,
        "step_results": step_results,
        "preflight_gate": preflight_result,
    }
    return report, run_records


def _execute_real_step(
    step_name: str,
    *,
    season_manifest: dict[str, Any] | None,
    episode_manifest: dict[str, Any] | None,
    season_jobs_bundle: dict[str, Any] | None,
    season_scan_report: dict[str, Any] | None,
    provider_requests_payload: dict[str, Any] | None,
    render_report: dict[str, Any] | None,
    providers_config_path: Path | None,
    asset_root: Path | None,
    render_output_dir: Path | None,
    render_mode: str,
    execute_dry_run: bool,
    execute_confirm_live: bool,
    execute_max_failures: int,
    execute_skip_existing: bool,
    run_ctx: dict[str, Any],
) -> dict[str, Any]:
    """Execute a single real-mode step, raising BatchStepError on failure."""

    try:
        if step_name == "build_season_jobs":
            if season_manifest is None or episode_manifest is None:
                raise ValueError("build_season_jobs requires season_manifest and episode_manifest")
            result = _build_season_jobs(season_manifest, episode_manifest)
            return {
                **result,
                "status": "completed",
                "message": f"Built {result.get('job_count', 0)} jobs across {result.get('episode_count', 0)} episodes",
            }

        elif step_name == "scan_season_assets":
            if season_manifest is None or episode_manifest is None or asset_root is None:
                raise ValueError("scan_season_assets requires season_manifest, episode_manifest, and asset_root")
            result = _scan_season_assets(season_manifest, episode_manifest, asset_root)
            return {
                "status": "completed",
                "scan_result": result,
                "message": (
                    f"Scanned {result.get('episode_count', 0)} episodes: "
                    f"{result.get('existing_count', 0)} assets found, "
                    f"{result.get('missing_required_count', 0)} required missing"
                ),
            }

        elif step_name == "build_provider_requests":
            if season_manifest is None or episode_manifest is None:
                raise ValueError("build_provider_requests requires season_manifest and episode_manifest")
            if season_jobs_bundle is None:
                raise ValueError("build_provider_requests requires build_season_jobs to run first")
            if providers_config_path is None:
                raise ValueError("build_provider_requests requires providers_config_path")
            output_root = providers_config_path.parent  # reasonable default
            result = _build_provider_requests_step(
                season_manifest, episode_manifest,
                season_jobs_bundle, providers_config_path, output_root,
            )
            return {
                **result,
                "status": "completed",
                "message": (
                    f"Built {result.get('request_count', 0)} provider requests "
                    f"({result.get('ready_count', 0)} ready, {result.get('blocked_count', 0)} blocked)"
                ),
            }

        elif step_name == "apply_provider_results":
            if providers_config_path is None:
                raise ValueError("apply_provider_results requires providers_config_path")
            if provider_requests_payload is None:
                raise ValueError("apply_provider_results requires build_provider_requests to run first")
            result = _apply_provider_results_step(
                provider_requests_payload,
                providers_config_path,
                dry_run=execute_dry_run,
                confirm_live=execute_confirm_live,
                max_failures=execute_max_failures,
                skip_existing=execute_skip_existing,
            )
            return {
                **result,
                "status": "completed",
                "message": (
                    f"Executed provider requests: "
                    f"{result.get('success_count', 0)} succeeded, "
                    f"{result.get('failed_count', 0)} failed, "
                    f"{result.get('skipped_count', 0)} skipped"
                ),
            }

        elif step_name == "render_season":
            if season_manifest is None or episode_manifest is None:
                raise ValueError("render_season requires season_manifest and episode_manifest")
            if asset_root is None:
                raise ValueError("render_season requires asset_root")
            if render_output_dir is None:
                raise ValueError("render_season requires render_output_dir")
            report_path = render_output_dir / f"{run_ctx['batch_id']}_render.json"
            result = _render_season_step(
                season_manifest, episode_manifest,
                asset_root, render_output_dir, report_path,
                mode=render_mode,
            )
            return {
                **result,
                "status": "completed",
                "message": (
                    f"Rendered {result.get('episode_count', 0)} episodes in {render_mode} mode"
                ),
            }

        elif step_name == "generate_publish_pack":
            if episode_manifest is None:
                raise ValueError("generate_publish_pack requires episode_manifest")
            result = _generate_publish_pack_for_season(episode_manifest)
            return {
                **result,
                "status": "completed",
                "message": f"Generated publish packs for {result.get('episode_count', 0)} episodes",
            }

        elif step_name == "build_season_summary":
            if season_manifest is None:
                raise ValueError("build_season_summary requires season_manifest")
            if season_jobs_bundle is None:
                raise ValueError("build_season_summary requires build_season_jobs to run first")
            if season_scan_report is None:
                raise ValueError("build_season_summary requires scan_season_assets to run first")
            if render_report is None:
                raise ValueError("build_season_summary requires render_season to run first")
            result = _build_season_summary_step(
                season_manifest, season_jobs_bundle, season_scan_report, render_report,
            )
            return {
                **result,
                "status": "completed",
                "message": "Season summary built",
            }

        else:
            # Unknown step — fall back to simulated stub
            return {
                "status": "simulated",
                "message": f"No real handler for step '{step_name}', recorded as simulated",
            }

    except Exception as exc:
        raise BatchStepError(step_name, exc) from exc
