from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect_character_database(database_path: Path) -> sqlite3.Connection:
    """Open (or create) the character SQLite database."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30.0)
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return connection


def ensure_character_schema(connection: sqlite3.Connection) -> None:
    """Create character-related tables if they don't exist.

    Schema follows the PRD data model:
      - characters:    角色定义表
      - reference_images:  参考图存储
      - lora_models:       LoRA 模型记录
      - project_characters: 项目-角色关联表
    """
    connection.executescript(
        """
        -- 角色定义表
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            gender TEXT DEFAULT '',
            age_group TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            reference_prompt TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 参考图表 (Phase 1: schema only, UI in later phase)
        CREATE TABLE IF NOT EXISTS reference_images (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            angle TEXT DEFAULT '',
            expression TEXT DEFAULT '',
            quality_score REAL DEFAULT 0.0,
            feature_vector BLOB DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        -- LoRA 模型表 (Phase 2: schema only)
        CREATE TABLE IF NOT EXISTS lora_models (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            base_model TEXT DEFAULT 'sdxl',
            training_params TEXT DEFAULT '{}',
            steps INTEGER DEFAULT 0,
            learning_rate REAL DEFAULT 0.0001,
            status TEXT DEFAULT 'pending',
            consistency_score REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        -- 项目-角色关联表
        CREATE TABLE IF NOT EXISTS project_characters (
            project_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            role_tag TEXT DEFAULT '',
            PRIMARY KEY (project_id, character_id),
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id);
        CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
        CREATE INDEX IF NOT EXISTS idx_ref_images_char ON reference_images(character_id);
        CREATE INDEX IF NOT EXISTS idx_lora_char ON lora_models(character_id);
        """
    )
    connection.commit()


# ── Character CRUD ────────────────────────────────────────────────────────


def insert_character(connection: sqlite3.Connection, record: dict[str, Any]) -> str:
    """Insert a new character row. Returns the character id."""
    character_id = record["id"]
    connection.execute(
        """
        INSERT INTO characters (id, name, description, gender, age_group, tags,
                                project_id, reference_prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            character_id,
            record["name"],
            record.get("description", ""),
            record.get("gender", ""),
            record.get("age_group", ""),
            ",".join(record.get("tags", [])),
            record.get("project_id", ""),
            record.get("reference_prompt", ""),
            record.get("created_at", ""),
            record.get("updated_at", ""),
        ),
    )
    connection.commit()
    return character_id


def update_character(connection: sqlite3.Connection, character_id: str, updates: dict[str, Any]) -> bool:
    """Update an existing character. Returns True if a row was changed."""
    set_clauses: list[str] = []
    params: list[Any] = []

    for field in ("name", "description", "gender", "age_group", "project_id", "reference_prompt"):
        if field in updates:
            set_clauses.append(f"{field} = ?")
            params.append(updates[field])

    if "tags" in updates:
        set_clauses.append("tags = ?")
        params.append(",".join(updates["tags"]))

    if not set_clauses:
        return False

    set_clauses.append("updated_at = ?")
    params.append(updates.get("updated_at", ""))

    params.append(character_id)
    cursor = connection.execute(
        f"UPDATE characters SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    connection.commit()
    return cursor.rowcount > 0


def get_character_by_id(connection: sqlite3.Connection, character_id: str) -> dict[str, Any] | None:
    """Fetch one character by id, returning a dict or None."""
    cursor = connection.execute(
        "SELECT * FROM characters WHERE id = ?",
        (character_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_characters(
    connection: sqlite3.Connection,
    project_id: str = "",
    tag: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List characters with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []

    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    cursor = connection.execute(
        f"SELECT * FROM characters {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return [_row_to_dict(row) for row in cursor.fetchall()]


def delete_character(connection: sqlite3.Connection, character_id: str) -> bool:
    """Delete a character and related cascade data. Returns True if deleted."""
    cursor = connection.execute("DELETE FROM characters WHERE id = ?", (character_id,))
    connection.commit()
    return cursor.rowcount > 0


def count_characters(connection: sqlite3.Connection, project_id: str = "") -> int:
    """Count characters with optional project filter."""
    if project_id:
        cursor = connection.execute(
            "SELECT COUNT(*) FROM characters WHERE project_id = ?",
            (project_id,),
        )
    else:
        cursor = connection.execute("SELECT COUNT(*) FROM characters")
    return int(cursor.fetchone()[0])


# ── Project-Character link ────────────────────────────────────────────────


def link_character_to_project(
    connection: sqlite3.Connection,
    project_id: str,
    character_id: str,
    role_tag: str = "",
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO project_characters (project_id, character_id, role_tag)
        VALUES (?, ?, ?)
        """,
        (project_id, character_id, role_tag),
    )
    connection.commit()


def get_project_characters(
    connection: sqlite3.Connection,
    project_id: str,
) -> list[dict[str, Any]]:
    """Get all characters linked to a project with their role tags."""
    cursor = connection.execute(
        """
        SELECT c.*, pc.role_tag
        FROM characters c
        JOIN project_characters pc ON c.id = pc.character_id
        WHERE pc.project_id = ?
        ORDER BY pc.role_tag
        """,
        (project_id,),
    )
    return [_row_to_dict(row) for row in cursor.fetchall()]


# ── Helpers ────────────────────────────────────────────────────────────────


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert an sqlite3.Row to a plain dict, parsing tags from comma-sep string."""
    data = dict(row)
    if "tags" in data and isinstance(data["tags"], str):
        data["tags"] = [t for t in data["tags"].split(",") if t]
    return data
