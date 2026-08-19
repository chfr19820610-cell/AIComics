"""Template marketplace — install/uninstall/share templates.

Phase 1: Install from dict (inline) or URL (base64-encoded YAML).
Validation: required fields check before writing.
Share: base64-encode to a portable string + install command.
"""
from __future__ import annotations

import base64
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def _templates_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "templates"


def _required_fields() -> set[str]:
    return {"template_id", "genre", "acts", "locations", "characters"}


def validate_template_yaml(t: Any) -> bool:
    """Check required fields. Returns True if valid."""
    if not isinstance(t, dict):
        return False
    if not _required_fields().issubset(t.keys()):
        return False
    if not t.get("acts"):
        return False
    if not t.get("locations"):
        return False
    if not t.get("characters"):
        return False
    return True


def install_template_from_dict(t: dict[str, Any], templates_dir: Path | None = None) -> dict[str, Any]:
    """Install a template dict as YAML. Returns {success, overwritten, path, error?}."""
    d = templates_dir or _templates_dir()
    if not validate_template_yaml(t):
        return {"success": False, "error": "validation failed: missing required fields or empty acts/locations/characters"}
    tid = t["template_id"]
    path = d / f"{tid}.yaml"
    overwritten = path.exists()
    d.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(t, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"success": True, "overwritten": overwritten, "path": str(path)}


def install_template_from_url(url: str, templates_dir: Path | None = None) -> dict[str, Any]:
    """Fetch base64-encoded YAML from URL, decode, validate, install."""
    d = templates_dir or _templates_dir()
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except Exception as e:
        return {"success": False, "error": f"fetch failed: {e}"}
    # Decode base64
    try:
        yaml_text = base64.b64decode(raw).decode("utf-8")
    except Exception:
        return {"success": False, "error": "invalid base64 content"}
    # Parse YAML
    try:
        t = yaml.safe_load(yaml_text)
    except Exception as e:
        return {"success": False, "error": f"YAML parse failed: {e}"}
    return install_template_from_dict(t, templates_dir=d)


def uninstall_template(name: str, templates_dir: Path | None = None) -> dict[str, Any]:
    """Remove a template by name."""
    d = templates_dir or _templates_dir()
    path = d / f"{name}.yaml"
    if not path.exists():
        return {"success": False, "error": f"template not found: {name}"}
    path.unlink()
    return {"success": True, "removed": name}


def share_template_url(t: dict[str, Any]) -> dict[str, Any]:
    """Encode a template to a shareable base64 string + install command."""
    yaml_text = yaml.dump(t, allow_unicode=True, default_flow_style=False, sort_keys=False)
    encoded = base64.b64encode(yaml_text.encode("utf-8")).decode("ascii")
    tid = t.get("template_id", "unknown")
    return {
        "format": "gist",
        "yaml_base64": encoded,
        "install_command": f"aicomic install-template --url <gist_url> --name {tid}",
    }


def list_installed_templates(templates_dir: Path | None = None) -> list[str]:
    """List all installed template names."""
    d = templates_dir or _templates_dir()
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.yaml"))
