"""phase C 接线测试（atomic_write_text / handoff / ai_label / release 钩子）。"""
from __future__ import annotations

import json


class TestAtomicWriteText:
    def test_write_and_read_back(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        assert target.read_text(encoding="utf-8") == "第一版"

    def test_overwrite(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        atomic_write_text(target, "第二版")
        assert target.read_text(encoding="utf-8") == "第二版"

    def test_utf8_and_parent_autocreate(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "nested" / "handoff.md"
        atomic_write_text(target, "line1\nline2 中文\n")
        assert target.read_text(encoding="utf-8") == "line1\nline2 中文\n"

    def test_finalize_failure_leaves_original_and_cleans_tmp(self, tmp_path, monkeypatch):
        from aicomic.utils import atomic_io

        target = tmp_path / "handoff.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(atomic_io.Path, "replace", lambda self, dest: (_ for _ in ()).throw(RuntimeError("disk")))
        try:
            atomic_io.atomic_write_text(target, "new")
        except RuntimeError:
            pass
        assert target.read_text(encoding="utf-8") == "original"
        assert [p.name for p in tmp_path.iterdir()] == ["handoff.md"]  # 无 .tmp 残留
