from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, ClassVar

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class OpenAIProvider(IProvider):
    """Provider adapter for OpenAI / DALL-E image generation and TTS."""

    provider_name: ClassVar[str] = "openai"
    display_name: ClassVar[str] = "OpenAI / DALL-E"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("image", "tts"),
        dispatch_channel="api",
        auth_required=True,
        required_env=("OPENAI_API_KEY",),
    )

    DALL_E_MODELS = frozenset({"dall-e-3", "dall-e-2", "gpt-image-1.5"})
    TTS_MODELS = frozenset({"gpt-4o-mini-tts", "tts-1", "tts-1-hd"})
    IMAGE_ENDPOINT = "/v1/images/generations"
    TTS_ENDPOINT = "/v1/audio/speech"

    def validate_config(self) -> dict[str, Any]:
        env_check = self._check_env_vars("OPENAI_API_KEY")
        if env_check["ready"]:
            return {
                "ready": True,
                "errors": [],
                "warnings": [],
                "api_key_configured": True,
            }
        return {
            "ready": False,
            "errors": env_check["errors"],
            "warnings": [
                "OpenAI API key not set; image/tts requests will be dry-run only."
            ],
            "api_key_configured": False,
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="API 自动出图/配音",
            notes="适合 DALL-E 图片生成和 OpenAI TTS 配音；支持 gpt-image-1.5 模型。",
        )

    # ── Config helpers ──────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "").strip()

    def _get_base_url(self, settings: dict[str, dict[str, object]]) -> str:
        api_cfg = settings.get("openai_api", {})
        return str(api_cfg.get("base_url", "https://api.openai.com")).rstrip("/")

    def _get_timeout(self, settings: dict[str, dict[str, object]]) -> int:
        raw = str(settings.get("openai_api", {}).get("timeout_seconds", "120")).strip()
        if raw.isdigit():
            return int(raw)
        return 120

    # ── Request building ────────────────────────────────────────────────

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", ""))
        base_url = self._get_base_url(settings)
        body: dict[str, Any] = {}

        if provider == "openai_image":
            endpoint = f"{base_url}{self.IMAGE_ENDPOINT}"
            img_cfg = settings.get("openai_image", {})
            body = {
                "model": str(img_cfg.get("model", "gpt-image-1.5")),
                "prompt": str(payload.get("prompt", "")),
                "n": 1,
                "size": str(img_cfg.get("size", "1024x1536")),
                "quality": str(img_cfg.get("quality", "medium")),
                "output_format": str(img_cfg.get("output_format", "png")),
            }
            preflight_info = {
                "ready": bool(self._get_api_key()),
                "notes": "" if self._get_api_key() else "OPENAI_API_KEY not set",
            }
        elif provider == "openai_tts":
            endpoint = f"{base_url}{self.TTS_ENDPOINT}"
            tts_cfg = settings.get("openai_tts", {})
            body = {
                "model": str(tts_cfg.get("model", "gpt-4o-mini-tts")),
                "input": str(payload.get("prompt", "")),
                "voice": str(tts_cfg.get("voice", "alloy")),
                "response_format": str(tts_cfg.get("response_format", "wav")),
                "speed": float(str(tts_cfg.get("speed", "1.0"))),
                "instructions": str(tts_cfg.get("instructions", "")),
            }
            preflight_info = {
                "ready": bool(self._get_api_key()),
                "notes": "" if self._get_api_key() else "OPENAI_API_KEY not set",
            }
        else:
            endpoint = ""
            preflight_info = {
                "ready": False,
                "notes": f"Unsupported OpenAI sub-provider: {provider}",
            }

        return {
            "method": "POST",
            "url": endpoint,
            "headers": {
                "Authorization": "Bearer $OPENAI_API_KEY",
                "Content-Type": "application/json",
            },
            "body": body,
            "preflight": preflight_info,
        }

    # ── Execution ───────────────────────────────────────────────────────

    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})
        provider = str(payload.get("provider", ""))
        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        preview = self.build_request(request_item, providers_config_path)
        endpoint = str(preview["url"])
        body_bytes = json.dumps(preview["body"], ensure_ascii=False).encode("utf-8")

        http_request = Request(
            endpoint,
            data=body_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._get_timeout(settings)) as response:
                response_bytes = response.read()
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTPError {error.code}: {error_body}") from error
        except URLError as error:
            raise RuntimeError(f"OpenAI URLError: {error.reason}") from error

        output_path = Path(str(payload["output_path"]))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if provider == "openai_image":
            response_json = json.loads(response_bytes.decode("utf-8"))
            image_payload = response_json["data"][0]["b64_json"]
            output_path.write_bytes(base64.b64decode(image_payload))
            return {
                "provider": provider,
                "output_path": str(output_path),
                "content_type": content_type,
                "response_meta": {
                    "created": response_json.get("created"),
                    "usage": response_json.get("usage"),
                    "revised_prompt": response_json["data"][0].get("revised_prompt", ""),
                },
            }

        if provider == "openai_tts":
            output_path.write_bytes(response_bytes)
            return {
                "provider": provider,
                "output_path": str(output_path),
                "content_type": content_type,
                "response_meta": {
                    "bytes": len(response_bytes),
                },
            }

        raise RuntimeError(f"Unsupported OpenAI provider: {provider}")

    def is_ready(self, request_item: dict[str, Any] | None = None) -> bool:
        return bool(self._get_api_key())


class DALL_EProvider(OpenAIProvider):
    """Specialised DALL-E adapter. Routes via openai_image provider name."""

    provider_name: ClassVar[str] = "dall_e"
    display_name: ClassVar[str] = "DALL-E Image Generation"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("image",),
        dispatch_channel="api",
        auth_required=True,
        required_env=("OPENAI_API_KEY",),
    )

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="API DALL-E 自动出图",
            notes="DALL-E 3 / gpt-image-1.5 图片生成专用。",
        )

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        # Force the provider key for routing
        payload = dict(request_item.get("payload", {}))
        payload["provider"] = "openai_image"
        modified_item = {**request_item, "payload": payload}
        return super().build_request(modified_item, providers_config_path)

    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        payload = dict(request_item.get("payload", {}))
        payload["provider"] = "openai_image"
        modified_item = {**request_item, "payload": payload}
        return super().execute_request(modified_item, providers_config_path)
