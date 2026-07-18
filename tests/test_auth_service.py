from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from web.backend.auth.auth_service import (
    authenticate_password_user,
    connect_auth_database,
    consume_auth_state,
    create_auth_state,
    create_refresh_session,
    ensure_auth_schema,
    hash_password,
    hash_refresh_token,
    is_auth_state_active,
    is_session_active,
    load_auth_state,
    load_password_credential,
    load_session_by_refresh_token,
    load_user_by_id,
    load_user_by_username,
    revoke_refresh_session,
    upsert_identity_binding,
    upsert_password_credential,
    upsert_user,
    verify_password,
)
from web.backend.settings import WebSettings


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    path = tmp_path / "auth_test.db"
    conn = connect_auth_database(path)
    ensure_auth_schema(conn)
    return conn


@pytest.fixture
def settings(tmp_path: Path) -> WebSettings:
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
        jwt_secret="test-secret",
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_token_minutes=60,
        refresh_token_days=7,
        access_token_cookie_name="test_access",
        refresh_token_cookie_name="test_refresh",
        default_role="creator",
        password_user_username="creator",
        password_user_display_name="Creator",
        password_user_email="creator@test.local",
        password_user_role="creator",
        password_user_password="test-password",
        cors_allow_origins=("*",),
    )


class TestConnectAuthDatabase:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        path = tmp_path / "new_auth.db"
        conn = connect_auth_database(path)
        assert path.exists()
        conn.close()

    def test_returns_connection(self) -> None:
        conn = connect_auth_database(Path("/tmp/auth_test_conn.db"))
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


class TestEnsureAuthSchema:
    def test_creates_all_tables(self, db: sqlite3.Connection) -> None:
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        assert "users" in tables
        assert "identity_bindings" in tables
        assert "auth_sessions" in tables
        assert "audit_logs" in tables
        assert "auth_state_tokens" in tables
        assert "password_credentials" in tables

    def test_idempotent(self, db: sqlite3.Connection) -> None:
        ensure_auth_schema(db)  # should not raise


class TestHashFunctions:
    def test_hash_refresh_token(self) -> None:
        h = hash_refresh_token("my_refresh_token")
        assert isinstance(h, str)
        assert len(h) == 64  # sha256 hex

    def test_hash_password_returns_dict(self) -> None:
        result = hash_password("my_password")
        assert "algorithm" in result
        assert "password_hash" in result
        assert "password_salt" in result

    def test_hash_password_deterministic_with_salt(self) -> None:
        r1 = hash_password("pass", "fixed_salt_1234567890123456")
        r2 = hash_password("pass", "fixed_salt_1234567890123456")
        assert r1["password_hash"] == r2["password_hash"]


class TestVerifyPassword:
    def test_none_credential(self) -> None:
        assert verify_password("pass", None) is False

    def test_wrong_algorithm(self) -> None:
        cred = {"algorithm": "md5", "password_hash": "x", "password_salt": "y"}
        assert verify_password("pass", cred) is False

    def test_correct_password(self) -> None:
        hashed = hash_password("correct_pass")
        assert verify_password("correct_pass", hashed) is True

    def test_wrong_password(self) -> None:
        hashed = hash_password("correct_pass")
        assert verify_password("wrong_pass", hashed) is False


class TestUpsertUser:
    def test_creates_user(self, db: sqlite3.Connection) -> None:
        user = upsert_user(db, "testuser", "Test User", "test@test.com", "creator")
        assert user["user_id"] == "user_testuser"
        assert user["status"] == "active"

    def test_replaces_existing(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "Old Name", "old@test.com", "viewer")
        user = upsert_user(db, "testuser", "New Name", "new@test.com", "creator")
        assert user["display_name"] == "New Name"


class TestLoadUserByUsername:
    def test_finds_user(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "Test", "t@t.com", "creator")
        user = load_user_by_username(db, "testuser")
        assert user is not None
        assert user["username"] == "testuser"

    def test_case_insensitive(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "TestUser", "Test", "t@t.com", "creator")
        user = load_user_by_username(db, "testuser")
        assert user is not None

    def test_not_found(self, db: sqlite3.Connection) -> None:
        assert load_user_by_username(db, "nonexistent") is None


class TestUpsertPasswordCredential:
    def test_creates_and_loads(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "T", "t@t.com", "creator")
        upsert_password_credential(db, "user_testuser", "mypassword")
        cred = load_password_credential(db, "user_testuser")
        assert cred is not None
        assert verify_password("mypassword", cred) is True


