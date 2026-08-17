# -*- coding: utf-8 -*-
"""
romance_pipeline.py — 都市爱情动漫剧蓝图+manifest生成

题材: 都市爱情动漫剧
结构: 偶遇→误会→心动→告白→结局
"""

from __future__ import annotations
from typing import Any
from aicomic.core.manifest import write_json


DEFAULT_ROMANCE_HOOK = "暴雨夜，她闯进他的便利店，浑身湿透，手里攥着一封被雨打湿的情书。"

ROMANCE_STRUCTURE = [
    ("A1", "命运偶遇", "meet_cute"),
    ("A2", "欢喜冤家", "bickering"),
    ("A3", "心动暗涌", "sparks"),
    ("A4", "真情告白", "confession"),
    ("A5", "甜蜜结局", "sweet_ending"),
]

ROMANCE_LOCATIONS = ["深夜便利店", "城市天桥", "咖啡馆落地窗", "樱花街道", "公寓楼下", "地铁车厢", "公司天台", "雨中街角"]
ROMANCE_CHARACTERS = ["便利店男孩", "都市女孩"]
VISUAL_MOTIFS = ["雨伞", "情书", "咖啡杯", "樱花瓣", "手机屏幕", "围巾"]
SOUND_CUES = ["雨声", "便利店门铃", "城市白噪音", "心跳音效", "风铃声", "轻音乐"]

EMOTION_MAP = {
    "meet_cute": "惊讶、好奇、微微尴尬",
    "bickering": "嘴硬、好笑、暗暗在意",
    "sparks": "心跳加速、不敢对视、偷偷微笑",
    "confession": "紧张、真诚、鼓起勇气",
    "sweet_ending": "温暖、甜蜜、安心",
}

CAMERA_MAP = {
    "meet_cute": "中景双人构图，便利店暖光",
    "bickering": "正反打近景，快速切换",
    "sparks": "特写眼神交流，浅景深",
    "confession": "侧面近景，柔和逆光",
    "sweet_ending": "双人全景，暖色调",
}

DIALOGUE_TEMPLATES = {
    "meet_cute": [
        "这么大的雨，你没事吧？",
        "便利店还开着，进来躲躲吧。",
        "你手里那封信...是被雨淋湿了吗？",
    ],
    "bickering": [
        "谁让你上次不等我的！",
        "嘴上说不要，身体很诚实嘛。",
        "我又不是故意迟到的，地铁故障怪我咯？",
    ],
    "sparks": [
        "他转头的瞬间，正好对上她的目光。",
        "心跳得好快，一定是因为咖啡太浓了。",
        "偷偷看他认真的侧脸，忍不住嘴角上扬。",
    ],
    "confession": [
        "其实...从那个雨夜起，我就一直在想你。",
        "我不是因为雨才撑伞的，是因为你在对面。",
        "这封信，我想亲手交给你，不管结果怎样。",
    ],
    "sweet_ending": [
        "原来最幸运的事，是那场暴雨让我遇见你。",
        "以后每个雨天，都有我撑伞。",
        "她靠在他肩上，雨后的城市亮起了万家灯火。",
    ],
}

