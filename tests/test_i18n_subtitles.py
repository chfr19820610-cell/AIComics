"""Multi-language subtitle & TTS routing tests.

Phase 1: LLM translation layer (zh→en/ja/ko SRT)
Phase 2: Multi-language TTS voice routing
"""
from __future__ import annotations

import pytest

from aicomic.video_synthesis.i18n import (
    LANGUAGES,
    VOICE_MAP,
    translate_subtitles,
    translate_srt_file,
    get_voice_for_language,
    build_multilang_subtitle_set,
)


class TestLanguageConfig:
    """Test language definitions and voice mapping."""

    def test_supported_languages(self):
        assert "en" in LANGUAGES
        assert "ja" in LANGUAGES
        assert "ko" in LANGUAGES
        assert "zh" in LANGUAGES

    def test_voice_map_has_all_languages(self):
        for lang in LANGUAGES:
            assert lang in VOICE_MAP, f"Missing voice for {lang}"

    def test_voice_map_has_male_and_female(self):
        for lang, voices in VOICE_MAP.items():
            assert "female" in voices, f"Missing female voice for {lang}"
            assert "male" in voices, f"Missing male voice for {lang}"


class TestTranslateSubtitles:
    """Test the translation layer."""

    def test_translate_returns_list(self):
        result = translate_subtitles(["你好世界", "测试字幕"], target_lang="en")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_translate_preserves_count(self):
        subs = ["第一句", "第二句", "第三句"]
        result = translate_subtitles(subs, target_lang="en")
        assert len(result) == len(subs)

    def test_translate_empty_list(self):
        result = translate_subtitles([], target_lang="en")
        assert result == []

    def test_translate_passthrough_for_zh(self):
        subs = ["你好世界"]
        result = translate_subtitles(subs, target_lang="zh")
        assert result == subs  # No translation needed

    def test_translate_uses_dictionary_for_common_phrases(self):
        # Built-in dictionary for common AI漫剧 phrases
        result = translate_subtitles(["前情回顾"], target_lang="en")
        assert isinstance(result[0], str)
        assert len(result[0]) > 0

    def test_translate_unknown_lang_raises(self):
        with pytest.raises(ValueError):
            translate_subtitles(["你好"], target_lang="fr")


class TestSrtTranslation:
    """Test SRT file translation."""

    def test_translate_srt_file(self, tmp_path):
        srt_content = "1\n00:00:00,000 --> 00:00:04,000\n你好世界\n\n2\n00:00:04,000 --> 00:00:08,000\n测试字幕\n"
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        out_path = tmp_path / "test_en.srt"
        translate_srt_file(srt_path, out_path, target_lang="en")

        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:04,000" in content  # timestamps preserved
        assert "00:00:04,000 --> 00:00:08,000" in content

    def test_translate_srt_preserves_timestamps(self, tmp_path):
        srt_content = "1\n00:00:01,500 --> 00:00:03,200\n你好\n"
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        out_path = tmp_path / "out.srt"
        translate_srt_file(srt_path, out_path, target_lang="ja")

        content = out_path.read_text(encoding="utf-8")
        assert "00:00:01,500 --> 00:00:03,200" in content


class TestVoiceRouting:
    """Test multi-language TTS voice routing."""

    def test_get_voice_for_language_default(self):
        voice = get_voice_for_language("en")
        assert voice.startswith("en-US-")

    def test_get_voice_for_language_with_gender(self):
        female = get_voice_for_language("en", gender="female")
        male = get_voice_for_language("en", gender="male")
        assert female != male

    def test_get_voice_for_japanese(self):
        voice = get_voice_for_language("ja")
        assert voice.startswith("ja-JP-")

    def test_get_voice_for_korean(self):
        voice = get_voice_for_language("ko")
        assert voice.startswith("ko-KR-")

    def test_get_voice_unknown_lang_raises(self):
        with pytest.raises(ValueError):
            get_voice_for_language("fr")


class TestMultilangSubtitleSet:
    """Test building a complete multi-language subtitle set from a single zh SRT."""

    def test_build_set_returns_all_languages(self, tmp_path):
        srt_content = "1\n00:00:00,000 --> 00:00:04,000\n你好世界\n"
        srt_path = tmp_path / "zh.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        result = build_multilang_subtitle_set(srt_path, tmp_path, languages=["en", "ja", "ko"])
        assert "en" in result
        assert "ja" in result
        assert "ko" in result
        for lang, path in result.items():
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "00:00:00,000 --> 00:00:04,000" in content

    def test_build_set_includes_original(self, tmp_path):
        srt_content = "1\n00:00:00,000 --> 00:00:02,000\n测试\n"
        srt_path = tmp_path / "zh.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        result = build_multilang_subtitle_set(srt_path, tmp_path, languages=["en"])
        # Original zh file should also be in result
        assert "zh" in result
