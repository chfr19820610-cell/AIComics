from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from web.backend.auth.jwt_service import (
    base64url_decode,
    base64url_encode,
    build_jwt_token,
    decode_jwt_token,
    sign_hs256,
)
from web.backend.settings import WebSettings


@pytest.fixture
def settings() -> WebSettings:
    return WebSettings(
        project_root=Path("/tmp"),
        reports_dir=Path("/tmp/reports"),
        jobs_dir=Path("/tmp/jobs"),
        state_dir=Path("/tmp/state"),
        allowed_commands=(),
        runnable_commands=(),
        command_execution_enabled=False,
        host="127.0.0.1",
        port=7860,
        require_confirm_live=True,
        auth_enabled=True,
        password_login_enabled=True,
        jwt_secret="test-secret-key-not-for-production",
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_token_minutes=60,
        refresh_token_days=7,
        access_token_cookie_name="test_access",
        refresh_token_cookie_name="test_refresh",
        default_role="creator",
        password_user_username="testuser",
        password_user_display_name="Test User",
        password_user_email="test@test.local",
        password_user_role="creator",
        password_user_password="testpass",
        cors_allow_origins=("*",),
    )


class TestBase64Url:
    def test_roundtrip(self) -> None:
        data = b"hello world"
        encoded = base64url_encode(data)
        decoded = base64url_decode(encoded)
        assert decoded == data

    def test_handles_padding(self) -> None:
        encoded = base64url_encode(b"test")
        assert "=" not in encoded

    def test_empty_string(self) -> None:
        encoded = base64url_encode(b"")
        decoded = base64url_decode(encoded)
        assert decoded == b""


class TestSignHs256:
    def test_produces_string(self) -> None:
        sig = sign_hs256(b"message", "secret")
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_different_keys_different_signatures(self) -> None:
        sig1 = sign_hs256(b"message", "secret1")
        sig2 = sign_hs256(b"message", "secret2")
        assert sig1 != sig2


class TestBuildJwtToken:
    def test_builds_token(self, settings: WebSettings) -> None:
        token = build_jwt_token(settings, "user_001", "测试用户", "creator")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_token_contains_three_parts(self, settings: WebSettings) -> None:
        token = build_jwt_token(settings, "user_001", "test", "admin")
        parts = token.split(".")
        assert len(parts) == 3


class TestDecodeJwtToken:
    def test_roundtrip(self, settings: WebSettings) -> None:
        token = build_jwt_token(settings, "user_001", "测试用户", "creator")
        payload = decode_jwt_token(settings, token)
        assert payload["sub"] == "user_001"
        assert payload["name"] == "测试用户"
        assert payload["role"] == "creator"
        assert payload["iss"] == "test-issuer"
        assert payload["aud"] == "test-audience"

    def test_invalid_signature_raises(self, settings: WebSettings) -> None:
        token = build_jwt_token(settings, "user_001", "test", "role")
        parts = token.split(".")
        tampered = f"{parts[0]}.{parts[1]}.invalidsig"
        with pytest.raises(ValueError, match="Invalid JWT signature"):
            decode_jwt_token(settings, tampered)

    def test_invalid_format_raises(self, settings: WebSettings) -> None:
        with pytest.raises(ValueError, match="Invalid JWT format"):
            decode_jwt_token(settings, "not-a-jwt-token")

    def test_expired_token_raises(self, settings: WebSettings) -> None:
        expired_settings = WebSettings(
            **{**settings.__dict__,
               "access_token_minutes": -1,
               "refresh_token_days": 7,
               "jwt_secret": settings.jwt_secret,
               "jwt_issuer": settings.jwt_issuer,
               "jwt_audience": settings.jwt_audience,
               "cors_allow_origins": settings.cors_allow_origins,
               "allowed_commands": settings.allowed_commands,
               "runnable_commands": settings.runnable_commands,
               })
        token = build_jwt_token(expired_settings, "user_001", "test", "role")
        with pytest.raises(ValueError, match="JWT expired"):
            decode_jwt_token(settings, token)
