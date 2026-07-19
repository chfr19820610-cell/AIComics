from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class KlingProvider(IProvider):
    """Provider adapter for Kling AI (快手可灵) video generation.

    Supports text-to-video and image-to-video modes via the Kling API.
    Uses JWT-based authentication (Access Key + Secret Key).
    Mirrors the SeedanceProvider lifecycle pattern.
    """

    provider_name: ClassVar[str] = "kling"
    display_name: ClassVar[str] = "Kling AI / 可灵视频生成"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("video",),
        dispatch_channel="api",
        auth_required=True,
        required_env=("KLING_ACCESS_KEY", "KLING_SECRET_KEY"),
    )

    TEXT2VIDEO_ENDPOINT = "/v1/videos/text2video"
    IMAGE2VIDEO_ENDPOINT = "/v1/videos/image2video"
    DEFAULT_BASE_URL = "https://api.klingai.com"
    DEFAULT_MODEL = "kling-v2-master"
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 120  # 10 minutes total

    # ── Configuration ───────────────────────────────────────────────────

    def __init__(self) -> None:
        self._access_key = os.environ.get("KLING_ACCESS_KEY", "").strip()
        self._secret_key = os.environ.get("KLING_SECRET_KEY", "").strip()
        self._base_url = (
            os.environ.get("KLING_BASE_URL", self.DEFAULT_BASE_URL).rstrip("/")
        )
        self._model = os.environ.get("KLING_MODEL", self.DEFAULT_MODEL)

    def validate_config(self) -> dict[str, Any]:
        env_check = self._check_env_vars("KLING_ACCESS_KEY", "KLING_SECRET_KEY")
        model = os.environ.get("KLING_MODEL", self.DEFAULT_MODEL)
        base_url = os.environ.get("KLING_BASE_URL", self.DEFAULT_BASE_URL)
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
            "warnings": ["KLING_ACCESS_KEY / KLING_SECRET_KEY not set; video requests will be dry-run only."],
            "api_key_configured": False,
            "model": model,
            "base_url": base_url,
        }

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="API Kling AI 视频生成",
            notes="快手可灵 AI 视频生成模型。支持 text2video 和 image2video。认证方式为 JWT (Access Key + Secret Key)。",
        )

    # ── JWT token generation ───────────────────────────────────────────

    def _generate_jwt(self, access_key: str, secret_key: str) -> str:
        """Generate a JWT token for Kling API authentication using HS256."""
        import hmac
        import hashlib

        header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
        current_time = int(time.time())
        payload = json.dumps(
            {
                "iss": access_key,
                "exp": current_time + 1800,  # 30 minutes
                "nbf": current_time - 5,  # valid from 5 seconds ago
            },
            separators=(",", ":"),
        )

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header_b64 = _b64url(header.encode("utf-8"))
        payload_b64 = _b64url(payload.encode("utf-8"))

        signature_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(
            secret_key.encode("utf-8"),
            signature_input,
            hashlib.sha256,
        ).digest()
        signature_b64 = _b64url(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    # ── Request building ────────────────────────────────────────────────

    def _build_common_body(
        self,
        payload: dict[str, Any],
        settings: dict[str, dict[str, object]],
        mode: str,  # "text2video" or "image2video"
    ) -> dict[str, Any]:
        """Build the common request body for both text2video and image2video."""
        model = self._resolve_setting(settings, "kling", "model", self._model)
        duration = self._resolve_setting(settings, "kling", "duration", "5")
        ratio = self._resolve_setting(settings, "kling", "aspect_ratio", "16:9")
        cfg_scale = self._resolve_setting(settings, "kling", "cfg_scale", "0.5")
        mode_setting = self._resolve_setting(settings, "kling", "mode", "standard")

        body: dict[str, Any] = {
            "model_name": model,
            "prompt": str(payload.get("prompt", "")),
            "negative_prompt": str(payload.get("negative_prompt", "")),
            "cfg_scale": float(cfg_scale),
            "aspect_ratio": ratio,
            "duration": duration,
            "mode": mode_setting,
        }

        # Camera control (optional, V2 models)
        camera_control = payload.get("camera_control")
        if camera_control and isinstance(camera_control, dict):
            body["camera_control"] = camera_control

        return body

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})

        base_url = self._resolve_setting(settings, "kling", "base_url", self._base_url)
        has_text = bool(str(payload.get("prompt", "")).strip())
        first_frame = str(payload.get("first_frame", "")).strip()
        has_image = bool(first_frame)

        # Determine which mode
        if has_image:
            # Image-to-video
            endpoint = f"{base_url.rstrip('/')}{self.IMAGE2VIDEO_ENDPOINT}"
            body = self._build_common_body(payload, settings, "image2video")
            body["image"] = self._resolve_image_path(first_frame)

            # Optional end image
            last_frame = str(payload.get("last_frame", "")).strip()
            if last_frame:
                body["image_tail_url"] = self._resolve_image_path(last_frame)
        else:
            # Text-to-video
            endpoint = f"{base_url.rstrip('/')}{self.TEXT2VIDEO_ENDPOINT}"
            body = self._build_common_body(payload, settings, "text2video")

            # Optional reference image (Kling's ref image feature)
            ref_image = str(payload.get("ref_image", "")).strip()
            if ref_image:
                body["image_url"] = self._resolve_image_path(ref_image)
                # Use duration as string as required by Kling API
                body["duration"] = self._resolve_setting(
                    settings, "kling", "duration", "5"
                )

        api_key_ready = bool(self._access_key and self._secret_key)
        preflight_info = {
            "ready": api_key_ready,
            "notes": "" if api_key_ready else "KLING_ACCESS_KEY / KLING_SECRET_KEY not set",
            "model": body.get("model_name", self._model),
            "endpoint": endpoint,
        }

        token = self._generate_jwt(self._access_key, self._secret_key) if api_key_ready else ""

        return {
            "method": "POST",
            "url": endpoint,
            "headers": {
                "Authorization": f"Bearer {token or '$KLING_JWT'}",
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
        if not self._access_key or not self._secret_key:
            raise RuntimeError("KLING_ACCESS_KEY / KLING_SECRET_KEY are not configured")

        settings = self._load_settings(providers_config_path)
        payload = request_item.get("payload", {})
        output_path = Path(str(payload.get("output_path", "")))

        # Phase 1: Submit task
        preview = self.build_request(request_item, providers_config_path)
        token = self._generate_jwt(self._access_key, self._secret_key)
        submit_body = json.dumps(preview["body"], ensure_ascii=False).encode("utf-8")

        submit_request = Request(
            str(preview["url"]),
            data=submit_body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                submit_request,
                timeout=self._resolve_int(settings, "kling", "timeout_seconds", 120),
            ) as response:
                submit_result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kling submit HTTPError {error.code}: {error_body}") from error
        except URLError as error:
            raise RuntimeError(f"Kling submit URLError: {error.reason}") from error

        # Check API-level error
        code = submit_result.get("code", 0)
        if code != 0:
            msg = submit_result.get("message", "unknown error")
            raise RuntimeError(f"Kling API error (code {code}): {msg}")

        task_data = submit_result.get("data", {}) or {}
        task_id = str(task_data.get("task_id", ""))
        if not task_id:
            raise RuntimeError(f"Kling submit did not return a task_id: {submit_result}")

        # Phase 2: Poll for completion
        video_url = self._poll_for_result(task_id, token, settings)

        # Phase 3: Download video
        video_request = Request(
            video_url,
            method="GET",
        )
        with urlopen(video_request, timeout=60) as response:
            video_bytes = response.read()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_bytes)

        result: dict[str, Any] = {
            "provider": "kling_video",
            "output_path": str(output_path),
            "content_type": "video/mp4",
            "response_meta": {
                "task_id": task_id,
                "model": self._model,
                "bytes": len(video_bytes),
            },
        }

        return result

    # ── Private helpers ─────────────────────────────────────────────────

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
            data = base64.b64encode(resolved.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"

        return path_or_url

    def _poll_for_result(
        self,
        task_id: str,
        token: str,
        settings: dict[str, dict[str, object]],
    ) -> str:
        """Poll the Kling task endpoint until completion.

        Kling uses the same endpoint for both text2video and image2video
        task status queries: GET /v1/videos/text2video/{task_id}
        The response structure is identical regardless of the source mode.
        """
        base_url = self._resolve_setting(settings, "kling", "base_url", self._base_url)
        poll_url = f"{base_url.rstrip('/')}/v1/videos/text2video/{task_id}"
        max_attempts = self._resolve_int(settings, "kling", "max_poll_attempts", self.MAX_POLL_ATTEMPTS)
        interval = self._resolve_int(settings, "kling", "poll_interval", self.POLL_INTERVAL)

        for attempt in range(1, max_attempts + 1):
            time.sleep(interval)
            try:
                poll_request = Request(
                    poll_url,
                    headers={"Authorization": f"Bearer {token}"},
                    method="GET",
                )
                with urlopen(poll_request, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, OSError) as error:
                if attempt == max_attempts:
                    raise RuntimeError(f"Kling poll failed after {max_attempts} attempts: {error}") from error
                continue

            # Check API-level error
            code = result.get("code", 0)
            if code != 0:
                msg = result.get("message", "unknown error")
                raise RuntimeError(f"Kling API error during polling (code {code}): {msg}")

            data = result.get("data", {}) or {}
            status = str(data.get("task_status", "")).lower()

            if status == "succeed":
                task_result = data.get("task_result", {}) or {}
                videos = task_result.get("videos", [])
                if not videos:
                    raise RuntimeError(f"Kling task succeeded but no videos in result: {result}")
                video_url = str(videos[0].get("url", ""))
                if not video_url:
                    raise RuntimeError(f"Kling task succeeded but video URL is empty: {result}")
                return video_url

            if status == "failed":
                error_msg = data.get("task_status_msg", "unknown")
                raise RuntimeError(f"Kling generation failed: {error_msg}")

            # Still processing — continue polling

        raise RuntimeError(f"Kling generation timed out after {max_attempts * interval}s")
