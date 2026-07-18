from __future__ import annotations

from typing import Any

from aicomic.core.config import ProjectPaths
from aicomic.core.edition import EDITION_PRESETS, load_edition_capability


def load_edition_summary() -> dict[str, Any]:
    edition = load_edition_capability()
    return {
        "edition_name": edition.edition_name,
        "display_name": edition.display_name,
        "capabilities": edition.to_dict(),
        "source": str(ProjectPaths.config_dir() / "edition.yaml"),
        "preset_options": sorted(EDITION_PRESETS.keys()),
    }
