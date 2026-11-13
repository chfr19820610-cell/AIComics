"""Domestic platform publisher — delegates to social-auto-upload.

Supports: 抖音 (douyin), 小红书 (xiaohongshu), B站 (bilibili).
Does NOT re-implement browser automation — calls social-auto-upload as subprocess.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aicomic.video_synthesis.ai_label import ai_label_present

# Project root (src/aicomic/publish/ → ../../..  = project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "publish.yaml"

SUPPORTED_PLATFORMS = ("douyin", "xiaohongshu", "bilibili")


@dataclass
class PublishPayload:
    """Standardized publish payload."""
    video_path: Path
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    cover_path: Path | None = None
    platform_copy: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_publish_pack(cls, pack: dict[str, Any], video: Path) -> "PublishPayload":
        pc = pack.get("platform_copy", {}).get("douyin", {})
        if not isinstance(pc, dict):
            pc = {}
        return cls(
            video_path=video,
            title=pc.get("title", pack.get("publish_title", pack.get("titles", {}).get("main", ""))),
            description=pc.get("description", pack.get("description", "")),
            tags=pc.get("tags", pack.get("hashtags", pack.get("tags", []))),
            platform_copy=pack.get("platform_copy", {}),
        )


_PATH_ENV_DEFAULTS: dict[str, str] = {
    # 未设置环境变量时的回落值。没有这一步，`${SOCIAL_AUTO_UPLOAD_PATH}` 会被
    # expandvars 原样保留成字面量，导致 cookie 路径必然 "missing"
    # （2026-11-13 回归：抖音就绪从 ok 变 missing，根因在此）。
    "SOCIAL_AUTO_UPLOAD_PATH": str(Path.home() / "social-auto-upload"),
    "YOUTUBE_CREDENTIALS_DIR": str(Path.home() / "credentials"),
}


def _expand_paths(value: Any) -> Any:
    """Expand `$VAR` / `~` inside path-like config strings.

    Keeps publish.yaml portable: an open-source checkout can point at
    `${SOCIAL_AUTO_UPLOAD_PATH}/cookies/douyin.json` instead of hard-coding one
    developer's home directory. When the variable is unset, fall back to the
    conventional location under the user's home rather than leaving the literal
    `${...}` text in place.
    """
    if isinstance(value, str):
        expanded = os.path.expanduser(os.path.expandvars(value))
        if "${" in expanded:
            for env_name, fallback in _PATH_ENV_DEFAULTS.items():
                expanded = expanded.replace(f"${{{env_name}}}", fallback)
                expanded = expanded.replace(f"${env_name}", fallback)
        return expanded or value
    if isinstance(value, list):
        return [_expand_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_paths(item) for key, item in value.items()}
    return value


def load_publish_config(path: Path | None = None) -> dict[str, Any]:
    """Load publish.yaml config (with env-var / ~ expansion)."""
    p = path or _CONFIG_PATH
    if not p.exists():
        return {"platforms": {}, "social_auto_upload_path": "", "defaults": {}}
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _expand_paths(raw)


def check_platform_ready(platform: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Check if a platform is configured and ready."""
    platforms = cfg.get("platforms", {})
    if platform not in platforms:
        return {"ready": False, "reason": f"unknown platform: {platform}"}
    p = platforms[platform]
    if not p.get("enabled", False):
        return {"ready": False, "reason": "disabled"}
    cookie = p.get("cookie_path", "")
    if not cookie or not Path(cookie).exists():
        return {"ready": False, "reason": f"cookie file missing: {cookie}"}
    return {"ready": True, "reason": "ok"}


def publish_to_platforms(
    payload: PublishPayload,
    platforms: list[str],
    cfg: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Publish to multiple platforms. Continues on partial failure."""
    results: dict[str, dict[str, Any]] = {}
    for plat in platforms:
        if plat not in SUPPORTED_PLATFORMS:
            results[plat] = {"success": False, "error": f"unsupported platform: {plat}"}
            continue
        ready = check_platform_ready(plat, cfg)
        if not ready["ready"]:
            results[plat] = {"success": False, "error": ready["reason"]}
            continue
        # SOP §10 #7 联检：平台发布前必须挂 AI 生成标识（require_ai_label=False 显式豁免）
        if cfg.get("require_ai_label", True) and not ai_label_present(payload.video_path):
            results[plat] = {"success": False, "error": "ai_label missing: run `ai-label-embed` first"}
            continue
        if not payload.video_path.exists():
            results[plat] = {"success": False, "error": f"video not found: {payload.video_path}"}
            continue
        if not payload.title:
            results[plat] = {"success": False, "error": "title is empty"}
            continue
        try:
            results[plat] = _run_sau_upload(plat, payload, cfg)
        except Exception as e:
            results[plat] = {"success": False, "error": str(e)}
    return results


def publish_batch(
    videos: list[Path],
    platforms: list[str],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Batch publish multiple videos to multiple platforms.

    Args:
        videos: List of video file paths (one per episode).
        platforms: List of platform names.
        config: Platform config dict.

    Returns:
        List of {platform: {success, url, error}} for each video.
    """
    results = []
    for video in videos:
        payload = PublishPayload(
            video_path=video,
            title=video.stem,
            description="",
            tags=[],
            platform_copy={},
        )
        results.append(publish_to_platforms(payload, platforms, config))
    return results


def _run_sau_upload(platform: str, payload: PublishPayload, cfg: dict[str, Any]) -> dict[str, Any]:
    """Execute social-auto-upload CLI for a platform.

    Builds a subprocess call to sau_cli.py with the right arguments.
    Returns {success, platform, url?}.
    """
    sau_path = cfg.get("social_auto_upload_path", "")
    if not sau_path or not Path(sau_path).exists():
        return {"success": False, "error": f"social-auto-upload not found: {sau_path}"}

    plat_cfg = cfg["platforms"][platform]
    headless = plat_cfg.get("headless", True)
    account = plat_cfg.get("account_name", "aicomic")

    # Use platform-specific copy if available
    title = payload.platform_copy.get(platform, payload.title)
    tags_str = ",".join(payload.tags) if payload.tags else ""
    desc = f"{payload.description} {tags_str}".strip()

    # Build CLI command
    tag_args = [t.lstrip("#") for t in payload.tags]
    cmd = [
        sys.executable, str(Path(sau_path) / "sau_cli.py"),
        platform, "video",
        "--account-name", account,
        "--video-file", str(payload.video_path),
        "--title", title,
        "--description", desc,
        "--publish-strategy", "immediate",
    ]
    for tag in tag_args:
        cmd.extend(["--tag", tag])

    env = os.environ.copy()
    if headless:
        env["LOCAL_CHROME_HEADLESS"] = "true"

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=sau_path)
    if proc.returncode == 0:
        return {"success": True, "platform": platform, "stdout": proc.stdout[-500:]}
    return {"success": False, "platform": platform, "error": proc.stderr[-500:] or proc.stdout[-500:]}
