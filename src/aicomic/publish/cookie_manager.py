"""Cookie manager — persistence + validity check + auto recovery for platform login state."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CookieStatus:
    valid: bool
    reason: str = ""
    cookie_count: int = 0
    platform: str = ""


def check_cookie_validity(cookie_path: Path, platform: str = "") -> CookieStatus:
    """Check if a cookie file exists and is not expired.

    Args:
        cookie_path: Path to JSON cookie file.
        platform: Platform name for logging.

    Returns:
        CookieStatus with validity info.
    """
    if not cookie_path.exists():
        return CookieStatus(valid=False, reason="not_found", platform=platform)

    try:
        cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return CookieStatus(valid=False, reason="corrupted", platform=platform)

    if not cookies:
        return CookieStatus(valid=False, reason="empty", platform=platform)

    now = time.time()
    for cookie in cookies:
        expires = cookie.get("expires", cookie.get("expiry", 0))
        if expires and expires < now:
            return CookieStatus(valid=False, reason="expired", platform=platform, cookie_count=len(cookies))

    return CookieStatus(valid=True, cookie_count=len(cookies), platform=platform)


def batch_check_cookies(
    platform_cookie_map: dict[str, Path],
) -> dict[str, CookieStatus]:
    """Batch check cookie validity for all platforms.

    Args:
        platform_cookie_map: {platform_name: cookie_path}

    Returns:
        {platform: CookieStatus}
    """
    return {
        platform: check_cookie_validity(path, platform=platform)
        for platform, path in platform_cookie_map.items()
    }


def get_expired_platforms(platform_cookie_map: dict[str, Path]) -> list[str]:
    """Get list of platforms with expired/invalid cookies that need re-login."""
    results = batch_check_cookies(platform_cookie_map)
    return [p for p, s in results.items() if not s.valid]
