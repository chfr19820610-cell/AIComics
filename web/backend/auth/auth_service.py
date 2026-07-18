from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any

from aicomic.core.config import ProjectPaths
from web.backend.settings import WebSettings


def connect_auth_database(database_path: Path | None = None) -> sqlite3.Connection:
    target_path = database_path or ProjectPaths.default_database_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target_path, timeout=30.0)
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return connection


def ensure_auth_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            default_role TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS identity_bindings (
            binding_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            provider_subject TEXT NOT NULL,
            provider_email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            refresh_token_hash TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            user_agent TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            result TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_state_tokens (
            state_token TEXT PRIMARY KEY,
            provider_name TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            username_hint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            consumed_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS password_credentials (
            credential_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            algorithm TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: str = "") -> dict[str, str]:
    active_salt = salt or secrets.token_urlsafe(24)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        active_salt.encode("utf-8"),
        210_000,
    ).hex()
    return {
        "algorithm": "pbkdf2_sha256_210000",
        "password_hash": password_hash,
        "password_salt": active_salt,
    }


def verify_password(password: str, credential: dict[str, Any] | None) -> bool:
    if not credential:
        return False
    if credential.get("algorithm") != "pbkdf2_sha256_210000":
        return False
    expected = str(credential.get("password_hash", ""))
    salt = str(credential.get("password_salt", ""))
    if not expected or not salt:
        return False
    actual = hash_password(password, salt)["password_hash"]
    return secrets.compare_digest(actual, expected)


def upsert_user(
    connection: sqlite3.Connection,
    username: str,
    display_name: str,
    email: str,
    default_role: str,
) -> dict[str, str]:
    user_id = f"user_{username.lower()}"
    login_at = now_iso()
    connection.execute(
        """
        INSERT OR REPLACE INTO users (
            user_id,
            username,
            display_name,
            email,
            status,
            default_role,
            last_login_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, display_name, email, "active", default_role, login_at),
    )
    connection.commit()
    return {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "email": email,
        "status": "active",
        "default_role": default_role,
        "last_login_at": login_at,
    }


def load_user_by_username(connection: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT user_id, username, display_name, email, status, default_role, last_login_at
        FROM users
        WHERE LOWER(username) = LOWER(?)
        """,
        (username.strip(),),
    ).fetchone()
    if row is None:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "display_name": row[2],
        "email": row[3],
        "status": row[4],
        "default_role": row[5],
        "last_login_at": row[6],
    }


