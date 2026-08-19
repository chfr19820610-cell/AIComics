from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from aicomic.core.models import JobRecord, ProviderRequestRecord
from aicomic.utils.atomic_io import atomic_write_json
from aicomic.providers.provider_planner import build_provider_plan, resolve_provider_profile

# Optional prompt enhancement (fused from Omni-Rewriter + prompt-optimizer)
from .prompt_enhancer import enhance_prompt, auto_select_profile, enhance_by_intent


class ProviderRequestBuildError(RuntimeError):
    def __init__(self, skipped_jobs: list[dict[str, str]]) -> None:
        self.skipped_jobs = skipped_jobs
        super().__init__(f"Provider 请求包构建失败，发现 {len(skipped_jobs)} 个无效任务。")


def index_episode_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    episodes: dict[str, dict[str, Any]] = {}
    for episode in manifest.get("episodes", []):
        shot_index = {
            str(shot["shot_id"]): shot
            for shot in episode.get("shots", [])
        }
        episodes[str(episode["episode_code"])] = {
            "episode": episode,
            "shots": shot_index,
        }
    return episodes


def parse_shot_id_from_job(job_id: str) -> str:
    parts = job_id.split("_")
    if len(parts) < 4:
        return ""
    return parts[2]


def resolve_endpoint(provider: str, job_type: str) -> str:
    if provider == "openai_image":
        return "/v1/images/generations"
    if provider == "local_comfyui_image":
        return "/local/comfyui/prompt"
    if provider == "openai_tts":
        return "/v1/audio/speech"
    if provider == "sora":
        return "/v1/videos"
    if provider == "local_comfyui_video":
        return "/local/comfyui/video"
    if provider == "manual_web":
        return "/manual/web-submit"
    if provider == "windows_tts":
        return "/local/windows-tts"
    if provider == "local_piper_tts":
        return "/local/piper-tts"
    return f"/providers/{provider}/{job_type}"


def _build_quality_suffix(shot: dict[str, Any]) -> str:
    """Select composition, lighting, and style instructions based on shot type (English output for SDXL/H3)."""
    scene = str(shot.get("scene", ""))
    camera = str(shot.get("camera", ""))
    emotion = str(shot.get("emotion", ""))

    # ── Composition ──
    if any(k in camera for k in ("特写", "近景", "close", "极近")):
        composition = ("Composition: shallow depth of field, subject prominent, "
                       "rule of thirds placing eyes on upper third line, soft bokeh background. ")
    elif any(k in camera for k in ("中景", "medium", "双人")):
        composition = ("Composition: medium shot, symmetrical or diagonal framing, "
                       "leading lines via character gaze direction, breathing room in foreground. ")
    elif any(k in camera for k in ("远景", "全景", "wide", "远")):
        composition = ("Composition: environment-dominant, leading lines (roads, architecture, natural contours) "
                       "guide the eye to the subject, foreground framing (doorways, windows, branches) adds depth. ")
    else:
        composition = ("Composition: rule of thirds, subject off-center, leading lines reinforce visual flow, "
                       "clear foreground/background layering. ")

    # ── Lighting ──
    if any(k in emotion for k in ("恐惧", "阴", "dark", "惊悚", "诡异")):
        lighting = ("Lighting: low-key dramatic, Rembrandt side-light sculpts facial contours, "
                    "rim light separates subject from background, shadow detail preserved. ")
    elif any(k in emotion for k in ("温柔", "浪漫", "温馨", "平静", "柔和", "心动", "心跳", "甜蜜", "安心", "暖")):
        lighting = ("Lighting: soft diffused illumination, golden backlit rim light, "
                    "gentle fill on face, highlights bloom, shadows transition smoothly. ")
    elif any(k in emotion for k in ("愤怒", "激烈", "战斗", "紧张", "爆发")):
        lighting = ("Lighting: hard high-contrast, three-point setup (key + side-rim + fill) enhances dimension, "
                    "strong shadows add dramatic tension, highlight areas reveal detail. ")
    else:
        lighting = ("Lighting: professional three-point setup, key light shapes the subject, "
                    "side-rim light defines edges, fill preserves shadow detail; balanced contrast, rich layers. ")

    # ── Style ──
    if any(k in scene for k in ("夜", "暗", "黑暗", "室内暗")):
        style = ("Style: high-detail anime illustration, night scenes use cool color temperature (blue-purple), "
                 "warm light sources (amber) create color contrast; preserve shadow detail, avoid noise and banding. ")
    elif any(k in scene for k in ("白天", "户外", "阳光", "外景")):
        style = ("Style: high-detail anime illustration, daylight scenes use warm color temperature, "
                 "highlights not blown out, shadows have color cast (cool blue bounce); "
                 "smooth sky gradients, no banding. ")
    else:
        style = ("Style: high-detail anime illustration, harmonious color palette, smooth light transitions, "
                 "clean linework, rich but uncluttered background detail. ")

    # ── Negative (embedded in prompt — gpt-image-1.5 has no separate negative_prompt param) ──
    negative = ("Avoid: text, subtitles, titles, speech bubbles, logos, watermarks; "
                "distorted hands, extra fingers or toes; deformed faces, misaligned features; "
                "blur, pixelation, color blocks, banding; mirror flips or framing imbalance. "
                "Character face, hair color, and clothing must remain consistent throughout the episode.")

    return f"{composition}{lighting}{style}{negative}"


