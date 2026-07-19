from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.providers.base import IProvider
from aicomic.providers.openai_provider import OpenAIProvider, DALL_EProvider
from aicomic.providers.seedance_provider import SeedanceProvider
from aicomic.providers.kling_provider import KlingProvider
from aicomic.providers.comfyui_provider import ComfyUIProvider
from aicomic.providers.manual_provider import ManualProvider, PiperTTSProvider


# ── Registry ─────────────────────────────────────────────────────────────

class ProviderRegistry:
    """Central registry for all IProvider implementations.

    Providers are registered by their provider_name. The registry
    provides factory methods, discovery, and lifecycle management.
    """

    def __init__(self) -> None:
        self._providers: dict[str, type[IProvider]] = {}
        self._instances: dict[str, IProvider] = {}
        self._project_root: Path | None = None

    def register(self, cls: type[IProvider]) -> None:
        """Register a provider class by its provider_name."""
        name: str = getattr(cls, "provider_name", "")
        if not name:
            raise ValueError(f"Provider {cls.__name__} has no provider_name")
        self._providers[name] = cls

    def unregister(self, name: str) -> None:
        """Remove a provider from the registry."""
        self._providers.pop(name, None)
        self._instances.pop(name, None)

    def get(self, name: str) -> IProvider | None:
        """Get a provider instance by name (cached singleton per name)."""
        if name in self._instances:
            return self._instances[name]

        cls = self._providers.get(name)
        if cls is None:
            return None

        kwargs: dict[str, Any] = {}
        if self._project_root is not None:
            # Only pass project_root if the class accepts it
            import inspect
            sig = inspect.signature(cls.__init__)
            if "project_root" in sig.parameters:
                kwargs["project_root"] = self._project_root

        instance = cls(**kwargs)
        self._instances[name] = instance
        return instance

    def get_or_fail(self, name: str) -> IProvider:
        """Like get() but raises KeyError if not found."""
        provider = self.get(name)
        if provider is None:
            raise KeyError(f"No provider registered for: {name}")
        return provider

    def list_registered(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers.keys())

    def list_available(self, job_type: str | None = None) -> list[IProvider]:
        """Return provider instances, optionally filtered by job type."""
        results: list[IProvider] = []
        for name in self._providers:
            provider = self.get(name)
            if provider is None:
                continue
            if job_type is not None:
                cap = provider.capabilities
                if job_type not in cap.job_types:
                    continue
            results.append(provider)
        return results

    def resolve_for_job(
        self,
        provider_name: str,
    ) -> IProvider | None:
        """Resolve a provider for a given name, with name remapping.

        Handles mapping from provider_planner names (openai_image, etc.)
        to registered provider names (openai, dall_e, etc.).
        """
        # Direct match first
        provider = self.get(provider_name)
        if provider is not None:
            return provider

        # Name remapping
        NAME_MAP: dict[str, str] = {
            "openai_image": "openai",
            "openai_tts": "openai",
            "local_comfyui_image": "comfyui",
            "local_comfyui_video": "comfyui",
            "local_comfyui_video_wan22": "comfyui",
            "local_piper_tts": "piper_tts",
            "manual_web": "manual",
            "windows_tts": "manual",
            "sora": "openai",
        }
        mapped = NAME_MAP.get(provider_name)
        if mapped is not None:
            return self.get(mapped)
        return None

    # ── Cloud-first with local fallback ────────────────────────────────

    FALLBACK_MAP: dict[str, str] = {
        "openai_image": "local_comfyui_image",
        "openai_tts": "local_piper_tts",
        "seedance": "local_comfyui_video_wan22",
        "kling": "local_comfyui_video_wan22",
        "openai": "comfyui",
    }

    def resolve_with_fallback(
        self,
        provider_name: str,
    ) -> tuple[IProvider | None, str | None]:
        """Try cloud provider first, fall back to local if unavailable.

        Returns (provider, actual_name_used).
        - If cloud provider is ready → use it
        - If cloud provider needs auth/key → fall back to local
        - If no fallback available → return the cloud provider anyway (dry-run)

        The caller should call provider.validate_config() to check readiness
        before dispatching a job.
        """
        # Try primary
        primary = self.resolve_for_job(provider_name)
        if primary is not None:
            cfg = primary.validate_config()
            if cfg.get("ready", False):
                return primary, provider_name

        # Try fallback
        fallback_name = self.FALLBACK_MAP.get(provider_name)
        if fallback_name is None:
            # Also check remapped name
            NAME_MAP: dict[str, str] = {
                "openai_image": "openai",
                "openai_tts": "openai",
                "local_comfyui_image": "comfyui",
                "local_comfyui_video": "comfyui",
                "local_comfyui_video_wan22": "comfyui",
                "local_piper_tts": "piper_tts",
                "manual_web": "manual",
                "windows_tts": "manual",
                "sora": "openai",
            }
            remapped = NAME_MAP.get(provider_name)
            if remapped:
                fallback_name = self.FALLBACK_MAP.get(remapped)
            if fallback_name is None:
                # No fallback, return primary (will dry-run)
                return primary, provider_name

        fallback = self.resolve_for_job(fallback_name)
        if fallback is not None:
            return fallback, fallback_name

        # Fallback not registered either, return primary
        return primary, provider_name

    def set_project_root(self, root: Path) -> None:
        """Set project root for providers that need it."""
        self._project_root = root
        # Clear cached instances so they re-init with the new root
        self._instances.clear()


# ── Default registry instance ────────────────────────────────────────────

_DEFAULT_REGISTRY: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get or create the default singleton provider registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _create_default_registry()
    return _DEFAULT_REGISTRY


def _create_default_registry() -> ProviderRegistry:
    """Create and populate the default registry with all built-in providers."""
    registry = ProviderRegistry()
    registry.register(OpenAIProvider)
    registry.register(DALL_EProvider)
    registry.register(SeedanceProvider)
    registry.register(KlingProvider)
    registry.register(ComfyUIProvider)
    registry.register(ManualProvider)
    registry.register(PiperTTSProvider)
    return registry


def reset_provider_registry() -> None:
    """Reset the default registry (useful for testing)."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
