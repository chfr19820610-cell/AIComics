"""Character Views — four-view reference image generation and management.

Provides:
  - Four-view coordinate system: front, 3/4 view, side, back
  - View-specific prompt generation for each angle
  - Reference image CRUD (store/retrieve/update generated views)
  - View composition and priority rules for image generation pipelines

Compatible with the existing ComfyUI+SDXL pipeline via structured prompts.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aicomic.characters.database import get_character_by_id
from aicomic.characters.models import now_utc_iso


# ── View definitions ──────────────────────────────────────────────────────


class ViewAngle(str, Enum):
    """Standard character view angles."""

    FRONT = "front"          # 正面
    THREE_QUARTER = "three_quarter"  # 3/4正面（四分之三侧）
    SIDE = "side"            # 侧面（正侧）
    BACK = "back"            # 背面

    @classmethod
    def ordered(cls) -> list[ViewAngle]:
        return [cls.FRONT, cls.THREE_QUARTER, cls.SIDE, cls.BACK]


# ── Data models ──────────────────────────────────────────────────────────


@dataclass
class ViewPrompt:
    """A prompt template for generating a character from a specific angle.

    Combines the character's reference description with angle-specific
    framing and composition instructions.
    """

    angle: ViewAngle
    base_prompt: str  # character description
    angle_suffix: str  # angle-specific composition instructions
    full_prompt: str = ""  # combined prompt ready for the generator
    negative_prompt: str = ""

    def build(self) -> str:
        """Build the full prompt."""
        self.full_prompt = f"{self.base_prompt}, {self.angle_suffix}"
        return self.full_prompt


@dataclass
class CharacterView:
    """A generated reference view for a character at a specific angle."""

    id: str
    character_id: str
    angle: ViewAngle
    image_path: str  # path to the generated image file
    prompt_used: str  # the prompt that was used to generate this view
    is_primary: bool = False  # whether this is the main reference image
    quality_score: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "angle": self.angle.value if isinstance(self.angle, ViewAngle) else self.angle,
            "image_path": self.image_path,
            "prompt_used": self.prompt_used,
            "is_primary": self.is_primary,
            "quality_score": self.quality_score,
            "params": self.params,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CharacterView:
        data = dict(row)
        params_raw = data.get("params", "{}")
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw) if params_raw else {}
            except (json.JSONDecodeError, TypeError):
                params = {}
        else:
            params = params_raw or {}
        angle_raw = data.get("angle", "front")
        try:
            angle = ViewAngle(angle_raw)
        except ValueError:
            angle = ViewAngle.FRONT
        return cls(
            id=data["id"],
            character_id=data["character_id"],
            angle=angle,
            image_path=data.get("image_path", ""),
            prompt_used=data.get("prompt_used", ""),
            is_primary=bool(data.get("is_primary", False)),
            quality_score=float(data.get("quality_score", 0.0)),
            params=params,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class FourViewSet:
    """A complete set of four views for one character.

    References either existing CharacterView objects or the data needed
    to generate them.
    """

    character_id: str
    character_name: str
    views: dict[ViewAngle, CharacterView] = field(default_factory=dict)
    completed_angles: list[ViewAngle] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Check if all four views are present."""
        return len(self.views) >= 4 and all(
            angle in self.views for angle in ViewAngle.ordered()
        )

    @property
    def missing_angles(self) -> list[ViewAngle]:
        """Angles that still need to be generated."""
        return [a for a in ViewAngle.ordered() if a not in self.views]


# ── Angle prompt templates ────────────────────────────────────────────────

_ANGLE_PROMPTS: dict[ViewAngle, str] = {
    ViewAngle.FRONT: (
        "front view, facing camera, looking straight ahead, "
        "full body visible, symmetrical pose, centered composition"
    ),
    ViewAngle.THREE_QUARTER: (
        "three-quarter view, 3/4 angle, slightly turned to the side, "
        "natural standing pose, dynamic and slightly asymmetrical"
    ),
    ViewAngle.SIDE: (
        "side view, profile view, facing left or right, "
        "body in profile, head in profile, one arm visible"
    ),
    ViewAngle.BACK: (
        "back view, from behind, character facing away, "
        "showing back of head and clothing, over-shoulder visible"
    ),
}

