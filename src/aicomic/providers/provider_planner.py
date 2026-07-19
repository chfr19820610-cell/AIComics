from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from aicomic.core.models import JobRecord


@dataclass(slots=True)
class ProviderProfile:
    provider: str
    supported_job_types: list[str]
    dispatch_channel: str
    queue_name: str
    run_mode: str
    auth_required: bool
    required_env: list[str]
    notes: str


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "manual_web": ProviderProfile(
        provider="manual_web",
        supported_job_types=["image", "video"],
        dispatch_channel="manual",
        queue_name="web_tasks",
        run_mode="网页人工生成",
        auth_required=False,
        required_env=[],
        notes="适合当前最稳路线：网页出图/视频后回填本地素材目录。",
    ),
    "openai_image": ProviderProfile(
        provider="openai_image",
        supported_job_types=["image"],
        dispatch_channel="api",
        queue_name="image_api",
        run_mode="API 自动出图",
        auth_required=True,
        required_env=["OPENAI_API_KEY"],
        notes="适合后续自动插画生成；当前只做路由规划，不直接调用外部服务。",
    ),
    "local_comfyui_image": ProviderProfile(
        provider="local_comfyui_image",
        supported_job_types=["image"],
        dispatch_channel="local",
        queue_name="image_local",
        run_mode="本地 ComfyUI 出图",
        auth_required=False,
        required_env=[],
        notes="适合替代 OpenAI 图片生成；默认只做 dry-run，配置 ComfyUI workflow 后可本地执行。",
    ),
    "sora": ProviderProfile(
        provider="sora",
        supported_job_types=["video"],
        dispatch_channel="api",
        queue_name="video_api",
        run_mode="API 自动视频",
        auth_required=True,
        required_env=["OPENAI_API_KEY"],
        notes="适合后续镜头动态化；当前只做路由规划，不直接调用外部服务。",
    ),
    "local_comfyui_video": ProviderProfile(
        provider="local_comfyui_video",
        supported_job_types=["video"],
        dispatch_channel="local",
        queue_name="video_local",
        run_mode="本地 ComfyUI 视频",
        auth_required=False,
        required_env=[],
        notes="适合替代 Sora/网页视频的本地工作流；配置视频 workflow 后可小批量验证。",
    ),
    "windows_tts": ProviderProfile(
        provider="windows_tts",
        supported_job_types=["tts"],
        dispatch_channel="local",
        queue_name="tts_local",
        run_mode="本地 TTS",
        auth_required=False,
        required_env=[],
        notes="适合无成本生成旁白或对白占位音轨。",
    ),
    "local_piper_tts": ProviderProfile(
        provider="local_piper_tts",
        supported_job_types=["tts"],
        dispatch_channel="local",
        queue_name="tts_local",
        run_mode="本地 Piper TTS",
        auth_required=False,
        required_env=[],
        notes="适合替代 OpenAI TTS 的轻量离线配音；配置 Piper 模型后可本地执行。",
    ),
    "openai_tts": ProviderProfile(
        provider="openai_tts",
        supported_job_types=["tts"],
        dispatch_channel="api",
        queue_name="tts_api",
        run_mode="API 自动配音",
        auth_required=True,
        required_env=["OPENAI_API_KEY"],
        notes="适合后续高质量旁白和角色音色；当前只做路由规划。",
    ),
    "blender_local": ProviderProfile(
        provider="blender_local",
        supported_job_types=["video", "image"],
        dispatch_channel="local",
        queue_name="video_local",
        run_mode="本地 Blender 三渲二渲染",
        auth_required=False,
        required_env=[],
        notes="基于 Blender Python API 的本地 3D 渲染 Provider。"
              "支持 EEVEE / CYCLES 引擎、Freestyle 线稿、精确摄像机控制。"
              "适合三渲二动画风格视频和静帧渲染。",
    ),
}


def load_provider_settings(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}

    settings: dict[str, dict[str, object]] = {}
    current_section = ""
    current_list_key = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue

        stripped_line = raw_line.strip()
        if not raw_line.startswith(" ") and stripped_line.endswith(":"):
            current_section = stripped_line[:-1]
            settings.setdefault(current_section, {})
            current_list_key = ""
            continue

        if not current_section:
            continue

        if stripped_line.endswith(":"):
            current_list_key = stripped_line[:-1]
            settings[current_section].setdefault(current_list_key, [])
            continue

        if stripped_line.startswith("- ") and current_list_key:
            list_value = settings[current_section].setdefault(current_list_key, [])
            if isinstance(list_value, list):
                list_value.append(stripped_line[2:].strip())
            continue

        if ":" in stripped_line:
            key, value = stripped_line.split(":", 1)
            settings[current_section][key.strip()] = value.strip()

    return settings


