"""角色四视图生成器测试（注入式，不依赖 ComfyUI）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.characters.view_generator import generate_views


class TestGenerateViews:
    def test_four_views_all_succeed(self, tmp_path):
        calls = []

        def fake(prompt, negative, out):
            calls.append((prompt, negative, out))
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        r = generate_views("林雪", "黑长直发，白色衬衫", tmp_path, generate_fn=fake)
        assert r["ok"] is True
        assert r["angle_count"] == 4
        assert sorted(r["views"]) == ["back", "front", "side", "three_quarter"]
        assert r["failed"] == []
        assert len(calls) == 4

    def test_prompts_are_angle_specific(self, tmp_path):
        seen = {}

        def fake(prompt, negative, out):
            seen[out.stem] = prompt
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        generate_views("林雪", "黑长直发", tmp_path, generate_fn=fake)
        assert "front view" in seen["front"].lower()
        assert "back view" in seen["back"].lower()
        assert "three-quarter" in seen["three_quarter"].lower()
        # 角色名与描述必须出现在每个 prompt 里
        for p in seen.values():
            assert "林雪" in p

    def test_partial_failure_is_reported_not_raised(self, tmp_path):
        def fake(prompt, negative, out):
            if "back view" in prompt.lower():
                return {"ok": False, "error": "gpu oom"}
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        r = generate_views("林雪", "黑长直发", tmp_path, generate_fn=fake)
        assert r["ok"] is False
        assert r["failed"] == ["back"]
        assert len([v for v in r["views"].values() if v["ok"]]) == 3

    def test_exception_in_one_view_does_not_abort_others(self, tmp_path):
        def fake(prompt, negative, out):
            if "side view" in prompt.lower():
                raise RuntimeError("boom")
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        r = generate_views("林雪", "黑长直发", tmp_path, generate_fn=fake)
        assert r["failed"] == ["side"]
        assert "RuntimeError" in r["views"]["side"]["error"]

    def test_angle_subset(self, tmp_path):
        def fake(prompt, negative, out):
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        r = generate_views("林雪", "黑长直发", tmp_path, generate_fn=fake, angles=["front", "back"])
        assert r["angle_count"] == 2
        assert sorted(r["views"]) == ["back", "front"]

    def test_creates_output_dir(self, tmp_path):
        def fake(prompt, negative, out):
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        target = tmp_path / "deep" / "views"
        r = generate_views("林雪", "黑长直发", target, generate_fn=fake)
        assert r["ok"] is True
        assert target.is_dir()

    def test_negative_prompt_is_angle_specific(self, tmp_path):
        seen = {}

        def fake(prompt, negative, out):
            seen[out.stem] = negative
            out.write_bytes(b"png")
            return {"ok": True, "path": str(out)}

        generate_views("林雪", "黑长直发", tmp_path, generate_fn=fake)
        # 正面视图的负面词应排除"回头/背对"，背面视图应排除"正面"
        assert seen["front"] != seen["back"]
