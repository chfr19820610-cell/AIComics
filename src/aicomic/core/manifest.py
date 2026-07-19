from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_json


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)

