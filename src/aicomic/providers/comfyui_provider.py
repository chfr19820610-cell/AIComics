from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, ClassVar

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class ComfyUIProvider(IProvider):
    """Provider adapter wrapping existing ComfyUI service logic.

    Uses the existing comfyui_service and local_adapter modules for
    the actual execution, providing a uniform class-based interface
    for the provider abstraction layer.
    """

    provider_name: ClassVar[str] = "comfyui"
    display_name: ClassVar[str] = "本地 ComfyUI"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("image", "video"),
        dispatch_channel="local",
        auth_required=False,
        required_env=(),
    )

    def __init__(self, project_root: Path | None = None) -> None:
        from aicomic.core.config import ProjectPaths
        self._project_root = project_root or ProjectPaths.project_root()

    def validate_config(self) -> dict[str, Any]:
        """Check ComfyUI runtime configuration."""
        from aicomic.providers.local_adapter import (
            LOCAL_EXECUTION_PROVIDERS,
            inspect_comfyui_model_requirements,
            inspect_comfyui_workflow_path,
            inspect_comfyui_workflow_model_usage,
            comfyui_server_available,
        )
        from aicomic.providers.comfyui_service import resolve_comfyui_service_config

        settings = self._load_providers_config()
        errors: list[str] = []
        warnings: list[str] = []

        # Check service config
        config = resolve_comfyui_service_config(project_root=self._project_root)
        comfyui_exists = config.comfyui_root.exists()

        if not comfyui_exists:
            errors.append(f"ComfyUI runtime not found at {config.comfyui_root}")

        # Check workflow
        image_workflow = self._resolve_workflow_path("image_workflow.json")
        video_workflow = self._resolve_workflow_path("video_workflow.json")

        if image_workflow:
            wf = inspect_comfyui_workflow_path(image_workflow)
            if not wf.get("workflow_api_format", False):
                warnings.append(f"Image workflow issue: {wf.get('workflow_error', 'not valid')}")

        if video_workflow:
            wf = inspect_comfyui_workflow_path(video_workflow)
            if not wf.get("workflow_api_format", False):
                warnings.append(f"Video workflow issue: {wf.get('workflow_error', 'not valid')}")

        # Check server availability
        available, server_err = comfyui_server_available(config.base_url, 2.0)
        if not available:
            warnings.append(f"ComfyUI server not reachable at {config.base_url}: {server_err}")

        # Check model requirements
        model_root = self._resolve_model_root()
        manifest_path = self._resolve_manifest_path()
        for provider in ("local_comfyui_image", "local_comfyui_video"):
            reqs = inspect_comfyui_model_requirements(provider, model_root, manifest_path)
            if not reqs.get("required_models_ready", False):
                warnings.append(f"{provider}: {reqs.get('missing_required_model_count', 0)} models missing")

        ready = len(errors) == 0
        return {
            "ready": ready,
            "errors": errors,
            "warnings": warnings,
            "comfyui_root_exists": comfyui_exists,
            "server_available": available,
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="本地 ComfyUI 出图/视频",
            notes="ComfyUI 本地工作流。支持 image 和 video 的 API prompt 模式。",
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
        from aicomic.providers.local_adapter import comfyui_server_available
        from aicomic.providers.comfyui_service import resolve_comfyui_service_config

        config = resolve_comfyui_service_config(project_root=self._project_root)
        available, _ = comfyui_server_available(config.base_url, 1.0)
        return available

    # ── Private helpers ─────────────────────────────────────────────────

    def _load_providers_config(self) -> dict[str, dict[str, object]]:
        config_path = self._project_root / "config" / "providers.yaml"
        if not config_path.exists():
            config_path = self._project_root / "providers.yaml"
        if config_path.exists():
            from aicomic.providers.provider_planner import load_provider_settings
            return load_provider_settings(config_path)
        return {}

    def _resolve_workflow_path(self, filename: str) -> Path | None:
        path = (
            self._project_root
            / "local_providers"
            / "comfyui"
            / "workflows"
            / filename
        )
        if path.exists():
            return path
        return None

    def _resolve_model_root(self) -> Path | None:
        root = self._project_root / "local_providers" / "comfyui" / "models"
        if root.exists():
            return root
        return None

    def _resolve_manifest_path(self) -> Path | None:
        path = (
            self._project_root
            / "local_providers"
            / "comfyui"
            / "model_requirements.json"
        )
        if path.exists():
            return path
        return None
