from __future__ import annotations

from math import ceil


DEFAULT_PIPELINE_STEPS = [
    "project_setup",
    "story_bible",
    "episode_outline",
    "shot_breakdown",
    "asset_generation",
    "tts_subtitle",
    "preview_render",
    "publish_pack",
]


def build_creator_profile(
    project_name: str,
    genre: str,
    style: str,
    logline: str,
    protagonist_name: str,
    target_audience: str,
    tone: str,
    season_hook: str,
    episode_target_count: int,
) -> dict[str, object]:
    return {
        "project_name": project_name,
        "genre": genre,
        "style_profile": style,
        "logline": logline,
        "protagonist_name": protagonist_name,
        "target_audience": target_audience,
        "tone": tone,
        "season_hook": season_hook,
        "episode_target_count": episode_target_count,
        "working_mode": "creator_single_user",
        "workflow_goal": "idea_to_episode_release",
        "pipeline_steps": list(DEFAULT_PIPELINE_STEPS),
    }


def build_story_bible(
    project_name: str,
    genre: str,
    logline: str,
    protagonist_name: str,
    tone: str,
    season_hook: str,
) -> dict[str, object]:
    return {
        "project_name": project_name,
        "genre": genre,
        "concept_logline": logline,
        "tone_keywords": [item for item in [tone, "强钩子", "情绪反转", "短剧节奏"] if item],
        "core_conflict": f"{protagonist_name} 必须在高压环境中完成身份反转，并持续制造每集反转钩子。",
        "season_hook": season_hook,
        "world_rules": [
            "单集时长优先控制在 45-90 秒。",
            "每集必须在前 3 个镜头内抛出冲突或悬念。",
            "每集结尾保留下一集强钩子。",
        ],
        "narrative_beats": [
            "被压制或误判",
            "信息反转",
            "身份/关系升级",
            "留出下一集钩子",
        ],
    }


def build_character_bible(protagonist_name: str) -> dict[str, object]:
    return {
        "characters": [
            {
                "name": protagonist_name,
                "role": "主角",
                "function": "承载观众代入与反转升级",
                "visual_notes": ["五官清晰", "情绪表达强", "适配 9:16 近景"],
                "voice_notes": ["普通话", "情绪克制后爆发", "适合短句台词"],
            },
            {
                "name": "对手角色",
                "role": "反派/阻力源",
                "function": "制造压迫感、误解和冲突",
                "visual_notes": ["辨识度高", "表情锋利", "适合对峙构图"],
                "voice_notes": ["语速更快", "压迫感更强"],
            },
            {
                "name": "关键助推角色",
                "role": "男主/盟友/信息源",
                "function": "承担反转落点与身份揭示",
                "visual_notes": ["冷静、强势、镜头存在感强"],
                "voice_notes": ["短句、压场、低情绪波动"],
            },
        ],
    }


def build_style_bible(style: str, tone: str) -> dict[str, object]:
    return {
        "style_profile": style,
        "tone": tone,
        "aspect_ratio": "9:16",
        "visual_direction": [
            "人物和情绪特写优先",
            "中近景为主，少量建立镜头",
            "画面信息聚焦在角色冲突",
        ],
        "shot_guidelines": [
            "每镜头 2-4 秒为主",
            "对白镜头优先稳镜或轻推进",
            "非关键镜头允许静态图加转场",
        ],
        "asset_strategy": {
            "image": "single_keyframe_then_reuse",
            "video": "use_motion_only_for_high_priority_hooks",
            "tts": "one_voice_per_core_character",
        },
    }


def build_episode_blueprint(
    episode_target_count: int,
    protagonist_name: str,
    season_hook: str,
) -> dict[str, object]:
    normalized_count = max(1, min(episode_target_count, 24))
    arc_count = max(1, ceil(normalized_count / 3))
    arcs = []
    for index in range(1, arc_count + 1):
        arcs.append(
            {
                "arc_id": f"A{index:02d}",
                "title": f"阶段剧情 {index}",
                "goal": f"推动 {protagonist_name} 的身份反转或关系升级",
                "episodes": [f"E{item:02d}" for item in range((index - 1) * 3 + 1, min(index * 3, normalized_count) + 1)],
            }
        )
    episodes = []
    for index in range(1, normalized_count + 1):
        episodes.append(
            {
                "episode_code": f"E{index:02d}",
                "title": f"第 {index} 集待补标题",
                "story_goal": f"围绕 {protagonist_name} 推进一次冲突与一次钩子回收",
                "ending_hook": season_hook if index == 1 else "下一集钩子待补充",
                "suggested_shot_count": 8 if index == 1 else 10,
                "status": "seeded" if index == 1 else "planned",
            }
        )
    return {
        "episode_target_count": normalized_count,
        "arcs": arcs,
        "episodes": episodes,
    }


def build_prompt_pack_template(
    project_name: str,
    genre: str,
    style: str,
    protagonist_name: str,
    tone: str,
) -> dict[str, object]:
    return {
        "project_name": project_name,
        "image_prompt_template": (
            f"{genre}，{style}，主角 {protagonist_name}，竖屏短剧镜头，情绪={tone}，"
            "突出人物关系、构图清晰、服装统一、适合 9:16。"
        ),
        "video_prompt_template": (
            "在保持人物一致性的前提下，增加轻微推拉、视线变化或手部动作，"
            "重点强化情绪和钩子，不追求大幅复杂运动。"
        ),
        "tts_prompt_template": "台词短句优先，停顿明确，单句 4-12 个字，避免口播腔。",
        "subtitle_rule": "字幕一行不超过 14 个汉字，情绪重音词尽量落在末尾。",
    }


def build_release_checklist_markdown(project_name: str) -> str:
    return "\n".join(
        [
            f"# {project_name} Creator 发布检查单",
            "",
            "- [ ] 世界观 / 角色 / 风格设定已补齐",
            "- [ ] 至少 1 集剧本已确认",
            "- [ ] Shot list 已完成并标记高优镜头",
            "- [ ] 图片 / 视频 / TTS 产物已齐备",
            "- [ ] 预览版已导出并人工看过一遍",
            "- [ ] 字幕时间轴已检查",
            "- [ ] 发布标题 / 封面文案 / 简介已生成",
            "- [ ] 成片、字幕、封面与发布文案已归档",
        ]
    )
