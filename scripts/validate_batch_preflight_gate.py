from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.batch.coordinator import apply_batch_preflight_gate, build_batch_payload, build_batch_record, run_batch_payload
from aicomic.core.config import ProjectPaths
from aicomic.security.production_rehearsal import build_rehearsal_environment, prepare_comfyui_fixture_models, run_mock_comfyui_server, temporary_environment


def main() -> int:
    state_root = ProjectPaths.state_dir() / "batch_preflight_gate_validation"
    state_root.mkdir(parents=True, exist_ok=True)
    model_root = state_root / "comfyui_models"
    run_token = datetime.now().strftime("%Y%m%d%H%M%S%f")
    fixture_report = prepare_comfyui_fixture_models(
        model_root,
        PROJECT_ROOT / "local_providers" / "comfyui" / "model_requirements.json",
    )
    base_record = build_batch_record(
        f"batch_preflight_gate_validation_{run_token}",
        "season_pipeline",
        "season",
        "S01",
        ["build_provider_requests", "render_season"],
        "local_comfyui_image,local_comfyui_video,local_piper_tts",
        ProjectPaths.reports_dir() / "batch_preflight_gate_validation_summary.json",
    )

    with run_mock_comfyui_server() as mock_server:
        rehearsal_env = build_rehearsal_environment(PROJECT_ROOT, str(mock_server["base_url"]), model_root)
        with temporary_environment(rehearsal_env):
            blocked_payload = apply_batch_preflight_gate(
                build_batch_payload(base_record),
                enabled=True,
                auto_run=False,
                providers_raw="local_comfyui_image,local_comfyui_video,local_piper_tts",
                report_path=ProjectPaths.reports_dir() / f"batch_preflight_gate_missing_smoke_{run_token}.json",
            )
            blocked_report, _ = run_batch_payload(blocked_payload, ProjectPaths.reports_dir())
            if blocked_report["status"] != "blocked_preflight_failed":
                raise RuntimeError(f"batch should block without preflight report: {blocked_report}")

            auto_payload = apply_batch_preflight_gate(
                build_batch_payload(base_record),
                enabled=True,
                auto_run=True,
                providers_raw="local_comfyui_image,local_comfyui_video,local_piper_tts",
                image_workflow_mode="smoke",
                video_workflow_mode="smoke",
                report_path=ProjectPaths.reports_dir() / f"batch_preflight_gate_auto_smoke_{run_token}.json",
            )
            auto_report, _ = run_batch_payload(auto_payload, ProjectPaths.reports_dir())
            if auto_report["status"] != "completed":
                raise RuntimeError(f"batch should complete after auto-run preflight: {auto_report}")
            preflight_gate = auto_report.get("preflight_gate", {})
            if preflight_gate.get("status") != "passed" or preflight_gate.get("mode") != "auto_ran":
                raise RuntimeError(f"batch preflight gate did not auto-run correctly: {preflight_gate}")
            smoke_report = preflight_gate.get("report", {})
            if smoke_report.get("status") != "passed":
                raise RuntimeError(f"auto-run smoke report failed: {smoke_report}")
            if smoke_report.get("image_workflow_mode") != "smoke" or smoke_report.get("video_workflow_mode") != "smoke":
                raise RuntimeError(f"auto-run smoke workflow mode mismatch: {smoke_report}")

    validation_payload = {
        "run_id": f"batch_preflight_gate_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "fixture_model_count": fixture_report["fixture_model_count"],
        "blocked_status": blocked_report["status"],
        "auto_run_status": auto_report["status"],
        "auto_preflight_status": auto_report["preflight_gate"]["status"],
        "auto_preflight_mode": auto_report["preflight_gate"]["mode"],
        "auto_preflight_report_path": auto_report["preflight_gate"]["report_path"],
        "report_path": str(ProjectPaths.reports_dir() / "batch_preflight_gate_validation_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "batch_preflight_gate_validation_report.json"
    report_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
