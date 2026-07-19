from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aicomic.characters.models import Character
from aicomic.characters.service import CharacterService


def resolve_episode_manifest_path(project_root: Path) -> Path:
    """Resolve the episode_manifest.json path for a project root.

    The expected location is <project_root>/manifests/episode_manifest.json.
    """
    return project_root / "manifests" / "episode_manifest.json"


def load_episode_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and return the episode_manifest.json content."""
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Episode manifest not found: {manifest_path}"
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ── Character reference extraction from script ──────────────────────────


# Matches [角色名] or [角色名:别名] patterns in text
CHARACTER_TAG_PATTERN = re.compile(r"\[([^\]]+?)(?::([^\]]+))?\]")


def extract_character_tags(text: str) -> list[dict[str, str]]:
    """Extract all [角色名] and [角色名:别名] tags from a string.

    Returns a list of dicts with 'name' (the character identifier)
    and optional 'alias'.
    """
    matches = CHARACTER_TAG_PATTERN.findall(text)
    return [
        {"name": name.strip(), "alias": alias.strip() if alias else ""}
        for name, alias in matches
    ]


def extract_characters_from_manifest(
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    """Extract unique character names from all shots in the episode manifest.

    Iterates every episode → shot → characters[] and returns a
    deduplicated list of character names found.
    """
    seen: set[str] = set()
    characters: list[dict[str, str]] = []

    for episode in manifest.get("episodes", []):
        for shot in episode.get("shots", []):
            for char_name in shot.get("characters", []):
                name = str(char_name).strip()
                if name and name not in seen:
                    seen.add(name)
                    characters.append({
                        "name": name,
                        "episode_code": str(episode.get("episode_code", "")),
                        "shot_id": str(shot.get("shot_id", "")),
                    })

    return characters


def extract_characters_with_visuals(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract characters from the manifest, including their visual descriptions.

    Because the 'visual' field in each shot describes character appearance,
    we group characters by name and collect their visual contexts.
    """
    char_map: dict[str, dict[str, Any]] = {}

    for episode in manifest.get("episodes", []):
        for shot in episode.get("shots", []):
            for char_name in shot.get("characters", []):
                name = str(char_name).strip()
                if not name:
                    continue
                if name not in char_map:
                    char_map[name] = {
                        "name": name,
                        "episodes": set(),
                        "visual_contexts": [],
                    }
                char_map[name]["episodes"].add(str(episode.get("episode_code", "")))
                visual = shot.get("visual", "")
                if visual:
                    char_map[name]["visual_contexts"].append(visual)

    result = []
    for name, data in char_map.items():
        result.append({
            "name": name,
            "episodes": sorted(data["episodes"]),
            "visual_contexts": data["visual_contexts"],
            # Best visual description is the first non-empty one
            "best_visual": data["visual_contexts"][0] if data["visual_contexts"] else "",
        })

    return result


# ── Auto-register characters from manifest ──────────────────────────────


def auto_register_manifest_characters(
    manifest_path: Path,
    char_service: CharacterService,
    project_id: str = "",
) -> list[Character]:
    """Automatically create Character records for every character found
    in the episode_manifest.json that doesn't already have a record.

    Returns the list of newly created characters.
    """
    manifest = load_episode_manifest(manifest_path)
    raw_chars = extract_characters_from_manifest(manifest)
    created: list[Character] = []

    for raw in raw_chars:
        name = raw["name"]

        # Check if a character with this name already exists in the project
        existing = char_service.list_characters(project_id=project_id, limit=200)
        if any(c.name == name for c in existing):
            continue

        # Try to find a visual description from shots
        visual = ""
        for episode in manifest.get("episodes", []):
            for shot in episode.get("shots", []):
                if name in shot.get("characters", []):
                    visual = shot.get("visual", "")
                    break
            if visual:
                break

        from aicomic.characters.models import CharacterCreateRequest
        request = CharacterCreateRequest(
            name=name,
            project_id=project_id,
            reference_prompt=visual,
            description=f"从 episode_manifest.json 自动提取的角色「{name}」",
        )
        character = char_service.create_character(request)
        created.append(character)

    return created