VISUAL_TEMPLATES = {
    "meet_cute": "深夜便利店暖光下，{char_a}正在整理货架，门铃响起，{char_b}浑身湿透冲进来，手里攥着一封被雨打湿的信封，两人四目相对。",
    "bickering": "{loc}，{char_a}和{char_b}并排走着，{char_a}故意把伞往自己这边偏，{char_b}假装生气地扯回来，两人嘴上互怼但嘴角都带着笑。",
    "sparks": "{loc}，{char_a}低头看手机，{char_b}悄悄从侧面看他认真的侧脸，咖啡杯上的热气模糊了画面，心跳声盖过了城市噪音。",
    "confession": "{loc}，{char_a}深呼吸后转向{char_b}，手里攥着那封被雨水晕开的信，夕阳从背后照过来，两人影子在地面交叠。",
    "sweet_ending": "{loc}，{char_a}撑着伞，{char_b}靠在他肩上，雨后的城市万家灯火亮起，樱花瓣飘过两人头顶，温暖收尾。",
}


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def build_romance_story_blueprint(
    hook: str,
    episode_code: str = "E01",
    target_seconds: int = 240,
    max_shots: int = 6,
) -> dict[str, Any]:
    normalized_hook = hook.strip() or DEFAULT_ROMANCE_HOOK
    shot_duration = 6
    shot_count = clamp_int(max_shots, 6, 12)
    act_shot_count = shot_count // len(ROMANCE_STRUCTURE)
    remainder = shot_count % len(ROMANCE_STRUCTURE)

    acts = []
    for index, (act_id, title, beat) in enumerate(ROMANCE_STRUCTURE):
        shots_in_act = act_shot_count + (1 if index < remainder else 0)
        acts.append({
            "act_id": act_id,
            "title": title,
            "romance_beat": beat,
            "target_seconds": shots_in_act * shot_duration,
            "shot_count": shots_in_act,
            "purpose": _build_act_purpose(title, normalized_hook),
        })

    return {
        "blueprint_version": "romance_content_factory/v1",
        "episode_code": episode_code,
        "title": normalized_hook[:18] + ("..." if len(normalized_hook) > 18 else ""),
        "hook": normalized_hook,
        "genre": "都市爱情动漫剧",
        "target_platform": "竖屏短视频",
        "aspect_ratio": "9:16",
        "target_seconds": shot_count * shot_duration,
        "shot_count": shot_count,
        "shot_duration_seconds": shot_duration,
        "acts": acts,
        "characters": [
            {"name": ROMANCE_CHARACTERS[0], "role": "男主", "visual_rule": "便利店围裙、温柔笑容、整理货架的日常感"},
            {"name": ROMANCE_CHARACTERS[1], "role": "女主", "visual_rule": "都市穿搭、湿发凌乱感、倔强但心软的表情"},
        ],
        "locations": ROMANCE_LOCATIONS,
        "visual_rules": [
            "优先暖色调、柔光、浅景深",
            "每场只保留1个核心场景",
            "角色表情和眼神交流是重点",
        ],
        "continuity_anchors": VISUAL_MOTIFS,
    }


def _build_act_purpose(title: str, hook: str) -> str:
    if title == "命运偶遇":
        return f"雨夜偶遇建立初印象：{hook}"
    if title == "欢喜冤家":
        return "日常互动中展现性格反差和化学反应。"
    if title == "心动暗涌":
        return "细节暗示双方心动，但还没说破。"
    if title == "真情告白":
        return "鼓起勇气告白，呼应开头的情书。"
    return "甜蜜收尾，留下余韵。"


def build_romance_episode_manifest(
    blueprint: dict[str, Any],
    project_id: str = "aicomic_system",
    season: int = 1,
) -> dict[str, Any]:
    episode_code = str(blueprint.get("episode_code", "E01"))
    shots: list[dict[str, Any]] = []
    global_index = 1

    for act in blueprint.get("acts", []):
        beat = str(act["romance_beat"])
        act_title = str(act["title"])
        for _ in range(int(act["shot_count"])):
            shot_id = f"S{global_index:02d}"
            loc = ROMANCE_LOCATIONS[(global_index - 1) % len(ROMANCE_LOCATIONS)]
            motif = VISUAL_MOTIFS[(global_index - 1) % len(VISUAL_MOTIFS)]
            sound = SOUND_CUES[(global_index - 1) % len(SOUND_CUES)]
            emotion = EMOTION_MAP.get(beat, "温暖、心动")
            camera = CAMERA_MAP.get(beat, "中景双人构图，暖色调")

            char_a = ROMANCE_CHARACTERS[0]
            char_b = ROMANCE_CHARACTERS[1]
            visual = VISUAL_TEMPLATES.get(beat, f"{loc}，{char_a}和{char_b}的都市爱情日常，{motif}作为视觉锚点。")
            visual = visual.format(loc=loc, char_a=char_a, char_b=char_b, motif=motif)

            dialogues = DIALOGUE_TEMPLATES.get(beat, ["..."])
            dialogue = dialogues[(global_index - 1) % len(dialogues)]

            shots.append({
                "shot_id": shot_id,
                "duration": int(blueprint.get("shot_duration_seconds", 6)),
                "scene": loc,
                "characters": [char_a, char_b],
                "visual": visual,
                "action": f"{char_a}和{char_b}在{loc}的互动，情绪：{emotion}",
                "dialogue": dialogue,
                "emotion": emotion,
                "camera": camera,
                "ai_video": False,
                "priority": "high",
                "act_id": str(act["act_id"]),
                "act_title": act_title,
                "sound_cue": sound,
                "motif": motif,
            })
            global_index += 1

    return {
        "episodes": [{
            "episode_code": episode_code,
            "title": str(blueprint.get("title", "都市爱情")),
            "status": "draft",
            "publish_title": str(blueprint.get("hook", "")),
            "cover_text": str(blueprint.get("hook", ""))[:30],
            "creator_goal": "用6个镜头讲完一段都市爱情的偶遇到告白",
            "ending_hook": "下次雨天，便利店的门铃还会为你响起吗？",
            "shots": shots,
        }],
        "project_id": project_id,
        "season": season,
    }
