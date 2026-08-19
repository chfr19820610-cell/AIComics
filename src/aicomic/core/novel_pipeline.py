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
    """Import a novel from a file path (.txt, .md, or .epub)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Novel file not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".epub":
        text = _read_epub(p)
    elif suffix in (".txt", ".md"):
        text = p.read_text(encoding="utf-8")
    else:
        raise ValueError(f"unsupported format: {suffix} (supported: .txt, .md, .epub)")

    return import_novel(text, template=template, **kwargs)


def _read_epub(path: Path) -> str:
    """Extract text from an epub file (zip with XHTML chapters)."""
    import zipfile
    import re as _re
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts: list[str] = []
        def handle_data(self, data: str):
            self._parts.append(data)
        def get_text(self) -> str:
            return " ".join(self._parts)

    with zipfile.ZipFile(path, "r") as zf:
        texts: list[str] = []
        for name in sorted(zf.namelist()):
            if name.endswith((".xhtml", ".html", ".htm")):
                raw = zf.read(name).decode("utf-8", errors="ignore")
                extractor = _TextExtractor()
                extractor.feed(raw)
                texts.append(extractor.get_text())
        return "\n\n".join(texts)


def count_novel_stats(text: str) -> dict[str, int]:
    """Quick stats for a novel text."""
    chapters = re.findall(r"第[一二三四五六七八九十百千]+章|第\d+章|Chapter\s+\d+", text)
    return {
        "char_count": len(text),
        "chapter_count": len(chapters),
        "estimated_episodes": max(1, len(text) // 3000),  # ~3000 chars per episode
    }


def narrate_rewrite(
    novel_text: str,
    llm_callback: Any | None = None,
    max_chars: int = 500,
) -> str:
    """Rewrite novel text into 漫剧旁白体 (compressed narration).

    Phase 1: Rule-based compression (remove dialogue tags, trim descriptions).
    Phase 2: LLM callback if provided.

    Args:
        novel_text: Raw novel text excerpt.
        llm_callback: Optional callable(text) -> str for LLM rewriting.
        max_chars: Maximum output length.

    Returns:
        Compressed narration text suitable for a single shot.
    """
    if not novel_text.strip():
        return ""

    # Rule-based: remove dialogue tags, compress whitespace, trim
    text = re.sub(r'["\u201c\u201d][^"\u201c\u201d]*["\u201c\u201d]?', "", novel_text)  # Remove quoted dialogue
    text = re.sub(r"[\u3000\u00a0]+", " ", text)  # Full-width spaces
    text = re.sub(r"\s+", " ", text).strip()

    # Cut to max_chars at a sentence boundary
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_period = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"), cut.rfind("."))
        if last_period > max_chars // 2:
            text = cut[:last_period + 1]
        else:
            text = cut + "…"

    # LLM enhancement if provided
    if llm_callback:
        try:
            enhanced = llm_callback(text)
            if enhanced and enhanced.strip():
                return enhanced.strip()
        except Exception:
            pass

    return text


def character_auto_register(
    novel_text: str,
    template_name: str = "workplace",
    max_characters: int = 8,
) -> list[dict[str, str]]:
    """Auto-detect character names from novel text and register them.

    Uses regex to find common Chinese name patterns and template character roles.

    Args:
        novel_text: Raw novel text.
        template_name: Template to map character roles from.
        max_characters: Maximum characters to extract.

    Returns:
        List of {name, role, visual_rule} dicts.
    """
    from aicomic.core.template_engine import load_template

    # Extract potential character names: 2-3 char Chinese names preceded by common patterns
    name_pattern = r"(?:叫|是|名叫|叫做|姓名|名字叫)\s*([\u4e00-\u9fff]{2,3})|([\u4e00-\u9fff]{2,3})(?:说|道|笑|哭|看|想|走|坐|站)"
    matches = re.findall(name_pattern, novel_text)
    candidates = []
    seen = set()
    for m in matches:
        name = m[0] or m[1]
        if name and name not in seen and name not in {"他们", "我们", "你们", "这个", "那个", "什么", "怎么"}:
            seen.add(name)
            candidates.append(name)
        if len(candidates) >= max_characters:
            break

    # Map to template character roles
    try:
        tmpl = load_template(template_name)
        tmpl_chars = tmpl.get("characters", [])
    except Exception:
        tmpl_chars = []

    result = []
    for i, name in enumerate(candidates):
        role = tmpl_chars[i]["role"] if i < len(tmpl_chars) else "配角"
        visual_rule = tmpl_chars[i].get("visual_rule", "") if i < len(tmpl_chars) else ""
        result.append({"name": name, "role": role, "visual_rule": visual_rule})
    return result


def run_full_pipeline(
    blueprint: dict[str, Any],
    template_name: str = "horror",
) -> dict[str, Any]:
    """Run the full pipeline: blueprint → shot breakdown → asset plan → render plan.

    This is the end-to-end connector from novel_pipeline to the production pipeline.

    Args:
        blueprint: Story blueprint with shots.
        template_name: Template for style/character mapping.

    Returns:
        {blueprint, shot_plan, asset_plan, render_plan}
    """
    shots = blueprint.get("shots", [])
    shot_plan = {
        "total_shots": len(shots),
        "shots": [
            {
                "shot_id": s.get("shot_id", f"S{i+1:02d}"),
                "visual": s.get("visual", ""),
                "narration": s.get("narration", ""),
                "duration": s.get("duration", 5),
            }
            for i, s in enumerate(shots)
        ],
    }

    asset_plan = {
        "images": [{"shot_id": s["shot_id"], "type": "keyframe", "prompt": s["visual"]} for s in shot_plan["shots"]],
        "audio": [{"shot_id": s["shot_id"], "type": "tts", "text": s["narration"]} for s in shot_plan["shots"]],
        "locations": list(set(s.get("visual", "").split()[0] for s in shot_plan["shots"] if s.get("visual"))),
    }

    render_plan = {
        "total_duration": sum(s["duration"] for s in shot_plan["shots"]),
        "resolution": "1280x720",
        "fps": 24,
        "shots": shot_plan["shots"],
    }

    return {
        "blueprint": blueprint,
        "shot_plan": shot_plan,
        "asset_plan": asset_plan,
        "render_plan": render_plan,
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