def build_image_prompt(episode_title: str, shot: dict[str, Any], char_service: Any = None, project_id: str = "") -> str:
    if is_horror_shot(shot):
        return build_horror_visual_prompt(shot, motion=False)
    characters = ", ".join(str(item) for item in shot.get("characters", []))
    horror_context = build_horror_prompt_context(shot)
    quality_suffix = _build_quality_suffix(shot)
    base_prompt = (
        f"Anime illustration, episode \"{episode_title}\", scene: {shot['scene']}. "
        f"Characters: {characters}. "
        f"Visual: {shot['visual']}. "
        f"Action: {shot['action']}. "
        f"Emotion: {shot['emotion']}. "
        f"Shot: {shot['camera']}. "
        f"{horror_context}"
        f"{quality_suffix} "
        "High contrast, strong dramatic tension, short-drama cover-quality rendering."
    )
    if char_service is not None:
        try:
            from aicomic.characters.prompt_injector import enhance_image_prompt
            shot_characters = shot.get("characters", [])
            return enhance_image_prompt(base_prompt, shot_characters, char_service, project_id)
        except Exception:
            pass
    return base_prompt


def build_video_prompt(episode_title: str, shot: dict[str, Any], char_service: Any = None, project_id: str = "") -> str:
    if is_horror_shot(shot):
        return build_horror_visual_prompt(shot, motion=True)
    characters = ", ".join(str(item) for item in shot.get("characters", []))
    horror_context = build_horror_prompt_context(shot)
    quality_suffix = _build_quality_suffix(shot)
    base_prompt = (
        f"Anime dynamic shot, episode \"{episode_title}\". "
        f"Characters: {characters}. "
        f"Scene: {shot['scene']}. "
        f"Visual: {shot['visual']}. "
        f"Action: {shot['action']}. "
        f"Emotion: {shot['emotion']}. "
        f"Camera: {shot['camera']}. "
        f"{horror_context}"
        f"{quality_suffix} "
        "Duration 3-4 seconds, stable camera, emphasize character emotional shifts, maintain consistent face, hair, and clothing."
    )
    if char_service is not None:
        try:
            from aicomic.characters.prompt_injector import enhance_image_prompt
            shot_characters = shot.get("characters", [])
            return enhance_image_prompt(base_prompt, shot_characters, char_service, project_id)
        except Exception:
            pass
    return base_prompt


