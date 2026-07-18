from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from web.backend.auth.auth_middleware import extract_access_token, get_request_user
from web.backend.auth.auth_service import (
    authenticate_password_user,
    connect_auth_database,
    create_refresh_session,
    ensure_auth_schema,
    is_session_active,
    load_session_by_refresh_token,
    load_user_by_id,
    revoke_refresh_session,
    upsert_identity_binding,
    upsert_password_credential,
    upsert_user,
    write_audit_log,
)
from web.backend.auth.jwt_service import build_jwt_token, decode_jwt_token
from web.backend.services.edition_policy import load_edition_policy
from web.backend.settings import load_web_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


class PasswordLoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = ""


def _is_local(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = load_web_settings()
    secure_cookie = not _is_local(settings.host)
    response.set_cookie(
        settings.access_token_cookie_name,
        access_token,
        httponly=True,
        samesite="strict",
        secure=secure_cookie,
    )
    response.set_cookie(
        settings.refresh_token_cookie_name,
        refresh_token,
        httponly=True,
        samesite="strict",
        secure=secure_cookie,
    )


def build_auth_payload(
    request: Request,
    user: dict[str, str],
    login_source: str,
    target_id: str,
    detail: str,
) -> dict[str, Any]:
    settings = load_web_settings()
    policy = load_edition_policy(settings)
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    session = create_refresh_session(
        connection,
        settings,
        user["user_id"],
        request.client.host if request.client else "",
        request.headers.get("User-Agent", ""),
    )
    access_token = build_jwt_token(settings, user["user_id"], user["display_name"], user["default_role"])
    write_audit_log(connection, user["user_id"], "login", "auth", target_id, "success", detail)
    connection.close()
    return {
        "authenticated": True,
        "auth_enabled": policy.auth_enabled,
        "access_token": access_token,
        "refresh_token": session["refresh_token"],
        "user": user,
        "login_source": login_source,
    }


def configured_password_users(settings: Any) -> list[dict[str, str]]:
    return [
        {
            "username": settings.password_user_username,
            "display_name": settings.password_user_display_name,
            "email": settings.password_user_email,
            "role": settings.password_user_role,
            "password": settings.password_user_password,
        }
    ]


def ensure_configured_password_users(settings: Any) -> None:
    if not settings.password_login_enabled:
        return
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    try:
        for item in configured_password_users(settings):
            password = str(item.get("password", "")).strip()
            username = str(item.get("username", "")).strip()
            if not username or not password:
                continue
            user = upsert_user(
                connection,
                username,
                str(item.get("display_name", username)).strip() or username,
                str(item.get("email", f"{username}@aicomic.local")).strip() or f"{username}@aicomic.local",
                str(item.get("role", settings.default_role)).strip() or settings.default_role,
            )
            upsert_password_credential(connection, user["user_id"], password)
            upsert_identity_binding(connection, user["user_id"], "password", username, user["email"])
    finally:
        connection.close()


@router.get("/config")
def auth_config() -> dict[str, Any]:
    settings = load_web_settings()
    policy = load_edition_policy(settings)
    return {
        "auth_enabled": policy.auth_enabled,
        "password_login_enabled": settings.password_login_enabled,
        "edition_name": policy.edition_name,
        "edition_display_name": policy.display_name,
        "auth_reason": policy.auth_reason,
        "creator_only_reason": policy.creator_only_reason,
        "configured_auth_enabled": settings.auth_enabled,
    }


@router.get("/providers")
def providers() -> dict[str, Any]:
    settings = load_web_settings()
    policy = load_edition_policy(settings)
    return {
        "auth_enabled": policy.auth_enabled,
        "edition_name": policy.edition_name,
        "items": [
            {
                "name": "password",
                "label": "个人账号密码登录",
                "enabled": settings.password_login_enabled,
                "mode": "password",
                "start_path": "/api/auth/login",
            }
        ],
    }


@router.post("/login")
def password_login(payload: PasswordLoginRequest, request: Request, response: Response) -> dict[str, Any]:
    settings = load_web_settings()
    if not settings.password_login_enabled:
        raise HTTPException(status_code=403, detail="Password login disabled")
    ensure_configured_password_users(settings)
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    user = authenticate_password_user(connection, payload.username, payload.password)
    if user is None:
        write_audit_log(
            connection,
            payload.username.strip() or "unknown",
            "login",
            "auth",
            "password",
            "failed",
            "Password login failed",
        )
        connection.close()
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    connection.close()
    auth_payload = build_auth_payload(request, user, "password", "password", "Password login")
    set_auth_cookies(response, str(auth_payload["access_token"]), str(auth_payload["refresh_token"]))
    return auth_payload


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    current_user = get_request_user(request)
    settings = load_web_settings()
    policy = load_edition_policy(settings)
    if current_user is None:
        token = extract_access_token(request, settings.access_token_cookie_name)
        if token:
            try:
                payload = decode_jwt_token(settings, token)
                connection = connect_auth_database()
                ensure_auth_schema(connection)
                current_user = load_user_by_id(connection, str(payload.get("sub", "")))
                connection.close()
            except Exception:
                current_user = None
    if current_user is None:
        return {
            "authenticated": False,
            "auth_enabled": policy.auth_enabled,
            "user": None,
        }
    return {
        "authenticated": True,
        "auth_enabled": policy.auth_enabled,
        "user": current_user,
    }


@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request, response: Response) -> dict[str, Any]:
    settings = load_web_settings()
    refresh_token = payload.refresh_token or str(request.cookies.get(settings.refresh_token_cookie_name, "")).strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Token refresh failed: invalid refresh token")

    connection = connect_auth_database()
    ensure_auth_schema(connection)
    session = load_session_by_refresh_token(connection, refresh_token)
    if not is_session_active(session):
        connection.close()
        raise HTTPException(status_code=400, detail="Token refresh failed: invalid refresh token")

    user = load_user_by_id(connection, str(session["user_id"]))
    if user is None:
        connection.close()
        raise HTTPException(status_code=400, detail="Token refresh failed: invalid refresh token")

    access_token = build_jwt_token(settings, user["user_id"], user["display_name"], user["default_role"])
    write_audit_log(
        connection,
        user["user_id"],
        "refresh",
        "auth",
        str(session["session_id"]),
        "success",
        "Refresh access token",
    )
    connection.close()
    response.set_cookie(
        settings.access_token_cookie_name,
        access_token,
        httponly=True,
        samesite="strict",
        secure=not _is_local(settings.host),
    )
    return {
        "authenticated": True,
        "access_token": access_token,
        "user": user,
    }


@router.post("/logout")
def logout(payload: RefreshRequest, request: Request, response: Response) -> dict[str, Any]:
    settings = load_web_settings()
    refresh_token = payload.refresh_token or str(request.cookies.get(settings.refresh_token_cookie_name, "")).strip()
    if refresh_token:
        connection = connect_auth_database()
        ensure_auth_schema(connection)
        session = load_session_by_refresh_token(connection, refresh_token)
        if session:
            revoke_refresh_session(connection, refresh_token)
            write_audit_log(
                connection,
                str(session["user_id"]),
                "logout",
                "auth",
                str(session["session_id"]),
                "success",
                "Logout",
            )
        connection.close()

    response.delete_cookie(settings.access_token_cookie_name)
    response.delete_cookie(settings.refresh_token_cookie_name)
    return {
        "authenticated": False,
        "detail": "Logged out",
    }
