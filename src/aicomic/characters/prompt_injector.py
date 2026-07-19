from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aicomic.characters.models import Character
from aicomic.characters.service import CharacterService


# Regex to find character tags in visual prompts: [角色名]
CHARACTER_REF_PATTERN = re.compile(r"\[([^\]]+)\]")


def inject_character_descriptions(
    base_prompt: str,
    characters: list[Character],
) -> str:
    """Replace [角色名] markers in a prompt with the character's description
    or reference_prompt.

    For each [角色名] occurrence, if a matching Character is found in the
    provided list, the marker is replaced with the character's
    reference_prompt (or description fallback). Unknown markers are left as-is.
    """
    char_map: dict[str, Character] = {}
    for c in characters:
        char_map[c.name] = c

    def _replacer(match: re.Match) -> str:
        name = match.group(1).strip()
        char = char_map.get(name)
        if char is None:
            return match.group(0)  # leave unknown tags unchanged
        char_prompt = char.reference_prompt or char.description
        if not char_prompt:
            return match.group(0)
        return char_prompt

    return CHARACTER_REF_PATTERN.sub(_replacer, base_prompt)


def build_character_context_block(
    shot_characters: list[str],
    char_service: CharacterService,
    project_id: str = "",
    existing_chars: list | None = None,
) -> str:
    """Build a structured character context block for prompt injection.

    Given a list of character names appearing in a shot, this looks up
    the character definitions and returns a formatted string to prepend
    to the generation prompt.

    Example output:
        [角色信息]
        - 女主: 黑长直发，淡蓝色丝巾，白色衬衫...
        - 反派主管: 40岁，深红色西装外套...
    """
    if existing_chars is not None:
        project_chars = existing_chars
    else:
        project_chars = char_service.list_characters(project_id=project_id, limit=200)
    char_map = {c.name: c for c in project_chars}

    lines: list[str] = ["[角色信息]"]

    for name in shot_characters:
        char = char_map.get(name)
        if char is None:
            lines.append(f"- {name}: (未定义角色描述)")
            continue
        desc = char.reference_prompt or char.description or "(未定义)"
        # Truncate very long descriptions for the context block
        if len(desc) > 300:
            desc = desc[:300] + "..."
        lines.append(f"- {char.name}: {desc}")

    return "\n".join(lines)


def enhance_image_prompt(
    base_prompt: str,
    shot_characters: list[str],
    char_service: CharacterService,
    project_id: str = "",
) -> str:
    """Enhance an image generation prompt by injecting character context.

    The character context block is prepended to the base prompt, and
    any [角色名] markers in the base prompt are replaced with the
    character's reference description.

    This is the primary entry point for prompt injection in Phase 1.
    """
    # First resolve [角色名] markers in the prompt
    project_chars = char_service.list_characters(project_id=project_id, limit=200)
    prompt_with_injections = inject_character_descriptions(base_prompt, project_chars)

    # Build the character context block (reuse project_chars, avoid second query)
    context_block = build_character_context_block(
        shot_characters, char_service, project_id, existing_chars=project_chars,
    )

    # Prepend context block if there's valuable info
    if "[角色信息]" in context_block:
        return f"{context_block}\n\n{prompt_with_injections}"

    return prompt_with_injections


def build_enriched_prompt_for_shot(
    shot: dict[str, Any],
    char_service: CharacterService,
    project_id: str = "",
) -> str:
    """Build an enriched image generation prompt for a single shot.

    Combines the shot's 'visual' description, 'scene', 'action', and
    'emotion' fields, then injects character context for all characters
    appearing in this shot.
    """
    base_parts: list[str] = []

    scene = shot.get("scene", "")
    if scene:
        base_parts.append(f"场景：{scene}")

    visual = shot.get("visual", "")
    if visual:
        base_parts.append(visual)

    action = shot.get("action", "")
    if action:
        base_parts.append(f"动作：{action}")

    emotion = shot.get("emotion", "")
    if emotion:
        base_parts.append(f"情绪：{emotion}")

    base_prompt = "\n".join(base_parts)

    shot_characters = shot.get("characters", [])
    return enhance_image_prompt(base_prompt, shot_characters, char_service, project_id)


def validate_character_prompt_integrity(
    enriched_prompt: str,
    original_length: int,
) -> dict[str, Any]:
    """Validate that prompt injection didn't destroy prompt structure.

    Checks:
    - Prompt is not empty after injection
    - Character context block is well-formed
    - Length change is reasonable (not exploded)
    """
    if not enriched_prompt.strip():
        return {"valid": False, "reason": "提示词为空"}

    length_diff = len(enriched_prompt) - original_length
    if length_diff < 0:
        return {"valid": False, "reason": "注入后提示词变短，可能丢失了内容"}

    if length_diff > 5000:
        return {
            "valid": False,
            "reason": f"注入后提示词过长（+{length_diff}字符），可能超出模型上下文限制",
        }

    context_block_markers = enriched_prompt.count("[角色信息]")
    if context_block_markers > 1:
        return {"valid": False, "reason": "存在重复的角色信息块"}

    return {
        "valid": True,
        "original_length": original_length,
        "enriched_length": len(enriched_prompt),
        "added_length": length_diff,
    }
