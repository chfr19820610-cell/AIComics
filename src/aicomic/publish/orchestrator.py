"""Unified multi-platform publish orchestrator — one call, all platforms.

Combines domestic (douyin/xiaohongshu/bilibili) and international
(youtube/tiktok/instagram) publishers into a single unified interface.

Usage:
    orchestrator = PublishOrchestrator()
    result = orchestrator.publish_all(
        video_path=Path("episode.mp4"),
        title="九转丹霄 第一集",
        platforms=["youtube", "tiktok", "douyin", "bilibili"],
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PublishResult:
    """Result of a multi-platform publish operation."""

    total_platforms: int = 0
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    details: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_platforms == 0:
            return 0.0
        return len(self.succeeded) / self.total_platforms

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_platforms": self.total_platforms,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 3),
            "details": self.details,
        }


class PublishOrchestrator:
    """Unified multi-platform publish orchestrator.

    Routes to domestic or international publisher based on platform name.
    """

    DOMESTIC_PLATFORMS = {"douyin", "xiaohongshu", "bilibili"}
    INTERNATIONAL_PLATFORMS = {"youtube", "tiktok", "instagram"}

    def __init__(self, domestic_config_path: Path | None = None) -> None:
        self._domestic_config_path = domestic_config_path

    def publish_all(
        self,
        video_path: Path | str,
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
        platforms: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> PublishResult:
        """Publish to all specified platforms.

        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            tags: List of tags/hashtags.
            platforms: List of platform names. Default: all configured.
            config: Optional config dict (otherwise loads from publish.yaml).

        Returns:
            PublishResult with per-platform details.
        """
        all_platforms = platforms or list(
            self.DOMESTIC_PLATFORMS | self.INTERNATIONAL_PLATFORMS
        )

        result = PublishResult(total_platforms=len(all_platforms))
        tags = tags or []

        domestic_platforms = [p for p in all_platforms if p in self.DOMESTIC_PLATFORMS]
        international_platforms = [p for p in all_platforms if p in self.INTERNATIONAL_PLATFORMS]
        unknown = [p for p in all_platforms if p not in self.DOMESTIC_PLATFORMS and p not in self.INTERNATIONAL_PLATFORMS]

        # Mark unknown platforms as skipped
        for p in unknown:
            result.skipped.append(p)
            result.details[p] = {"success": False, "error": "Unknown platform"}

        # Publish to domestic platforms
        if domestic_platforms:
            dom_result = self._publish_domestic(
                video_path, title, description, tags, domestic_platforms, config,
            )
            for platform, detail in dom_result.items():
                result.details[platform] = detail
                if detail.get("success"):
                    result.succeeded.append(platform)
                else:
                    result.failed.append(platform)

        # Publish to international platforms
        if international_platforms:
            intl_result = self._publish_international(
                video_path, title, description, tags, international_platforms, config,
            )
            for platform, detail in intl_result.items():
                result.details[platform] = detail
                if detail.get("success"):
                    if platform not in result.succeeded:
                        result.succeeded.append(platform)
                else:
                    if platform not in result.failed:
                        result.failed.append(platform)

        return result

    def _publish_domestic(
        self,
        video_path: Path | str,
        title: str,
        description: str,
        tags: list[str],
        platforms: list[str],
        config: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Publish to domestic platforms via domestic_publisher."""
        from aicomic.publish.domestic_publisher import (
            PublishPayload as DomesticPayload,
            load_publish_config,
            publish_to_platforms,
        )

        cfg = config or load_publish_config(self._domestic_config_path)
        payload = DomesticPayload(
            video_path=Path(video_path),
            title=title,
            description=description,
            tags=tags,
        )
        return publish_to_platforms(payload, platforms, cfg)

    def _publish_international(
        self,
        video_path: Path | str,
        title: str,
        description: str,
        tags: list[str],
        platforms: list[str],
        config: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Publish to international platforms via international module."""
        from aicomic.publish.international import PublishPayload as IntlPayload, publish as intl_publish

        cfg = config or {}
        payload = IntlPayload(
            video_path=Path(video_path),
            title=title,
            description=description,
            tags=tags,
        )
        return intl_publish(payload, platforms, cfg)

    def get_supported_platforms(self) -> dict[str, list[str]]:
        """Get all supported platforms grouped by category."""
        return {
            "domestic": sorted(self.DOMESTIC_PLATFORMS),
            "international": sorted(self.INTERNATIONAL_PLATFORMS),
        }
