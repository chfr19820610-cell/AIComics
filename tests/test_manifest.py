from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aicomic.core.manifest import load_json, write_json


class TestManifest:
    def test_load_json_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            load_json(missing)

    def test_write_json_and_load_back(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        payload = {"key": "value", "number": 42}
        write_json(path, payload)
        assert path.exists()
        loaded = load_json(path)
        assert loaded == payload

    def test_write_json_creates_parent(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "deep.json"
        write_json(path, {"ok": True})
        assert path.exists()

    def test_load_json_empty_object(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.json"
        write_json(path, {})
        assert load_json(path) == {}

    def test_load_json_with_list(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        write_json(path, [1, 2, 3])
        assert load_json(path) == [1, 2, 3]
