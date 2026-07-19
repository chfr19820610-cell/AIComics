from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aicomic.characters.database import (
    connect_character_database,
    count_characters,
    delete_character,
    ensure_character_schema,
    get_character_by_id,
    get_project_characters,
    insert_character,
    link_character_to_project,
    list_characters,
    update_character,
)
from aicomic.characters.models import (
    Character,
    CharacterCreateRequest,
    CharacterUpdateRequest,
    now_utc_iso,
)


def _default_db_path(state_dir: Path) -> Path:
    return state_dir / "character.db"


class CharacterService:
    """High-level character CRUD operations.

    Manages the character SQLite database and provides business-logic
    methods for creating, reading, updating, deleting, and searching
    character definitions.
    """

    def __init__(self, state_dir: Path | str | None = None) -> None:
        if state_dir is None:
            from aicomic.core.config import ProjectPaths
            state_dir = ProjectPaths.default_database_path().parent
        elif isinstance(state_dir, str):
            state_dir = Path(state_dir)
        self._db_path = _default_db_path(Path(state_dir))
        self._connection = connect_character_database(self._db_path)
        ensure_character_schema(self._connection)

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ── Create ──────────────────────────────────────────────────────────

    def create_character(self, request: CharacterCreateRequest) -> Character:
        """Create a new character from the request payload."""
        now = now_utc_iso()
        character_id = str(uuid.uuid4())
        record: dict[str, Any] = {
            "id": character_id,
            "name": request.name,
            "description": request.description,
            "gender": request.gender,
            "age_group": request.age_group,
            "tags": request.tags,
            "project_id": request.project_id,
            "reference_prompt": request.reference_prompt,
            "created_at": now,
            "updated_at": now,
        }
        insert_character(self._connection, record)

        # If a project_id was provided, auto-link
        if request.project_id:
            link_character_to_project(
                self._connection,
                request.project_id,
                character_id,
                role_tag=request.name,
            )

        return Character.from_dict(record)

    # ── Read ────────────────────────────────────────────────────────────

    def get_character(self, character_id: str) -> Character | None:
        """Fetch a single character by id."""
        row = get_character_by_id(self._connection, character_id)
        if row is None:
            return None
        return Character.from_dict(row)

    def list_characters(
        self,
        project_id: str = "",
        tag: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Character]:
        """List characters with optional filters."""
        rows = list_characters(self._connection, project_id, tag, limit, offset)
        return [Character.from_dict(r) for r in rows]

    def get_project_characters(self, project_id: str) -> list[Character]:
        """Get all characters linked to a specific project."""
        rows = get_project_characters(self._connection, project_id)
        return [Character.from_dict(r) for r in rows]

    def count_characters(self, project_id: str = "") -> int:
        """Count total characters, optionally filtered by project."""
        return count_characters(self._connection, project_id)

    # ── Update ──────────────────────────────────────────────────────────

    def update_character(
        self,
        character_id: str,
        updates: CharacterUpdateRequest,
    ) -> Character | None:
        """Update an existing character. Returns the updated character or None."""
        existing = self.get_character(character_id)
        if existing is None:
            return None

        update_dict: dict[str, Any] = {
            "updated_at": now_utc_iso(),
        }

        for field in ("name", "description", "gender", "age_group", "project_id", "reference_prompt", "tags"):
            value = getattr(updates, field, None)
            if value is not None:
                update_dict[field] = value

        updated = update_character(self._connection, character_id, update_dict)
        if not updated:
            return None

        return self.get_character(character_id)

    # ── Delete ──────────────────────────────────────────────────────────

    def delete_character(self, character_id: str) -> bool:
        """Delete a character by id. Returns True if deleted."""
        return delete_character(self._connection, character_id)

    # ── Search ──────────────────────────────────────────────────────────

    def search_characters(self, query: str, limit: int = 20) -> list[Character]:
        """Simple LIKE-based search across name, description, and tags."""
        like = f"%{query}%"
        cursor = self._connection.execute(
            """
            SELECT * FROM characters
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (like, like, like, limit),
        )
        return [Character.from_row(tuple(row)) for row in cursor.fetchall()]
