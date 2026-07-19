from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from aicomic.core.models import JobRecord, ProviderRequestRecord
from aicomic.utils.atomic_io import atomic_write_json
from aicomic.providers.provider_planner import build_provider_plan, resolve_provider_profile


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
    """根据镜头类型选择构图+光影+风格指令"""
    scene = str(shot.get("scene", ""))
    camera = str(shot.get("camera", ""))
    emotion = str(shot.get("emotion", ""))

    # ── 构图策略 ──
    # 近景/特写 → 浅景深构图
    if any(k in camera for k in ("特写", "近景", "close", "极近")):
        composition = (
            "构图：浅景深主体突出，三分法将角色眼睛置于上三分线；"
            "背景虚化柔焦。"
        )
    # 中景/双人对话 → 中景构图，引导线
    elif any(k in camera for k in ("中景", "medium", "双人")):
        composition = (
            "构图：中景双人对称/斜线构图，视线引导利用角色目光方向；"
            "前景留呼吸空间。"
        )
    # 远景/全景 → 框架构图+引导线
    elif any(k in camera for k in ("远景", "全景", "wide", "远")):
        composition = (
            "构图：环境主导，运用引导线（道路/建筑/自然轮廓）牵引视线至主体；"
            "前景框架（门框/窗/树枝）增加层次纵深。"
        )
    else:
        composition = (
            "构图：三分法主体偏离中心，运用引导线强化视觉流向；"
            "前景/背景层次分明。"
        )

    # ── 光影策略 ──
    # 恐怖/紧张情绪 → 低调+伦勃朗光
    if any(k in emotion for k in ("恐惧", "紧张", "诡异", "阴", "dark", "恐惧", "惊")):
        lighting = (
            "光影：低调戏剧光，伦勃朗式侧光勾勒面部轮廓；"
            "背光边缘光分离主体与背景；暗部保留细节不漆黑。"
        )
    # 浪漫/温柔 → 柔光+逆光
    elif any(k in emotion for k in ("温柔", "浪漫", "温馨", "平静", "柔和")):
        lighting = (
            "光影：柔光漫射照明，逆光金色边缘轮廓光；"
            "面部补光柔和，高光扩散，阴影柔和过渡。"
        )
    # 激烈/动作 → 硬光+高对比
    elif any(k in emotion for k in ("愤怒", "激烈", "战斗", "紧张", "爆发")):
        lighting = (
            "光影：硬光高对比，三点布光（主光+侧逆光+补光）提升立体感；"
            "强阴影增加戏剧张力，高光区域提示细节。"
        )
    # 默认 → 三点布光+层次
    else:
        lighting = (
            "光影：专业三点布光，主光塑造主体形态，侧逆光勾勒轮廓边缘，"
            "补光保留暗部细节；整体光比适中，层次丰富不扁平。"
        )

    # ── 风格强化 ──
    # 夜景
    if any(k in scene for k in ("夜", "暗", "黑暗", "室内暗")):
        style = (
            "画风：高精度动漫插画，夜间场景注意色温偏冷（蓝紫调），"
            "光源色温偏暖（橙黄调）形成色彩对比；"
            "暗部保留细节不漆黑，避免AI常见噪点和色块。"
        )
    # 白天/户外
    elif any(k in scene for k in ("白天", "户外", "阳光", "外景")):
        style = (
            "画风：高精度动漫插画，日光场景注意色温偏暖，"
            "高光不过曝，阴影有色彩倾向（冷蓝反射）；"
            "天空渐变平滑，无带状色阶。"
        )
    else:
        style = (
            "画风：高精度动漫插画，色彩和谐统一，光影过渡细腻，"
            "线条干净利落，背景细节丰富不杂乱。"
        )

    # ── 通用负项（嵌入 prompt 内，因为 gpt-image-1.5 不支持独立 negative_prompt 参数） ──
    negative = (
        "注意：画面中不要出现文字、字幕、标题、气泡对话框、logo、水印；"
        "不要出现扭曲的手部、多余的手指或脚趾；"
        "不要出现畸形面部、错位五官；"
        "不要出现模糊、像素化、色块噪点、带状色阶；"
        "不要出现镜像翻转或画面切割失调；"
        "角色面容、发色、服装等关键特征在本集内保持一致。"
    )

    return f"{composition}{lighting}{style}{negative}"


def build_image_prompt(episode_title: str, shot: dict[str, Any]) -> str:
    if is_horror_shot(shot):
        return build_horror_visual_prompt(shot, motion=False)
    characters = "、".join(str(item) for item in shot.get("characters", []))
    horror_context = build_horror_prompt_context(shot)
    quality_suffix = _build_quality_suffix(shot)
    return (
        f"动漫插画风，剧集《{episode_title}》，场景：{shot['scene']}。"
        f"人物：{characters}。"
        f"画面：{shot['visual']}。"
        f"动作：{shot['action']}。"
        f"情绪：{shot['emotion']}。"
        f"镜头：{shot['camera']}。"
        f"{horror_context}"
        f"{quality_suffix}"
        "高对比、强戏剧张力、短剧封面级质感。"
    )


def build_video_prompt(episode_title: str, shot: dict[str, Any]) -> str:
    if is_horror_shot(shot):
        return build_horror_visual_prompt(shot, motion=True)
    horror_context = build_horror_prompt_context(shot)
    return (
        f"动漫动态镜头，剧集《{episode_title}》。"
        f"场景：{shot['scene']}。"
        f"画面：{shot['visual']}。"
        f"动作：{shot['action']}。"
        f"情绪：{shot['emotion']}。"
        f"运镜：{shot['camera']}。"
        f"{horror_context}"
        "时长控制在 3-4 秒，镜头稳定，突出人物情绪变化。"
    )


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
    avoidance_strategy = str(shot.get("avoidance_strategy", "")).strip()
    continuity_anchor = str(shot.get("continuity_anchor", "")).strip()
    sound_cue = str(shot.get("sound_cue", "")).strip()
    if not any([horror_beat, avoidance_strategy, continuity_anchor, sound_cue]):
        return ""
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
) -> dict[str, Any]:
    if job.job_type == "image":
        prompt = build_image_prompt(episode_title, shot)
        output_path = output_root / job.episode_code / "images" / f"{job.episode_code}_{shot_id}_key.png"
    elif job.job_type == "video":
        prompt = build_video_prompt(episode_title, shot)
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
