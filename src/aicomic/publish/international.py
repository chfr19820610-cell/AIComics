"""International platform uploaders — YouTube (Data API v3), TikTok (sau), Instagram (Graph API).

YouTube: youtube_publisher.py (Data API v3, not selenium)
TikTok: social-auto-upload tk_uploader (playwright automation)
Instagram: Instagram Graph API (reels media publish)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PublishPayload:
    """Standardized publish payload."""
    def __init__(
        self,
        video_path: Path,
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
        cover_path: Path | None = None,
    ):
        self.video_path = video_path
        self.title = title
        self.description = description
        self.tags = tags or []
        self.cover_path = cover_path


class IPlatformUploader(Protocol):
    """Protocol for platform-specific uploaders."""

    def upload(self, payload: PublishPayload, config: dict[str, Any]) -> dict[str, Any]:
        """Upload video to platform. Returns {success, url, platform}."""
        ...


class YouTubeUploader:
    """YouTube uploader via Data API v3 (not selenium)."""

    PLATFORM = "youtube"

    def upload(self, payload: PublishPayload, config: dict[str, Any]) -> dict[str, Any]:
        """Upload to YouTube via Data API v3."""
        from aicomic.publish.youtube_publisher import YouTubePayload, check_youtube_ready, build_youtube_upload_command
        yt_payload = YouTubePayload(
            video_path=str(payload.video_path),
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            privacy="public",
        )
        ready = check_youtube_ready(config)
        if not ready["ready"]:
            return {"success": False, "platform": self.PLATFORM, "error": ready["reason"]}
        cmd = build_youtube_upload_command(yt_payload, config)
        import subprocess
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            return {"success": True, "platform": self.PLATFORM, "url": proc.stdout.strip()}
        return {"success": False, "platform": self.PLATFORM, "error": proc.stderr.strip()[:200]}


class TikTokUploader:
    """TikTok uploader via social-auto-upload (playwright automation)."""

    PLATFORM = "tiktok"

    def upload(self, payload: PublishPayload, config: dict[str, Any]) -> dict[str, Any]:
        """Upload to TikTok via sau tk_uploader."""
        account_file = config.get("tiktok_account_file", "")
        if not account_file:
            return {"success": False, "platform": self.PLATFORM, "error": "tiktok_account_file not configured"}
        scheduled_at = config.get("scheduled_at", "")
        try:
            import asyncio
            import subprocess
            import json

            # Call sau_cli.py for TikTok upload
            sau_cli = config.get("sau_cli_path", "/Users/eric/social-auto-upload/sau_cli.py")
            cmd = [
                "python", sau_cli, "upload",
                "--platform", "tiktok",
                "--video", str(payload.video_path),
                "--title", payload.title,
                "--account-file", account_file,
            ]
            if payload.tags:
                cmd.extend(["--tags", ",".join(payload.tags)])
            if scheduled_at:
                cmd.extend(["--schedule", scheduled_at])

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0:
                return {"success": True, "platform": self.PLATFORM, "url": "tiktok://uploaded"}
            return {"success": False, "platform": self.PLATFORM, "error": proc.stderr.strip()[:200]}
        except Exception as e:
            return {"success": False, "platform": self.PLATFORM, "error": str(e)}


class InstagramUploader:
    """Instagram Reels uploader via Graph API."""

    PLATFORM = "instagram"

    def upload(self, payload: PublishPayload, config: dict[str, Any]) -> dict[str, Any]:
        """Upload to Instagram Reels via Graph API."""
        access_token = config.get("instagram_access_token", "")
        ig_user_id = config.get("instagram_user_id", "")
        if not access_token or not ig_user_id:
            return {"success": False, "platform": self.PLATFORM, "error": "instagram_access_token or instagram_user_id not configured"}
        try:
            import requests

            # Step 1: Create media container
            api_base = "https://graph.facebook.com/v21.0"
            media_url = config.get("video_url", str(payload.video_path))
            resp = requests.post(
                f"{api_base}/{ig_user_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": media_url,
                    "caption": f"{payload.title} {' '.join('#' + t for t in payload.tags)}",
                    "access_token": access_token,
                },
                timeout=30,
            )
            data = resp.json()
            if "id" not in data:
                return {"success": False, "platform": self.PLATFORM, "error": f"container creation failed: {data}"}
            container_id = data["id"]

            # Step 2: Publish media
            resp2 = requests.post(
                f"{api_base}/{ig_user_id}/media_publish",
                data={"creation_id": container_id, "access_token": access_token},
                timeout=30,
            )
            data2 = resp2.json()
            if "id" in data2:
                return {"success": True, "platform": self.PLATFORM, "url": f"instagram://media/{data2['id']}"}
            return {"success": False, "platform": self.PLATFORM, "error": f"publish failed: {data2}"}
        except Exception as e:
            return {"success": False, "platform": self.PLATFORM, "error": str(e)}


def publish(
    payload: PublishPayload,
    platforms: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Publish video to multiple international platforms.

    Args:
        payload: Standardized publish payload.
        platforms: List of platform names ("youtube", "tiktok", "instagram").
        config: Platform config dict.

    Returns:
        {platform: {success, url, error}} for each platform.
    """
    uploaders = {
        "youtube": YouTubeUploader(),
        "tiktok": TikTokUploader(),
        "instagram": InstagramUploader(),
    }

    results = {}
    for platform in platforms:
        uploader = uploaders.get(platform)
        if not uploader:
            results[platform] = {"success": False, "error": f"unknown platform: {platform}"}
            continue
        try:
            results[platform] = uploader.upload(payload, config)
        except Exception as e:
            results[platform] = {"success": False, "error": str(e)}
    return results
