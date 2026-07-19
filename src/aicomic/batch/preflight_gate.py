from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from aicomic.core.config import ProjectPaths
from aicomic.providers.live_smoke import SUPPORTED_LIVE_SMOKE_PROVIDERS, run_local_provider_live_smoke, write_local_provider_live_smoke_report


DEFAULT_LOCAL_PROVIDER_PREFLIGHT_PROVIDERS = ",".join(SUPPORTED_LIVE_SMOKE_PROVIDERS)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def parse_provider_filter(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def default_preflight_report_path(batch_id: str) -> Path:
    return ProjectPaths.reports_dir() / f"{batch_id}_local_provider_live_smoke.json"


def should_require_local_provider_preflight(provider_filter: str, enabled: bool) -> bool:
    if not enabled:
        return False
    selected_providers = parse_provider_filter(provider_filter)
    if not selected_providers:
        return True
    return bool(selected_providers & set(SUPPORTED_LIVE_SMOKE_PROVIDERS))


def build_batch_preflight_gate(
    batch_id: str,
    provider_filter: str,
    enabled: bool = True,
    auto_run: bool = True,
    providers_raw: str = DEFAULT_LOCAL_PROVIDER_PREFLIGHT_PROVIDERS,
    max_age_minutes: int = 240,
    image_workflow_mode: str = "smoke",
    video_workflow_mode: str = "smoke",
    report_path: Path | None = None,
) -> dict[str, Any]:
    required = should_require_local_provider_preflight(provider_filter, enabled)
    providers = sorted(parse_provider_filter(providers_raw) or set(SUPPORTED_LIVE_SMOKE_PROVIDERS))
    resolved_report_path = report_path or default_preflight_report_path(batch_id)
    return {
        "enabled": required,
        "auto_run": bool(auto_run),
        "providers": providers,
        "max_age_minutes": max(1, int(max_age_minutes)),
        "image_workflow_mode": image_workflow_mode,
        "video_workflow_mode": video_workflow_mode,
        "report_path": str(resolved_report_path),
        "created_at": now_iso(),
    }


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_run_time(raw_value: str) -> datetime | None:
    if not raw_value.strip():
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def evaluate_existing_preflight_report(gate: dict[str, Any]) -> dict[str, Any]:
    report_path = Path(str(gate.get("report_path", "")))
    report = load_optional_json(report_path) if report_path else {}
    if not report_path or not report_path.exists():
        return {
            "status": "missing",
            "report_path": str(report_path),
            "reason": "local provider preflight report is missing",
            "report": {},
            "age_minutes": None,
        }
    if str(report.get("status", "")) != "passed":
        return {
            "status": "failed",
            "report_path": str(report_path),
            "reason": "local provider preflight report did not pass",
            "report": report,
            "age_minutes": None,
        }
    run_at = parse_run_time(str(report.get("run_at", "")))
    age_minutes: float | None = None
    if run_at is not None:
        now = datetime.now(run_at.tzinfo or timezone.utc)
        age_minutes = max(0.0, (now - run_at).total_seconds() / 60.0)
    max_age_minutes = int(gate.get("max_age_minutes", 240) or 240)
    if age_minutes is not None and age_minutes > max_age_minutes:
        return {
            "status": "stale",
            "report_path": str(report_path),
            "reason": f"local provider preflight report is older than {max_age_minutes} minutes",
            "report": report,
            "age_minutes": age_minutes,
        }
    expected_providers = set(gate.get("providers", []))
    actual_providers = set(report.get("selected_providers", []))
    if expected_providers and not expected_providers.issubset(actual_providers):
        return {
            "status": "provider_mismatch",
            "report_path": str(report_path),
            "reason": "local provider preflight report does not cover all required providers",
            "report": report,
            "age_minutes": age_minutes,
        }
    workflow_mode_mismatches: list[str] = []
    if "local_comfyui_image" in expected_providers:
        expected_image_workflow_mode = str(gate.get("image_workflow_mode", "")).strip()
        actual_image_workflow_mode = str(report.get("image_workflow_mode", "")).strip()
        if expected_image_workflow_mode and actual_image_workflow_mode != expected_image_workflow_mode:
            workflow_mode_mismatches.append(
                f"image workflow mode expected {expected_image_workflow_mode}, got {actual_image_workflow_mode or 'missing'}"
            )
    if "local_comfyui_video" in expected_providers:
        expected_video_workflow_mode = str(gate.get("video_workflow_mode", "")).strip()
        actual_video_workflow_mode = str(report.get("video_workflow_mode", "")).strip()
        if expected_video_workflow_mode and actual_video_workflow_mode != expected_video_workflow_mode:
            workflow_mode_mismatches.append(
                f"video workflow mode expected {expected_video_workflow_mode}, got {actual_video_workflow_mode or 'missing'}"
            )
    if workflow_mode_mismatches:
        return {
            "status": "workflow_mode_mismatch",
            "report_path": str(report_path),
            "reason": "; ".join(workflow_mode_mismatches),
            "report": report,
            "age_minutes": age_minutes,
        }
    return {
        "status": "passed",
        "report_path": str(report_path),
        "reason": "",
        "report": report,
        "age_minutes": age_minutes,
    }


def ensure_batch_preflight_gate(gate: dict[str, Any]) -> dict[str, Any]:
    if not bool(gate.get("enabled", False)):
        return {
            "status": "disabled",
            "reason": "",
            "report_path": str(gate.get("report_path", "")),
            "mode": "disabled",
            "report": {},
        }
    existing = evaluate_existing_preflight_report(gate)
    if existing["status"] == "passed":
        return {
            "status": "passed",
            "reason": "",
            "report_path": existing["report_path"],
            "mode": "reused",
            "report": existing["report"],
            "age_minutes": existing.get("age_minutes"),
        }
    if not bool(gate.get("auto_run", True)):
        return {
            "status": "blocked",
            "reason": str(existing.get("reason", "local provider preflight is required")),
            "report_path": existing["report_path"],
            "mode": "blocked",
            "report": existing.get("report", {}),
            "age_minutes": existing.get("age_minutes"),
        }
    report_path = Path(str(gate.get("report_path", "")))
    report_payload = run_local_provider_live_smoke(
        providers_config_path=ProjectPaths.providers_config_path(),
        selected_providers=set(gate.get("providers", [])),
        output_root=ProjectPaths.state_dir() / "batch_preflight" / report_path.stem,
        image_workflow_mode=str(gate.get("image_workflow_mode", "smoke")),
        video_workflow_mode=str(gate.get("video_workflow_mode", "smoke")),
        skip_comfyui_start=False,
        restart_comfyui=True,
        retry_comfyui_on_failure=True,
        max_failures=1,
    )
    write_local_provider_live_smoke_report(report_path, report_payload)
    final_status = "passed" if str(report_payload.get("status", "")) == "passed" else "failed"
    return {
        "status": final_status,
        "reason": "" if final_status == "passed" else "auto-run local provider preflight failed",
        "report_path": str(report_path),
        "mode": "auto_ran",
        "report": report_payload,
        "age_minutes": 0.0,
    }