def build_h3_video_prompt(episode_title: str, shot: dict[str, Any], char_service: Any = None, project_id: str = "") -> str:
    """将shot数据转成H3官方3字段格式（integrated_multimodal_description + overall_soundscape + non_diegetic_music）。"""
    # horror shot 走独立路径
    if is_horror_shot(shot):
        return build_horror_visual_prompt(shot, motion=True)

    characters = "、".join(str(item) for item in shot.get("characters", []))
    scene = str(shot.get("scene", ""))
    visual = str(shot.get("visual", ""))
    action = str(shot.get("action", ""))
    emotion = str(shot.get("emotion", ""))
    camera = str(shot.get("camera", ""))
    dialogue = str(shot.get("dialogue", "")).strip()
    duration = shot.get("duration", 4)

    # ── 运镜映射（中文→H3官方英文）──
    CAMERA_MAP = [
        ("推近", "Push In"), ("推进", "Push In"),
        ("拉远", "Pull Out"), ("拉出", "Pull Out"),
        ("左摇", "Pan Left"),
        ("右摇", "Pan Right"),
        ("上摇", "Tilt Up"), ("仰拍", "Tilt Up"),
        ("下摇", "Tilt Down"), ("俯拍", "Tilt Down"),
        ("跟拍", "Tracking Shot"), ("跟随", "Tracking Shot"),
        ("环绕", "Arc Shot"),
        ("固定", "Static Shot"), ("静止", "Static Shot"),
        ("手持", "Shake Slightly"),
        ("主观", "POV"),
    ]
    camera_motion = "holds a static shot"
    for cn, en in CAMERA_MAP:
        if cn in camera:
            camera_motion = {
                "Push In": "pushes in with small amplitude at slow speed",
                "Pull Out": "pulls out with small amplitude at slow speed",
                "Pan Left": "pans left with small amplitude",
                "Pan Right": "pans right with small amplitude",
                "Tilt Up": "tilts up with small amplitude",
                "Tilt Down": "tilts down with small amplitude",
                "Tracking Shot": "tracks the subject with small amplitude",
                "Arc Shot": "arcs around the subject with small amplitude",
                "Static Shot": "holds a static shot",
                "Shake Slightly": "shakes slightly",
                "POV": "adopts the subject's point of view",
            }.get(en, "holds a static shot")
            break

    # ── 场景中文→英文翻译（常见漫剧场景）──
    SCENE_MAP = [
        ("老井", "an old well at night"), ("老宅", "an abandoned old house interior"),
        ("堂屋", "an ancestral hall interior"), ("祠堂", "a deserted ancestral shrine"),
        ("村口", "a village entrance"), ("山路", "a mountain road"),
        ("坟", "a graveyard"), ("井口", "a dry well opening"),
        ("室内", "an indoor room"), ("室外", "an outdoor scene"),
        ("街道", "a city street"), ("办公室", "an office"),
        ("教室", "a classroom"), ("卧室", "a bedroom"),
        ("走廊", "a corridor"), ("门口", "a doorway"),
    ]
    scene_en = scene
    for cn, en in SCENE_MAP:
        if cn in scene:
            scene_en = en
            break
    if scene_en == scene:
        scene_en = f"a location described as {scene}"

    # ── 运镜描述（景别，英文）──
    camera_desc_map = [
        ("背影", "shot from behind"),
        ("特写", "close-up shot"),
        ("近景", "medium-close shot"),
        ("中景", "medium shot"),
        ("远景", "wide shot"),
        ("全景", "wide shot"),
        ("局部", "extreme close-up"),
    ]
    camera_desc = "medium shot"
    for cn, en in camera_desc_map:
        if cn in camera:
            camera_desc = en
            break

    # ── 多角色对话分配 ──
    dialogue_section = ""
    if dialogue:
        char_list = shot.get("characters", [])
        # 多角色时按顺序分配S1/S2
        if len(char_list) >= 2:
            speaker = f"The {char_list[0]}"
            dialogue_section = f"{speaker} (S1) says: <d>[Chinese] {dialogue}</d>"
        else:
            speaker = f"The {char_list[0]}" if char_list else "A character"
            dialogue_section = f"{speaker} (S1) says: <d>[Chinese] {dialogue}</d>"
    EMOTION_MAP = [
        (("恐惧", "紧张", "诡异", "阴", "惊悚", "压迫", "悬念", "禁忌"), "fear and tension"),
        (("温柔", "浪漫", "温馨", "平静", "柔和"), "warmth and tenderness"),
        (("愤怒", "激烈", "战斗", "爆发"), "anger and intensity"),
        (("悲伤", "忧伤", "失落"), "sadness and melancholy"),
        (("欢乐", "开心", "喜悦"), "joy and lightness"),
    ]
    emotion_desc = "a neutral emotional tone"
    for keywords, desc in EMOTION_MAP:
        if any(k in emotion for k in keywords):
            emotion_desc = desc
            break

    # ── 情绪→音效推导 ──
    SOUND_MAP = [
        (("恐惧", "紧张", "诡异", "阴", "惊悚", "压迫", "悬念", "禁忌"),
         "Wind whistles through cracks, creaking floorboards, distant whispers"),
        (("温柔", "浪漫", "温馨", "平静", "柔和"),
         "Soft ambient sounds, gentle breeze, quiet footsteps"),
        (("愤怒", "激烈", "战斗", "爆发"),
         "Heavy impacts, rapid footsteps, sharp breathing"),
        (("悲伤", "忧伤", "失落"),
         "Muffled ambient sounds, slow breathing, distant echo"),
        (("欢乐", "开心", "喜悦"),
         "Bright ambient sounds, light footsteps, soft laughter"),
    ]
    sound_desc = "Ambient environmental sounds with subtle movement"
    for keywords, desc in SOUND_MAP:
        if any(k in emotion for k in keywords):
            sound_desc = desc
            break

    # ── 情绪→配乐推导 ──
    MUSIC_MAP = [
        (("恐惧", "紧张", "诡异", "阴", "惊悚", "压迫", "悬念", "禁忌"),
         "Sparse high piano notes at slow tempo with low drone strings building tension"),
        (("温柔", "浪漫", "温馨", "平静", "柔和"),
         "Soft acoustic guitar at moderate tempo with gentle string pads"),
        (("愤怒", "激烈", "战斗", "爆发"),
         "Driving percussion with aggressive string staccato at fast tempo"),
        (("悲伤", "忧伤", "失落"),
         "Slow cello notes with sparse piano, gradually fading"),
        (("欢乐", "开心", "喜悦"),
         "Light ukulele strumming at upbeat tempo with bright bell accents"),
    ]
    music_desc = "Subtle ambient pad at slow tempo"
    for keywords, desc in MUSIC_MAP:
        if any(k in emotion for k in keywords):
            music_desc = desc
            break

    # ── 组装H3官方3字段格式 ──
    visual_en = visual if visual else f"{characters} in {scene_en}"
    action_en = action if action else "subtle character motion"

    h3_prompt = (
        f"integrated_multimodal_description: [Shot 1] 2D-animated, cinematic, "
        f"a {camera_desc} frames {characters} in {scene_en}. "
        f"The camera {camera_motion} as {action_en}. "
        f"The scene conveys {emotion_desc}. "
        f"{dialogue_section}\n\n"
        f"overall_soundscape: {sound_desc}\n\n"
        f"non_diegetic_music: {music_desc}"
    )

    # 角色描述注入（同build_video_prompt逻辑）
    if char_service is not None:
        try:
            from aicomic.characters.prompt_injector import enhance_image_prompt
            shot_characters = shot.get("characters", [])
            return enhance_image_prompt(h3_prompt, shot_characters, char_service, project_id)
        except Exception:
            pass
    return h3_prompt