def collect_available_providers(settings: dict[str, dict[str, object]]) -> set[str]:
    providers: set[str] = set()
    for section in settings.values():
        available = section.get("available", [])
        if isinstance(available, list):
            providers.update(str(item) for item in available)
        default_provider = section.get("default")
        if default_provider:
            providers.add(str(default_provider))
    return providers


def resolve_provider_profile(provider: str) -> ProviderProfile:
    profile = PROVIDER_PROFILES.get(provider)
    if profile is not None:
        return profile
    return ProviderProfile(
        provider=provider,
        supported_job_types=[],
        dispatch_channel="api",
        queue_name="unknown_api",
        run_mode="未知 Provider",
        auth_required=True,
        required_env=[],
        notes="配置中未登记该 Provider 的详细能力，需要补充适配器。",
    )


def build_provider_plan(jobs: list[JobRecord], providers_config_path: Path) -> dict[str, object]:
    settings = load_provider_settings(providers_config_path)
    available_providers = collect_available_providers(settings)
    job_counts: dict[str, dict[str, int]] = {}
    unresolved_jobs: list[dict[str, str]] = []

    for job in jobs:
        provider_counts = job_counts.setdefault(job.provider, {})
        provider_counts[job.job_type] = provider_counts.get(job.job_type, 0) + 1
        if available_providers and job.provider not in available_providers:
            unresolved_jobs.append(
                {
                    "job_id": job.job_id,
                    "episode_code": job.episode_code,
                    "job_type": job.job_type,
                    "provider": job.provider,
                    "reason": "Provider 不在配置可用列表中",
                }
            )

    providers = []
    for provider_name in sorted(job_counts):
        profile = resolve_provider_profile(provider_name)
        required_env_status = [
            {
                "name": env_name,
                "configured": bool(os.environ.get(env_name)),
            }
            for env_name in profile.required_env
        ]
        providers.append(
            {
                **asdict(profile),
                "job_counts": job_counts[provider_name],
                "job_count": sum(job_counts[provider_name].values()),
                "env_ready": all(item["configured"] for item in required_env_status),
                "required_env_status": required_env_status,
            }
        )

    return {
        "providers_config_path": str(providers_config_path),
        "configured_providers": sorted(available_providers),
        "provider_count": len(providers),
        "job_route_count": len(jobs),
        "unresolved_provider_count": len(unresolved_jobs),
        "providers": providers,
        "unresolved_jobs": unresolved_jobs,
        "recommendations": build_provider_recommendations(providers, unresolved_jobs),
    }


def build_provider_recommendations(
    providers: list[dict[str, object]],
    unresolved_jobs: list[dict[str, str]],
) -> list[str]:
    recommendations: list[str] = []
    provider_names = {str(item["provider"]) for item in providers}

    if "manual_web" in provider_names:
        recommendations.append("继续保留 manual_web 作为最稳生产路线，先保证网页出图/视频回填稳定。")
    if "windows_tts" in provider_names:
        recommendations.append("旁白和对白可先走 windows_tts 占位，后续再切换高质量 TTS Provider。")
    if "local_comfyui_image" in provider_names:
        recommendations.append("图片可试运行 local_comfyui_image：先 dry-run 校验工作流路径，确认后再本地执行。")
    if "local_comfyui_video" in provider_names:
        recommendations.append("视频可试运行 local_comfyui_video：建议先用 1 条镜头小批量验证耗时和显存。")
    if "local_piper_tts" in provider_names:
        recommendations.append("配音可试运行 local_piper_tts：安装 Piper 并配置模型路径后可离线生成 wav。")
    if unresolved_jobs:
        recommendations.append("存在未登记 Provider 的任务，需要先补充 providers.yaml 与适配器。")
    if not unresolved_jobs:
        recommendations.append("当前任务 Provider 均可路由，可进入 API 适配器封装阶段。")
    return recommendations


def write_provider_plan(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
