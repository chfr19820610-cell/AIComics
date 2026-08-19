"""YouTube Data API v3 publisher — international platform upload.

Uses Google API client for authorized uploads (not selenium).
Requires: client_secret.json (OAuth) + credentials.json (token).
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class YouTubePayload:
    video_path: str
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    privacy: str = "public"  # public / unlisted / private
    category_id: int = 22  # 22 = Film & Animation


    @classmethod
    def from_publish_pack(cls, pack: dict[str, Any], video_path: str) -> "YouTubePayload":
        yt = pack.get("platform_copy", {}).get("youtube", {})
        if yt:
            return cls(
                video_path=video_path,
                title=yt.get("title", pack.get("titles", {}).get("main", "")),
                description=yt.get("description", pack.get("description", "")),
                tags=yt.get("tags", pack.get("tags", [])),
            )
        # Fallback to generic
        return cls(
            video_path=video_path,
            title=pack.get("titles", {}).get("main", ""),
            description=pack.get("description", ""),
            tags=pack.get("tags", []),
        )


def check_youtube_ready(cfg: dict[str, Any]) -> dict[str, Any]:
    """Check if YouTube OAuth credentials are configured."""
    secret = Path(cfg.get("client_secret_path", ""))
    creds = Path(cfg.get("credentials_path", ""))
    if not cfg:
        return {"ready": False, "reason": "no youtube config"}
    if not secret.exists():
        return {"ready": False, "reason": f"client_secret not found: {secret}"}
    if not creds.exists():
        return {"ready": False, "reason": f"credentials not found: {creds} (run OAuth flow first)"}
    return {"ready": True, "reason": "ok"}


def build_youtube_upload_command(payload: YouTubePayload, script_path: str = "scripts/yt_upload.py") -> list[str]:
    """Build CLI command for the upload script."""
    cmd = [sys.executable, script_path,
           "--file", payload.video_path,
           "--title", payload.title,
           "--description", payload.description,
           "--privacy", payload.privacy,
           "--category", str(payload.category_id)]
    for tag in payload.tags:
        cmd.extend(["--tag", tag])
    return cmd


def publish_to_youtube(payload: YouTubePayload, cfg: dict[str, Any], script_path: str = "scripts/yt_upload.py", headless: bool = True) -> dict[str, Any]:
    """Execute YouTube upload. Returns {success, video_id?, error?}."""
    ready = check_youtube_ready(cfg)
    if not ready["ready"]:
        return {"success": False, "error": ready["reason"]}
    if not Path(payload.video_path).exists():
        return {"success": False, "error": f"video not found: {payload.video_path}"}
    if not payload.title:
        return {"success": False, "error": "title is empty"}
    cmd = build_youtube_upload_command(payload, script_path)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
        if result.returncode == 0:
            return {"success": True, "stdout": result.stdout[:500]}
        return {"success": False, "error": result.stderr[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}