def is_horror_shot(shot: dict[str, Any]) -> bool:
    horror_beat = shot.get("horror_beat")
    if horror_beat is None:
        return False
    return bool(str(horror_beat).strip())


def build_horror_visual_prompt(shot: dict[str, Any], motion: bool) -> str:
    scene = translate_horror_scene(str(shot.get("scene", "")).strip())
    emotion = translate_horror_emotion(str(shot.get("emotion", "")).strip())
    camera = translate_horror_camera(str(shot.get("camera", "")).strip())
    horror_beat = str(shot.get("horror_beat", "folk horror")).strip()
    avoidance_strategy = str(shot.get("avoidance_strategy", "dark_light")).strip()
    continuity_anchor = translate_horror_anchor(str(shot.get("continuity_anchor", "ritual object")).strip())
    motion_text = (
        "Subtle cinematic motion, stable camera, slow push-in, 3 to 4 seconds. "
        if motion
        else "Single vertical keyframe illustration. "
    )
    return (
        "Vertical 9:16 anime folk horror scene, no text, no subtitles, no captions, "
        "no Chinese characters, no letters, no logos, no watermark. "
        f"{motion_text}"
        f"Location: {scene}. "
        f"Visual direction: {visual_direction_for_strategy(avoidance_strategy, continuity_anchor)}. "
        f"Action: {action_for_beat(horror_beat, continuity_anchor)}. "
        f"Emotion: {emotion}. "
        f"Camera: {camera}. "
        f"Horror beat: {horror_beat}. "
        f"Continuity anchor object: {continuity_anchor}. "
        f"Character consistency avoidance strategy: {avoidance_strategy}. "
        "Use darkness, fog, back view, silhouettes, object close-ups, door gaps, low contrast moonlight. "
        "If ritual paper, photographs, bowls, door frames, grave markers, shrine plaques, wall notices, posted sheets, "
        "paper scraps, hanging labels, or any flat surface appear, keep all markings blank, abstract, torn, blurred, "
        "aged, or fully obscured. "
        "Do not draw readable words, calligraphy, talisman script, labels, stamps, seals, symbols, numbers, signage, "
        "inscriptions, or printed notices anywhere in the frame."
    )


