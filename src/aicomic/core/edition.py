from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aicomic.core.config import ProjectPaths


@dataclass(frozen=True)
class EditionCapability:
    edition_name: str
    display_name: str
    single_user_mode: bool
    multi_user_enabled: bool
    auth_enabled: bool
    oidc_enabled: bool
    rbac_enabled: bool
    audit_enabled: bool
    batch_enabled: bool
    distributed_queue_enabled: bool
    enterprise_storage_enabled: bool
    cost_control_enabled: bool
    default_database: str
    default_storage: str
    deployment_mode: str
    default_entry: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capability_count"] = sum(
            1
            for key, value in payload.items()
            if key.endswith("_enabled") and bool(value)
        )
        return payload


EDITION_PRESETS: dict[str, dict[str, Any]] = {
    "creator": {
        "display_name": "Creator 个人创作者版",
        "single_user_mode": True,
        "multi_user_enabled": False,
        "auth_enabled": True,
        "oidc_enabled": False,
        "rbac_enabled": False,
        "audit_enabled": False,
        "batch_enabled": True,
        "distributed_queue_enabled": False,
        "enterprise_storage_enabled": False,
        "cost_control_enabled": False,
        "default_database": "sqlite",
        "default_storage": "local_filesystem",
        "deployment_mode": "windows_single_machine",
        "default_entry": "frontend_spa",
    },
}


def parse_scalar(raw_value: str) -> Any:
    value = raw_value.strip().strip("'").strip('"')
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def load_simple_yaml_map(config_path: Path) -> dict[str, dict[str, Any]]:
    if not config_path.exists():
        return {}

    config_map: dict[str, dict[str, Any]] = {}
    current_section = ""
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            config_map.setdefault(current_section, {})
            continue
        if ":" not in line or not current_section:
            continue
        key, raw_value = line.split(":", 1)
        config_map[current_section][key.strip()] = parse_scalar(raw_value)
    return config_map


def resolve_edition_config_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path

    env_path = os.environ.get("AICOMIC_EDITION_CONFIG_PATH", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser()
        if not candidate.is_absolute():
            candidate = ProjectPaths.project_root() / candidate
        return candidate
    return ProjectPaths.config_dir() / "edition.yaml"


def load_edition_capability(config_path: Path | None = None) -> EditionCapability:
    target_path = resolve_edition_config_path(config_path)
    config_map = load_simple_yaml_map(target_path)
    edition_config = config_map.get("edition", {})
    edition_name = str(edition_config.get("name", "creator")).strip().lower() or "creator"
    preset = EDITION_PRESETS.get(edition_name, EDITION_PRESETS["creator"])

    merged = {
        **preset,
        **edition_config,
    }
    return EditionCapability(
        edition_name=edition_name,
        display_name=str(merged.get("display_name", preset["display_name"])),
        single_user_mode=bool(merged.get("single_user_mode", preset["single_user_mode"])),
        multi_user_enabled=bool(merged.get("multi_user_enabled", preset["multi_user_enabled"])),
        auth_enabled=bool(merged.get("auth_enabled", preset["auth_enabled"])),
        oidc_enabled=bool(merged.get("oidc_enabled", preset["oidc_enabled"])),
        rbac_enabled=bool(merged.get("rbac_enabled", preset["rbac_enabled"])),
        audit_enabled=bool(merged.get("audit_enabled", preset["audit_enabled"])),
        batch_enabled=bool(merged.get("batch_enabled", preset["batch_enabled"])),
        distributed_queue_enabled=bool(
            merged.get("distributed_queue_enabled", preset["distributed_queue_enabled"])
        ),
        enterprise_storage_enabled=bool(
            merged.get("enterprise_storage_enabled", preset["enterprise_storage_enabled"])
        ),
        cost_control_enabled=bool(merged.get("cost_control_enabled", preset["cost_control_enabled"])),
        default_database=str(merged.get("default_database", preset["default_database"])),
        default_storage=str(merged.get("default_storage", preset["default_storage"])),
        deployment_mode=str(merged.get("deployment_mode", preset["deployment_mode"])),
        default_entry=str(merged.get("default_entry", preset["default_entry"])),
    )
