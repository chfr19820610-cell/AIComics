from __future__ import annotations

import os
from pathlib import Path


WEB_CONFIG_ENV_KEYS = {
    "AICOMIC_JWT_SECRET",
    "AICOMIC_NORMAL_USER_PASSWORD",
}


def parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, raw_value = line.split("=", 1)
    name = key.strip()
    if not name:
        return None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return name, value


def load_dotenv_file(
    path: Path,
    *,
    override: bool = False,
    allowed_keys: set[str] | None = None,
) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if allowed_keys is not None and key not in allowed_keys:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def candidate_runtime_env_files(project_root: Path, web_config_path: Path | None = None) -> list[Path]:
    config_name = web_config_path.name if web_config_path is not None else ""
    if config_name in {"web.production.example.yaml", "web.production.docker.yaml", "web.yaml"}:
        names = [".env.production.local", ".env.production.example", ".env.docker.local"]
    elif config_name == "web.docker.yaml":
        names = [".env.docker.local", ".env.production.local", ".env.production.example"]
    else:
        names = [".env.production.local", ".env.docker.local", ".env.production.example"]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for name in names:
        path = (project_root / name).resolve()
        if path not in seen:
            candidates.append(path)
            seen.add(path)
    return candidates


def prime_runtime_env_for_web_config(web_config_path: Path, *, override: bool = False) -> list[str]:
    resolved_config_path = web_config_path.resolve()
    project_root = resolved_config_path.parent.parent
    loaded_files: list[str] = []
    for env_path in candidate_runtime_env_files(project_root, resolved_config_path):
        loaded = load_dotenv_file(env_path, override=override, allowed_keys=WEB_CONFIG_ENV_KEYS)
        if loaded:
            loaded_files.append(str(env_path))
    return loaded_files
