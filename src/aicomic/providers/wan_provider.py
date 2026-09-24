"""Wan video generation provider — open-source model via API.

Wan 2.2/2.5 models are accessed through OpenAI-compatible or Fal.ai-style
endpoints.  This adapter implements the full IProvider lifecycle so the
video router can dispatch wide/landscape shots to Wan without falling back
to a stub.

Environment variables:
    WAN_API_KEY      — API key for the Wan endpoint
    WAN_BASE_URL     — Base URL (default: https://api.fal.ai/v1)
    WAN_MODEL        — Model name (default: wan-2.5-i2v)
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from aicomic.providers.base import (
    IProvider,
    ProviderCapability,
    ProviderInfo,
)
from aicomic.providers._vidgen_mixin import _VidGenProviderMixin


class WanProvider(IProvider, _VidGenProviderMixin):
    """Wan open-source video model provider (I2V / T2V)."""

    provider_name: str = "wan"
    display_name: str = "Wan 2.5 (Open-Source Video Model)"

    capabilities: ProviderCapability = ProviderCapability(
        job_types=("text-to-video", "image-to-video"),
        dispatch_channel="api",
        auth_required=True,
        required_env=("WAN_API_KEY",),
    )

    def __init__(self, providers_config_path: Path | None = None) -> None:
        self._config_path = providers_config_path
        self._api_key = os.environ.get("WAN_API_KEY", "")
        self._base_url = os.environ.get("WAN_BASE_URL", "https://api.fal.ai/v1")
        self._model = os.environ.get("WAN_MODEL", "wan-2.5-i2v")

    # ── Configuration Lifecycle ──────────────────────────────────────────

    def validate_config(self) -> dict[str, Any]:
        """Check that WAN_API_KEY is set and non-empty."""
        if not self._api_key:
            return {"valid": False, "reason": "WAN_API_KEY environment variable is not set"}
        return {"valid": True, "model": self._model, "base_url": self._base_url}

    def get_provider_info(self) -> ProviderInfo:
        valid = self.validate_config()
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="api" if valid["valid"] else "not-configured",
            notes=f"Model: {self._model} | Endpoint: {self._base_url}",
        )

    def is_ready(self) -> bool:
        """Quick readiness check — API key present."""
        return bool(self._api_key)

    # ── Request Lifecycle ────────────────────────────────────────────────

    def build_request(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        duration: float = 5.0,
        resolution: str = "1280x720",
        seed: int | None = None,
        image_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build a Wan API request payload.

        Wan supports both T2V and I2V — if ``image_url`` is provided,
        builds an I2V request; otherwise T2V.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": str(duration),
            "resolution": resolution,
            "seed": seed if seed is not None else -1,
        }
        if image_url:
            payload["image_url"] = image_url
            payload["task_type"] = "i2v"
        else:
            payload["task_type"] = "t2v"
        return payload

    def execute_request(
        self,
        request: dict[str, Any],
        providers_config_path: str | Path | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the Wan API request and poll for completion.

        Wan uses an async submit-then-poll pattern:
        1. POST /submit → get task_id
        2. GET /status/{task_id} → poll until SUCCEEDED/FAILED
        3. Return video URL + metadata

        Returns:
            Dict with keys: status, video_url, task_id, metadata.
        """
        import httpx

        if not self._api_key:
            return {"status": "error", "reason": "WAN_API_KEY not set"}

        headers = {
            "Authorization": f"Key {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Step 1: Submit task
            submit_resp = httpx.post(
                f"{self._base_url}/submit",
                headers=headers,
                json=request,
                timeout=60.0,
            )
            submit_resp.raise_for_status()
            task_data = submit_resp.json()
            task_id = task_data.get("request_id") or task_data.get("task_id")
            if not task_id:
                return {"status": "error", "reason": "No task_id in submit response", "raw": task_data}

            # Step 2: Poll for completion (max 5 minutes)
            max_polls = 60
            poll_interval = 5.0
            for _ in range(max_polls):
                time.sleep(poll_interval)
                status_resp = httpx.get(
                    f"{self._base_url}/status/{task_id}",
                    headers=headers,
                    timeout=30.0,
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
                state = status_data.get("status", "").upper()

                if state == "COMPLETED" or state == "SUCCEEDED":
                    video_url = (
                        status_data.get("video_url")
                        or status_data.get("output", {}).get("video_url")
                        or status_data.get("result", {}).get("video_url", "")
                    )
                    return {
                        "status": "success",
                        "video_url": video_url,
                        "task_id": task_id,
                        "metadata": status_data,
                    }
                if state == "FAILED" or state == "ERROR":
                    return {
                        "status": "failed",
                        "task_id": task_id,
                        "reason": status_data.get("error", "Unknown error"),
                        "metadata": status_data,
                    }
                # Still processing — continue polling

            return {"status": "timeout", "task_id": task_id, "reason": "Polling exceeded 5 minutes"}

        except httpx.HTTPError as exc:
            return {"status": "error", "reason": f"HTTP error: {exc}"}
        except Exception as exc:
            return {"status": "error", "reason": f"Unexpected error: {exc}"}
