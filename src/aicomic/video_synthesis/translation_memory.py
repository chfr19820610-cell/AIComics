"""Translation memory — 翻译记忆库，术语一致性."""
from __future__ import annotations

import json
import re
from pathlib import Path


class TranslationMemory:
    """Persistent translation memory for consistent terminology across episodes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, dict[str, str]] = {}  # {term: {lang: translation}}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def add_term(self, term: str, translation: str, lang: str) -> None:
        if term not in self._data:
            self._data[term] = {}
        self._data[term][lang] = translation
        self._save()

    def lookup(self, term: str, lang: str) -> str | None:
        return self._data.get(term, {}).get(lang)

    def apply_to_entries(self, entries: list[dict], lang: str) -> list[dict]:
        """Apply known translations to subtitle entries (in-place replacement)."""
        result = []
        for entry in entries:
            text = entry["text"]
            for term, translations in self._data.items():
                if lang in translations and term in text:
                    text = text.replace(term, translations[lang])
            new_entry = dict(entry)
            new_entry["text"] = text
            result.append(new_entry)
        return result

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
