from __future__ import annotations

import json
from pathlib import Path

import pytest

from aicomic.utils.atomic_io import atomic_write_json


class TestAtomicWriteJson:
    def test_writes_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        data = {"name": "test", "count": 42}
        atomic_write_json(path, data)
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == data

    def test_writes_list(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        data = [1, 2, 3]
        atomic_write_json(path, data)
        assert json.loads(path.read_text(encoding="utf-8")) == data

    def test_writes_string(self, tmp_path: Path) -> None:
        path = tmp_path / "str.json"
        atomic_write_json(path, "hello")
        assert json.loads(path.read_text(encoding="utf-8")) == "hello"

    def test_custom_indent(self, tmp_path: Path) -> None:
        path = tmp_path / "pretty.json"
        atomic_write_json(path, {"a": 1}, indent=4)
        raw = path.read_text(encoding="utf-8")
        assert "    " in raw

    def test_ensure_ascii_false_keeps_unicode(self, tmp_path: Path) -> None:
        path = tmp_path / "unicode.json"
        atomic_write_json(path, {"greeting": "你好"}, ensure_ascii=False)
        raw = path.read_text(encoding="utf-8")
        assert "你好" in raw

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "overwrite.json"
        path.write_text('{"old": true}', encoding="utf-8")
        atomic_write_json(path, {"new": True})
        assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "nested" / "out.json"
        atomic_write_json(path, {"key": "val"})
        assert path.exists()

    def test_tmp_file_cleaned_on_write_error(self, tmp_path: Path) -> None:
        """If the write somehow fails, temp file should not remain."""
        path = tmp_path / "fail.json"
        # Force an error with unserializable data
        class Unserializable:
            pass

        with pytest.raises(TypeError):
            atomic_write_json(path, {"bad": Unserializable()})
        assert not path.exists()
        # Verify no .tmp. files linger
        leftovers = list(tmp_path.glob("*.tmp.*"))
        assert len(leftovers) == 0
