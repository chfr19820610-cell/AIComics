from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.providers.executor import execute_provider_requests
from aicomic.providers.readiness import build_provider_readiness_report, write_provider_readiness_report
from aicomic.security.production_rehearsal import (
    build_rehearsal_environment,
    prepare_comfyui_fixture_models,
    run_mock_comfyui_server,
    temporary_environment,
)


def build_rehearsal_requests(output_root: Path) -> dict[str, object]:
    return {
        "request_count": 2,
        "ready_count": 2,
        "blocked_count": 0,
        "requests": [
            {
                "request_id": "REQ_REHEARSAL_COMFYUI_IMAGE",
                "endpoint": "/local/comfyui/prompt",
                "payload": {
                    "job_id": "JOB_REHEARSAL_COMFYUI_IMAGE",
                    "episode_code": "E00",
                    "shot_id": "S00",
                    "job_type": "image",
                    "provider": "local_comfyui_image",
                    "prompt": "AIComics ComfyUI image production rehearsal",
                    "output_path": str(output_root / "E00_S00_rehearsal_image.png"),
                },
            },
            {
                "request_id": "REQ_REHEARSAL_COMFYUI_VIDEO",
                "endpoint": "/local/comfyui/video",
                "payload": {
                    "job_id": "JOB_REHEARSAL_COMFYUI_VIDEO",
                    "episode_code": "E00",
                    "shot_id": "S00",
                    "job_type": "video",
                    "provider": "local_comfyui_video",
                    "prompt": "AIComics ComfyUI video production rehearsal",
                    "output_path": str(output_root / "E00_S00_rehearsal_video.mp4"),
                },
            },
        ],
    }


def main() -> int:
    state_root = ProjectPaths.state_dir() / "production_rehearsal_validation"
    output_root = state_root / "outputs"
    model_root = state_root / "comfyui_models"
    output_root.mkdir(parents=True, exist_ok=True)
    fixture_report = prepare_comfyui_fixture_models(
        model_root,
        PROJECT_ROOT / "local_providers" / "comfyui" / "model_requirements.json",
    )
    provider_requests = build_rehearsal_requests(output_root)
    requests_path = ProjectPaths.reports_dir() / "comfyui_production_rehearsal_requests.json"
    requests_path.write_text(json.dumps(provider_requests, ensure_ascii=False, indent=2), encoding="utf-8")

    with run_mock_comfyui_server() as mock_comfyui:
        rehearsal_env = build_rehearsal_environment(PROJECT_ROOT, str(mock_comfyui["base_url"]), model_root)
        with temporary_environment(rehearsal_env):
            readiness_report = build_provider_readiness_report(ProjectPaths.providers_config_path(), requests_path)
            readiness_path = ProjectPaths.reports_dir() / "comfyui_production_rehearsal_readiness.json"
            write_provider_readiness_report(readiness_path, readiness_report)
            execution_report = execute_provider_requests(
                provider_requests,
                ProjectPaths.providers_config_path(),
                {"local_comfyui_image", "local_comfyui_video"},
                dry_run=False,
                confirm_live=True,
                limit=2,
                max_failures=1,
            )

    output_paths = [
        output_root / "E00_S00_rehearsal_image.png",
        output_root / "E00_S00_rehearsal_video.mp4",
    ]
    missing_outputs = [str(path) for path in output_paths if not path.exists() or path.stat().st_size <= 0]
    if int(execution_report["success_count"]) != 2 or int(execution_report["failed_count"]) != 0:
        raise RuntimeError(f"mock ComfyUI rehearsal execution failed: {execution_report}")
    if missing_outputs:
        raise RuntimeError(f"mock ComfyUI rehearsal did not write outputs: {missing_outputs}")
    items_by_provider = {
        str(item["provider"]): item
        for item in readiness_report.get("items", [])
        if item.get("provider") in {"local_comfyui_image", "local_comfyui_video"}
    }
    for provider, item in items_by_provider.items():
        readiness = item.get("readiness", {})
        if not bool(item.get("ready", False)):
            raise RuntimeError(f"{provider} should be ready in production rehearsal: {item}")
        if str(readiness.get("comfyui_server_mode", "")) != "mock":
            raise RuntimeError(f"{provider} should record mock server mode: {readiness}")
        if int(readiness.get("fixture_required_model_count", 0)) <= 0:
            raise RuntimeError(f"{provider} should record fixture model use: {readiness}")

    validation_payload = {
        "run_id": f"comfyui_production_rehearsal_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "fixture_model_count": fixture_report["fixture_model_count"],
        "mock_comfyui_base_url": mock_comfyui["base_url"],
        "readiness_status": readiness_report["status"],
        "execution_success_count": execution_report["success_count"],
        "execution_failed_count": execution_report["failed_count"],
        "output_paths": [str(path) for path in output_paths],
        "requests_path": str(requests_path),
        "report_path": str(ProjectPaths.reports_dir() / "comfyui_production_rehearsal_validation_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "comfyui_production_rehearsal_validation_report.json"
    report_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
