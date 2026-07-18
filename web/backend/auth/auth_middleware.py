from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, load_user_by_id
from web.backend.auth.jwt_service import decode_jwt_token
from web.backend.services.edition_policy import load_edition_policy
from web.backend.settings import load_web_settings


PUBLIC_API_PATHS = {
    "/api/health",
    "/api/edition",
    "/api/auth/config",
    "/api/auth/providers",
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/refresh",
    "/api/auth/logout",
}


def build_auth_error_response(request: Request, settings, payload: dict[str, str]) -> JSONResponse:
    response = JSONResponse(payload, status_code=401)
    origin = request.headers.get("Origin", "").strip()
    allowed_origins = set(settings.cors_allow_origins)
    if origin and ("*" in allowed_origins or origin in allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = origin if "*" not in allowed_origins else "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def extract_access_token(request: Request, cookie_name: str) -> str:
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return str(request.cookies.get(cookie_name, "")).strip()


def _lookup_user_sync(settings, user_id: str) -> dict[str, Any] | None:
    """Sync helper: connect to auth DB, look up user, and return user dict or None."""
    connection = connect_auth_database()
    try:
        ensure_auth_schema(connection)
        return load_user_by_id(connection, user_id)
    finally:
        connection.close()


def register_auth_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def auth_guard(request: Request, call_next):  # type: ignore[override]
        settings = load_web_settings()
        policy = load_edition_policy(settings)
        request.state.current_user = None
        if not policy.auth_enabled or not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if request.url.path in PUBLIC_API_PATHS:
            return await call_next(request)

        token = extract_access_token(request, settings.access_token_cookie_name)
        if not token:
            return build_auth_error_response(request, settings, {"detail": "Authentication required"})

        try:
            payload = decode_jwt_token(settings, token)
        except Exception as error:
            return build_auth_error_response(request, settings, {"detail": str(error)})

        user = await asyncio.to_thread(_lookup_user_sync, settings, str(payload.get("sub", "")))
        if not user or user.get("status") != "active":
            return build_auth_error_response(request, settings, {"detail": "User is not active"})

        request.state.current_user = user
        return await call_next(request)


def get_request_user(request: Request) -> dict[str, Any] | None:
    current_user = getattr(request.state, "current_user", None)
    return current_user if isinstance(current_user, dict) else None
