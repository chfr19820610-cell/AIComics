from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.manifest import write_json


DEFAULT_HORROR_HOOK = "村里老人说，夜里不能回头看井口。"
HORROR_STRUCTURE = [
    ("A1", "开场禁忌", "taboo"),
    ("A2", "触犯规则", "omen"),
    ("A3", "异象升级", "escalation"),
    ("A4", "真相反转", "reveal"),
    ("A5", "结尾钩子", "hook"),
]
HORROR_LOCATIONS = ["老宅堂屋", "村口枯井", "雾气山路", "祖坟边", "废弃祠堂"]
HORROR_CHARACTERS = ["返乡青年", "守夜老人", "失踪母亲"]
AVOIDANCE_STRATEGIES = ["back_view", "silhouette", "close_up", "object", "fog", "dark_light"]
SOUND_CUES = ["低频风声", "木门吱呀", "远处铃声", "井底水滴", "纸钱摩擦", "压低的人声"]
VISUAL_MOTIFS = ["符纸", "红绳", "旧照片", "白瓷碗", "黑伞", "门缝"]


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def normalize_hook(hook: str) -> str:
    cleaned = hook.strip()
    return cleaned or DEFAULT_HORROR_HOOK


def build_horror_story_blueprint(
    hook: str,
    episode_code: str = "E01",
    target_seconds: int = 360,
    max_shots: int = 60,
) -> dict[str, Any]:
    normalized_hook = normalize_hook(hook)
    target_seconds = clamp_int(target_seconds, 300, 420)
    max_shots = clamp_int(max_shots, 40, 60)
    shot_duration = 6
    shot_count = clamp_int(round(target_seconds / shot_duration), 40, max_shots)
    target_seconds = shot_count * shot_duration
    act_shot_count = shot_count // len(HORROR_STRUCTURE)
    remainder = shot_count % len(HORROR_STRUCTURE)
    acts = []
    for index, (act_id, title, beat) in enumerate(HORROR_STRUCTURE):
        shots_in_act = act_shot_count + (1 if index < remainder else 0)
        acts.append(
            {
                "act_id": act_id,
                "title": title,
                "horror_beat": beat,
                "target_seconds": shots_in_act * shot_duration,
                "shot_count": shots_in_act,
                "purpose": build_act_purpose(title, normalized_hook),
            }
        )
    return {
        "blueprint_version": "horror_content_factory/v1",
        "episode_code": episode_code,
        "title": title_from_hook(normalized_hook),
        "hook": normalized_hook,
        "genre": "玄学/民俗恐怖",
        "target_platform": "竖屏短视频",
        "aspect_ratio": "9:16",
        "target_seconds": target_seconds,
        "shot_count": shot_count,
        "shot_duration_seconds": shot_duration,
        "acts": acts,
        "taboos": [
            "夜里听见有人叫名字不能答应",
            "经过枯井不能回头",
            "红绳断开前不能进祠堂",
        ],
        "twist": "所谓鬼怪不是来害人，而是在阻止主角重复上一代人的死法。",
        "characters": [
            {"name": HORROR_CHARACTERS[0], "role": "主视角", "visual_rule": "多用背影、手部和侧脸，减少正脸连续性要求"},
            {"name": HORROR_CHARACTERS[1], "role": "规则讲述者", "visual_rule": "草帽、烟袋、佝偻背影作为识别锚点"},
            {"name": HORROR_CHARACTERS[2], "role": "真相线索", "visual_rule": "旧照片、红绳和白衣轮廓作为识别锚点"},
        ],
        "locations": HORROR_LOCATIONS,
        "visual_rules": [
            "优先暗光、雾、遮挡、背影、门缝和物件特写",
            "每幕只保留 1 个核心场景，减少跨场景连续性压力",
            "不要要求画面直接出现字幕、角色名或可读文字",
        ],
        "continuity_anchors": VISUAL_MOTIFS,
    }


def build_act_purpose(title: str, hook: str) -> str:
    if title == "开场禁忌":
        return f"用一句禁忌把观众钩住：{hook}"
    if title == "触犯规则":
        return "主角为了找人或找真相，主动做了老人警告不能做的事。"
    if title == "异象升级":
        return "连续出现不合常理的物件、声音和背影，把风险推高。"
    if title == "真相反转":
        return "揭示规则背后的真实原因，让前面异象重新成立。"
    return "留下下一集必须点击的未解画面或一句话。"


def title_from_hook(hook: str) -> str:
    trimmed = hook.strip("。！？!? ")
    if len(trimmed) <= 18:
        return trimmed
    return f"{trimmed[:18]}..."


