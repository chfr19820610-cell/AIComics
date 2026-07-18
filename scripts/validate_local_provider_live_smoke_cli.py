from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.security.production_rehearsal import build_rehearsal_environment, prepare_comfyui_fixture_models, run_mock_comfyui_server, temporary_environment


def run_python_command(arguments: list[str], timeout_seconds: int = 300) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = f"{SRC_DIR}:{PROJECT_ROOT}" if not existing_pythonpath else f"{SRC_DIR}:{PROJECT_ROOT}:{existing_pythonpath}"
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def load_json_report(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    state_root = ProjectPaths.state_dir() / "local_provider_live_smoke_cli_validation"
    model_root = state_root / "comfyui_models"
    empty_model_root = state_root / "empty_comfyui_models"
    output_root = state_root / "outputs"
    image_smoke_output_root = state_root / "image_smoke_outputs"
    state_root.mkdir(parents=True, exist_ok=True)
    empty_model_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    image_smoke_output_root.mkdir(parents=True, exist_ok=True)
    fixture_report = prepare_comfyui_fixture_models(
        model_root,
        PROJECT_ROOT / "local_providers" / "comfyui" / "model_requirements.json",
    )

    with run_mock_comfyui_server() as mock_server:
        rehearsal_env = build_rehearsal_environment(PROJECT_ROOT, str(mock_server["base_url"]), model_root)
        with temporary_environment(rehearsal_env):
            service_report_path = ProjectPaths.reports_dir() / "comfyui_service_cli_validation_report.json"
            smoke_report_path = ProjectPaths.reports_dir() / "local_provider_live_smoke_cli_validation_report.json"
            image_smoke_report_path = ProjectPaths.reports_dir() / "local_provider_image_smoke_no_models_validation_report.json"

            service_result = run_python_command(
                [
                    "scripts/manage_comfyui_service.py",
                    "status",
                    "--host",
                    str(mock_server["host"]),
                    "--port",
                    str(mock_server["port"]),
                    "--output",
                    str(service_report_path),
                ]
            )
            if service_result.returncode != 0:
                raise RuntimeError(
                    f"manage_comfyui_service.py failed with code {service_result.returncode}: "
                    f"{(service_result.stderr or service_result.stdout).strip()}"
                )

            smoke_result = run_python_command(
                [
                    "scripts/run_local_provider_live_smoke.py",
                    "--providers",
                    "local_comfyui_image,local_comfyui_video,local_piper_tts",
                    "--skip-comfyui-start",
                    "--image-workflow-mode",
                    "smoke",
                    "--video-workflow-mode",
                    "smoke",
                    "--output-root",
                    str(output_root),
                    "--output",
                    str(smoke_report_path),
                    "--comfyui-host",
                    str(mock_server["host"]),
                    "--comfyui-port",
                    str(mock_server["port"]),
                ]
            )
            if smoke_result.returncode != 0:
                raise RuntimeError(
                    f"run_local_provider_live_smoke.py failed with code {smoke_result.returncode}: "
                    f"{(smoke_result.stderr or smoke_result.stdout).strip()}"
                )

            image_smoke_env = dict(rehearsal_env)
            image_smoke_env["AICOMIC_COMFYUI_MODEL_ROOT"] = str(empty_model_root)
            with temporary_environment(image_smoke_env):
                image_smoke_result = run_python_command(
                    [
                        "scripts/run_local_provider_live_smoke.py",
                        "--providers",
                        "local_comfyui_image",
                        "--skip-comfyui-start",
                        "--image-workflow-mode",
                        "smoke",
                        "--output-root",
                        str(image_smoke_output_root),
                        "--output",
                        str(image_smoke_report_path),
                        "--comfyui-host",
                        str(mock_server["host"]),
                        "--comfyui-port",
                        str(mock_server["port"]),
                    ]
                )
                if image_smoke_result.returncode != 0:
                    raise RuntimeError(
                        f"image smoke without models failed with code {image_smoke_result.returncode}: "
                        f"{(image_smoke_result.stderr or image_smoke_result.stdout).strip()}"
                    )

    service_report = load_json_report(service_report_path)
    smoke_report = load_json_report(smoke_report_path)
    image_smoke_report = load_json_report(image_smoke_report_path)

    if not bool(service_report.get("status_after", {}).get("health", {}).get("reachable", False)):
        raise RuntimeError(f"ComfyUI service status health probe failed: {service_report}")
    final_summary = smoke_report.get("final_summary", {})
    if str(smoke_report.get("status", "")) != "passed":
        raise RuntimeError(f"local provider live smoke failed: {smoke_report}")
    if smoke_report.get("image_workflow_mode") != "smoke" or smoke_report.get("video_workflow_mode") != "smoke":
        raise RuntimeError(f"live smoke workflow mode mismatch: {smoke_report}")
    if int(final_summary.get("success_count", 0)) != 3 or int(final_summary.get("failed_count", 0)) != 0:
        raise RuntimeError(f"unexpected live smoke counts: {final_summary}")
    if image_smoke_report.get("status") != "passed":
        raise RuntimeError(f"image smoke without model files did not pass: {image_smoke_report}")
    image_smoke_previews = image_smoke_report.get("previews", [])
    image_smoke_preflight = (
        image_smoke_previews[0].get("preview", {}).get("preflight", {})
        if image_smoke_previews and isinstance(image_smoke_previews[0], dict)
        else {}
    )
    if bool(image_smoke_preflight.get("model_requirements_enforced", True)):
        raise RuntimeError(f"image smoke should not enforce model weights: {image_smoke_preflight}")
    if not bool(image_smoke_preflight.get("required_models_ready", False)):
        raise RuntimeError(f"image smoke should be model-ready without weights: {image_smoke_preflight}")

    output_paths = [
        output_root / "local_comfyui_image" / "E01_S01_image.png",
        output_root / "local_comfyui_video" / "E01_S02_video.mp4",
        output_root / "local_piper_tts" / "E01_S01_tts.wav",
        image_smoke_output_root / "local_comfyui_image" / "E01_S01_image.png",
    ]
    missing_outputs = [str(path) for path in output_paths if not path.exists() or path.stat().st_size <= 0]
    if missing_outputs:
        raise RuntimeError(f"live smoke did not write outputs: {missing_outputs}")

    validation_payload = {
        "run_id": f"local_provider_live_smoke_cli_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "mock_comfyui_base_url": mock_server["base_url"],
        "fixture_model_count": fixture_report["fixture_model_count"],
        "service_report_path": str(service_report_path),
        "smoke_report_path": str(smoke_report_path),
        "image_smoke_report_path": str(image_smoke_report_path),
        "success_count": final_summary["success_count"],
        "output_paths": [str(path) for path in output_paths],
        "report_path": str(ProjectPaths.reports_dir() / "validate_local_provider_live_smoke_cli_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "validate_local_provider_live_smoke_cli_report.json"
    report_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
