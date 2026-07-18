from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("AICOMIC_WEB_CONFIG_PATH", str(PROJECT_ROOT / "config" / "web.development.yaml"))
os.environ.setdefault("AICOMIC_NORMAL_USER_PASSWORD", "creator_validation_password")

from web.backend.app import app


def main() -> int:
    username = "creator"
    password = os.environ["AICOMIC_NORMAL_USER_PASSWORD"]
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"auth_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with TestClient(app) as client:
        config_response = client.get("/api/auth/config")
        providers_response = client.get("/api/auth/providers")
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": password,
            },
        )
        me_response = client.get("/api/auth/me")
        refresh_response = client.post("/api/auth/refresh", json={})
        logout_response = client.post("/api/auth/logout", json={})
        me_after_logout_response = client.get("/api/auth/me")

    if config_response.status_code != 200:
        raise RuntimeError(f"auth config failed: {config_response.status_code}")
    if providers_response.status_code != 200:
        raise RuntimeError(f"auth providers failed: {providers_response.status_code}")
    if login_response.status_code != 200:
        raise RuntimeError(f"password login failed: {login_response.status_code} {login_response.text}")
    if me_response.status_code != 200:
        raise RuntimeError(f"auth me failed: {me_response.status_code}")
    if refresh_response.status_code != 200:
        raise RuntimeError(f"auth refresh failed: {refresh_response.status_code}")
    if logout_response.status_code != 200:
        raise RuntimeError(f"auth logout failed: {logout_response.status_code}")
    if me_after_logout_response.status_code != 200:
        raise RuntimeError(f"auth me after logout failed: {me_after_logout_response.status_code}")

    config_payload = config_response.json()
    providers_payload = providers_response.json()
    login_payload = login_response.json()
    me_payload = me_response.json()
    refresh_payload = refresh_response.json()
    logout_payload = logout_response.json()
    me_after_logout_payload = me_after_logout_response.json()

    provider_names = [str(item.get("name", "")) for item in providers_payload.get("items", [])]
    if provider_names != ["password"]:
        raise RuntimeError(f"unexpected auth providers: {provider_names}")
    if not bool(config_payload.get("auth_enabled")):
        raise RuntimeError(f"auth should be enabled: {config_payload}")
    if not bool(login_payload.get("authenticated")):
        raise RuntimeError(f"login should authenticate: {login_payload}")
    if not bool(me_payload.get("authenticated")):
        raise RuntimeError(f"/me should be authenticated: {me_payload}")
    if str((me_payload.get("user") or {}).get("username", "")) != username:
        raise RuntimeError(f"/me returned unexpected user: {me_payload}")
    if not bool(refresh_payload.get("authenticated")):
        raise RuntimeError(f"/refresh should be authenticated: {refresh_payload}")
    if bool(logout_payload.get("authenticated")):
        raise RuntimeError(f"/logout should clear auth: {logout_payload}")
    if bool(me_after_logout_payload.get("authenticated")):
        raise RuntimeError(f"/me after logout should be anonymous: {me_after_logout_payload}")

    payload = {
        "run_id": run_id,
        "run_at": run_at,
        "username": username,
        "auth_enabled": config_payload.get("auth_enabled", False),
        "password_login_enabled": config_payload.get("password_login_enabled", False),
        "provider_names": provider_names,
        "login_authenticated": login_payload.get("authenticated", False),
        "me_authenticated": me_payload.get("authenticated", False),
        "refresh_authenticated": refresh_payload.get("authenticated", False),
        "logout_authenticated": logout_payload.get("authenticated", False),
        "me_after_logout_authenticated": me_after_logout_payload.get("authenticated", False),
        "user": me_payload.get("user"),
        "report_path": str(PROJECT_ROOT / "reports" / "auth_validation_report.json"),
    }

    output_path = PROJECT_ROOT / "reports" / "auth_validation_report.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
