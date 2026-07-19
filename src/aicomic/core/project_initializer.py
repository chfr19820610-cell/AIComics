from __future__ import annotations

import json
from pathlib import Path

from aicomic.core.creator_bootstrap import (
    build_character_bible,
    build_creator_profile,
    build_episode_blueprint,
    build_prompt_pack_template,
    build_release_checklist_markdown,
    build_story_bible,
    build_style_bible,
)
from aicomic.utils.atomic_io import atomic_write_json

DEFAULT_DIRECTORIES = (
    "config",
    "docs",
    "templates",
    "prompts",
    "publish",
    "manifests",
    "jobs",
    "reports",
    "logs",
    "state",
    "assets",
    "assets/characters",
    "assets/scenes",
    "assets/episodes",
)


def normalize_project_id(project_name: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in project_name.strip())
    normalized = "_".join(item for item in normalized.split("_") if item)
    if normalized:
        return normalized
    return "aicomic_project"


def build_project_manifest(
    project_id: str,
    project_name: str,
    genre: str,
    style: str,
    creator_profile: dict[str, object],
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "project_name": project_name,
        "genre": genre,
        "style_profile": style,
        "status": "initialized",
        "target_platforms": ["douyin", "kuaishou", "bilibili"],
        "default_providers": {
            "image": "manual_web",
            "video": "manual_web",
            "tts": "windows_tts",
        },
        "creator_profile": creator_profile,
        "seasons": [
            {
                "season": 1,
                "season_title": "第一季",
                "status": "planning",
            }
        ],
    }


def build_season_manifest(
    project_id: str,
    project_name: str,
    season_hook: str,
    episode_target_count: int,
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "season": 1,
        "season_title": f"{project_name} 第一季",
        "status": "planning",
        "episodes": [
            {
                "episode_code": "E01",
                "title": "第一集",
                "status": "idea",
            }
        ],
        "batch_policy": {
            "default_scope": "season",
            "default_steps": ["build_jobs", "build_provider_requests", "scan_assets", "render_preview"],
        },
        "creator_plan": {
            "season_hook": season_hook,
            "episode_target_count": episode_target_count,
        },
    }


def build_episode_manifest(project_id: str, protagonist_name: str, season_hook: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "season": 1,
        "episodes": [
            {
                "episode_code": "E01",
                "title": "第一集",
                "status": "idea",
                "publish_title": "第一集发布标题待定",
                "cover_text": "封面文案待定",
                "creator_goal": f"完成 {protagonist_name} 的第一次冲突与钩子建立",
                "ending_hook": season_hook,
                "shots": [],
            }
        ],
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def initialize_project(
    output_root: Path,
    project_name: str,
    genre: str,
    style: str,
    project_id: str | None = None,
    logline: str = "一个普通人被卷入高压环境后，靠连续反转赢回主动权。",
    protagonist_name: str = "女主",
    target_audience: str = "短剧用户 / 二次元短视频观众",
    tone: str = "强钩子",
    season_hook: str = "结尾必须留下身份、关系或真相反转。",
    episode_target_count: int = 12,
) -> dict[str, object]:
    resolved_project_id = project_id or normalize_project_id(project_name)
    project_root = output_root / resolved_project_id
    created_directories: list[str] = []
    for directory in DEFAULT_DIRECTORIES:
        directory_path = project_root / directory
        directory_path.mkdir(parents=True, exist_ok=True)
        created_directories.append(str(directory_path))

    project_manifest_path = project_root / "manifests" / "project_manifest.json"
    season_manifest_path = project_root / "manifests" / "season_manifest.json"
    episode_manifest_path = project_root / "manifests" / "episode_manifest.json"
    story_bible_path = project_root / "docs" / "creator_story_bible.json"
    character_bible_path = project_root / "docs" / "character_bible.json"
    style_bible_path = project_root / "docs" / "style_bible.json"
    episode_blueprint_path = project_root / "docs" / "episode_blueprint.json"
    prompt_pack_path = project_root / "prompts" / "prompt_pack_template.json"
    release_checklist_path = project_root / "publish" / "release_checklist.md"
    readme_path = project_root / "README.md"

    creator_profile = build_creator_profile(
        project_name,
        genre,
        style,
        logline,
        protagonist_name,
        target_audience,
        tone,
        season_hook,
        episode_target_count,
    )

    write_json(project_manifest_path, build_project_manifest(resolved_project_id, project_name, genre, style, creator_profile))
    write_json(season_manifest_path, build_season_manifest(resolved_project_id, project_name, season_hook, episode_target_count))
    write_json(episode_manifest_path, build_episode_manifest(resolved_project_id, protagonist_name, season_hook))
    write_json(story_bible_path, build_story_bible(project_name, genre, logline, protagonist_name, tone, season_hook))
    write_json(character_bible_path, build_character_bible(protagonist_name))
    write_json(style_bible_path, build_style_bible(style, tone))
    write_json(episode_blueprint_path, build_episode_blueprint(episode_target_count, protagonist_name, season_hook))
    write_json(prompt_pack_path, build_prompt_pack_template(project_name, genre, style, protagonist_name, tone))
    release_checklist_path.write_text(build_release_checklist_markdown(project_name), encoding="utf-8")
    readme_path.write_text(
        "\n".join(
            [
                f"# {project_name}",
                "",
                f"- 项目 ID：`{resolved_project_id}`",
                f"- 题材：`{genre}`",
                f"- 风格：`{style}`",
                f"- 主角：`{protagonist_name}`",
                f"- 受众：`{target_audience}`",
                f"- 调性：`{tone}`",
                "- 状态：`initialized`",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "project_id": resolved_project_id,
        "project_name": project_name,
        "project_root": str(project_root),
        "created_directory_count": len(created_directories),
        "created_directories": created_directories,
        "manifest_paths": {
            "project": str(project_manifest_path),
            "season": str(season_manifest_path),
            "episode": str(episode_manifest_path),
        },
        "bootstrap_paths": {
            "story_bible": str(story_bible_path),
            "character_bible": str(character_bible_path),
            "style_bible": str(style_bible_path),
            "episode_blueprint": str(episode_blueprint_path),
            "prompt_pack_template": str(prompt_pack_path),
            "release_checklist": str(release_checklist_path),
        },
        "readme_path": str(readme_path),
    }
