"""Tests for narrate_rewrite + character_auto_register + YouTube integration fix."""
from __future__ import annotations

import pytest

from aicomic.core.novel_pipeline import (
    narrate_rewrite,
    character_auto_register,
)


class TestNarrateRewrite:
    def test_compresses_long_text(self):
        text = "他走进了房间。" * 100
        result = narrate_rewrite(text, max_chars=100)
        assert len(result) <= 102  # max_chars + ellipsis
        assert "…" in result or len(result) <= 100

    def test_removes_dialogue(self):
        text = '他说"你好吗？"然后离开了房间。'
        result = narrate_rewrite(text)
        assert "你好吗" not in result

    def test_empty_text_returns_empty(self):
        assert narrate_rewrite("") == ""
        assert narrate_rewrite("   ") == ""

    def test_llm_callback_used(self):
        text = "原始文本"
        result = narrate_rewrite(text, llm_callback=lambda t: f"[改写]{t}")
        assert "[改写]" in result

    def test_llm_callback_fallback_on_error(self):
        text = "原始文本"
        def bad_callback(t):
            raise Exception("LLM error")
        result = narrate_rewrite(text, llm_callback=bad_callback)
        assert "原始文本" in result


class TestCharacterAutoRegister:
    def test_extracts_names_from_pattern(self):
        text = "林晚说了一句话。陈墨道：好的。苏晴笑了笑。"
        chars = character_auto_register(text, template_name="workplace")
        assert len(chars) >= 1
        names = [c["name"] for c in chars]
        assert "林晚" in names or "陈墨" in names or "苏晴" in names

    def test_filters_common_words(self):
        text = "他们说了很多。我们走。你们看。"
        chars = character_auto_register(text, template_name="workplace")
        names = [c["name"] for c in chars]
        assert "他们" not in names
        assert "我们" not in names

    def test_max_characters_limit(self):
        text = "甲说。乙道。丙笑。丁哭。戊看。己想。庚走。辛坐。壬说。癸道。"
        chars = character_auto_register(text, max_characters=3)
        assert len(chars) <= 3

    def test_maps_to_template_roles(self):
        text = "林晚说了一句话。"
        chars = character_auto_register(text, template_name="horror")
        if chars:
            assert "role" in chars[0]
            assert "visual_rule" in chars[0]

    def test_empty_text_returns_empty(self):
        assert character_auto_register("") == []

    def test_unknown_template_still_works(self):
        text = "林晚说。"
        chars = character_auto_register(text, template_name="nonexistent")
        if chars:
            assert chars[0]["role"] == "配角"


class TestYouTubeIntegrationFix:
    def test_youtube_uploader_uses_api_not_stub(self):
        """YouTubeUploader should import youtube_publisher, not _selenium_upload."""
        from aicomic.publish.international import YouTubeUploader
        import inspect
        source = inspect.getsource(YouTubeUploader.upload)
        assert "youtube_publisher" in source
        assert "_selenium_upload" not in source
