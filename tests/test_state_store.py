from __future__ import annotations

import json
from pathlib import Path

from aicomic.core.models import EpisodeState
from aicomic.core.state_store import build_state_snapshot, load_state_snapshot, write_state_snapshot


class TestBuildStateSnapshot:
    def test_empty_list(self) -> None:
        snapshot = build_state_snapshot([])
        assert snapshot == {"episode_states": [], "episode_count": 0}

    def test_single_state(self) -> None:
        states = [EpisodeState(episode_code="E01", status="running", completed_jobs=3, total_jobs=10)]
        snapshot = build_state_snapshot(states)
        assert snapshot["episode_count"] == 1
        assert len(snapshot["episode_states"]) == 1
        assert snapshot["episode_states"][0]["episode_code"] == "E01"

    def test_multiple_states(self) -> None:
        states = [
            EpisodeState(episode_code="E01", status="running", completed_jobs=3, total_jobs=10),
            EpisodeState(episode_code="E02", status="completed", completed_jobs=10, total_jobs=10),
        ]
        snapshot = build_state_snapshot(states)
        assert snapshot["episode_count"] == 2

    def test_state_contains_all_fields(self) -> None:
        states = [EpisodeState(episode_code="E01", status="running", completed_jobs=5, total_jobs=8)]
        entry = build_state_snapshot(states)["episode_states"][0]
        assert entry["episode_code"] == "E01"
        assert entry["status"] == "running"
        assert entry["completed_jobs"] == 5
        assert entry["total_jobs"] == 8


class TestWriteStateSnapshot:
    def test_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        states = [EpisodeState(episode_code="E01", status="running", completed_jobs=0, total_jobs=5)]
        write_state_snapshot(path, states)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["episode_count"] == 1

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "state.json"
        write_state_snapshot(path, [])
        assert path.exists()


class TestLoadStateSnapshot:
    def test_loads_saved_data(self, tmp_path: Path) -> None:
        path = tmp_path / "snap.json"
        write_state_snapshot(path, [EpisodeState(episode_code="E01", status="running", completed_jobs=1, total_jobs=2)])
        loaded = load_state_snapshot(path)
        assert loaded["episode_count"] == 1
        assert loaded["episode_states"][0]["episode_code"] == "E01"
