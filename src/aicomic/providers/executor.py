from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from aicomic.providers.local_adapter import LOCAL_EXECUTION_PROVIDERS, build_local_request_preview, perform_local_request
from aicomic.providers.openai_adapter import build_openai_request_preview, get_openai_api_key, perform_openai_request


OPENAI_EXECUTION_PROVIDERS = {"openai_image", "openai_tts"}
SUPPORTED_EXECUTION_PROVIDERS = OPENAI_EXECUTION_PROVIDERS | LOCAL_EXECUTION_PROVIDERS


def should_include_provider(provider: str, selected_providers: set[str] | None) -> bool:
    if not selected_providers:
        return True
    return provider in selected_providers


def build_provider_request_preview(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    if provider in OPENAI_EXECUTION_PROVIDERS:
        return build_openai_request_preview(request_item, providers_config_path)
    if provider in LOCAL_EXECUTION_PROVIDERS:
        return build_local_request_preview(request_item, providers_config_path)
    return {
        "method": "",
        "url": "",
        "headers": {},
        "body": {},
        "preflight": {"ready": False, "notes": f"Unsupported provider: {provider}"},
    }


def perform_provider_request(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    if provider in OPENAI_EXECUTION_PROVIDERS:
        return perform_openai_request(request_item, providers_config_path)
    if provider in LOCAL_EXECUTION_PROVIDERS:
        return perform_local_request(request_item, providers_config_path)
    raise RuntimeError(f"Unsupported provider: {provider}")


def resolve_provider_ready(provider: str, preview: dict[str, Any], api_key_ready: bool) -> bool:
    if provider in OPENAI_EXECUTION_PROVIDERS:
        return api_key_ready
    preflight = preview.get("preflight", {})
    if isinstance(preflight, dict):
        return bool(preflight.get("ready", False))
    return False


def execute_provider_requests(
    provider_requests: dict[str, Any],
    providers_config_path: Path,
    selected_providers: set[str] | None = None,
    dry_run: bool = False,
    confirm_live: bool = False,
    limit: int = 0,
    max_failures: int = 1,
    skip_existing: bool = False,
    max_workers: int = 1,
    preview: bool = False,
) -> dict[str, Any]:
    api_key_ready = bool(get_openai_api_key())
    results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    skipped_count = 0
    dry_run_count = 0
    blocked_count = 0
    provider_ready_count = 0
    provider_not_ready_count = 0
    execution_attempt_count = 0
    stopped_by_failure_guard = False
    normalized_limit = max(0, limit)
    normalized_max_failures = max(0, max_failures)

    # ── Pre-filter & build request list ────────────────────────────────
    candidate_requests: list[dict[str, Any]] = []
    for request_item in provider_requests.get("requests", []):
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", ""))
        if not should_include_provider(provider, selected_providers):
            continue
        candidate_requests.append(request_item)

    # ── First pass: handle skip-existing, unsupported, dry-run, blocked ─
    # These are fast path items that don't need actual execution.
    for request_item in candidate_requests:
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", ""))
        result = {
            "request_id": str(request_item.get("request_id", "")),
            "job_id": str(payload.get("job_id", "")),
            "provider": provider,
            "job_type": str(payload.get("job_type", "")),
        }
        output_path = Path(str(payload.get("output_path", "")))
        if skip_existing and output_path.exists() and output_path.stat().st_size > 0:
            result["status"] = "cached_existing_output"
            result["output_path"] = str(output_path)
            success_count += 1
            results.append(result)
            continue

        if provider not in SUPPORTED_EXECUTION_PROVIDERS:
            result["status"] = "skipped_unsupported_provider"
            skipped_count += 1
            results.append(result)
            continue

        if stopped_by_failure_guard:
            result["status"] = "stopped_by_failure_guard"
            skipped_count += 1
            results.append(result)
            continue

        if normalized_limit > 0 and execution_attempt_count >= normalized_limit:
            result["status"] = "skipped_by_limit"
            skipped_count += 1
            results.append(result)
            continue

        preview_info = build_provider_request_preview(request_item, providers_config_path)
        provider_ready = resolve_provider_ready(provider, preview_info, api_key_ready)
        if provider_ready:
            provider_ready_count += 1
        else:
            provider_not_ready_count += 1
        result["request_preview"] = preview_info
        result["provider_ready"] = provider_ready
        execution_attempt_count += 1

        if dry_run:
            result["status"] = "dry_run"
            result["api_key_ready"] = api_key_ready
            dry_run_count += 1
            results.append(result)
            continue

        if not confirm_live:
            result["status"] = "blocked_live_confirmation_required"
            result["api_key_ready"] = api_key_ready
            result["provider_ready"] = provider_ready
            blocked_count += 1
            skipped_count += 1
            results.append(result)
            continue

        # Mark as pending execution for the second pass
        result["_pending"] = True
        results.append(result)

    # ── Second pass: execute pending requests in parallel ───────────────
    pending_results = [r for r in results if r.get("_pending")]
    # Remove the _pending flag from all results
    for r in results:
        r.pop("_pending", None)

    if pending_results and not stopped_by_failure_guard:
        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map: dict[Any, dict[str, Any]] = {}
                for res_idx, res_item in enumerate(pending_results):
                    # Find the original request_item
                    req = candidate_requests[res_idx]
                    # Inject preview flag into payload if preview mode is on
                    if preview:
                        req.setdefault("payload", {})["preview"] = True
                    future = pool.submit(perform_provider_request, req, providers_config_path)
                    future_map[future] = res_item

                for future in as_completed(future_map):
                    res_item = future_map[future]
                    try:
                        execution_output = future.result()
                        res_item["status"] = "succeeded"
                        res_item["execution_output"] = execution_output
                        success_count += 1
                    except Exception as error:
                        res_item["status"] = "failed"
                        res_item["error"] = str(error)
                        failed_count += 1
                        if normalized_max_failures > 0 and failed_count >= normalized_max_failures:
                            stopped_by_failure_guard = True
        else:
            # Serial execution (original behavior)
            for res_item in pending_results:
                idx = results.index(res_item)
                req = candidate_requests[idx]
                if preview:
                    req.setdefault("payload", {})["preview"] = True
                try:
                    execution_output = perform_provider_request(req, providers_config_path)
                    res_item["status"] = "succeeded"
                    res_item["execution_output"] = execution_output
                    success_count += 1
                except Exception as error:
                    res_item["status"] = "failed"
                    res_item["error"] = str(error)
                    failed_count += 1
                    if normalized_max_failures > 0 and failed_count >= normalized_max_failures:
                        stopped_by_failure_guard = True

    return {
        "request_count": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "dry_run_count": dry_run_count,
        "blocked_count": blocked_count,
        "provider_ready_count": provider_ready_count,
        "provider_not_ready_count": provider_not_ready_count,
        "execution_attempt_count": execution_attempt_count,
        "selected_providers": sorted(selected_providers) if selected_providers else [],
        "dry_run": dry_run,
        "confirm_live": confirm_live,
        "limit": normalized_limit,
        "max_failures": normalized_max_failures,
        "skip_existing": skip_existing,
        "max_workers": max_workers,
        "preview": preview,
        "stopped_by_failure_guard": stopped_by_failure_guard,
        "api_key_ready": api_key_ready,
        "results": results,
    }


def write_provider_execution_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