_NEGATIVE_PROMPTS: dict[ViewAngle, str] = {
    ViewAngle.FRONT: (
        "profile, turned, three-quarter, back view, looking away, "
        "asymmetrical face, blurry face"
    ),
    ViewAngle.THREE_QUARTER: (
        "front facing, straight on, profile, back view, "
        "symmetrical, looking away from camera"
    ),
    ViewAngle.SIDE: (
        "looking at camera, front view, three-quarter, "
        "turned towards camera, asymmetrical features"
    ),
    ViewAngle.BACK: (
        "front view, face visible, looking at camera, "
        "three-quarter, side view, portrait"
    ),
}


# ── Database schema ──────────────────────────────────────────────────────


def ensure_views_schema(connection: sqlite3.Connection) -> None:
    """Create character_views table if it doesn't exist.

    Extends the existing reference_images table with view-specific data.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS character_views (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            angle TEXT NOT NULL CHECK(angle IN ('front', 'three_quarter', 'side', 'back')),
            image_path TEXT DEFAULT '',
            prompt_used TEXT DEFAULT '',
            is_primary INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            params TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_char_views_char ON character_views(character_id);
        CREATE INDEX IF NOT EXISTS idx_char_views_angle ON character_views(character_id, angle);
        """
    )
    connection.commit()


# ── Database helpers ─────────────────────────────────────────────────────


