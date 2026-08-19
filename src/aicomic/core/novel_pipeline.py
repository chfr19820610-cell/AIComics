"""Novel → 漫剧 pipeline: import novel text → split episodes → generate blueprints.

Connects novel_splitter (chapter splitting) with template_engine (blueprint generation).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aicomic.core.novel_splitter import split_novel_to_episodes, build_manifest_from_episodes
from aicomic.core.template_engine import load_template, build_blueprint_from_template


def import_novel(
    text: str,
    template: str = "workplace",
    episode_target_count: int = 12,
    shots_per_episode: int = 10,
) -> dict[str, Any]:
    """Import a novel and produce a full season plan.

    Args:
        text: Novel full text
        template: Template ID for visual style
        episode_target_count: Max episodes to generate
        shots_per_episode: Shots per episode
    Returns:
        {template, episode_count, episodes: [{episode_code, title, hook, blueprint}]}
    """
    # 1. Split novel into episodes
    episodes = split_novel_to_episodes(text, target_shots_per_ep=shots_per_episode, chars_per_shot=300)

    # 2. Cap at episode_target_count
    episodes = episodes[:episode_target_count]

    # 3. Load template for style
    tmpl = load_template(template)
    default_hook = tmpl.get("default_hook", "")

    # 4. For each episode, generate a blueprint using the template
    result_episodes = []
    for ep in episodes:
        # Use first shot's dialogue or visual as hook
        first_shot = ep["shots"][0] if ep["shots"] else {}
        hook = first_shot.get("dialogue", "") or first_shot.get("visual", "") or default_hook
        hook = hook[:50]  # truncate to reasonable length

        bp = build_blueprint_from_template(
            template,
            hook=hook,
            episode_code=ep["episode_code"],
            max_shots=len(ep["shots"]),
        )
        result_episodes.append({
            "episode_code": ep["episode_code"],
            "title": ep["title"],
            "hook": hook,
            "shot_count": len(ep["shots"]),
            "novel_shots": ep["shots"],  # original novel content
            "blueprint": bp,  # template-driven blueprint
        })

    return {
        "template": template,
        "genre": tmpl.get("genre", ""),
        "episode_count": len(result_episodes),
        "episodes": result_episodes,
    }


def import_novel_file(path: str | Path, template: str = "workplace", **kwargs: Any) -> dict[str, Any]:
    """Import a novel from a file path (.txt or .md)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Novel file not found: {p}")
    text = p.read_text(encoding="utf-8")
    return import_novel(text, template=template, **kwargs)


def count_novel_stats(text: str) -> dict[str, int]:
    """Quick stats for a novel text."""
    chapters = re.findall(r"第[一二三四五六七八九十百千]+章|第\d+章|Chapter\s+\d+", text)
    return {
        "char_count": len(text),
        "chapter_count": len(chapters),
        "estimated_episodes": max(1, len(text) // 3000),  # ~3000 chars per episode
    }


def generate_episode_plan(blueprint: dict[str, Any], template_name: str = "workplace", shots_per_episode: int = 10) -> dict[str, Any]:
    """Phase 2: Generate per-shot plan + asset plan from a blueprint.

    blueprint: output from template_engine.build_blueprint_from_template
    returns: {shot_plan, asset_plan, total_shots}
    """
    if shots_per_episode <= 0:
        raise ValueError("shots_per_episode must be > 0")

    acts = blueprint.get("acts", [])
    characters = blueprint.get("characters", [])
    locations = blueprint.get("locations", [])
    motifs = blueprint.get("visual_motifs", [])
    emotion_map = blueprint.get("emotion_map", {})

    # Distribute shots across acts proportionally
    total_act_shots = sum(a.get("shot_count", 0) for a in acts) or 1
    shots = []
    shot_idx = 0
    for act in acts:
        act_shots = max(1, round(shots_per_episode * act.get("shot_count", 1) / total_act_shots))
        for i in range(act_shots):
            if shot_idx >= shots_per_episode:
                break
            loc = locations[shot_idx % len(locations)] if locations else "unknown"
            beat = act.get("beat", "default")
            emotion = emotion_map.get(beat, "")
            shots.append({
                "shot_id": f"S{shot_idx+1:03d}",
                "act_id": act.get("act_id", ""),
                "location": loc,
                "emotion": emotion,
                "narration": f"[{act.get('title', '')}] 第{shot_idx+1}镜",
                "motif": motifs[shot_idx % len(motifs)] if motifs else "",
            })
            shot_idx += 1
    # Fill remaining shots
    while len(shots) < shots_per_episode:
        shots.append({
            "shot_id": f"S{len(shots)+1:03d}",
            "act_id": acts[-1]["act_id"] if acts else "",
            "location": locations[len(shots) % len(locations)] if locations else "unknown",
            "emotion": "",
            "narration": f"第{len(shots)+1}镜",
            "motif": "",
        })

    asset_plan = {
        "characters": [{"name": c["name"], "role": c.get("role", ""), "visual_rule": c.get("visual_rule", "")} for c in characters],
        "locations": list(set(s["location"] for s in shots)),
        "motifs": list(set(s["motif"] for s in shots if s["motif"])),
    }
    return {"shot_plan": shots, "asset_plan": asset_plan, "total_shots": len(shots)}


def build_season_production_plan(episodes: list[dict[str, Any]], template_name: str = "workplace") -> dict[str, Any]:
    """Phase 2: Build full season production plan from episodes list.

    episodes: list of {episode_code, shot_count, blueprint}
    returns: {episode_count, total_shots, episode_plans}
    """
    plans = []
    total = 0
    for ep in episodes:
        plan = generate_episode_plan(
            ep.get("blueprint", {}),
            template_name=template_name,
            shots_per_episode=ep.get("shot_count", 10),
        )
        plans.append({"episode_code": ep.get("episode_code", ""), "plan": plan})
        total += plan["total_shots"]
    return {"episode_count": len(episodes), "total_shots": total, "episode_plans": plans}
