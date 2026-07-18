from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WebSettings:
    project_root: Path
    reports_dir: Path
    jobs_dir: Path
    state_dir: Path
    allowed_commands: tuple[str, ...]
    runnable_commands: tuple[str, ...]
    command_execution_enabled: bool
    host: str
    port: int
    require_confirm_live: bool
    auth_enabled: bool
    password_login_enabled: bool
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    access_token_minutes: int
    refresh_token_days: int
    access_token_cookie_name: str
    refresh_token_cookie_name: str
    default_role: str
    password_user_username: str
    password_user_display_name: str
    password_user_email: str
    password_user_role: str
    password_user_password: str
    cors_allow_origins: tuple[str, ...]


def _require_jwt_secret(auth_config: dict) -> str:
    value = str(auth_config.get("jwt_secret", "")).strip()
    if not value:
        raise ValueError(
            "JWT secret is not configured. Set auth.jwt_secret in config/web.yaml "
            "or AICOMIC_JWT_SECRET environment variable."
        )
    return value


def resolve_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_scalar(raw_value: str) -> Any:
    value = os.path.expandvars(raw_value.strip().strip("'").strip('"'))
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit() and (value == "0" or not value.startswith("0")):
        return int(value)
    return value


def load_web_config_map(config_path: Path) -> dict[str, dict[str, Any]]:
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


def load_web_settings() -> WebSettings:
    project_root = resolve_project_root()
    state_dir = Path(os.environ.get("AICOMIC_STATE_DIR", "").strip() or project_root / "state")
    web_config_path = Path(
        os.environ.get("AICOMIC_WEB_CONFIG_PATH", "").strip() or project_root / "config" / "web.yaml"
    )
    config_map = load_web_config_map(web_config_path)
    server_config = config_map.get("server", {})
    safety_config = config_map.get("safety", {})
    auth_config = config_map.get("auth", {})
    cors_raw = str(server_config.get("cors_allow_origins", "*"))
    cors_allow_origins = tuple(item.strip() for item in cors_raw.split(",") if item.strip()) or ("*",)
    return WebSettings(
        project_root=project_root,
        reports_dir=project_root / "reports",
        jobs_dir=project_root / "jobs",
        state_dir=state_dir,
        allowed_commands=(
            "status",
            "build-jobs",
            "sync-states",
            "dispatch-jobs",
            "scan-assets",
            "render-preview",
            "render-release",
            "build-provider-requests",
            "execute-provider-requests",
            "apply-provider-results",
            "manual-import-batch",
            "retry-batch",
            "build-batch",
            "run-batch",
            "dashboard-export",
            "review-metrics",
            "build-navigator",
            "scan-season-assets",
            "render-season",
            "build-season-summary",
        ),
        runnable_commands=(
            "status",
            "dashboard-export",
            "review-metrics",
            "build-navigator",
        ),
        command_execution_enabled=bool(safety_config.get("command_execution_enabled", False)),
        host=str(server_config.get("host", "127.0.0.1")),
        port=int(server_config.get("port", 7860)),
        require_confirm_live=bool(safety_config.get("require_confirm_live", True)),
        auth_enabled=bool(auth_config.get("auth_enabled", False)),
        password_login_enabled=bool(auth_config.get("password_login_enabled", False)),
        jwt_secret=_require_jwt_secret(auth_config),
        jwt_issuer=str(auth_config.get("jwt_issuer", "aicomic-web")),
        jwt_audience=str(auth_config.get("jwt_audience", "aicomic-users")),
        access_token_minutes=int(auth_config.get("access_token_minutes", 60)),
        refresh_token_days=int(auth_config.get("refresh_token_days", 7)),
        access_token_cookie_name=str(auth_config.get("access_token_cookie_name", "aicomic_access_token")),
        refresh_token_cookie_name=str(auth_config.get("refresh_token_cookie_name", "aicomic_refresh_token")),
        default_role=str(auth_config.get("default_role", "creator")),
        password_user_username=str(auth_config.get("password_user_username", "creator")),
        password_user_display_name=str(auth_config.get("password_user_display_name", "个人创作者")),
        password_user_email=str(auth_config.get("password_user_email", "creator@aicomic.local")),
        password_user_role=str(auth_config.get("password_user_role", "creator")),
        password_user_password=str(auth_config.get("password_user_password", "")),
        cors_allow_origins=cors_allow_origins,
    )