def upsert_password_credential(connection: sqlite3.Connection, user_id: str, password: str) -> None:
    hashed = hash_password(password)
    connection.execute(
        """
        INSERT OR REPLACE INTO password_credentials (
            credential_id,
            user_id,
            password_hash,
            password_salt,
            algorithm,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            f"credential_{user_id}",
            user_id,
            hashed["password_hash"],
            hashed["password_salt"],
            hashed["algorithm"],
            now_iso(),
        ),
    )
    connection.commit()


def load_password_credential(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT credential_id, user_id, password_hash, password_salt, algorithm, updated_at
        FROM password_credentials
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "credential_id": row[0],
        "user_id": row[1],
        "password_hash": row[2],
        "password_salt": row[3],
        "algorithm": row[4],
        "updated_at": row[5],
    }


def update_user_last_login(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    connection.execute(
        """
        UPDATE users
        SET last_login_at = ?
        WHERE user_id = ?
        """,
        (now_iso(), user_id),
    )
    connection.commit()
    return load_user_by_id(connection, user_id)


def authenticate_password_user(
    connection: sqlite3.Connection,
    username: str,
    password: str,
) -> dict[str, Any] | None:
    user = load_user_by_username(connection, username)
    if user is None or user.get("status") != "active":
        return None
    credential = load_password_credential(connection, str(user["user_id"]))
    if not verify_password(password, credential):
        return None
    return update_user_last_login(connection, str(user["user_id"])) or user


def upsert_identity_binding(
    connection: sqlite3.Connection,
    user_id: str,
    provider_name: str,
    provider_subject: str,
    provider_email: str,
) -> None:
    binding_id = f"binding_{provider_name}_{provider_subject}"
    timestamp = now_iso()
    connection.execute(
        """
        INSERT OR REPLACE INTO identity_bindings (
            binding_id,
            user_id,
            provider_name,
            provider_subject,
            provider_email,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (binding_id, user_id, provider_name, provider_subject, provider_email, timestamp, timestamp),
    )
    connection.commit()


def create_refresh_session(
    connection: sqlite3.Connection,
    settings: WebSettings,
    user_id: str,
    ip_address: str,
    user_agent: str,
) -> dict[str, str]:
    refresh_token = secrets.token_urlsafe(32)
    session_id = f"session_{secrets.token_hex(8)}"
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=settings.refresh_token_days)
    connection.execute(
        """
        INSERT OR REPLACE INTO auth_sessions (
            session_id,
            user_id,
            refresh_token_hash,
            issued_at,
            expires_at,
            revoked_at,
            ip_address,
            user_agent
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            user_id,
            hash_refresh_token(refresh_token),
            issued_at.isoformat(),
            expires_at.isoformat(),
            "",
            ip_address,
            user_agent,
        ),
    )
    connection.commit()
    return {
        "session_id": session_id,
        "refresh_token": refresh_token,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def create_auth_state(
    connection: sqlite3.Connection,
    provider_name: str,
    redirect_uri: str,
    username_hint: str,
    ttl_minutes: int = 10,
) -> dict[str, str]:
    state_token = secrets.token_urlsafe(24)
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(minutes=ttl_minutes)
    connection.execute(
        """
        INSERT INTO auth_state_tokens (
            state_token,
            provider_name,
            redirect_uri,
            username_hint,
            created_at,
            expires_at,
            consumed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            state_token,
            provider_name,
            redirect_uri,
            username_hint,
            created_at.isoformat(),
            expires_at.isoformat(),
            "",
        ),
    )
    connection.commit()
    return {
        "state_token": state_token,
        "provider_name": provider_name,
        "redirect_uri": redirect_uri,
        "username_hint": username_hint,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def revoke_refresh_session(connection: sqlite3.Connection, refresh_token: str) -> None:
    connection.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = ?
        WHERE refresh_token_hash = ?
        """,
        (now_iso(), hash_refresh_token(refresh_token)),
    )
    connection.commit()


def load_auth_state(connection: sqlite3.Connection, state_token: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT
            state_token,
            provider_name,
            redirect_uri,
            username_hint,
            created_at,
            expires_at,
            consumed_at
        FROM auth_state_tokens
        WHERE state_token = ?
        """,
        (state_token,),
    ).fetchone()
    if row is None:
        return None
    return {
        "state_token": row[0],
        "provider_name": row[1],
        "redirect_uri": row[2],
        "username_hint": row[3],
        "created_at": row[4],
        "expires_at": row[5],
        "consumed_at": row[6],
    }


def consume_auth_state(connection: sqlite3.Connection, state_token: str) -> None:
    connection.execute(
        """
        UPDATE auth_state_tokens
        SET consumed_at = ?
        WHERE state_token = ?
        """,
        (now_iso(), state_token),
    )
    connection.commit()


def load_session_by_refresh_token(connection: sqlite3.Connection, refresh_token: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT session_id, user_id, issued_at, expires_at, revoked_at
        FROM auth_sessions
        WHERE refresh_token_hash = ?
        """,
        (hash_refresh_token(refresh_token),),
    ).fetchone()
    if row is None:
        return None
    return {
        "session_id": row[0],
        "user_id": row[1],
        "issued_at": row[2],
        "expires_at": row[3],
        "revoked_at": row[4],
    }


def is_session_active(session: dict[str, Any] | None) -> bool:
    if not session:
        return False
    if str(session.get("revoked_at", "")).strip():
        return False
    expires_at = str(session.get("expires_at", "")).strip()
    if not expires_at:
        return False
    try:
        expires_at_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    return expires_at_dt > datetime.now(timezone.utc)


def is_auth_state_active(auth_state: dict[str, Any] | None) -> bool:
    if not auth_state:
        return False
    if str(auth_state.get("consumed_at", "")).strip():
        return False
    expires_at = str(auth_state.get("expires_at", "")).strip()
    if not expires_at:
        return False
    try:
        expires_at_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    return expires_at_dt > datetime.now(timezone.utc)


def load_user_by_id(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT user_id, username, display_name, email, status, default_role, last_login_at
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "display_name": row[2],
        "email": row[3],
        "status": row[4],
        "default_role": row[5],
        "last_login_at": row[6],
    }


def load_users(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT user_id, username, display_name, email, status, default_role, last_login_at
        FROM users
        ORDER BY username ASC
        """
    ).fetchall()
    return [
        {
            "user_id": row[0],
            "username": row[1],
            "display_name": row[2],
            "email": row[3],
            "status": row[4],
            "default_role": row[5],
            "last_login_at": row[6],
        }
        for row in rows
    ]


