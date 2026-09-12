"""Genre template loader — load YAML genre templates into pipeline config.

Templates live in config/templates/*.yaml and provide per-genre prompt
overrides, art-style hints, and character design defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _template_dir() -> Path:
    """Return the path to the genre templates directory."""
    # src/aicomic/core/template_loader.py → project root is 3 levels up
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / "templates"


def list_genre_templates() -> list[str]:
    """List all available genre template names (without .yaml extension)."""
    d = _template_dir()
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.yaml"))


def load_genre_template(genre: str) -> dict[str, Any]:
    """Load a single genre template by name.

    Args:
        genre: Template name (e.g. "cultivation", "romance").

    Returns:
        Parsed YAML dict with keys like ``name``, ``style``,
        ``prompts``, ``character_style``, ``art_style``.
    """
    path = _template_dir() / f"{genre}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Genre template not found: {genre} ({path})")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid template format in {path}: expected mapping")
    return data


def apply_template_to_manifest(
    manifest: dict[str, Any], genre: str
) -> dict[str, Any]:
    """Merge genre template overrides into a pipeline manifest.

    Non-destructive: only fills in missing keys; existing manifest
    values take precedence over template defaults.
    """
    template = load_genre_template(genre)
    merged = dict(template)
    merged.update(manifest)
    return merged
