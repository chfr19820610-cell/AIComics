"""Stock material search provider — Pexels/Pixabay API search + download + cache.

Distilled from MoneyPrinterTurbo material.py (102K⭐).
Supports: keyword search, aspect ratio filter, 24h cache, API key rotation.
"""
from __future__ import annotations

import os
import json
import time
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class StockMaterialProvider(IProvider):
    """Pexels + Pixabay 素材搜索 provider."""

    PROVIDER_NAME = "stock_material"
    CACHE_DIR = Path(os.environ.get("AICOMIC_STATE_DIR", ".")) / "stock_cache"
    CACHE_TTL = 86400  # 24h

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._pexels_keys = self.config.get("pexels_api_keys", [])
        self._pixabay_keys = self.config.get("pixabay_api_keys", [])
        self._key_idx = 0
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def validate_config(self) -> bool:
        return bool(self._pexels_keys or self._pixabay_keys)

    def is_ready(self) -> bool:
        return self.validate_config()

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.PROVIDER_NAME,
            display_name="Stock Material (Pexels/Pixabay)",
            capabilities=ProviderCapability(
                job_types=("material_search",),
                dispatch_channel="sync",
                auth_required=True,
                required_env=(),
            ),
            run_mode="api",
            notes="Online stock video search. Fallback for ComfyUI generation.",
        )

    def build_request(self, job: dict[str, Any]) -> dict[str, Any]:
        """Build search params from job."""
        return {
            "query": job.get("query", ""),
            "aspect": job.get("aspect", "portrait"),
            "limit": job.get("limit", 5),
            "source": job.get("source", "pexels"),
        }

    def execute_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute search + return material list."""
        results = self.search(
            query=request["query"],
            aspect=request["aspect"],
            limit=request["limit"],
            source=request["source"],
        )
        return {"materials": results, "count": len(results)}

    def search(
        self,
        query: str,
        aspect: str = "portrait",
        limit: int = 5,
        source: str = "pexels",
    ) -> list[dict[str, Any]]:
        """Search stock materials. Returns list of {url, duration, provider, width, height}."""
        cache_key = self._cache_key(query, aspect, source)
        cached = self._cache_get(cache_key)
        if cached:
            return cached[:limit]

        if source == "pexels" and self._pexels_keys:
            results = self._search_pexels(query, aspect, limit)
        elif source == "pixabay" and self._pixabay_keys:
            results = self._search_pixabay(query, aspect, limit)
        else:
            results = []

        if results:
            self._cache_set(cache_key, results)
        return results[:limit]

    def download(self, url: str, dest: Path) -> bool:
        """Download material to dest path."""
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "AIComics/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return dest.exists() and dest.stat().st_size > 1024
        except Exception:
            return False

    def _search_pexels(self, query: str, aspect: str, limit: int) -> list[dict]:
        if not self._pexels_keys:
            return []
        key = self._pexels_keys[self._key_idx % len(self._pexels_keys)]
        self._key_idx += 1
        w, h = self._aspect_to_resolution(aspect)
        params = urllib.parse.urlencode({
            "query": query, "per_page": str(limit * 2),
            "orientation": "portrait" if aspect == "portrait" else "landscape",
        })
        req = urllib.request.Request(
            f"https://api.pexels.com/videos/search?{params}",
            headers={"Authorization": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []
        results = []
        for clip in data.get("videos", []):
            best = max(clip.get("video_files", []), key=lambda f: f.get("width", 0), default={})
            if best and best.get("width", 0) >= min(w, h) // 2:
                results.append({
                    "url": best.get("link", ""),
                    "duration": clip.get("duration", 0),
                    "provider": "pexels",
                    "width": best.get("width", 0),
                    "height": best.get("height", 0),
                })
        return results

    def _search_pixabay(self, query: str, aspect: str, limit: int) -> list[dict]:
        if not self._pixabay_keys:
            return []
        key = self._pixabay_keys[self._key_idx % len(self._pixabay_keys)]
        self._key_idx += 1
        w, h = self._aspect_to_resolution(aspect)
        video_type = "vertical" if aspect == "portrait" else "horizontal"
        params = urllib.parse.urlencode({
            "key": key, "q": query, "per_page": str(limit * 2),
            "video_type": video_type, "min_width": str(min(w, h) // 2),
        })
        try:
            with urllib.request.urlopen(f"https://pixabay.com/api/videos/?{params}", timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []
        results = []
        for clip in data.get("hits", []):
            vids = clip.get("videos", {})
            best = vids.get("large") or vids.get("medium") or vids.get("small") or {}
            if best:
                results.append({
                    "url": best.get("url", ""),
                    "duration": clip.get("duration", 0),
                    "provider": "pixabay",
                    "width": best.get("width", 0),
                    "height": best.get("height", 0),
                })
        return results

    @staticmethod
    def _aspect_to_resolution(aspect: str) -> tuple[int, int]:
        return {"portrait": (1080, 1920), "landscape": (1920, 1080), "square": (1080, 1080)}.get(aspect, (1080, 1920))

    @staticmethod
    def _cache_key(query: str, aspect: str, source: str) -> str:
        return hashlib.md5(f"{source}:{aspect}:{query}".encode()).hexdigest()

    def _cache_get(self, key: str) -> list[dict] | None:
        path = self.CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.CACHE_TTL:
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _cache_set(self, key: str, data: list[dict]) -> None:
        path = self.CACHE_DIR / f"{key}.json"
        try:
            path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
