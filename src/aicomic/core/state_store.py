from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from aicomic.core.models import EpisodeState


def build_state_snapshot(states: list[EpisodeState]) -> dict[str, object]:
    return {
        "episode_states": [asdict(state) for state in states],
        "episode_count": len(states),
    }


from aicomic.utils.atomic_io import atomic_write_json


def write_state_snapshot(path: Path, states: list[EpisodeState]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_state_snapshot(states)
    atomic_write_json(path, snapshot)


def load_state_snapshot(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))

