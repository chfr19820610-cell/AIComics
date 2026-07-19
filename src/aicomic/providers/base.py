from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    """Describes what a provider can do."""
    job_types: tuple[str, ...]
    dispatch_channel: str
    auth_required: bool
    required_env: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    """Metadata returned by IProvider.get_provider_info()."""
    provider_name: str
    display_name: str
    capabilities: ProviderCapability
    run_mode: str
    notes: str = ""


class IProvider(ABC):
    """Abstract base class for all AIComics model providers.

    Each provider subclass implements the lifecycle:
      validate_config()  → check env vars, files, services
      build_request()    → construct the API request payload
      execute_request()  → send the request and return results
      get_provider_info() → metadata for routing/readiness
      is_ready()         → quick readiness check
    """

    provider_name: ClassVar[str]
    display_name: ClassVar[str]
    capabilities: ClassVar[ProviderCapability]

    # ── Configuration Lifecycle ──────────────────────────────────────────

    @abstractmethod
    def validate_config(self) -> dict[str, Any]:
        """Validate the provider's configuration.

        Checks environment variables, configuration files, or service
        availability. Returns a dict with at least:
          {"ready": bool, "errors": list[str], "warnings": list[str]}
        """
        ...

    # ── Request Building ────────────────────────────────────────────────

    @abstractmethod
    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        """Build a request preview without executing it.

        Returns the structured request that *would* be sent, including
        method, URL, headers, and body. Also includes a 'preflight' key
        with readiness information.
        """
        ...

    # ── Execution ───────────────────────────────────────────────────────

    @abstractmethod
    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        """Execute the provider request and return results.

        The return dict MUST include at least:
          {"provider": str, "output_path": str, "content_type": str}
        and may include additional provider-specific metadata.
        """
        ...

    # ── Metadata / Readiness ────────────────────────────────────────────

    @abstractmethod
    def get_provider_info(self) -> ProviderInfo:
        """Return metadata about this provider for routing and planning."""
        ...

    def is_ready(self, request_item: dict[str, Any] | None = None) -> bool:
        """Quick readiness check. Default: delegates to validate_config."""
        return bool(self.validate_config().get("ready", False))

    # ── Helpers ─────────────────────────────────────────────────────────

    def _check_env_vars(self, *names: str) -> dict[str, Any]:
        """Check required environment variables."""
        errors: list[str] = []
        warnings: list[str] = []
        statuses: list[dict[str, Any]] = []
        for name in names:
            value = os.environ.get(name, "").strip()
            configured = bool(value)
            statuses.append({"name": name, "configured": configured})
            if not configured:
                errors.append(f"Missing environment variable: {name}")
        return {
            "ready": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "env_status": statuses,
        }

    def _load_settings(self, providers_config_path: Path) -> dict[str, dict[str, object]]:
        """Load YAML-style provider settings."""
        if not providers_config_path.exists():
            return {}
        settings: dict[str, dict[str, object]] = {}
        current_section = ""
        current_list_key = ""
        for raw_line in providers_config_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.strip().startswith("#"):
                continue
            stripped_line = raw_line.strip()
            if not raw_line.startswith(" ") and stripped_line.endswith(":"):
                current_section = stripped_line[:-1]
                settings.setdefault(current_section, {})
                current_list_key = ""
                continue
            if not current_section:
                continue
            if stripped_line.endswith(":"):
                current_list_key = stripped_line[:-1]
                settings[current_section].setdefault(current_list_key, [])
                continue
            if stripped_line.startswith("- ") and current_list_key:
                list_value = settings[current_section].setdefault(current_list_key, [])
                if isinstance(list_value, list):
                    list_value.append(stripped_line[2:].strip())
                continue
            if ":" in stripped_line:
                key, value = stripped_line.split(":", 1)
                settings[current_section][key.strip()] = value.strip()
        return settings

    def _prod(
        self,
        path: Path | None,
        *parts: str,
    ) -> Path | None:
        """Resolve a path if base is set, else None."""
        if path is None:
            return None
        return path.joinpath(*parts).resolve()
