"""Template engine — YAML-driven story blueprint + episode manifest generator.

Replaces hardcoded horror_pipeline.py and romance_pipeline.py with a generic
engine that reads template YAMLs from config/templates/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aicomic.core.manifest import write_json


def _templates_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "templates"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def list_templates() -> list[str]:
    d = _templates_dir()
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.yaml"))


def load_template(name: str) -> dict[str, Any]:
    p = _templates_dir() / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    with open(p, encoding="utf-8") as f:
        t = yaml.safe_load(f)
    if not isinstance(t, dict):
        raise ValueError(f"Invalid template YAML: {name}")
    return t


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _title_from_hook(hook: str) -> str:
    trimmed = hook.strip("。！？!? ")
    return trimmed if len(trimmed) <= 18 else trimmed[:18] + "..."


def build_blueprint_from_template(
    template_name: str,
    hook: str = "",
    episode_code: str = "E01",
    target_seconds: int | None = None,
    max_shots: int | None = None,
) -> dict[str, Any]:
    t = load_template(template_name)
    hook = hook.strip() or t["default_hook"]
    shot_dur = t.get("shot_duration_seconds", 6)
    ts = target_seconds or t.get("default_target_seconds", 360)
    ms = max_shots or t.get("default_max_shots", 60)
    shot_count = _clamp(round(ts / shot_dur), 1, ms)
    ts = shot_count * shot_dur

    acts_data = t["acts"]
    n = len(acts_data)
    base = shot_count // n
    rem = shot_count % n
    acts = []
    for i, a in enumerate(acts_data):
        sc = base + (1 if i < rem else 0)
        acts.append({
            "act_id": a["act_id"],
            "title": a["title"],
            "beat": a["beat"],
            "target_seconds": sc * shot_dur,
            "shot_count": sc,
            "purpose": _act_purpose(a, hook),
        })

    bp: dict[str, Any] = {
        "blueprint_version": t.get("blueprint_version", f"{template_name}/v1"),
        "episode_code": episode_code,
        "title": _title_from_hook(hook),
        "hook": hook,
        "genre": t["genre"],
        "target_platform": t.get("target_platform", "竖屏短视频"),
        "aspect_ratio": t.get("aspect_ratio", "9:16"),
        "target_seconds": ts,
        "shot_count": shot_count,
        "shot_duration_seconds": shot_dur,
        "acts": acts,
        "characters": [
            {"name": c["name"], "role": c["role"], "visual_rule": c.get("visual_rule", "")}
            for c in t["characters"]
        ],
        "locations": t["locations"],
        "visual_rules": t.get("visual_rules", []),
        "continuity_anchors": t.get("visual_motifs", []),
    }
    # Horror-specific extras
    for key in ("taboos", "twist"):
        if key in t:
            bp[key] = t[key]
    return bp


def _act_purpose(act: dict, hook: str) -> str:
    beat = act.get("beat", "")
    title = act.get("title", "")
    purposes = {
        "taboo": f"用一句禁忌把观众钩住：{hook}",
        "omen": "主角为了找人或找真相，主动做了老人警告不能做的事。",
        "escalation": "连续出现不合常理的物件、声音和背影，把风险推高。",
        "reveal": "揭示规则背后的真实原因，让前面异象重新成立。",
        "hook": "留下下一集必须点击的未解画面或一句话。",
        "meet_cute": f"雨夜偶遇建立初印象：{hook}",
        "bickering": "日常互动中展现性格反差和化学反应。",
        "sparks": "细节暗示双方心动，但还没说破。",
        "confession": "鼓起勇气告白，呼应开头的情书。",
        "sweet_ending": "甜蜜收尾，留下余韵。",
    }
    return purposes.get(beat, f"{title}阶段。")


def build_manifest_from_template(
    blueprint: dict[str, Any],
    template_name: str = "",
    project_id: str = "aicomic_system",
    season: int = 1,
) -> dict[str, Any]:
    # Infer template from blueprint_version if not given
    if not template_name:
        bp_ver = str(blueprint.get("blueprint_version", ""))
        # blueprint_version format: "{template_id}_content_factory/v1" or "{template_id}/v1"
        if "/" in bp_ver:
            prefix = bp_ver.split("/")[0]
            # Strip "_content_factory" suffix to get template_id
            template_name = prefix.removesuffix("_content_factory")
        else:
            template_name = "horror"

    t = load_template(template_name)
    locations = t["locations"]
    motifs = t.get("visual_motifs", [])
    sounds = t.get("sound_cues", [])
    chars = [c["name"] for c in t["characters"]]
    emotion_map = t.get("emotion_map", {})
    camera_map = t.get("camera_map", {})

    shot_dur = blueprint.get("shot_duration_seconds", 6)
    episode_code = str(blueprint.get("episode_code", "E01"))

    shots: list[dict[str, Any]] = []
    gi = 1
    for act in blueprint.get("acts", []):
        beat = str(act.get("beat", ""))
        act_title = str(act["title"])
        for ai in range(1, int(act["shot_count"]) + 1):
            loc = locations[(gi - 1) % len(locations)] if locations else ""
            motif = motifs[(gi - 1) % len(motifs)] if motifs else ""
            sound = sounds[(gi - 1) % len(sounds)] if sounds else ""
            emotion = emotion_map.get(beat, "")
            camera = camera_map.get(beat, "中景")
            char_list = _select_chars(beat, chars, template_name)

            visual = _build_visual(template_name, t, beat, act_title, loc, motif, gi)
            action = _build_action(template_name, beat, motif, act_title, chars)
            dialogue = _build_dialogue(template_name, t, beat, ai, blueprint)

            shots.append({
                "shot_id": f"S{gi:02d}",
                "duration": shot_dur,
                "scene": loc,
                "characters": char_list,
                "visual": visual,
                "action": action,
                "dialogue": dialogue,
                "emotion": emotion,
                "camera": camera,
                "ai_video": gi % 3 == 0 if template_name == "horror" else False,
                "priority": "high" if ai in {1, int(act["shot_count"])} else "medium",
                "act_id": str(act["act_id"]),
                "act_title": act_title,
                "sound_cue": sound,
                "continuity_anchor": motif if template_name == "horror" else None,
            })
            gi += 1

    return {
        "project_id": project_id,
        "season": season,
        "episodes": [{
            "episode_code": episode_code,
            "title": str(blueprint.get("title", template_name)),
            "status": "shotlist_ready" if template_name == "horror" else "draft",
            "publish_title": _publish_title(template_name, blueprint),
            "cover_text": _cover_text(template_name, blueprint),
            "creator_goal": _creator_goal(template_name),
            "ending_hook": str(blueprint.get("twist", "")) if template_name == "horror"
                           else "下次雨天，便利店的门铃还会为你响起吗？",
            "shots": shots,
        }],
    }


def _select_chars(beat: str, chars: list[str], template_name: str) -> list[str]:
    if not chars:
        return []
    if template_name == "horror":
        if beat in {"taboo", "omen"} and len(chars) >= 2:
            return [chars[0], chars[1]]
        if beat == "reveal" and len(chars) >= 3:
            return [chars[0], chars[2]]
        return [chars[0]]
    # romance: both characters in every shot
    return chars[:2] if len(chars) >= 2 else chars


def _build_visual(template_name: str, t: dict, beat: str, act_title: str,
                  loc: str, motif: str, gi: int) -> str:
    if template_name == "horror":
        avoidance_map = t.get("avoidance_strategies", [])
        avoidance_visual_map = t.get("avoidance_visual_map", {})
        avoidance = avoidance_map[(gi - 1) % len(avoidance_map)] if avoidance_map else ""
        av_text = avoidance_visual_map.get(avoidance, "")
        av_text = av_text.replace("{motif}", motif)
        return f"{loc}，{act_title}，{av_text}，民俗恐怖氛围，{beat} 节拍。"
    # romance
    vt = t.get("visual_templates", {})
    chars = [c["name"] for c in t["characters"]]
    char_a = chars[0] if chars else ""
    char_b = chars[1] if len(chars) >= 2 else ""
    tmpl = vt.get(beat, f"{loc}，{char_a}和{char_b}的都市爱情日常，{motif}作为视觉锚点。")
    return tmpl.format(loc=loc, char_a=char_a, char_b=char_b, motif=motif)


def _build_action(template_name: str, beat: str, motif: str,
                  act_title: str, chars: list[str]) -> str:
    if template_name == "horror":
        actions = {
            "taboo": f"守夜老人压低声音指向 {motif}，主角停下脚步。",
            "omen": f"主角触碰 {motif} 后，远处传来不该出现的脚步声。",
            "escalation": f"{motif} 自己移动了半寸，镜头缓慢推近。",
            "reveal": f"主角发现 {motif} 和母亲失踪那晚有关。",
            "hook": f"画面停在 {motif} 上，黑暗里有人叫出主角的名字。",
        }
        return actions.get(beat, f"{act_title}，线索出现。")
    # romance
    char_a = chars[0] if chars else ""
    char_b = chars[1] if len(chars) >= 2 else ""
    return f"{char_a}和{char_b}的互动，情绪：{beat}"


def _build_dialogue(template_name: str, t: dict, beat: str, ai: int,
                    blueprint: dict) -> str:
    if template_name == "horror":
        hook = str(blueprint.get("hook", ""))
        if beat == "taboo" and ai == 1:
            return hook
        if beat == "reveal" and ai == 1:
            return "我终于明白，村里人怕的不是鬼，是当年被藏起来的真相。"
        if beat == "hook" and ai >= 3:
            return "如果你听见井底有人叫你的名字，千万不要答应。"
        return f"{beat}，第 {ai} 个线索出现。"
    # romance
    dt = t.get("dialogue_templates", {})
    lines = dt.get(beat, ["..."])
    return lines[(ai - 1) % len(lines)]


def _publish_title(template_name: str, blueprint: dict) -> str:
    title = str(blueprint.get("title", ""))
    if template_name == "horror":
        return f"老人说这条禁忌千万别犯：{title}"
    return str(blueprint.get("hook", title))


def _cover_text(template_name: str, blueprint: dict) -> str:
    if template_name == "horror":
        return "夜里千万别回头"
    return str(blueprint.get("hook", ""))[:30]


def _creator_goal(template_name: str) -> str:
    if template_name == "horror":
        return "产出第一条 5-10 分钟玄学/民俗恐怖漫剧样片。"
    return "用6个镜头讲完一段都市爱情的偶遇到告白"


def write_blueprint(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)
