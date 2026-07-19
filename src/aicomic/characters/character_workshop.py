"""Character Workshop — character variant management, merge/deduplication,
and auto-extraction from narrative text."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from aicomic.characters.database import (
    connect_character_database, delete_character,
    get_character_by_id, insert_character,
)
from aicomic.characters.models import Character, CharacterCreateRequest, now_utc_iso

# ── Workshop schema extension ─────────────────────────────────────────────


def ensure_workshop_schema(connection: sqlite3.Connection) -> None:
    """Create workshop-related tables."""
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS character_variants (id TEXT PRIMARY KEY, character_id TEXT NOT NULL, variant_type TEXT NOT NULL DEFAULT 'outfit', variant_name TEXT NOT NULL DEFAULT '', prompt_delta TEXT DEFAULT '', image_path TEXT DEFAULT '', params TEXT DEFAULT '{}', sort_order INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS character_merge_log (id TEXT PRIMARY KEY, target_character_id TEXT NOT NULL, source_character_ids TEXT NOT NULL, merge_reason TEXT DEFAULT '', merge_strategy TEXT DEFAULT 'manual', created_at TEXT NOT NULL, FOREIGN KEY (target_character_id) REFERENCES characters(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_char_var_char ON character_variants(character_id);
        CREATE INDEX IF NOT EXISTS idx_char_var_type ON character_variants(variant_type);
        CREATE INDEX IF NOT EXISTS idx_merge_log_target ON character_merge_log(target_character_id);
    """)
    connection.commit()


# ── Data models ──────────────────────────────────────────────────────────


@dataclass
class CharacterVariant:
    """A variant of a character (different outfit, expression, or state)."""
    id: str
    character_id: str
    variant_type: str = "outfit"
    variant_name: str = ""
    prompt_delta: str = ""
    image_path: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "character_id": self.character_id, "variant_type": self.variant_type,
                "variant_name": self.variant_name, "prompt_delta": self.prompt_delta,
                "image_path": self.image_path, "params": self.params, "sort_order": self.sort_order,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CharacterVariant:
        data = dict(row)
        raw = data.get("params", "{}")
        params = json.loads(raw) if isinstance(raw, str) and raw else (raw or {})
        return cls(id=data["id"], character_id=data["character_id"],
                   variant_type=data.get("variant_type", "outfit"),
                   variant_name=data.get("variant_name", ""),
                   prompt_delta=data.get("prompt_delta", ""),
                   image_path=data.get("image_path", ""), params=params,
                   sort_order=data.get("sort_order", 0),
                   created_at=data.get("created_at", ""),
                   updated_at=data.get("updated_at", ""))


@dataclass
class MergeLogEntry:
    """Record of a character merge operation."""
    id: str
    target_character_id: str
    source_character_ids: list[str]
    merge_reason: str = ""
    merge_strategy: str = "manual"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "target_character_id": self.target_character_id,
                "source_character_ids": self.source_character_ids,
                "merge_reason": self.merge_reason, "merge_strategy": self.merge_strategy,
                "created_at": self.created_at}

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MergeLogEntry:
        d = dict(row)
        src = d.get("source_character_ids", "[]")
        parsed = json.loads(src) if isinstance(src, str) and src else (src or [])
        return cls(id=d["id"], target_character_id=d["target_character_id"],
                   source_character_ids=parsed,
                   merge_reason=d.get("merge_reason", ""),
                   merge_strategy=d.get("merge_strategy", "manual"),
                   created_at=d.get("created_at", ""))


@dataclass
class ExtractionResult:
    """Result of auto-extracting a character from narrative text."""
    name: str
    confidence: float
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    gender: str = ""
    age_group: str = ""
    tags: list[str] = field(default_factory=list)
    extracted_from: str = ""


# ── Database helpers ─────────────────────────────────────────────────────


def _insert_variant(connection: sqlite3.Connection, v: CharacterVariant) -> str:
    connection.execute(
        "INSERT INTO character_variants (id, character_id, variant_type, variant_name, prompt_delta, "
        "image_path, params, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (v.id, v.character_id, v.variant_type, v.variant_name, v.prompt_delta, v.image_path,
         json.dumps(v.params, ensure_ascii=False), v.sort_order, v.created_at, v.updated_at),
    )
    connection.commit()
    return v.id


def _update_variant(connection: sqlite3.Connection, variant_id: str, updates: dict[str, Any]) -> bool:
    clauses, params = [], []
    for f in ("variant_type", "variant_name", "prompt_delta", "image_path"):
        if f in updates:
            clauses.append(f"{f} = ?"); params.append(updates[f])
    if "params" in updates:
        clauses.append("params = ?"); params.append(json.dumps(updates["params"], ensure_ascii=False))
    if "sort_order" in updates:
        clauses.append("sort_order = ?"); params.append(updates["sort_order"])
    if not clauses:
        return False
    clauses.append("updated_at = ?"); params.append(updates.get("updated_at", now_utc_iso()))
    params.append(variant_id)
    cursor = connection.execute(f"UPDATE character_variants SET {', '.join(clauses)} WHERE id = ?", params)
    connection.commit()
    return cursor.rowcount > 0