def _insert_view(connection: sqlite3.Connection, view: CharacterView) -> str:
    connection.execute(
        """
        INSERT INTO character_views
            (id, character_id, angle, image_path, prompt_used,
             is_primary, quality_score, params, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            view.id,
            view.character_id,
            view.angle.value if isinstance(view.angle, ViewAngle) else view.angle,
            view.image_path,
            view.prompt_used,
            1 if view.is_primary else 0,
            view.quality_score,
            json.dumps(view.params, ensure_ascii=False),
            view.created_at,
            view.updated_at,
        ),
    )
    connection.commit()
    return view.id


def _update_view(
    connection: sqlite3.Connection, view_id: str, updates: dict[str, Any]
) -> bool:
    set_clauses: list[str] = []
    params: list[Any] = []

    for field in ("image_path", "prompt_used", "quality_score", "angle"):
        if field in updates:
            set_clauses.append(f"{field} = ?")
            val = updates[field]
            if field == "quality_score":
                val = float(val)
            params.append(val)

    if "is_primary" in updates:
        set_clauses.append("is_primary = ?")
        params.append(1 if updates["is_primary"] else 0)

    if "params" in updates:
        set_clauses.append("params = ?")
        params.append(json.dumps(updates["params"], ensure_ascii=False))

    if not set_clauses:
        return False

    set_clauses.append("updated_at = ?")
    params.append(updates.get("updated_at", now_utc_iso()))
    params.append(view_id)

    cursor = connection.execute(
        f"UPDATE character_views SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    connection.commit()
    return cursor.rowcount > 0


def _delete_view(connection: sqlite3.Connection, view_id: str) -> bool:
    cursor = connection.execute(
        "DELETE FROM character_views WHERE id = ?", (view_id,)
    )
    connection.commit()
    return cursor.rowcount > 0


def _get_views_for_character(
    connection: sqlite3.Connection, character_id: str
) -> list[CharacterView]:
    cursor = connection.execute(
        "SELECT * FROM character_views WHERE character_id = ? ORDER BY angle",
        (character_id,),
    )
    return [CharacterView.from_row(row) for row in cursor.fetchall()]


def _get_view_by_id(
    connection: sqlite3.Connection, view_id: str
) -> CharacterView | None:
    cursor = connection.execute(
        "SELECT * FROM character_views WHERE id = ?", (view_id,)
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return CharacterView.from_row(row)


# ── View Generation Service ──────────────────────────────────────────────


class FourViewGenerator:
    """Generates and manages character four-view reference images.

    Produces prompts for front, 3/4, side, and back views of any character,
    managing the full lifecycle from prompt generation through image storage.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    # ── Prompt generation ──────────────────────────────────────────────

    def build_view_prompt(
        self,
        character_name: str,
        character_description: str,
        angle: ViewAngle,
        extra_instructions: str = "",
    ) -> ViewPrompt:
        """Build an optimized prompt for a specific view angle.

        Args:
            character_name: Name of the character.
            character_description: Core description (clothing, hair, features).
            angle: The target view angle.
            extra_instructions: Additional style or composition instructions.

        Returns:
            A ViewPrompt with base, angle suffix, negative prompt.
        """
        base = f"{character_name}, {character_description}"
        angle_suffix = _ANGLE_PROMPTS.get(angle, _ANGLE_PROMPTS[ViewAngle.FRONT])
        negative = _NEGATIVE_PROMPTS.get(angle, _NEGATIVE_PROMPTS[ViewAngle.FRONT])

        if extra_instructions:
            angle_suffix = f"{angle_suffix}, {extra_instructions}"

        vp = ViewPrompt(
            angle=angle,
            base_prompt=base,
            angle_suffix=angle_suffix,
            negative_prompt=negative,
        )
        vp.build()
        return vp

    def build_all_view_prompts(
        self,
        character_name: str,
        character_description: str,
        extra_instructions: str = "",
    ) -> dict[ViewAngle, ViewPrompt]:
        """Build prompts for all four view angles at once."""
        return {
            angle: self.build_view_prompt(
                character_name, character_description, angle, extra_instructions,
            )
            for angle in ViewAngle.ordered()
        }

    # ── View record management ─────────────────────────────────────────

    def record_view(
        self,
        character_id: str,
        angle: ViewAngle,
        image_path: str,
        prompt_used: str = "",
        is_primary: bool = False,
        quality_score: float = 0.0,
        params: dict[str, Any] | None = None,
    ) -> CharacterView | None:
        """Record a generated view image in the database.

        Returns the created CharacterView, or None if the character
        doesn't exist.
        """
        char = get_character_by_id(self._connection, character_id)
        if char is None:
            return None

        now = now_utc_iso()
        view = CharacterView(
            id=str(uuid.uuid4()),
            character_id=character_id,
            angle=angle,
            image_path=image_path,
            prompt_used=prompt_used,
            is_primary=is_primary,
            quality_score=quality_score,
            params=params or {},
            created_at=now,
            updated_at=now,
        )
        _insert_view(self._connection, view)

        # If this is marked as primary, unmark others for this angle
        if is_primary:
            self._connection.execute(
                "UPDATE character_views SET is_primary = 0 "
                "WHERE character_id = ? AND angle = ? AND id != ?",
                (character_id, angle.value if isinstance(angle, ViewAngle) else angle, view.id),
            )
            self._connection.commit()

        return view

    def update_view(
        self,
        view_id: str,
        **updates: Any,
    ) -> CharacterView | None:
        """Update a view record."""
        existing = _get_view_by_id(self._connection, view_id)
        if existing is None:
            return None

        update_dict: dict[str, Any] = {"updated_at": now_utc_iso()}
        for field in ("image_path", "prompt_used", "quality_score", "is_primary", "params", "angle"):
            if field in updates:
                update_dict[field] = updates[field]

        _update_view(self._connection, view_id, update_dict)
        return _get_view_by_id(self._connection, view_id)

    def delete_view(self, view_id: str) -> bool:
        """Delete a view record."""
        return _delete_view(self._connection, view_id)

    def get_view(self, view_id: str) -> CharacterView | None:
        """Get a single view by id."""
        return _get_view_by_id(self._connection, view_id)

    # ── View listing and retrieval ─────────────────────────────────────

    def get_character_views(
        self, character_id: str
    ) -> FourViewSet:
        """Get all views for a character, organized as a FourViewSet."""
        char = get_character_by_id(self._connection, character_id)
        name = char["name"] if char else ""

        views = _get_views_for_character(self._connection, character_id)
        view_set = FourViewSet(
            character_id=character_id,
            character_name=name,
        )

        for v in views:
            view_set.views[v.angle] = v
            view_set.completed_angles.append(v.angle)

        return view_set

    def get_primary_view(
        self, character_id: str
    ) -> CharacterView | None:
        """Get the primary (main reference) view for a character."""
        cursor = self._connection.execute(
            "SELECT * FROM character_views WHERE character_id = ? AND is_primary = 1 LIMIT 1",
            (character_id,),
        )
        row = cursor.fetchone()
        if row is None:
            # Fall back to front view
            cursor = self._connection.execute(
                "SELECT * FROM character_views WHERE character_id = ? AND angle = 'front' LIMIT 1",
                (character_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return CharacterView.from_row(row)

    def get_view_by_angle(
        self, character_id: str, angle: ViewAngle
    ) -> CharacterView | None:
        """Get the view for a specific angle."""
        angle_val = angle.value if isinstance(angle, ViewAngle) else angle
        cursor = self._connection.execute(
            "SELECT * FROM character_views WHERE character_id = ? AND angle = ?",
            (character_id, angle_val),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return CharacterView.from_row(row)

    # ── Reference image mode helpers ───────────────────────────────────

    def build_reference_image_params(
        self,
        character_id: str,
        preferred_angle: ViewAngle = ViewAngle.FRONT,
        style: str = "",
    ) -> dict[str, Any]:
        """Build ComfyUI-compatible reference image parameters.

        Returns a dict that can be passed to the image generation pipeline
        as reference image guidance, matching the AIComicBuilder reference
        image mode pattern.

        The result includes:
          - reference_image_path: path to the best-matching-angle view image
          - use_reference: boolean flag
          - reference_strength: influence weight (0.0-1.0)
          - style: optional style override
        """
        view = self.get_view_by_angle(character_id, preferred_angle)
        if view is None:
            # Fallback to primary
            view = self.get_primary_view(character_id)

        if view is None:
            return {
                "use_reference": False,
                "reason": "No reference image available for this character",
            }

        return {
            "use_reference": True,
            "reference_image_path": view.image_path,
            "reference_angle": view.angle.value if isinstance(view.angle, ViewAngle) else view.angle,
            "reference_strength": 0.7,
            "style": style,
            "character_id": character_id,
            "view_id": view.id,
        }

    def get_reference_image_map(
        self, character_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Build a reference image map for multiple characters.

        Returns a dict keyed by character_id with reference image params,
        suitable for batch generation pipelines.
        """
        result: dict[str, dict[str, Any]] = {}
        for cid in character_ids:
            result[cid] = self.build_reference_image_params(cid)
        return result


# ── Public API ────────────────────────────────────────────────────────────


def generate_view_prompt(
    character_description: str,
    angle: str,
    character_name: str = "",
    extra_instructions: str = "",
) -> str:
    """Standalone helper: generate a single view prompt without DB access.

    Args:
        character_description: The character's visual description.
        angle: One of 'front', 'three_quarter', 'side', 'back'.
        character_name: Optional character name to prepend.
        extra_instructions: Additional instructions.

    Returns:
        A complete prompt string ready for an image generator.
    """
    try:
        view_angle = ViewAngle(angle)
    except ValueError:
        view_angle = ViewAngle.FRONT

    base = character_description
    if character_name:
        base = f"{character_name}, {character_description}"

    suffix = _ANGLE_PROMPTS.get(view_angle, _ANGLE_PROMPTS[ViewAngle.FRONT])
    if extra_instructions:
        suffix = f"{suffix}, {extra_instructions}"

    return f"{base}, {suffix}"


def generate_four_view_prompts(
    character_description: str,
    character_name: str = "",
    extra_instructions: str = "",
) -> dict[str, str]:
    """Standalone helper: generate all four view prompts without DB access.

    Returns a dict keyed by angle name ('front', 'three_quarter', 'side', 'back')
    with full prompt strings.
    """
    return {
        angle.value: generate_view_prompt(
            character_description, angle.value, character_name, extra_instructions,
        )
        for angle in ViewAngle.ordered()
    }


def get_negative_prompt_for_angle(angle: str) -> str:
    """Get the standard negative prompt for a given angle."""
    try:
        view_angle = ViewAngle(angle)
    except ValueError:
        return ""
    return _NEGATIVE_PROMPTS.get(view_angle, "")
