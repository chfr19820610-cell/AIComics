from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths


EXPECTED_PYTHON_VERSION = "3.12.13"
BROKEN_SHEBANG_MARKERS = (
    ".venv311",
    ".venv310",
    ".venv39",
    "/usr/bin/python3",
    "/usr/local/bin/python",
    ".cache/codex-runtimes",
)


def read_shebang(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    if not first_line.startswith("#!"):
        raise RuntimeError(f"{path} missing shebang")
    return first_line


def ensure_clean_shebang(path: Path, *, expected_prefix: str | None = None, exact: str | None = None) -> str:
    shebang = read_shebang(path)
    if any(marker in shebang for marker in BROKEN_SHEBANG_MARKERS):
        raise RuntimeError(f"{path} still uses a stale interpreter path: {shebang}")
    if exact is not None and shebang != exact:
        raise RuntimeError(f"{path} should use {exact!r}, got {shebang!r}")
    if expected_prefix is not None and not shebang.startswith(expected_prefix):
        raise RuntimeError(f"{path} should start with {expected_prefix!r}, got {shebang!r}")
    return shebang


def ensure_command_works(command: list[str], cwd: Path) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise RuntimeError(f"command failed: {' '.join(command)} :: {detail}")
    return {
        "command": command,
        "stdout_tail": (result.stdout or "").strip()[-500:],
    }


def main() -> int:
    run_id = f"python_runtime_entrypoints_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    run_at = datetime.now().astimezone().isoformat()

    python_version_file = PROJECT_ROOT / ".python-version"
    if not python_version_file.exists():
        raise RuntimeError(f"missing {python_version_file}")
    pinned_version = python_version_file.read_text(encoding="utf-8").strip()
    if pinned_version != EXPECTED_PYTHON_VERSION:
        raise RuntimeError(f".python-version should be {EXPECTED_PYTHON_VERSION}, got {pinned_version}")

    venv_bin_dir = PROJECT_ROOT / ".venv" / "bin"
    venv_python = venv_bin_dir / "python"
    if not venv_python.exists():
        raise RuntimeError(f"missing virtualenv interpreter: {venv_python}")

    python_target = venv_python.resolve()
    pyvenv_cfg = PROJECT_ROOT / ".venv" / "pyvenv.cfg"
    if not pyvenv_cfg.exists():
        raise RuntimeError(f"missing virtualenv metadata: {pyvenv_cfg}")
    pyvenv_text = pyvenv_cfg.read_text(encoding="utf-8")
    if "version = 3.12.13" not in pyvenv_text:
        raise RuntimeError(f"pyvenv.cfg does not pin {EXPECTED_PYTHON_VERSION}")
    if any(marker in pyvenv_text for marker in (".venv311", ".venv310", ".venv39")):
        raise RuntimeError("pyvenv.cfg still references a stale virtualenv path")

    entrypoints = [
        venv_bin_dir / "pip",
        venv_bin_dir / "uvicorn",
        venv_bin_dir / "fastapi",
        venv_bin_dir / "piper",
        venv_bin_dir / "pip-audit",
    ]
    shebangs: dict[str, str] = {}
    for path in entrypoints:
        if not path.exists():
            raise RuntimeError(f"missing entrypoint: {path}")
        shebangs[path.name] = ensure_clean_shebang(path, expected_prefix=f"#!{venv_python}")

    piper_bin_dir = PROJECT_ROOT / "local_providers" / "piper" / "python" / "bin"
    piper_entrypoints = [
        piper_bin_dir / "piper",
        piper_bin_dir / "numpy-config",
        piper_bin_dir / "f2py",
        piper_bin_dir / "onnxruntime_test",
    ]
    piper_shebangs: dict[str, str] = {}
    for path in piper_entrypoints:
        if not path.exists():
            raise RuntimeError(f"missing local Piper helper: {path}")
        piper_shebangs[path.name] = ensure_clean_shebang(path, exact="#!/bin/sh")

    command_checks = [
        ensure_command_works([str(venv_python), "--version"], PROJECT_ROOT),
        ensure_command_works([str(venv_bin_dir / "uvicorn"), "--version"], PROJECT_ROOT),
        ensure_command_works([str(venv_bin_dir / "pip"), "--version"], PROJECT_ROOT),
        ensure_command_works([str(piper_bin_dir / "piper"), "--help"], PROJECT_ROOT),
        ensure_command_works([str(piper_bin_dir / "numpy-config"), "--help"], PROJECT_ROOT),
        ensure_command_works([str(piper_bin_dir / "f2py"), "-h"], PROJECT_ROOT),
    ]

    version_text = str(command_checks[0]["stdout_tail"]).strip()
    if EXPECTED_PYTHON_VERSION not in version_text:
        raise RuntimeError(f"virtualenv python version drifted: {version_text}")

    report_payload = {
        "run_id": run_id,
        "run_at": run_at,
        "expected_python_version": EXPECTED_PYTHON_VERSION,
        "pinned_python_version": pinned_version,
        "virtualenv_python": str(venv_python),
        "virtualenv_python_target": str(python_target),
        "pyvenv_cfg": str(pyvenv_cfg),
        "entrypoint_shebangs": shebangs,
        "local_piper_entrypoint_shebangs": piper_shebangs,
        "command_checks": command_checks,
        "report_path": str(ProjectPaths.reports_dir() / "python_runtime_entrypoints_validation_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "python_runtime_entrypoints_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