def build_horror_episode_manifest(
    blueprint: dict[str, Any],
    project_id: str = "aicomic_system",
    season: int = 1,
) -> dict[str, Any]:
    episode_code = str(blueprint.get("episode_code", "E01"))
    shots: list[dict[str, Any]] = []
    global_index = 1
    for act in blueprint.get("acts", []):
        act_id = str(act["act_id"])
        horror_beat = str(act["horror_beat"])
        act_title = str(act["title"])
        for act_index in range(1, int(act["shot_count"]) + 1):
            shot_id = f"S{global_index:02d}"
            location = HORROR_LOCATIONS[(global_index - 1) % len(HORROR_LOCATIONS)]
            motif = VISUAL_MOTIFS[(global_index - 1) % len(VISUAL_MOTIFS)]
            avoidance = AVOIDANCE_STRATEGIES[(global_index - 1) % len(AVOIDANCE_STRATEGIES)]
            sound_cue = SOUND_CUES[(global_index - 1) % len(SOUND_CUES)]
            shots.append(
                {
                    "shot_id": shot_id,
                    "duration": int(blueprint.get("shot_duration_seconds", 6)),
                    "scene": location,
                    "characters": select_characters_for_beat(horror_beat),
                    "visual": build_shot_visual(act_title, horror_beat, location, motif, avoidance, act_index),
                    "action": build_shot_action(horror_beat, motif, act_index),
                    "dialogue": build_shot_dialogue(blueprint, act_title, horror_beat, act_index),
                    "emotion": build_shot_emotion(horror_beat),
                    "camera": build_camera_rule(avoidance),
                    "ai_video": global_index % 3 == 0,
                    "priority": "high" if act_index in {1, int(act["shot_count"])} else "medium",
                    "act_id": act_id,
                    "horror_beat": horror_beat,
                    "continuity_anchor": motif,
                    "avoidance_strategy": avoidance,
                    "sound_cue": sound_cue,
                    "regeneration_reason": "",
                }
            )
            global_index += 1
    episode = {
        "episode_code": episode_code,
        "title": str(blueprint.get("title", "民俗禁忌夜")),
        "status": "shotlist_ready",
        "publish_title": f"老人说这条禁忌千万别犯：{str(blueprint.get('title', '民俗禁忌夜'))}",
        "cover_text": "夜里千万别回头",
        "creator_goal": "产出第一条 5-10 分钟玄学/民俗恐怖漫剧样片。",
        "ending_hook": str(blueprint.get("twist", "")),
        "shots": shots,
    }
    return {
        "project_id": project_id,
        "season": season,
        "episodes": [episode],
    }


def select_characters_for_beat(horror_beat: str) -> list[str]:
    if horror_beat in {"taboo", "omen"}:
        return [HORROR_CHARACTERS[0], HORROR_CHARACTERS[1]]
    if horror_beat == "reveal":
        return [HORROR_CHARACTERS[0], HORROR_CHARACTERS[2]]
    return [HORROR_CHARACTERS[0]]


def build_shot_visual(
    act_title: str,
    horror_beat: str,
    location: str,
    motif: str,
    avoidance: str,
    act_index: int,
) -> str:
    avoidance_text = {
        "back_view": "主角背影停在画面前景",
        "silhouette": "远处只出现模糊人影轮廓",
        "close_up": f"{motif} 的极近特写占满画面",
        "object": f"{motif} 被风吹动，周围没有人",
        "fog": "雾从地面压过来，人物轮廓若隐若现",
        "dark_light": "暗光里只有一束冷色手电光",
    }[avoidance]
    return f"{location}，{act_title}第 {act_index} 个镜头，{avoidance_text}，民俗恐怖氛围，{horror_beat} 节拍。"


def build_shot_action(horror_beat: str, motif: str, act_index: int) -> str:
    if horror_beat == "taboo":
        return f"守夜老人压低声音指向 {motif}，主角停下脚步。"
    if horror_beat == "omen":
        return f"主角触碰 {motif} 后，远处传来不该出现的脚步声。"
    if horror_beat == "escalation":
        return f"{motif} 自己移动了半寸，镜头缓慢推近。"
    if horror_beat == "reveal":
        return f"主角发现 {motif} 和母亲失踪那晚有关。"
    return f"画面停在 {motif} 上，黑暗里有人叫出主角的名字。"


def build_shot_dialogue(blueprint: dict[str, Any], act_title: str, horror_beat: str, act_index: int) -> str:
    hook = str(blueprint.get("hook", DEFAULT_HORROR_HOOK))
    if horror_beat == "taboo" and act_index == 1:
        return hook
    if horror_beat == "reveal" and act_index == 1:
        return "我终于明白，村里人怕的不是鬼，是当年被藏起来的真相。"
    if horror_beat == "hook" and act_index >= 3:
        return "如果你听见井底有人叫你的名字，千万不要答应。"
    return f"{act_title}，第 {act_index} 个线索出现。"


def build_shot_emotion(horror_beat: str) -> str:
    return {
        "taboo": "压低、禁忌、悬念",
        "omen": "不安、试探、异样",
        "escalation": "惊惧、逼近、失控",
        "reveal": "震惊、悲凉、真相",
        "hook": "未解、寒意、强钩子",
    }[horror_beat]


def build_camera_rule(avoidance: str) -> str:
    return {
        "back_view": "背影中景，缓慢推进",
        "silhouette": "远景定镜，雾中轮廓",
        "close_up": "极近特写，浅景深",
        "object": "物件特写，轻微摇晃",
        "fog": "低角度广角，雾气遮挡",
        "dark_light": "暗光手持感，慢慢扫过",
    }[avoidance]


def write_horror_blueprint(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def write_horror_episode_manifest(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)
