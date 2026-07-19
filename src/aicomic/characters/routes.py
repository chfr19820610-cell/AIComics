from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from aicomic.characters.models import (
    CharacterCreateRequest,
    CharacterResponse,
    CharacterUpdateRequest,
)
from aicomic.characters.script_parser import (
    auto_register_manifest_characters,
    extract_characters_from_manifest,
    load_episode_manifest,
    resolve_episode_manifest_path,
)
from aicomic.characters.service import CharacterService
from web.backend.auth.auth_middleware import get_request_user


def build_character_router(
    state_dir: Path | str,
) -> APIRouter:
    """Factory: create an APIRouter with character CRUD endpoints.

    Requires a state_dir so the CharacterService knows where to
    store/create its SQLite database.
    """
    router = APIRouter(prefix="/api/characters", tags=["characters"])
    char_service = CharacterService(state_dir=state_dir)

    from functools import lru_cache

    def _get_service() -> CharacterService:
        return char_service

    # ── List characters ────────────────────────────────────────────────

    @router.get("")
    def list_characters(
        request: Request,
        project_id: str = Query(default="", description="按项目筛选"),
        tag: str = Query(default="", description="按标签筛选"),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        svc = _get_service()
        items = svc.list_characters(
            project_id=project_id,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        total = svc.count_characters(project_id=project_id)
        return {
            "items": [c.to_response().model_dump() for c in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ── Get single character ────────────────────────────────────────────

    @router.get("/{character_id}")
    def get_character(character_id: str) -> dict[str, Any]:
        svc = _get_service()
        char = svc.get_character(character_id)
        if char is None:
            raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")
        return char.to_response().model_dump()

    # ── Create character ────────────────────────────────────────────────

    @router.post("", status_code=201)
    def create_character(payload: CharacterCreateRequest) -> dict[str, Any]:
        svc = _get_service()
        char = svc.create_character(payload)
        return char.to_response().model_dump()

    # ── Update character ────────────────────────────────────────────────

    @router.patch("/{character_id}")
    def update_character(
        character_id: str,
        payload: CharacterUpdateRequest,
    ) -> dict[str, Any]:
        svc = _get_service()
        char = svc.update_character(character_id, payload)
        if char is None:
            raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")
        return char.to_response().model_dump()

    # ── Delete character ────────────────────────────────────────────────

    @router.delete("/{character_id}")
    def delete_character(character_id: str) -> dict[str, Any]:
        svc = _get_service()
        deleted = svc.delete_character(character_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")
        return {"deleted": True, "id": character_id}

    # ── Search characters ──────────────────────────────────────────────

    @router.get("/search/{query:path}")
    def search_characters(query: str, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        svc = _get_service()
        items = svc.search_characters(query, limit=limit)
        return {
            "items": [c.to_response().model_dump() for c in items],
            "count": len(items),
        }

    # ── Auto-register from episode manifest ────────────────────────────

    @router.post("/auto-register")
    def auto_register(
        project_root: str = Query(default="", description="项目根目录路径"),
        project_id: str = Query(default="", description="项目 ID"),
    ) -> dict[str, Any]:
        svc = _get_service()
        root = Path(project_root) if project_root else Path.cwd()
        manifest_path = resolve_episode_manifest_path(root)
        if not manifest_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Episode manifest not found at: {manifest_path}",
            )
        created = auto_register_manifest_characters(
            manifest_path, svc, project_id=project_id,
        )
        return {
            "created_count": len(created),
            "characters": [c.to_response().model_dump() for c in created],
        }

    # ── Parse character names from manifest ────────────────────────────

    @router.post("/parse-from-manifest")
    def parse_from_manifest(
        project_root: str = Query(default="", description="项目根目录路径"),
    ) -> dict[str, Any]:
        root = Path(project_root) if project_root else Path.cwd()
        manifest_path = resolve_episode_manifest_path(root)
        if not manifest_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Episode manifest not found at: {manifest_path}",
            )
        manifest = load_episode_manifest(manifest_path)
        characters = extract_characters_from_manifest(manifest)
        return {
            "characters": characters,
            "count": len(characters),
            "manifest_path": str(manifest_path),
        }

    return router
