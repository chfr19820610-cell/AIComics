from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class _VidGenProviderMixin:
    """Shared helper methods for video generation providers (Seedance, Kling).

    Provides common setting resolution and image path handling to reduce
    code duplication between SeedanceProvider and KlingProvider.
    Designed for multiple inheritance alongside IProvider.
    """

    def _resolve_setting(
        self,
        settings: dict[str, dict[str, object]],
        section: str,
        key: str,
        default: str,
    ) -> str:
        value = settings.get(section, {}).get(key)
        if value is not None:
            return str(value).strip()
        return default

    def _resolve_int(
        self,
        settings: dict[str, dict[str, object]],
        section: str,
        key: str,
        default: int,
    ) -> int:
        value = settings.get(section, {}).get(key)
        if value is not None:
            raw = str(value).strip()
            if raw.isdigit():
                return int(raw)
        return default

    def _resolve_image_path(self, path_or_url: str) -> str:
        """Convert a local file path to a data URL if needed."""
        parsed = urlparse(path_or_url)
        if parsed.scheme in ("http", "https", "data"):
            return path_or_url

        resolved = Path(path_or_url)
        if resolved.exists() and resolved.is_file():
            ext = resolved.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }
            mime = mime_map.get(ext, "image/png")
            data = base64.b64encode(resolved.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"

        return path_or_url
