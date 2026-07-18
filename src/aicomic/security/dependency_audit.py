from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

from aicomic.utils.atomic_io import atomic_write_json
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Any


DIRECT_OPTIONAL_GROUPS = ("web", "validation", "local-providers")
LOCK_FILE_NAME = "requirements-lock.txt"
IGNORED_INSTALLED_PACKAGES = {"aicomic-system", "pip", "setuptools", "wheel"}


def text_tail(value: str | bytes | None, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value.strip()[-limit:]


def pip_audit_timeout_seconds(default: int = 90) -> int:
    raw_value = os.environ.get("AICOMIC_PIP_AUDIT_TIMEOUT_SECONDS", "").strip()
    if not raw_value:
        return default
    try:
        return max(15, int(raw_value))
    except ValueError:
        return default


def normalize_package_name(raw_name: str) -> str:
    return raw_name.strip().lower().replace("_", "-")


def extract_requirement_name(requirement: str) -> str:
    head = re.split(r"[\[<>=!~; ]", requirement.strip(), maxsplit=1)[0]
    return normalize_package_name(head)


def load_project_direct_dependencies(pyproject_path: Path) -> dict[str, list[str]]:
    if not pyproject_path.exists():
        return {}
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    groups = project.get("optional-dependencies", {})
    dependencies: dict[str, list[str]] = {}
    for group_name in DIRECT_OPTIONAL_GROUPS:
        group_dependencies = groups.get(group_name, [])
        if isinstance(group_dependencies, list):
            dependencies[group_name] = [str(item) for item in group_dependencies]
    return dependencies


def parse_constraint_pins(constraints_path: Path) -> dict[str, str]:
    if not constraints_path.exists():
        return {}
    pins: dict[str, str] = {}
    for raw_line in constraints_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            continue
        package_name, version = line.split("==", 1)
        pins[normalize_package_name(package_name)] = version.strip()
    return pins


def docker_uses_constraints(dockerfile_path: Path, lock_file_name: str = LOCK_FILE_NAME) -> bool:
    if not dockerfile_path.exists():
        return False
    content = dockerfile_path.read_text(encoding="utf-8")
    return f"--constraint {lock_file_name}" in content or f"-c {lock_file_name}" in content


def collect_installed_distribution_versions() -> dict[str, str]:
    distributions: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name", "")
        if not name:
            continue
        normalized_name = normalize_package_name(name)
        if normalized_name in IGNORED_INSTALLED_PACKAGES:
            continue
        distributions[normalized_name] = distribution.version
    return dict(sorted(distributions.items()))


def run_optional_pip_audit(project_root: Path, timeout_seconds: int | None = None) -> dict[str, Any]:
    active_timeout_seconds = timeout_seconds if timeout_seconds is not None else pip_audit_timeout_seconds()
    if shutil.which("pip-audit") is None:
        module_check = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--version"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if module_check.returncode != 0:
            return {
                "audit_tool_status": "not_installed",
                "cve_audit_status": "not_run",
                "known_vulnerability_count": 0,
                "stdout_tail": "",
                "stderr_tail": text_tail(module_check.stderr or module_check.stdout, 2000),
            }
        command = [sys.executable, "-m", "pip_audit"]
    else:
        command = ["pip-audit"]

    try:
        result = subprocess.run(
            [
                *command,
                "--requirement",
                LOCK_FILE_NAME,
                "--format",
                "json",
                "--progress-spinner",
                "off",
                "--no-deps",
                "--disable-pip",
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=active_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "audit_tool_status": "timeout",
            "cve_audit_status": "not_completed",
            "known_vulnerability_count": 0,
            "timeout_seconds": active_timeout_seconds,
            "stdout_tail": text_tail(error.stdout, 2000),
            "stderr_tail": text_tail(error.stderr, 2000),
        }

    known_vulnerability_count = 0
    if result.stdout.strip():
        try:
            audit_payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            audit_payload = {}
        dependencies = audit_payload.get("dependencies", []) if isinstance(audit_payload, dict) else []
        if isinstance(dependencies, list):
            known_vulnerability_count = sum(
                len(item.get("vulns", []))
                for item in dependencies
                if isinstance(item, dict) and isinstance(item.get("vulns", []), list)
            )

    return {
        "audit_tool_status": "completed" if result.returncode in {0, 1} else "failed",
        "cve_audit_status": "completed" if result.returncode in {0, 1} else "not_completed",
        "known_vulnerability_count": known_vulnerability_count,
        "return_code": result.returncode,
        "timeout_seconds": active_timeout_seconds,
        "stdout_tail": text_tail(result.stdout, 4000),
        "stderr_tail": text_tail(result.stderr, 4000),
    }


def build_dependency_audit_report(project_root: Path) -> dict[str, Any]:
    pyproject_path = project_root / "pyproject.toml"
    constraints_path = project_root / LOCK_FILE_NAME
    dockerfile_path = project_root / "Dockerfile"
    direct_dependencies = load_project_direct_dependencies(pyproject_path)
    direct_names = sorted(
        {
            extract_requirement_name(requirement)
            for requirements in direct_dependencies.values()
            for requirement in requirements
        }
    )
    constraint_pins = parse_constraint_pins(constraints_path)
    missing_direct_pins = [name for name in direct_names if name not in constraint_pins]
    unconstrained_pins = [name for name in constraint_pins if name not in direct_names]
    docker_constraint_enabled = docker_uses_constraints(dockerfile_path)
    audit_result = run_optional_pip_audit(project_root)

    direct_lock_enforced = constraints_path.exists() and not missing_direct_pins and docker_constraint_enabled
    transitive_lock_enforced = constraints_path.exists() and not missing_direct_pins and docker_constraint_enabled
    risk_items: list[dict[str, Any]] = []
    if not constraints_path.exists():
        risk_items.append(
            {
                "id": "dependency-lock-file-missing",
                "severity": "high",
                "status": "open",
                "detail": f"{LOCK_FILE_NAME} is missing.",
            }
        )
    if missing_direct_pins:
        risk_items.append(
            {
                "id": "dependency-direct-pins-missing",
                "severity": "high",
                "status": "open",
                "detail": f"Missing direct dependency pins: {', '.join(missing_direct_pins)}",
            }
        )
    if not docker_constraint_enabled:
        risk_items.append(
            {
                "id": "docker-dependency-lock-not-enforced",
                "severity": "high",
                "status": "open",
                "detail": "Dockerfile install step does not enforce requirements-lock.txt.",
            }
        )
    if audit_result.get("cve_audit_status") != "completed":
        risk_items.append(
            {
                "id": "dependency-cve-audit-not-completed",
                "severity": "medium",
                "status": "open",
                "detail": "pip-audit is not installed or did not complete; CVE evidence is still pending.",
            }
        )
    elif int(audit_result.get("known_vulnerability_count", 0)) > 0:
        risk_items.append(
            {
                "id": "dependency-known-vulnerabilities",
                "severity": "high",
                "status": "open",
                "detail": f"pip-audit found {audit_result['known_vulnerability_count']} known vulnerabilities.",
            }
        )

    return {
        "pyproject_path": str(pyproject_path),
        "constraints_path": str(constraints_path),
        "dockerfile_path": str(dockerfile_path),
        "direct_dependency_groups": direct_dependencies,
        "direct_dependency_names": direct_names,
        "constraint_pins": constraint_pins,
        "missing_direct_pins": missing_direct_pins,
        "unconstrained_pins": sorted(unconstrained_pins),
        "docker_constraint_enabled": docker_constraint_enabled,
        "direct_lock_enforced": direct_lock_enforced,
        "lock_status": "direct_lock_enforced" if direct_lock_enforced else "lock_incomplete",
        "transitive_lock_enforced": transitive_lock_enforced,
        "transitive_lock_status": "fully_locked" if transitive_lock_enforced else "not_fully_locked",
        **audit_result,
        "risk_items": risk_items,
        "blocking_count": sum(1 for item in risk_items if item["severity"] == "high"),
        "warning_count": sum(1 for item in risk_items if item["severity"] != "high"),
    }


def write_dependency_audit_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)
