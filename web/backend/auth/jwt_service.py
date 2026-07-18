from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from web.backend.settings import WebSettings


def base64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("utf-8")


def base64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(f"{payload}{padding}")


def sign_hs256(message: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64url_encode(signature)


def build_jwt_token(settings: WebSettings, subject: str, name: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "name": name,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    encoded_header = base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = sign_hs256(signing_input, settings.jwt_secret)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_jwt_token(settings: WebSettings, token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".")
    except ValueError as error:
        raise ValueError("Invalid JWT format") from error

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = sign_hs256(signing_input, settings.jwt_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid JWT signature")

    payload = json.loads(base64url_decode(encoded_payload).decode("utf-8"))
    now_timestamp = int(datetime.now(timezone.utc).timestamp())
    if int(payload.get("exp", 0)) < now_timestamp:
        raise ValueError("JWT expired")
    if str(payload.get("iss", "")) != settings.jwt_issuer:
        raise ValueError("Invalid JWT issuer")
    if str(payload.get("aud", "")) != settings.jwt_audience:
        raise ValueError("Invalid JWT audience")
    return payload
