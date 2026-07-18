from __future__ import annotations

from pathlib import Path

from web.backend.auth.auth_middleware import extract_access_token, PUBLIC_API_PATHS


class TestPublicApiPaths:
    def test_contains_expected_paths(self) -> None:
        assert "/api/health" in PUBLIC_API_PATHS
        assert "/api/auth/login" in PUBLIC_API_PATHS
        assert "/api/auth/me" in PUBLIC_API_PATHS
        assert "/api/auth/refresh" in PUBLIC_API_PATHS
        assert "/api/auth/logout" in PUBLIC_API_PATHS
        assert "/api/edition" in PUBLIC_API_PATHS

    def test_protected_paths_not_in_public(self) -> None:
        assert "/api/commands" not in PUBLIC_API_PATHS
        assert "/api/batch" not in PUBLIC_API_PATHS


class TestExtractAccessToken:
    def test_bearer_token(self) -> None:
        class MockRequest:
            headers = {"Authorization": "Bearer my-access-token"}
            cookies = {}

        token = extract_access_token(MockRequest(), "cookie_name")  # type: ignore[arg-type]
        assert token == "my-access-token"

    def test_bearer_with_extra_whitespace(self) -> None:
        class MockRequest:
            headers = {"Authorization": "  Bearer   token-value  "}
            cookies = {}

        token = extract_access_token(MockRequest(), "cookie_name")  # type: ignore[arg-type]
        assert token == "token-value"

    def test_cookie_fallback(self) -> None:
        class MockRequest:
            headers = {}
            cookies = {"my_cookie": "cookie-token"}

        token = extract_access_token(MockRequest(), "my_cookie")  # type: ignore[arg-type]
        assert token == "cookie-token"

    def test_no_token_returns_empty(self) -> None:
        class MockRequest:
            headers = {}
            cookies = {}

        token = extract_access_token(MockRequest(), "my_cookie")  # type: ignore[arg-type]
        assert token == ""

    def test_authorization_override_cookie(self) -> None:
        """Authorization header should take precedence over cookie."""
        class MockRequest:
            headers = {"Authorization": "Bearer from-header"}
            cookies = {"my_cookie": "from-cookie"}

        token = extract_access_token(MockRequest(), "my_cookie")  # type: ignore[arg-type]
        assert token == "from-header"  # Authorization Bearer actually takes precedence

    def test_non_bearer_authorization(self) -> None:
        class MockRequest:
            headers = {"Authorization": "Basic dXNlcjpwYXNz"}
            cookies = {}

        token = extract_access_token(MockRequest(), "my_cookie")  # type: ignore[arg-type]
        assert token == ""
