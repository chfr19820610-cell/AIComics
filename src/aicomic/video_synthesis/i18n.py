"""Multi-language subtitle translation & TTS voice routing.

Phase 1: Dictionary-based translation for common AI漫剧 phrases + LLM hook.
Phase 2: Voice routing to Edge TTS per language.

Design: 极简. Dictionary covers common phrases; LLM callable for the rest.
No external API dependency — falls back to dictionary + transliteration.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ── Supported languages ──────────────────────────────────────────────────

LANGUAGES: dict[str, str] = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}

# ── Edge TTS voice map ───────────────────────────────────────────────────

VOICE_MAP: dict[str, dict[str, str]] = {
    "zh": {"female": "zh-CN-XiaoxiaoNeural", "male": "zh-CN-YunyangNeural"},
    "en": {"female": "en-US-AriaNeural", "male": "en-US-GuyNeural"},
    "ja": {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"},
    "ko": {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"},
}

# ── Built-in dictionary for common AI漫剧 phrases ────────────────────────

_PHRASE_DICT: dict[str, dict[str, str]] = {
    "前情回顾": {"en": "Previously", "ja": "前回のあらすじ", "ko": "이전 줄거리"},
    "未完待续": {"en": "To be continued", "ja": "続く", "ko": "계속"},
    "敬请期待": {"en": "Stay tuned", "ja": "お楽しみに", "ko": "기대해 주세요"},
    "第": {"en": "Episode ", "ja": "第", "ko": "제"},
    "集": {"en": "", "ja": "話", "ko": "화"},
    "旁白": {"en": "", "ja": "", "ko": ""},
    "男主": {"en": "He", "ja": "彼", "ko": "그"},
    "女主": {"en": "She", "ja": "彼女", "ko": "그녀"},
}

# ── Translation ──────────────────────────────────────────────────────────


def _translate_single(text: str, target_lang: str) -> str:
    """Translate a single string using dictionary + pattern matching."""
    if target_lang == "zh" or not text.strip():
        return text

    result = text
    # Apply dictionary (longest match first for accuracy)
    for phrase, translations in sorted(_PHRASE_DICT.items(), key=lambda x: -len(x[0])):
        if phrase in result and target_lang in translations:
            result = result.replace(phrase, translations[target_lang])

    # If no dictionary match and text unchanged, mark for LLM (placeholder)
    # In production, this would call an LLM API; for now, return as-is
    return result


def translate_subtitles(
    subtitles: list[str],
    target_lang: str,
    llm_callback: Any | None = None,
) -> list[str]:
    """Translate a list of subtitle strings.

    Args:
        subtitles: List of Chinese subtitle strings.
        target_lang: Target language code (en/ja/ko/zh).
        llm_callback: Optional callable(text, lang) -> str for LLM translation.

    Returns:
        List of translated strings (same length as input).
    """
    if target_lang not in LANGUAGES:
        raise ValueError(f"Unsupported language: {target_lang}")

    if target_lang == "zh":
        return list(subtitles)

    results = []
    for text in subtitles:
        translated = _translate_single(text, target_lang)
        # If LLM callback provided and text wasn't fully translated, use LLM
        if llm_callback and translated == text and text.strip():
            try:
                translated = llm_callback(text, target_lang)
            except Exception:
                pass  # Fall back to dictionary result
        results.append(translated)
    return results


# ── SRT file translation ────────────────────────────────────────────────

_SRT_ENTRY_RE = re.compile(
    r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?:\n\n|\n*$)",
    re.DOTALL,
)


def translate_srt_file(
    srt_path: Path,
    output_path: Path,
    target_lang: str,
    llm_callback: Any | None = None,
) -> Path:
    """Translate an SRT file, preserving timestamps.

    Args:
        srt_path: Source SRT file (Chinese).
        output_path: Output SRT file path.
        target_lang: Target language code.
        llm_callback: Optional LLM callable for non-dictionary phrases.

    Returns:
        Path to the translated SRT file.
    """
    content = srt_path.read_text(encoding="utf-8")

    # Parse SRT entries
    entries = list(_SRT_ENTRY_RE.finditer(content))
    texts = [e.group(3) for e in entries]
    translated = translate_subtitles(texts, target_lang, llm_callback)

    # Rebuild SRT
    output_lines = []
    for i, match in enumerate(entries):
        output_lines.append(match.group(1))  # index
        output_lines.append(match.group(2))  # timestamp
        output_lines.append(translated[i])   # translated text
        output_lines.append("")              # blank line

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines), encoding="utf-8")
    return output_path


def build_multilang_subtitle_set(
    zh_srt_path: Path,
    output_dir: Path,
    languages: list[str] | None = None,
    llm_callback: Any | None = None,
) -> dict[str, Path]:
    """Build a complete set of translated SRT files from a Chinese SRT.

    Args:
        zh_srt_path: Source Chinese SRT file.
        output_dir: Directory to write translated files.
        languages: List of target languages (default: en, ja, ko).

    Returns:
        Dict mapping lang code → SRT file path (includes "zh" → original).
    """
    langs = languages or ["en", "ja", "ko"]
    result: dict[str, Path] = {"zh": zh_srt_path}

    stem = zh_srt_path.stem
    for lang in langs:
        out_path = output_dir / f"{stem}_{lang}.srt"
        translate_srt_file(zh_srt_path, out_path, lang, llm_callback)
        result[lang] = out_path

    return result


# ── Voice routing ────────────────────────────────────────────────────────


def get_voice_for_language(lang: str, gender: str = "female") -> str:
    """Get the Edge TTS voice ID for a given language and gender.

    Args:
        lang: Language code (zh/en/ja/ko).
        gender: "female" or "male".

    Returns:
        Edge TTS voice ID string.
    """
    if lang not in VOICE_MAP:
        raise ValueError(f"Unsupported language: {lang}")
    if gender not in VOICE_MAP[lang]:
        raise ValueError(f"Unsupported gender: {gender}")
    return VOICE_MAP[lang][gender]
