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


def load_publish_config(path: Path | None = None) -> dict[str, Any]:
    """Load publish.yaml config."""
    p = path or _CONFIG_PATH
    if not p.exists():
        return {"platforms": {}, "social_auto_upload_path": "", "defaults": {}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
    cookie = plat_cfg["cookie_path"]
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
