from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class ManualProvider(IProvider):
    """Provider adapter for manual web-based content generation and fallback routes.

    This covers manual_web (image/video via web), windows_tts (placeholder),
    and any other "human-in-the-loop" provider that doesn't execute API calls.
    """

    provider_name: ClassVar[str] = "manual"
    display_name: ClassVar[str] = "Manual / 人工"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("image", "video", "tts"),
        dispatch_channel="manual",
        auth_required=False,
        required_env=(),
    )

    def validate_config(self) -> dict[str, Any]:
        return {
            "ready": True,
            "errors": [],
            "warnings": [],
            "notes": "Manual provider is always available when output filenames follow convention.",
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="网页人工生成",
            notes="适合手动出图/视频后回填本地素材目录，以及 Windows TTS 占位。不执行 API 调用。",
        )

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", "manual_web"))
        return {
            "method": "NONE",
            "url": "",
            "headers": {},
            "body": {},
            "preflight": {
                "ready": True,
                "notes": "Manual/web-import based; no API request generated.",
                "provider": provider,
            },
        }

    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        """Manual providers don't execute API calls."""
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", "manual_web"))
        output_path = str(payload.get("output_path", ""))
        return {
            "provider": provider,
            "output_path": output_path,
            "content_type": "",
            "metadata": {
                "note": "Manual provider — no API call executed. Use import-manual-outputs to populate.",
                "provider": provider,
            },
        }

    def is_ready(self, request_item: dict[str, Any] | None = None) -> bool:
        return True


class PiperTTSProvider(IProvider):
    """Provider adapter for local Piper TTS."""

    provider_name: ClassVar[str] = "piper_tts"
    display_name: ClassVar[str] = "Piper TTS (本地)"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("tts",),
        dispatch_channel="local",
        auth_required=False,
        required_env=(),
    )

    def validate_config(self) -> dict[str, Any]:
        from aicomic.providers.local_adapter import (
            inspect_piper_paths,
            inspect_piper_license,
            inspect_piper_license_policy,
        )
        from aicomic.providers.local_adapter import resolve_config_path
        from aicomic.core.config import ProjectPaths

        project_root = ProjectPaths.project_root()
        errors: list[str] = []
        warnings: list[str] = []
        settings = self._load_providers_config(project_root)

        model_path_raw = str(settings.get("local_piper_tts", {}).get("model_path", ""))
        config_path_raw = str(settings.get("local_piper_tts", {}).get("config_path", ""))
        model_card_raw = str(settings.get("local_piper_tts", {}).get("model_card", ""))

        model_info = inspect_piper_paths(
            resolve_config_path(model_path_raw, project_root) if model_path_raw else None,
            resolve_config_path(config_path_raw, project_root) if config_path_raw else None,
        )
        model_card = Path(model_card_raw) if model_card_raw else None
        license_info = inspect_piper_license(model_card)
        license_policy = inspect_piper_license_policy(model_card)

        if not model_info.get("model_exists", False):
            errors.append("Piper model not found at configured path")
        if not license_info.get("license_status") == "known":
            warnings.append(f"Piper license is {license_info.get('license_status', 'unknown')} — review before production")

        return {
            "ready": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "model_info": model_info,
            "license_info": license_info,
            "license_policy": license_policy,
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="本地 Piper TTS",
            notes="基于 Piper 的本地离线 TTS。",
        )

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        from aicomic.providers.local_adapter import build_local_request_preview
        return build_local_request_preview(request_item, providers_config_path)

    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        from aicomic.providers.local_adapter import perform_local_request
        return perform_local_request(request_item, providers_config_path)

    def is_ready(self, request_item: dict[str, Any] | None = None) -> bool:
        config = self.validate_config()
        return bool(config.get("ready", False))

    def _load_providers_config(
        self,
        project_root: Path,
    ) -> dict[str, dict[str, object]]:
        config_path = project_root / "config" / "providers.yaml"
        if not config_path.exists():
            config_path = project_root / "providers.yaml"
        if config_path.exists():
            from aicomic.providers.provider_planner import load_provider_settings
            return load_provider_settings(config_path)
        return {}