def load_identity_bindings_for_users(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT user_id, provider_name, provider_subject, provider_email, created_at, updated_at
        FROM identity_bindings
        ORDER BY updated_at DESC
        """
    ).fetchall()
    bindings_map: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        bindings_map.setdefault(str(row[0]), []).append(
            {
                "provider_name": row[1],
                "provider_subject": row[2],
                "provider_email": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
        )
    return bindings_map


def load_active_session_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT user_id, COUNT(*)
        FROM auth_sessions
        WHERE revoked_at = ''
        GROUP BY user_id
        """
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def update_user_role(
    connection: sqlite3.Connection,
    user_id: str,
    default_role: str,
) -> dict[str, Any] | None:
    connection.execute(
        """
        UPDATE users
        SET default_role = ?
        WHERE user_id = ?
        """,
        (default_role, user_id),
    )
    connection.commit()
    return load_user_by_id(connection, user_id)


def update_user_status(
    connection: sqlite3.Connection,
    user_id: str,
    status: str,
) -> dict[str, Any] | None:
    connection.execute(
        """
        UPDATE users
        SET status = ?
        WHERE user_id = ?
        """,
        (status, user_id),
    )
    connection.commit()
    return load_user_by_id(connection, user_id)


def revoke_sessions_for_user(connection: sqlite3.Connection, user_id: str) -> int:
    cursor = connection.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = ?
        WHERE user_id = ? AND revoked_at = ''
        """,
        (now_iso(), user_id),
    )
    connection.commit()
    return int(cursor.rowcount or 0)


def load_sessions_for_user(connection: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            session_id,
            user_id,
            issued_at,
            expires_at,
            revoked_at,
            ip_address,
            user_agent
        FROM auth_sessions
        WHERE user_id = ?
        ORDER BY issued_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [build_session_record(row) for row in rows]


def build_session_record(row: tuple[Any, ...]) -> dict[str, Any]:
    session = {
        "session_id": row[0],
        "user_id": row[1],
        "issued_at": row[2],
        "expires_at": row[3],
        "revoked_at": row[4],
        "ip_address": row[5],
        "user_agent": row[6],
    }
    session["active"] = is_session_active(session)
    return session


def load_sessions_by_ids(connection: sqlite3.Connection, session_ids: list[str]) -> list[dict[str, Any]]:
    normalized_ids = [session_id.strip() for session_id in session_ids if session_id.strip()]
    if not normalized_ids:
        return []
    placeholders = ", ".join("?" for _ in normalized_ids)
    rows = connection.execute(
        f"""
        SELECT
            session_id,
            user_id,
            issued_at,
            expires_at,
            revoked_at,
            ip_address,
            user_agent
        FROM auth_sessions
        WHERE session_id IN ({placeholders})
        ORDER BY issued_at DESC
        """,
        tuple(normalized_ids),
    ).fetchall()
    return [build_session_record(row) for row in rows]


def build_global_session_filters(
    username: str = "",
    role: str = "",
    session_status: str = "",
    ip_address: str = "",
) -> tuple[list[str], list[Any]]:
    where_clauses = ["1 = 1"]
    parameters: list[Any] = []
    now_marker = now_iso()

    normalized_username = username.strip().lower()
    if normalized_username:
        where_clauses.append("LOWER(u.username) LIKE ?")
        parameters.append(f"%{normalized_username}%")

    normalized_role = role.strip().lower()
    if normalized_role:
        where_clauses.append("LOWER(u.default_role) = ?")
        parameters.append(normalized_role)

    normalized_status = session_status.strip().lower()
    if normalized_status == "active":
        where_clauses.append("s.revoked_at = ''")
        where_clauses.append("s.expires_at > ?")
        parameters.append(now_marker)
    elif normalized_status == "revoked":
        where_clauses.append("(s.revoked_at <> '' OR s.expires_at <= ?)")
        parameters.append(now_marker)

    normalized_ip = ip_address.strip().lower()
    if normalized_ip:
        where_clauses.append("LOWER(s.ip_address) LIKE ?")
        parameters.append(f"%{normalized_ip}%")

    return where_clauses, parameters


def resolve_security_sort(sort_by: str = "", sort_order: str = "") -> tuple[str, str]:
    allowed_fields = {
        "issued_at": "s.issued_at",
        "expires_at": "s.expires_at",
        "ip_address": "s.ip_address",
        "username": "u.username",
        "default_role": "u.default_role",
        "user_status": "u.status",
    }
    normalized_sort_by = sort_by.strip().lower() or "issued_at"
    normalized_sort_order = sort_order.strip().lower() or "desc"
    if normalized_sort_by not in allowed_fields:
        normalized_sort_by = "issued_at"
    if normalized_sort_order not in {"asc", "desc"}:
        normalized_sort_order = "desc"
    order_expression = allowed_fields[normalized_sort_by]
    if normalized_sort_by == "issued_at":
        order_by = f"CASE WHEN s.revoked_at = '' THEN 0 ELSE 1 END ASC, {order_expression} {normalized_sort_order.upper()}"
    else:
        order_by = f"{order_expression} {normalized_sort_order.upper()}, s.issued_at DESC"
    return normalized_sort_by, order_by


def load_global_sessions(
    connection: sqlite3.Connection,
    username: str = "",
    role: str = "",
    session_status: str = "",
    ip_address: str = "",
    limit: int = 200,
    offset: int = 0,
    sort_by: str = "",
    sort_order: str = "",
) -> list[dict[str, Any]]:
    where_clauses, parameters = build_global_session_filters(
        username=username,
        role=role,
        session_status=session_status,
        ip_address=ip_address,
    )
    _, order_by = resolve_security_sort(sort_by, sort_order)
    parameters.extend([max(1, min(limit, 500)), max(0, offset)])
    query = Template(
        """
        SELECT
            s.session_id,
            s.user_id,
            s.issued_at,
            s.expires_at,
            s.revoked_at,
            s.ip_address,
            s.user_agent,
            u.username,
            u.display_name,
            u.email,
            u.status,
            u.default_role
        FROM auth_sessions s
        INNER JOIN users u
            ON u.user_id = s.user_id
        WHERE $where_clause
        ORDER BY $order_by
        LIMIT ?
        OFFSET ?
        """
    ).substitute(where_clause=" AND ".join(where_clauses), order_by=order_by)
    rows = connection.execute(
        query,
        tuple(parameters),
    ).fetchall()
    return [
        {
            **build_session_record(row[:7]),
            "username": row[7],
            "display_name": row[8],
            "email": row[9],
            "user_status": row[10],
            "default_role": row[11],
        }
        for row in rows
    ]


def load_global_session_stats(
    connection: sqlite3.Connection,
    username: str = "",
    role: str = "",
    session_status: str = "",
    ip_address: str = "",
) -> dict[str, int]:
    where_clauses, parameters = build_global_session_filters(
        username=username,
        role=role,
        session_status=session_status,
        ip_address=ip_address,
    )

    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS total_count,
            SUM(CASE WHEN s.revoked_at = '' THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN s.revoked_at <> '' THEN 1 ELSE 0 END) AS revoked_count
        FROM auth_sessions s
        INNER JOIN users u
            ON u.user_id = s.user_id
        WHERE {" AND ".join(where_clauses)}
        """,
        tuple(parameters),
    ).fetchone()
    return {
        "total_count": int((row[0] if row and row[0] is not None else 0) or 0),
        "active_count": int((row[1] if row and row[1] is not None else 0) or 0),
        "revoked_count": int((row[2] if row and row[2] is not None else 0) or 0),
    }


def revoke_session_by_id(connection: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    session_row = connection.execute(
        """
        SELECT session_id, user_id, issued_at, expires_at, revoked_at, ip_address, user_agent
        FROM auth_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if session_row is None:
        return None
    connection.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = ?
        WHERE session_id = ? AND revoked_at = ''
        """,
        (now_iso(), session_id),
    )
    connection.commit()
    refreshed_row = connection.execute(
        """
        SELECT session_id, user_id, issued_at, expires_at, revoked_at, ip_address, user_agent
        FROM auth_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if refreshed_row is None:
        return None
    return build_session_record(refreshed_row)


def write_audit_log(
    connection: sqlite3.Connection,
    user_id: str,
    action_type: str,
    target_type: str,
    target_id: str,
    result: str,
    detail: str,
) -> None:
    audit_id = f"audit_{secrets.token_hex(8)}"
    connection.execute(
        """
        INSERT INTO audit_logs (
            audit_id,
            user_id,
            action_type,
            target_type,
            target_id,
            result,
            detail,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (audit_id, user_id, action_type, target_type, target_id, result, detail, now_iso()),
    )
    connection.commit()
