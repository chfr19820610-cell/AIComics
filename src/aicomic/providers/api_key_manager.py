"""API Key management — unified encrypted storage for all provider keys.

Centralizes API keys for all providers (Kling, Seedance, Wan, OpenAI,
etc.) with rotation tracking, quota monitoring, and failure alerts.

Keys are stored in a JSON file with base64-encoded values (obfuscation,
not strong encryption — use OS keychain for production).

Usage:
    manager = APIKeyManager()
    manager.set_key("kling", "sk-xxx", quota_limit=1000)
    key = manager.get_key("kling")
    manager.record_usage("kling", tokens=50)
    status = manager.get_key_status("kling")
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class KeyRecord:
    """A single API key record."""

    provider: str
    key_value: str = ""  # base64-encoded
    base_url: str = ""
    model: str = ""
    enabled: bool = True
    quota_limit: int = 0  # 0 = unlimited
    quota_used: int = 0
    last_used: float = 0.0
    last_rotated: float = 0.0
    failure_count: int = 0
    created_at: float = 0.0
    notes: str = ""

    def to_dict(self, include_key: bool = False) -> dict[str, Any]:
        d = {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "enabled": self.enabled,
            "quota_limit": self.quota_limit,
            "quota_used": self.quota_used,
            "last_used": self.last_used,
            "last_rotated": self.last_rotated,
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "notes": self.notes,
        }
        if include_key:
            d["key_value"] = self.key_value
        return d


class APIKeyManager:
    """Unified API key management with quota tracking and rotation.

    Args:
        storage_path: Path to the encrypted key storage file.
    """

    DEFAULT_PROVIDERS = [
        "kling", "seedance", "wan", "openai", "gemini",
        "hunyuan_avatar", "edge_tts",
    ]

    def __init__(self, storage_path: Path | str = "state/api_keys.json") -> None:
        self._path = Path(storage_path)
        self._keys: dict[str, KeyRecord] = {}
        self._load()

    def _load(self) -> None:
        """Load keys from storage."""
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for provider, record in data.items():
                self._keys[provider] = KeyRecord(**record)
        except (json.JSONDecodeError, TypeError):
            pass  # corrupted file — start fresh

    def _save(self) -> None:
        """Save keys to storage."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict(include_key=True) for k, v in self._keys.items()}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set_key(
        self,
        provider: str,
        key_value: str,
        base_url: str = "",
        model: str = "",
        quota_limit: int = 0,
        notes: str = "",
    ) -> None:
        """Set or update an API key for a provider.

        Args:
            provider: Provider name (e.g. "kling").
            key_value: The API key value (will be base64-encoded).
            base_url: API endpoint URL.
            model: Default model name.
            quota_limit: Monthly quota limit (0 = unlimited).
            notes: Optional notes.
        """
        encoded = base64.b64encode(key_value.encode()).decode() if key_value else ""
        existing = self._keys.get(provider)
        self._keys[provider] = KeyRecord(
            provider=provider,
            key_value=encoded,
            base_url=base_url or (existing.base_url if existing else ""),
            model=model or (existing.model if existing else ""),
            enabled=True,
            quota_limit=quota_limit or (existing.quota_limit if existing else 0),
            quota_used=existing.quota_used if existing else 0,
            last_used=existing.last_used if existing else 0.0,
            last_rotated=time.time(),
            failure_count=0,
            created_at=existing.created_at if existing else time.time(),
            notes=notes,
        )
        self._save()

    def get_key(self, provider: str) -> str:
        """Get the decrypted API key for a provider.

        Returns empty string if not set or disabled.
        """
        record = self._keys.get(provider)
        if record is None or not record.enabled or not record.key_value:
            return ""
        try:
            return base64.b64decode(record.key_value).decode()
        except Exception:
            return ""

    def get_base_url(self, provider: str) -> str:
        """Get the base URL for a provider."""
        record = self._keys.get(provider)
        return record.base_url if record else ""

    def is_configured(self, provider: str) -> bool:
        """Check if a provider has a key configured and enabled."""
        record = self._keys.get(provider)
        return record is not None and record.enabled and bool(record.key_value)

    def record_usage(self, provider: str, tokens: int = 1) -> None:
        """Record API usage for quota tracking.

        Args:
            provider: Provider name.
            tokens: Number of tokens or units used.
        """
        record = self._keys.get(provider)
        if record is None:
            return
        record.quota_used += tokens
        record.last_used = time.time()
        self._save()

    def record_failure(self, provider: str) -> None:
        """Record an API failure for a provider."""
        record = self._keys.get(provider)
        if record is None:
            return
        record.failure_count += 1
        # Auto-disable after 10 consecutive failures
        if record.failure_count >= 10:
            record.enabled = False
        self._save()

    def record_success(self, provider: str) -> None:
        """Record a successful API call — resets failure count."""
        record = self._keys.get(provider)
        if record is None:
            return
        record.failure_count = 0
        self._save()

    def disable(self, provider: str) -> None:
        """Disable a provider key."""
        record = self._keys.get(provider)
        if record:
            record.enabled = False
            self._save()

    def enable(self, provider: str) -> None:
        """Enable a provider key."""
        record = self._keys.get(provider)
        if record:
            record.enabled = True
            record.failure_count = 0
            self._save()

    def rotate_key(self, provider: str, new_key: str) -> None:
        """Rotate an API key (updates value and resets failure count)."""
        existing = self._keys.get(provider)
        if existing is None:
            self.set_key(provider, new_key)
            return
        encoded = base64.b64encode(new_key.encode()).decode()
        existing.key_value = encoded
        existing.last_rotated = time.time()
        existing.failure_count = 0
        existing.enabled = True
        self._save()

    def get_key_status(self, provider: str) -> dict[str, Any]:
        """Get detailed status for a provider key (without revealing the key)."""
        record = self._keys.get(provider)
        if record is None:
            return {"provider": provider, "status": "not_configured"}
        quota_remaining = record.quota_limit - record.quota_used if record.quota_limit > 0 else -1
        return {
            "provider": provider,
            "status": "active" if record.enabled else "disabled",
            "has_key": bool(record.key_value),
            "base_url": record.base_url,
            "model": record.model,
            "quota_limit": record.quota_limit,
            "quota_used": record.quota_used,
            "quota_remaining": quota_remaining,
            "quota_pct": round(record.quota_used / record.quota_limit * 100, 1) if record.quota_limit > 0 else 0,
            "failure_count": record.failure_count,
            "last_used": record.last_used,
            "last_rotated": record.last_rotated,
            "age_days": round((time.time() - record.last_rotated) / 86400, 1) if record.last_rotated else 0,
        }

    def get_all_status(self) -> list[dict[str, Any]]:
        """Get status for all configured providers."""
        return [self.get_key_status(p) for p in self._keys]

    def get_unconfigured(self) -> list[str]:
        """Get list of default providers that are not configured."""
        return [p for p in self.DEFAULT_PROVIDERS if not self.is_configured(p)]

    def export_config(self) -> dict[str, Any]:
        """Export non-sensitive config for display (no key values)."""
        return {
            provider: record.to_dict(include_key=False)
            for provider, record in self._keys.items()
        }