def translate_horror_scene(value: str) -> str:
    return {
        "老宅堂屋": "an abandoned ancestral house interior",
        "村口枯井": "an old dry well at the edge of a rural village",
        "雾气山路": "a foggy mountain road at night",
        "祖坟边": "an old family graveyard under moonlight",
        "废弃祠堂": "a deserted ancestral shrine",
    }.get(value, "a rural Chinese folk horror location at night")


def translate_horror_anchor(value: str) -> str:
    return {
        "符纸": "a blank yellow ritual paper strip with torn edges and no writing",
        "红绳": "red ritual thread",
        "旧照片": "an old faded family photograph",
        "白瓷碗": "a white porcelain offering bowl",
        "黑伞": "a black umbrella",
        "门缝": "a narrow door gap",
    }.get(value, "ritual object")


def translate_horror_emotion(value: str) -> str:
    if "震惊" in value or "真相" in value:
        return "shocked, tragic, truth revealed"
    if "惊惧" in value or "失控" in value:
        return "terrified, escalating, out of control"
    if "不安" in value:
        return "uneasy, suspicious, supernatural"
    if "未解" in value or "钩子" in value:
        return "unresolved, chilling, cliffhanger"
    return "quiet dread, taboo, suspense"


def translate_horror_camera(value: str) -> str:
    if "背影" in value:
        return "medium back-view shot, slow push-in"
    if "远景" in value:
        return "distant static wide shot through fog"
    if "极近" in value:
        return "extreme close-up, shallow depth of field"
    if "物件" in value:
        return "ritual object close-up, slight handheld shake"
    if "低角度" in value:
        return "low angle wide shot with heavy fog occlusion"
    if "暗光" in value:
        return "dark handheld flashlight sweep"
    return "cinematic vertical shot, restrained camera movement"


def visual_direction_for_strategy(avoidance_strategy: str, anchor: str) -> str:
    return {
        "back_view": "a young protagonist seen only from behind in the foreground",
        "silhouette": "a distant human silhouette barely visible in fog",
        "close_up": f"an extreme close-up of {anchor}",
        "object": f"{anchor} moving slightly by itself with no person nearby",
        "fog": "thick ground fog swallowing vague human shapes",
        "dark_light": "a single cold flashlight beam cutting through darkness",
    }.get(avoidance_strategy, "a dark obstructed horror composition")


def action_for_beat(horror_beat: str, anchor: str) -> str:
    return {
        "taboo": f"an old villager silently points toward {anchor}",
        "omen": f"after the protagonist touches {anchor}, distant footsteps appear",
        "escalation": f"{anchor} shifts by itself as the camera slowly moves closer",
        "reveal": f"the protagonist realizes {anchor} is connected to a past disappearance",
        "hook": "someone whispers the protagonist's name from the darkness",
    }.get(horror_beat, "a restrained supernatural moment unfolds")


