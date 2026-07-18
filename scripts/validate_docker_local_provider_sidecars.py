from __future__ import annotations

import json
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths


def require_contains(path: Path, patterns: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [pattern for pattern in patterns if pattern not in text]
    if missing:
        raise RuntimeError(f"{path.name} missing patterns: {missing}")


def main() -> int:
    local_override = PROJECT_ROOT / "docker-compose.local-providers.yml"
    production_override = PROJECT_ROOT / "docker-compose.production.local-providers.yml"
    require_contains(local_override, ["aicomic-comfyui", "aicomic-piper", "AICOMIC_COMFYUI_BASE_URL", "AICOMIC_PIPER_BASE_URL"])
    require_contains(production_override, ["aicomic-comfyui", "aicomic-piper", "AICOMIC_COMFYUI_BASE_URL", "AICOMIC_PIPER_BASE_URL"])
    dockerfile_path = PROJECT_ROOT / "Dockerfile.comfyui-sidecar"
    if not dockerfile_path.exists():
        raise RuntimeError(f"missing dockerfile: {dockerfile_path}")
    image_smoke_workflow = PROJECT_ROOT / "local_providers" / "comfyui" / "workflows" / "image_workflow_live_smoke.json"
    if not image_smoke_workflow.exists():
        raise RuntimeError(f"missing lightweight image smoke workflow: {image_smoke_workflow}")
    sidecar_scripts = [
        PROJECT_ROOT / "scripts" / "run_comfyui_sidecar.py",
        PROJECT_ROOT / "scripts" / "manage_comfyui_image_cache.py",
        PROJECT_ROOT / "scripts" / "run_piper_http_server.py",
        PROJECT_ROOT / "scripts" / "manage_local_provider_stack.sh",
    ]
    missing_scripts = [str(path) for path in sidecar_scripts if not path.exists()]
    if missing_scripts:
        raise RuntimeError(f"missing sidecar helper scripts: {missing_scripts}")
    cache_manager = PROJECT_ROOT / "scripts" / "manage_comfyui_image_cache.py"
    cache_manager_text = cache_manager.read_text(encoding="utf-8")
    if not cache_manager_text.startswith("#!/usr/bin/env python3\n"):
        raise RuntimeError("manage_comfyui_image_cache.py must be directly runnable with a python3 shebang")
    if not os.access(cache_manager, os.X_OK):
        raise RuntimeError("manage_comfyui_image_cache.py must be executable for documented operations")
    bash_check = subprocess.run(
        ["bash", "-n", str(PROJECT_ROOT / "scripts" / "manage_local_provider_stack.sh")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if bash_check.returncode != 0:
        raise RuntimeError(f"manage_local_provider_stack.sh syntax error: {(bash_check.stderr or bash_check.stdout).strip()}")
    python_check = subprocess.run(
        [sys.executable, "-m", "py_compile", str(PROJECT_ROOT / "scripts" / "manage_comfyui_image_cache.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if python_check.returncode != 0:
        raise RuntimeError(f"manage_comfyui_image_cache.py syntax error: {(python_check.stderr or python_check.stdout).strip()}")
    validation_payload = {
        "run_id": f"docker_local_provider_sidecars_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "local_override": str(local_override),
        "production_override": str(production_override),
        "dockerfile": str(dockerfile_path),
        "image_smoke_workflow": str(image_smoke_workflow),
        "script_count": len(sidecar_scripts),
        "report_path": str(ProjectPaths.reports_dir() / "docker_local_provider_sidecars_validation_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "docker_local_provider_sidecars_validation_report.json"
    report_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
