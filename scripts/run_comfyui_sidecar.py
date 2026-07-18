from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys


PROJECT_ROOT = Path(os.environ.get("AICOMIC_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
COMFYUI_ROOT = Path(os.environ.get("AICOMIC_COMFYUI_ROOT", "/opt/comfyui")).resolve()


def ensure_container_extra_model_paths_config() -> Path:
    config_path = PROJECT_ROOT / "state" / "comfyui_docker_extra_model_paths.yaml"
    base_path = (PROJECT_ROOT / "local_providers" / "comfyui").resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "aicomic:",
                f"  base_path: {base_path.as_posix()}",
                "  text_encoders: models/text_encoders",
                "  diffusion_models: models/diffusion_models",
                "  vae: models/vae",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def main() -> int:
    host = os.environ.get("AICOMIC_COMFYUI_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = os.environ.get("AICOMIC_COMFYUI_PORT", "8188").strip() or "8188"
    device_mode = os.environ.get("AICOMIC_COMFYUI_DEVICE_MODE", "cpu").strip().lower() or "cpu"
    extra_args = shlex.split(os.environ.get("AICOMIC_COMFYUI_EXTRA_ARGS", "").strip())
    extra_model_paths = ensure_container_extra_model_paths_config()
    output_directory = PROJECT_ROOT / "state" / "comfyui_docker_output"
    input_directory = PROJECT_ROOT / "state" / "comfyui_docker_input"
    temp_directory = PROJECT_ROOT / "state" / "comfyui_docker_temp"
    output_directory.mkdir(parents=True, exist_ok=True)
    input_directory.mkdir(parents=True, exist_ok=True)
    temp_directory.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "main.py",
        "--listen",
        host,
        "--port",
        port,
        "--disable-auto-launch",
        "--extra-model-paths-config",
        str(extra_model_paths),
        "--output-directory",
        str(output_directory),
        "--input-directory",
        str(input_directory),
        "--temp-directory",
        str(temp_directory),
        "--log-stdout",
    ]
    if device_mode == "cpu":
        command.append("--cpu")
    command.extend(extra_args)
    process = subprocess.run(
        command,
        cwd=str(COMFYUI_ROOT),
        check=False,
    )
    return int(process.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
