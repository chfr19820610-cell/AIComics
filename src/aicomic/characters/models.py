from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ── Pydantic request/response models (used by FastAPI) ────────────────────


class CharacterCreateRequest(BaseModel):
    """Request payload for creating a new character."""
    name: str = Field(..., min_length=1, max_length=128, description="角色名称")
    description: str = Field(default="", description="LLM 生成的结构化外貌描述")
    gender: str = Field(default="", description="性别：男/女/其他")
    age_group: str = Field(default="", description="年龄：少年/青年/中年/老年")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    project_id: str = Field(default="", description="所属项目 ID（空表示全局角色）")
    reference_prompt: str = Field(default="", description="角色参考 prompt，用于注入生成")


class CharacterUpdateRequest(BaseModel):
    """Request payload for updating an existing character."""
    name: str | None = Field(default=None, description="角色名称")
    description: str | None = Field(default=None, description="结构化外貌描述")
    gender: str | None = Field(default=None, description="性别")
    age_group: str | None = Field(default=None, description="年龄")
    tags: list[str] | None = Field(default=None, description="标签列表")
    project_id: str | None = Field(default=None, description="所属项目 ID")
    reference_prompt: str | None = Field(default=None, description="角色参考 prompt")


class CharacterResponse(BaseModel):
    """Response payload for character data."""
    id: str
    name: str
    description: str
    gender: str
    age_group: str
    tags: list[str]
    project_id: str
    reference_prompt: str
    created_at: str
    updated_at: str


# ── Internal data models ──────────────────────────────────────────────────


@dataclass
class Character:
    """Internal character data object."""
    id: str
    name: str
    description: str = ""
    gender: str = ""
    age_group: str = ""
    tags: list[str] = field(default_factory=list)
    project_id: str = ""
    reference_prompt: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "gender": self.gender,
            "age_group": self.age_group,
            "tags": self.tags,
            "project_id": self.project_id,
            "reference_prompt": self.reference_prompt,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: tuple) -> Character:
        return cls(
            id=row[0],
            name=row[1],
            description=row[2] or "",
            gender=row[3] or "",
            age_group=row[4] or "",
            tags=row[5].split(",") if row[5] else [],
            project_id=row[6] or "",
            reference_prompt=row[7] or "",
            created_at=row[8] or "",
            updated_at=row[9] or "",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            gender=data.get("gender", ""),
            age_group=data.get("age_group", ""),
            tags=data.get("tags", []),
            project_id=data.get("project_id", ""),
            reference_prompt=data.get("reference_prompt", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_response(self) -> CharacterResponse:
        return CharacterResponse(
            id=self.id,
            name=self.name,
            description=self.description,
            gender=self.gender,
            age_group=self.age_group,
            tags=self.tags,
            project_id=self.project_id,
            reference_prompt=self.reference_prompt,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
