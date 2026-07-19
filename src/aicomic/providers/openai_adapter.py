from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aicomic.providers.provider_planner import load_provider_settings


def get_openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def get_openai_base_url(settings: dict[str, dict[str, object]]) -> str:
    openai_api = settings.get("openai_api", {})
    base_url = str(openai_api.get("base_url", "https://api.openai.com")).rstrip("/")
    return base_url


def get_openai_timeout(settings: dict[str, dict[str, object]]) -> int:
    openai_api = settings.get("openai_api", {})
    timeout_raw = str(openai_api.get("timeout_seconds", "120")).strip()
    if timeout_raw.isdigit():
        return int(timeout_raw)
    return 120


def resolve_image_body(payload: dict[str, Any], settings: dict[str, dict[str, object]]) -> dict[str, Any]:
    image_settings = settings.get("openai_image", {})
    default_size = str(image_settings.get("size", "1024x1536"))
    # Preview mode: use smaller resolution for faster generation
    if payload.get("preview"):
        size = str(image_settings.get("preview_size", "512x768"))
    else:
        size = default_size
    return {
        "model": str(image_settings.get("model", "gpt-image-1.5")),
        "prompt": str(payload["prompt"]),
        "n": 1,
        "size": size,
        "quality": str(image_settings.get("quality", "medium")),
        "output_format": str(image_settings.get("output_format", "png")),
    }


def resolve_tts_body(payload: dict[str, Any], settings: dict[str, dict[str, object]]) -> dict[str, Any]:
    tts_settings = settings.get("openai_tts", {})
    return {
        "model": str(tts_settings.get("model", "gpt-4o-mini-tts")),
        "input": str(payload["prompt"]),
        "voice": str(tts_settings.get("voice", "alloy")),
        "response_format": str(tts_settings.get("response_format", "wav")),
        "speed": float(str(tts_settings.get("speed", "1.0"))),
        "instructions": str(tts_settings.get("instructions", "冷静、克制、都市职场动漫语气")),
    }


def build_openai_request_preview(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    base_url = get_openai_base_url(settings)

    if provider == "openai_image":
        endpoint = f"{base_url}/v1/images/generations"
        body = resolve_image_body(payload, settings)
    elif provider == "openai_tts":
        endpoint = f"{base_url}/v1/audio/speech"
        body = resolve_tts_body(payload, settings)
    else:
        endpoint = ""
        body = {}

    return {
        "method": "POST",
        "url": endpoint,
        "headers": {
            "Authorization": "Bearer $OPENAI_API_KEY",
            "Content-Type": "application/json",
        },
        "body": body,
    }


def perform_openai_request(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    preview = build_openai_request_preview(request_item, providers_config_path)
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

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
        with urlopen(http_request, timeout=get_openai_timeout(settings)) as response:
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