class TestAuthenticatePasswordUser:
    def test_successful_login(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "T", "t@t.com", "creator")
        upsert_password_credential(db, "user_testuser", "correct_pass")
        user = authenticate_password_user(db, "testuser", "correct_pass")
        assert user is not None
        assert user["username"] == "testuser"

    def test_wrong_password(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "T", "t@t.com", "creator")
        upsert_password_credential(db, "user_testuser", "correct_pass")
        assert authenticate_password_user(db, "testuser", "wrong_pass") is None

    def test_inactive_user(self, db: sqlite3.Connection) -> None:
        user_id = "user_inactive"
        db.execute(
            "INSERT INTO users (user_id, username, display_name, email, status, default_role, last_login_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, "inactive_user", "Inactive", "i@i.com", "disabled", "viewer", ""),
        )
        db.commit()
        assert authenticate_password_user(db, "inactive_user", "any") is None


class TestCreateRefreshSession:
    def test_creates_session(self, db: sqlite3.Connection, settings: WebSettings) -> None:
        result = create_refresh_session(db, settings, "user_001", "127.0.0.1", "test-agent")
        assert "session_id" in result
        assert "refresh_token" in result
        assert result["session_id"].startswith("session_")


class TestIsSessionActive:
    def test_none_session(self) -> None:
        assert is_session_active(None) is False

    def test_revoked_session(self) -> None:
        session = {
            "session_id": "s1",
            "user_id": "u1",
            "issued_at": "2025-01-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "revoked_at": "2025-01-02T00:00:00+00:00",
        }
        assert is_session_active(session) is False

    def test_expired_session(self) -> None:
        session = {
            "session_id": "s1",
            "user_id": "u1",
            "issued_at": "2020-01-01T00:00:00+00:00",
            "expires_at": "2020-01-02T00:00:00+00:00",
            "revoked_at": "",
        }
        assert is_session_active(session) is False


class TestCreateAuthState:
    def test_creates_state(self, db: sqlite3.Connection) -> None:
        state = create_auth_state(db, "password", "/callback", "user_hint")
        assert "state_token" in state
        assert state["provider_name"] == "password"


class TestIsAuthStateActive:
    def test_none_state(self) -> None:
        assert is_auth_state_active(None) is False

    def test_consumed_state(self) -> None:
        state = {
            "state_token": "tok",
            "provider_name": "p",
            "redirect_uri": "",
            "username_hint": "",
            "created_at": "2025-01-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "consumed_at": "2025-01-01T00:00:01+00:00",
        }
        assert is_auth_state_active(state) is False

    def test_expired_state(self) -> None:
        state = {
            "state_token": "tok",
            "provider_name": "p",
            "redirect_uri": "",
            "username_hint": "",
            "created_at": "2020-01-01T00:00:00+00:00",
            "expires_at": "2020-01-02T00:00:00+00:00",
            "consumed_at": "",
        }
        assert is_auth_state_active(state) is False

    def test_active_state(self, db: sqlite3.Connection) -> None:
        created = create_auth_state(db, "password", "/cb", "hint", ttl_minutes=60)
        loaded = load_auth_state(db, created["state_token"])
        assert is_auth_state_active(loaded) is True


class TestRevokeRefreshSession:
    def test_revokes(self, db: sqlite3.Connection, settings: WebSettings) -> None:
        session = create_refresh_session(db, settings, "user_001", "::1", "test")
        revoke_refresh_session(db, session["refresh_token"])
        loaded = load_session_by_refresh_token(db, session["refresh_token"])
        assert is_session_active(loaded) is False


class TestLoadUserById:
    def test_finds_user(self, db: sqlite3.Connection) -> None:
        upsert_user(db, "testuser", "T", "t@t.com", "creator")
        user = load_user_by_id(db, "user_testuser")
        assert user is not None
        assert user["username"] == "testuser"

    def test_not_found(self, db: sqlite3.Connection) -> None:
        assert load_user_by_id(db, "nonexistent") is None


class TestConsumeAuthState:
    def test_consumes(self, db: sqlite3.Connection) -> None:
        created = create_auth_state(db, "password", "/cb", "hint")
        consume_auth_state(db, created["state_token"])
        loaded = load_auth_state(db, created["state_token"])
        assert is_auth_state_active(loaded) is False


class TestUpsertIdentityBinding:
    def test_creates_binding(self, db: sqlite3.Connection) -> None:
        upsert_identity_binding(db, "user_001", "password", "testuser", "t@t.com")
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM identity_bindings WHERE user_id = ?", ("user_001",))
        assert cursor.fetchone()[0] == 1
