"""SaaS API key system — multi-tenant API key management."""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path


def generate_api_key() -> str:
    return f"aic_{secrets.token_hex(16)}"


def validate_api_key(key: str, manager: APIKeyManager) -> bool:
    """Validate an API key against a manager instance."""
    return manager.validate(key)


class APIKeyManager:
    """Manage API keys with tenant isolation."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._keys: dict[str, dict] = {}  # {key: {tenant, plan, created_at, revoked}}
        if self.path.exists():
            self._keys = json.loads(self.path.read_text(encoding="utf-8"))

    def create_key(self, tenant: str, plan: str = "free") -> str:
        key = generate_api_key()
        self._keys[key] = {
            "tenant": tenant,
            "plan": plan,
            "created_at": int(time.time()),
            "revoked": False,
        }
        self._save()
        return key

    def validate(self, key: str) -> bool:
        info = self._keys.get(key)
        return info is not None and not info.get("revoked", False)

    def revoke(self, key: str) -> None:
        if key in self._keys:
            self._keys[key]["revoked"] = True
            self._save()

    def get_tenant(self, key: str) -> dict | None:
        return self._keys.get(key)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._keys, ensure_ascii=False, indent=2), encoding="utf-8")