def build_horror_prompt_context(shot: dict[str, Any]) -> str:
    horror_beat = str(shot.get("horror_beat", "")).strip()
    if not horror_beat:
        return ""  # 非恐怖shot不注入任何恐怖上下文
    avoidance_strategy = str(shot.get("avoidance_strategy", "")).strip()
    continuity_anchor = str(shot.get("continuity_anchor", "")).strip()
    sound_cue = str(shot.get("sound_cue", "")).strip()
    return (
        "玄学民俗恐怖题材。"
        f"恐怖节拍：{horror_beat or '氛围悬念'}。"
        f"连续性锚点：{continuity_anchor or '核心道具'}。"
        f"规避策略：{avoidance_strategy or '暗光遮挡'}。"
        f"音效提示：{sound_cue or '低频环境声'}。"
        "优先暗光、背影、远景、局部物件、门缝、雾气，不要求稳定正脸。"
        "画面不要出现字幕、角色姓名或可读文字。"
    )


def build_tts_prompt(shot: dict[str, Any]) -> str:
    return str(shot.get("dialogue", "")).strip()


def build_request_payload(
    job: JobRecord,
    request_provider: str,
    episode_title: str,
    shot_id: str,
    shot: dict[str, Any],
    output_root: Path,
    char_service: Any = None,
    project_id: str = "",
) -> dict[str, Any]:
    if job.job_type == "image":
        result = build_image_prompt_enhanced(episode_title, shot, char_service=char_service, project_id=project_id)
        prompt = result.get("prompt", "") if isinstance(result, dict) else str(result)
        output_path = output_root / job.episode_code / "images" / f"{job.episode_code}_{shot_id}_key.png"
    elif job.job_type == "video":
        prompt = build_video_prompt(episode_title, shot, char_service=char_service, project_id=project_id)
        output_path = output_root / job.episode_code / "videos" / f"{job.episode_code}_{shot_id}_motion.mp4"
    else:
        prompt = build_tts_prompt(shot)
        output_path = output_root / job.episode_code / "audio" / f"{job.episode_code}_{shot_id}_tts.wav"

    return {
        "job_id": job.job_id,
        "episode_code": job.episode_code,
        "shot_id": shot_id,
        "job_type": job.job_type,
        "provider": request_provider,
        "source_provider": job.provider,
        "prompt": prompt,
        "output_path": str(output_path),
        "priority": str(shot.get("priority", "medium")),
        "duration": int(shot.get("duration", 0)),
        "scene": str(shot.get("scene", "")),
        "camera": str(shot.get("camera", "")),
    }


def apply_provider_overrides(
    jobs: list[JobRecord],
    provider_overrides: dict[str, str] | None,
) -> list[JobRecord]:
    if not provider_overrides:
        return jobs

    routed_jobs: list[JobRecord] = []
    for job in jobs:
        routed_jobs.append(
            JobRecord(
                job_id=job.job_id,
                episode_code=job.episode_code,
                job_type=job.job_type,
                provider=provider_overrides.get(job.job_type, job.provider),
                status=job.status,
            )
        )
    return routed_jobs


