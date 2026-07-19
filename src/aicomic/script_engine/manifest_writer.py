"""Manifest Writer — 将 Screenplay/Scene 写入 episode_manifest.json。

复用现有 aicomic.core.manifest.write_json / load_json。
输出格式与现有管线字段级兼容。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.manifest import write_json
from aicomic.script_engine.engine import Scene, Screenplay


def build_episode_manifest(
    project_id: str,
    season: int,
    episode_code: str,
    screenplay: Screenplay,
    scenes: list[Scene],
) -> dict[str, Any]:
    """构建完整的 episode_manifest dict。

    Args:
        project_id: 项目 ID
        season: 季度编号
        episode_code: 剧集代码（如 E01）
        screenplay: Screenplay 剧本
        scenes: Scene 分镜列表

    Returns:
        episode_manifest dict（可直接 write_json）
    """
    return {
        "project_id": project_id,
        "season": season,
        "episodes": [
            {
                "episode_code": episode_code,
                "title": screenplay.title,
                "genre": screenplay.genre,
                "style": screenplay.style,
                "status": "shotlist_ready",
                "publish_title": screenplay.publish_title or screenplay.title,
                "cover_text": screenplay.cover_text or "",
                "shot_count": len(scenes),
                "creator_goal": screenplay.creator_goal,
                "ending_hook": screenplay.ending_hook,
                "shots": [_scene_to_dict(s) for s in scenes],
            }
        ],
    }


def _scene_to_dict(scene: Scene) -> dict[str, Any]:
    """将 Scene 对象转为与现有 manifest 兼容的 dict。"""
    return {
        "shot_id": scene.shot_id,
        "duration": scene.duration,
        "scene": scene.scene,
        "characters": scene.characters,
        "visual": scene.visual,
        "action": scene.action,
        "dialogue": scene.dialogue,
        "emotion": scene.emotion,
        "camera": scene.camera,
        "narration": scene.narration,
        "ai_video": scene.ai_video,
        "priority": scene.priority,
    }


def write_screenplay_to_episode_manifest(
    project_root: Path,
    project_id: str,
    season: int,
    episode_code: str,
    screenplay: Screenplay,
    scenes: list[Scene],
) -> Path:
    """将 Screenplay + scenes 写入 episode_manifest.json。

    Args:
        project_root: 项目根目录
        project_id: 项目 ID
        season: 季度编号
        episode_code: 剧集代码
        screenplay: Screenplay 剧本
        scenes: Scene 分镜列表

    Returns:
        写入的 manifest 文件路径
    """
    manifest = build_episode_manifest(
        project_id=project_id,
        season=season,
        episode_code=episode_code,
        screenplay=screenplay,
        scenes=scenes,
    )

    manifest_dir = project_root / "manifests"
    manifest_path = manifest_dir / "episode_manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path