def _delete_variant(connection: sqlite3.Connection, variant_id: str) -> bool:
    cursor = connection.execute("DELETE FROM character_variants WHERE id = ?", (variant_id,))
    connection.commit()
    return cursor.rowcount > 0


def _get_variants_for_character(connection: sqlite3.Connection, character_id: str) -> list[CharacterVariant]:
    cursor = connection.execute(
        "SELECT * FROM character_variants WHERE character_id = ? ORDER BY sort_order, variant_name",
        (character_id,),
    )
    return [CharacterVariant.from_row(row) for row in cursor.fetchall()]


def _get_variant_by_id(connection: sqlite3.Connection, variant_id: str) -> CharacterVariant | None:
    cursor = connection.execute("SELECT * FROM character_variants WHERE id = ?", (variant_id,))
    row = cursor.fetchone()
    return CharacterVariant.from_row(row) if row else None


# ── Workshop Service ─────────────────────────────────────────────────────


class CharacterWorkshop:
    """Character Workshop — variant management, merge, and auto-extraction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    # ── Variants ────────────────────────────────────────────────────────

    def create_variant(self, character_id: str, variant_type: str = "outfit",
                       variant_name: str = "", prompt_delta: str = "", image_path: str = "",
                       params: dict[str, Any] | None = None, sort_order: int = 0) -> CharacterVariant | None:
        if get_character_by_id(self._connection, character_id) is None:
            return None
        now = now_utc_iso()
        v = CharacterVariant(id=str(uuid.uuid4()), character_id=character_id, variant_type=variant_type,
                             variant_name=variant_name, prompt_delta=prompt_delta, image_path=image_path,
                             params=params or {}, sort_order=sort_order, created_at=now, updated_at=now)
        _insert_variant(self._connection, v)
        return v

    def update_variant(self, variant_id: str, **updates: Any) -> CharacterVariant | None:
        if _get_variant_by_id(self._connection, variant_id) is None:
            return None
        d: dict[str, Any] = {"updated_at": now_utc_iso()}
        for f in ("variant_type", "variant_name", "prompt_delta", "image_path", "params", "sort_order"):
            if f in updates:
                d[f] = updates[f]
        _update_variant(self._connection, variant_id, d)
        return _get_variant_by_id(self._connection, variant_id)

    def delete_variant(self, variant_id: str) -> bool:
        return _delete_variant(self._connection, variant_id)

    def get_variant(self, variant_id: str) -> CharacterVariant | None:
        return _get_variant_by_id(self._connection, variant_id)

    def list_variants(self, character_id: str, variant_type: str = "") -> list[CharacterVariant]:
        variants = _get_variants_for_character(self._connection, character_id)
        return [v for v in variants if v.variant_type == variant_type] if variant_type else variants

    # ── Merge ───────────────────────────────────────────────────────────

    def merge_characters(self, target_id: str, source_ids: list[str],
                         reason: str = "", strategy: str = "manual") -> Character | None:
        """Merge source characters into target, reassigning variants/images/links."""
        if get_character_by_id(self._connection, target_id) is None:
            return None
        now = now_utc_iso()
        for src_id in source_ids:
            if get_character_by_id(self._connection, src_id) is None:
                continue
            # Reassign variants (has updated_at)
            variant_ids = [r["id"] for r in self._connection.execute(
                "SELECT id FROM character_variants WHERE character_id = ?", (src_id,)
            ).fetchall()]
            for vid in variant_ids:
                self._connection.execute("UPDATE character_variants SET character_id = ?, updated_at = ? WHERE id = ?",
                                         (target_id, now, vid))
            # Reassign reference_images (no updated_at)
            self._connection.execute("UPDATE reference_images SET character_id = ? WHERE character_id = ?",
                                     (target_id, src_id))
            # Reassign lora_models (no updated_at)
            self._connection.execute("UPDATE lora_models SET character_id = ? WHERE character_id = ?",
                                     (target_id, src_id))
            for link in self._connection.execute(
                "SELECT project_id, role_tag FROM project_characters WHERE character_id = ?", (src_id,)
            ).fetchall():
                self._connection.execute(
                    "INSERT OR IGNORE INTO project_characters (project_id, character_id, role_tag) VALUES (?, ?, ?)",
                    (link["project_id"], target_id, link["role_tag"]),
                )
            delete_character(self._connection, src_id)

        self._connection.execute(
            "INSERT INTO character_merge_log (id, target_character_id, source_character_ids, "
            "merge_reason, merge_strategy, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), target_id, json.dumps(source_ids, ensure_ascii=False), reason, strategy, now),
        )
        self._connection.commit()
        target = get_character_by_id(self._connection, target_id)
        return Character.from_dict(target) if target else None

    def get_merge_history(self, character_id: str) -> list[MergeLogEntry]:
        cursor = self._connection.execute(
            "SELECT * FROM character_merge_log WHERE target_character_id = ? ORDER BY created_at DESC",
            (character_id,),
        )
        return [MergeLogEntry.from_row(row) for row in cursor.fetchall()]

    def find_duplicates(self, project_id: str = "", threshold: float = 0.6) -> list[dict[str, Any]]:
        """Find potential duplicate characters based on name similarity."""
        from difflib import SequenceMatcher
        cursor = self._connection.execute(
            "SELECT id, name, description, tags FROM characters" +
            (" WHERE project_id = ?" if project_id else ""),
            (project_id,) if project_id else (),
        )
        chars = [dict(row) for row in cursor.fetchall()]
        duplicates: list[dict[str, Any]] = []
        for i in range(len(chars)):
            for j in range(i + 1, len(chars)):
                a_name, b_name = chars[i]["name"], chars[j]["name"]
                score = max(SequenceMatcher(None, a_name, b_name).ratio(),
                            0.5 if (a_name in b_name or b_name in a_name) else 0.0)
                if score >= threshold:
                    duplicates.append({
                        "character_a": {"id": chars[i]["id"], "name": a_name, "description": chars[i].get("description", "")},
                        "character_b": {"id": chars[j]["id"], "name": b_name, "description": chars[j].get("description", "")},
                        "similarity_score": round(score, 4), "suggest_merge": score >= 0.75,
                    })
        duplicates.sort(key=lambda d: d["similarity_score"], reverse=True)
        return duplicates

    # ── Auto-extraction ─────────────────────────────────────────────────

    def extract_characters_from_text(self, text: str, known_names: list[str] | None = None) -> list[ExtractionResult]:
        """Extract character candidates from narrative text."""
        results: list[ExtractionResult] = []
        seen: set[str] = set(known_names or [])

        for pattern, confidence, source in [
            (re.compile(r"(?:角色|人物|角色名|姓名|名字)[：:]\s*([\u4e00-\u9fff\w]{1,10})"), 0.9, "role_definition"),
            (re.compile(r"(?:^|[，。！？、\s\n\r])([\u4e00-\u9fff]{2,4})(?:说|道|问|答|喊|叫|骂|叹|吼|哭|笑)"), 0.7, "dialogue_attribution"),
            (re.compile(r"[\[【]([\u4e00-\u9fff\w]{1,10})[\]】]"), 0.8, "bracket_tag"),
        ]:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    desc = _extract_description_after(text, match.end()) if source == "role_definition" else ""
                    results.append(ExtractionResult(name=name, confidence=confidence, description=desc,
                                                    tags=["auto-extracted"] if desc else [],
                                                    extracted_from=source))
        return results

    def auto_create_characters(self, text: str, project_id: str = "",
                               min_confidence: float = 0.7) -> list[Character]:
        """Extract characters from text and auto-create them in the database."""
        cursor = self._connection.execute(
            "SELECT name FROM characters" + (" WHERE project_id = ?" if project_id else ""),
            (project_id,) if project_id else (),
        )
        existing_names = {row["name"] for row in cursor.fetchall()}
        extractions = self.extract_characters_from_text(text, known_names=list(existing_names))
        created: list[Character] = []
        for ext in extractions:
            if ext.confidence < min_confidence or ext.name in existing_names:
                continue
            now = now_utc_iso()
            char_id = str(uuid.uuid4())
            record = {"id": char_id, "name": ext.name, "description": ext.description,
                      "gender": ext.gender, "age_group": ext.age_group, "tags": ext.tags,
                      "project_id": project_id, "reference_prompt": ext.description,
                      "created_at": now, "updated_at": now}
            insert_character(self._connection, record)
            if project_id:
                from aicomic.characters.database import link_character_to_project
                link_character_to_project(self._connection, project_id, char_id, role_tag=ext.name)
            created.append(Character.from_dict(record))
            existing_names.add(ext.name)
        return created

    # ── Batch operations ────────────────────────────────────────────────

    def batch_update_tags(self, character_ids: list[str], add_tags: list[str] | None = None,
                          remove_tags: list[str] | None = None) -> int:
        """Add and/or remove tags from multiple characters at once."""
        updated = 0
        now = now_utc_iso()
        add_set = set(add_tags or [])
        remove_set = set(remove_tags or [])
        for cid in character_ids:
            char = get_character_by_id(self._connection, cid)
            if char is None:
                continue
            current = set(char.get("tags", []) or [])
            new = (current | add_set) - remove_set
            if new != current:
                self._connection.execute("UPDATE characters SET tags = ?, updated_at = ? WHERE id = ?",
                                         (",".join(sorted(new)), now, cid))
                updated += 1
        if updated:
            self._connection.commit()
        return updated


# ── Internal helpers ─────────────────────────────────────────────────────


def _extract_description_after(text: str, start_pos: int, max_chars: int = 100) -> str:
    snippet = text[start_pos: start_pos + max_chars].strip()
    for delim in ("。", "！", "？", "\n", "；"):
        if (idx := snippet.find(delim)) > 0:
            return snippet[:idx].strip()
    return snippet.strip()