def build_provider_requests(
    manifest: dict[str, Any],
    jobs: list[JobRecord],
    providers_config_path: Path,
    output_root: Path,
    provider_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    indexed_manifest = index_episode_manifest(manifest)
    routed_jobs = apply_provider_overrides(jobs, provider_overrides)
    provider_plan = build_provider_plan(routed_jobs, providers_config_path)
    provider_map = {
        str(item["provider"]): item
        for item in provider_plan["providers"]
    }
    requests: list[dict[str, Any]] = []
    request_records: list[ProviderRequestRecord] = []
    skipped_jobs: list[dict[str, str]] = []

    for job, routed_job in zip(jobs, routed_jobs, strict=False):
        episode_context = indexed_manifest.get(job.episode_code, {})
        episode = episode_context.get("episode", {})
        shots = episode_context.get("shots", {})
        shot_id = parse_shot_id_from_job(job.job_id)
        shot = shots.get(shot_id, {})
        if not episode or not shot_id or not shot:
            reason = "missing_episode"
            if episode and not shot_id:
                reason = "invalid_job_id"
            elif episode and shot_id and not shot:
                reason = "missing_shot"
            skipped_jobs.append(
                {
                    "job_id": job.job_id,
                    "episode_code": job.episode_code,
                    "provider": routed_job.provider,
                    "reason": reason,
                }
            )
            continue

        provider_profile = provider_map.get(routed_job.provider)
        endpoint = resolve_endpoint(routed_job.provider, job.job_type)
        request_status = "ready"
        if provider_profile is not None and not bool(provider_profile["env_ready"]):
            request_status = "blocked"

        payload = build_request_payload(job, routed_job.provider, str(episode["title"]), shot_id, shot, output_root)
        request_id = f"REQ_{job.job_id}"
        requests.append(
            {
                "request_id": request_id,
                "request_status": request_status,
                "endpoint": endpoint,
                "run_mode": resolve_provider_profile(routed_job.provider).run_mode,
                "payload": payload,
            }
        )
        request_records.append(
            ProviderRequestRecord(
                request_id=request_id,
                job_id=job.job_id,
                provider=routed_job.provider,
                job_type=job.job_type,
                request_status=request_status,
                endpoint=endpoint,
                payload_path=payload["output_path"],
            )
        )

    blocked_count = sum(1 for item in requests if item["request_status"] == "blocked")
    ready_count = sum(1 for item in requests if item["request_status"] == "ready")
    if skipped_jobs:
        raise ProviderRequestBuildError(skipped_jobs)
    return {
        "providers_config_path": str(providers_config_path),
        "provider_overrides": provider_overrides or {},
        "request_count": len(requests),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "requests": requests,
        "request_records": [asdict(item) for item in request_records],
        "skipped_jobs": skipped_jobs,
    }


def extract_request_records(payload: dict[str, Any]) -> list[ProviderRequestRecord]:
    return [
        ProviderRequestRecord(
            request_id=str(item["request_id"]),
            job_id=str(item["job_id"]),
            provider=str(item["provider"]),
            job_type=str(item["job_type"]),
            request_status=str(item["request_status"]),
            endpoint=str(item["endpoint"]),
            payload_path=str(item["payload_path"]),
        )
        for item in payload.get("request_records", [])
    ]


def write_provider_requests(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable_payload = dict(payload)
    serializable_payload.pop("request_records", None)
    atomic_write_json(path, serializable_payload)


# ============ Prompt Enhancement (fused from Omni-Rewriter + prompt-optimizer) ============

def build_image_prompt_enhanced(
    episode_title: str,
    shot: dict[str, Any],
    char_service=None,
    project_id: str = "",
    use_llm: bool = False,
    negative_prompt: str = "",
    shot_index: int = 0,
    total_shots: int = 1,
    prev_shot: dict[str, Any] | None = None,
    next_shot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """build_image_prompt + prompt_enhancer + 镜头意图分类 统一入口。"""
    base = build_image_prompt(episode_title, shot, char_service=char_service, project_id=project_id)
    profile_name = auto_select_profile(shot)
    return enhance_by_intent(
        base, shot=shot, shot_index=shot_index, total_shots=total_shots,
        prev_shot=prev_shot, next_shot=next_shot,
        profile_name=profile_name, use_llm=use_llm, negative_prompt=negative_prompt,
    )


def build_video_prompt_enhanced(
    episode_title: str,
    shot: dict[str, Any],
    char_service=None,
    project_id: str = "",
    use_llm: bool = False,
    negative_prompt: str = "",
    shot_index: int = 0,
    total_shots: int = 1,
    prev_shot: dict[str, Any] | None = None,
    next_shot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """build_video_prompt + prompt_enhancer + 镜头意图分类 统一入口。"""
    base = build_h3_video_prompt(episode_title, shot, char_service=char_service, project_id=project_id)
    profile_name = "video_h3"  # 视频固定用H3 profile
    return enhance_by_intent(
        base, shot=shot, shot_index=shot_index, total_shots=total_shots,
        prev_shot=prev_shot, next_shot=next_shot,
        profile_name=profile_name, use_llm=use_llm, negative_prompt=negative_prompt,
    )
