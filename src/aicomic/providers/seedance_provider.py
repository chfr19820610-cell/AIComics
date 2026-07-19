from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class SeedanceProvider(IProvider):
    """Provider adapter for Seedance (豆包/火山引擎) video generation.

    Supports text-to-video and image-to-video modes via the Volc Ark API.
    Mirrors the AIComicBuilder SeedanceProvider pattern but in Python,
    matching the existing codebase's synchronous request pattern.
    """

    provider_name: ClassVar[str] = "seedance"
    display_name: ClassVar[str] = "Seedance / 豆包视频生成"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("video",),
        dispatch_channel="api",
        auth_required=True,
        required_env=("SEEDANCE_API_KEY",),
    )

    BASE_SUBMIT_ENDPOINT = "/contents/generations/tasks"
    DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    DEFAULT_MODEL = "doubao-seedance-1-5-pro-250528"
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 120  # 10 minutes total

    # ── Configuration ───────────────────────────────────────────────────

    def __init__(self) -> None:
        self._api_key = os.environ.get("SEEDANCE_API_KEY", "").strip()
        self._base_url = (
            os.environ.get("SEEDANCE_BASE_URL", self.DEFAULT_BASE_URL).rstrip("/")
        )
        self._model = os.environ.get("SEEDANCE_MODEL", self.DEFAULT_MODEL)

    def validate_config(self) -> dict[str, Any]:
        env_check = self._check_env_vars("SEEDANCE_API_KEY")
        model = os.environ.get("SEEDANCE_MODEL", self.DEFAULT_MODEL)
        base_url = os.environ.get("SEEDANCE_BASE_URL", self.DEFAULT_BASE_URL)
        if env_check["ready"]:
            return {
                "ready": True,
                "errors": [],
                "warnings": [],
                "api_key_configured": True,
                "model": model,
                "base_url": base_url,
            }
        return {
            "ready": False,
            "errors": env_check["errors"],
            "warnings": ["SEEDANCE_API_KEY not set; video requests will be dry-run only."],
            "api_key_configured": False,
            "model": model,
            "base_url": base_url,
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="API Seedance 视频生成",
            notes="火山引擎 Seedance / 豆包视频生成模型。支持 text2video 和 image2video。",
        )

    # ── Request building ────────────────────────────────────────────────

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})

        base_url = self._resolve_setting(settings, "seedance_api", "base_url", self._base_url)
        model = self._resolve_setting(settings, "seedance_api", "model", self._model)
        duration = self._resolve_int(settings, "seedance_api", "duration", 5)
        ratio = self._resolve_setting(settings, "seedance_api", "ratio", "16:9")

        endpoint = f"{base_url.rstrip('/')}{self.BASE_SUBMIT_ENDPOINT}"

        content: list[dict[str, Any]] = [
            {"type": "text", "text": str(payload.get("prompt", ""))}
        ]

        # Image-to-video: include first_frame and optionally last_frame
        first_frame = str(payload.get("first_frame", "")).strip()
        last_frame = str(payload.get("last_frame", "")).strip()
        if first_frame:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._resolve_image_path(first_frame)},
                "role": "first_frame",
            })
        if last_frame:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._resolve_image_path(last_frame)},
                "role": "last_frame",
            })
        elif os.path.isfile(str(payload.get("output_path", ""))):
            # Reference image mode: use a previously generated keyframe
            ref_frame = str(payload.get("output_path", ""))
            if ref_frame:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": self._resolve_image_path(ref_frame)},
                })

        body: dict[str, Any] = {
            "model": model,
            "content": content,
            "duration": duration,
            "ratio": ratio,
            "watermark": False,
        }

        # Seedance 2.0 features
        if "seedance-2" in model:
            body["generate_audio"] = True
            body["return_last_frame"] = True

        api_key = self._get_api_key()
        preflight_info = {
            "ready": bool(api_key),
            "notes": "" if api_key else "SEEDANCE_API_KEY not set",
            "model": model,
            "endpoint": endpoint,
        }

        return {
            "method": "POST",
            "url": endpoint,
            "headers": {
                "Authorization": f"Bearer {api_key or '$SEEDANCE_API_KEY'}",
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
        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError("SEEDANCE_API_KEY is not configured")

        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})
        output_path = Path(str(payload.get("output_path", "")))

        # Phase 1: Submit task
        preview = self.build_request(request_item, providers_config_path)
        submit_body = json.dumps(preview["body"], ensure_ascii=False).encode("utf-8")

        submit_request = Request(
            str(preview["url"]),
            data=submit_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                submit_request,
                timeout=self._resolve_int(settings, "seedance_api", "timeout_seconds", 120),
            ) as response:
                submit_result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Seedance submit HTTPError {error.code}: {error_body}") from error
        except URLError as error:
            raise RuntimeError(f"Seedance submit URLError: {error.reason}") from error

        task_id = str(submit_result.get("id", ""))
        if not task_id:
            raise RuntimeError(f"Seedance submit did not return a task id: {submit_result}")

        # Phase 2: Poll for completion
        video_url, last_frame_url = self._poll_for_result(task_id, api_key, settings)

        # Phase 3: Download video
        video_request = Request(
            video_url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urlopen(video_request, timeout=60) as response:
            video_bytes = response.read()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_bytes)

        result: dict[str, Any] = {
            "provider": "seedance_video",
            "output_path": str(output_path),
            "content_type": "video/mp4",
            "response_meta": {
                "task_id": task_id,
                "model": self._model,
                "bytes": len(video_bytes),
            },
        }
        if last_frame_url:
            last_frame_path = output_path.with_name(
                output_path.stem + "_lastframe.png"
            )
            try:
                lf_request = Request(
                    last_frame_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    method="GET",
                )
                with urlopen(lf_request, timeout=30) as lf_response:
                    last_frame_path.write_bytes(lf_response.read())
                result["response_meta"]["last_frame_path"] = str(last_frame_path)
            except (HTTPError, URLError, OSError):
                pass  # Last frame download is best-effort

        return result

    # ── Private helpers ─────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        return os.environ.get("SEEDANCE_API_KEY", "").strip()

    def _resolve_setting(
        self,
        settings: dict[str, dict[str, object]],
        section: str,
        key: str,
        default: str,
    ) -> str:
        value = settings.get(section, {}).get(key)
        if value is not None:
            return str(value).strip()
        return default

    def _resolve_int(
        self,
        settings: dict[str, dict[str, object]],
        section: str,
        key: str,
        default: int,
    ) -> int:
        value = settings.get(section, {}).get(key)
        if value is not None:
            raw = str(value).strip()
            if raw.isdigit():
                return int(raw)
        return default

    def _resolve_image_path(self, path_or_url: str) -> str:
        """Convert a local file path to a data URL if needed."""
        from urllib.parse import urlparse

        parsed = urlparse(path_or_url)
        if parsed.scheme in ("http", "https", "data"):
            return path_or_url

        resolved = Path(path_or_url)
        if resolved.exists() and resolved.is_file():
            ext = resolved.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }
            mime = mime_map.get(ext, "image/png")
            import base64
            data = base64.b64encode(resolved.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"

        return path_or_url

    def _poll_for_result(
        self,
        task_id: str,
        api_key: str,
        settings: dict[str, dict[str, object]],
    ) -> tuple[str, str | None]:
        """Poll the Seedance task endpoint until completion."""
        base_url = self._resolve_setting(settings, "seedance_api", "base_url", self._base_url)
        poll_url = f"{base_url.rstrip('/')}{self.BASE_SUBMIT_ENDPOINT}/{task_id}"
        max_attempts = self._resolve_int(settings, "seedance_api", "max_poll_attempts", self.MAX_POLL_ATTEMPTS)
        interval = self._resolve_int(settings, "seedance_api", "poll_interval", self.POLL_INTERVAL)

        for attempt in range(1, max_attempts + 1):
            time.sleep(interval)
            try:
                poll_request = Request(
                    poll_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    method="GET",
                )
                with urlopen(poll_request, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, OSError) as error:
                if attempt == max_attempts:
                    raise RuntimeError(f"Seedance poll failed after {max_attempts} attempts: {error}") from error
                continue

            status = str(result.get("status", "")).lower()
            if status == "succeeded":
                content = result.get("content", {}) or {}
                video_url = str(content.get("video_url", "") or "")
                last_frame_url = str(content.get("last_frame_url", "") or "") or None
                if not video_url:
                    raise RuntimeError(f"Seedance task succeeded but no video_url: {result}")
                return video_url, last_frame_url

            if status == "failed":
                error_msg = "unknown"
                if isinstance(result.get("error"), dict):
                    error_msg = str(result["error"].get("message", "unknown"))
                raise RuntimeError(f"Seedance generation failed: {error_msg}")

            # Still processing — continue polling

        raise RuntimeError(f"Seedance generation timed out after {max_attempts * interval}s")
