from __future__ import annotations

from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, upsert_user
from web.backend.auth.jwt_service import build_jwt_token
from web.backend.services.edition_policy import load_edition_policy
from web.backend.settings import load_web_settings


def build_validation_auth_headers(username: str, role: str = "creator") -> dict[str, str]:
    settings = load_web_settings()
    policy = load_edition_policy(settings)
    if not policy.auth_enabled:
        return {}

    safe_username = username.strip().lower().replace(" ", "_") or "validation_admin"
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    try:
        user = upsert_user(
            connection,
            safe_username,
            "Validation Creator",
            f"{safe_username}@aicomic.local",
            role,
        )
    finally:
        connection.close()

    token = build_jwt_token(settings, user["user_id"], user["display_name"], user["default_role"])
    return {"Authorization": f"Bearer {token}"}
