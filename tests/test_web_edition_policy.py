from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.edition import EditionCapability
from web.backend.services.edition_policy import (
    EditionPolicy,
    build_auth_reason,
    build_creator_only_reason,
    load_edition_policy,
)
from web.backend.settings import WebSettings


def _make_settings(**overrides: Any) -> WebSettings:
    kwargs: dict[str, Any] = dict(
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
        jwt_issuer="test",
        jwt_audience="test",
        access_token_minutes=60,
        refresh_token_days=7,
        access_token_cookie_name="test",
        refresh_token_cookie_name="test",
        default_role="creator",
        password_user_username="creator",
        password_user_display_name="Creator",
        password_user_email="creator@test.local",
        password_user_role="creator",
        password_user_password="pass",
        cors_allow_origins=("*",),
    )
    kwargs.update(overrides)
    return WebSettings(**kwargs)


def _make_edition(**overrides: Any) -> EditionCapability:
    kwargs: dict[str, Any] = dict(
        edition_name="creator",
        display_name="Creator 个人创作者版",
        single_user_mode=True,
        multi_user_enabled=False,
        auth_enabled=True,
        oidc_enabled=False,
        rbac_enabled=False,
        audit_enabled=False,
        batch_enabled=True,
        distributed_queue_enabled=False,
        enterprise_storage_enabled=False,
        cost_control_enabled=False,
        default_database="sqlite",
        default_storage="local_filesystem",
        deployment_mode="windows_single_machine",
        default_entry="frontend_spa",
    )
    kwargs.update(overrides)
    return EditionCapability(**kwargs)


class TestEditionPolicy:
    def test_both_enabled_auth_true(self) -> None:
        settings = _make_settings(auth_enabled=True)
        edition = _make_edition(auth_enabled=True)
        policy = load_edition_policy(settings, edition)
        assert policy.auth_enabled is True
        assert policy.edition_name == "creator"

    def test_edition_disabled_auth(self) -> None:
        settings = _make_settings(auth_enabled=True)
        edition = _make_edition(auth_enabled=False)
        policy = load_edition_policy(settings, edition)
        assert policy.auth_enabled is False

    def test_settings_disabled_auth(self) -> None:
        settings = _make_settings(auth_enabled=False)
        edition = _make_edition(auth_enabled=True)
        policy = load_edition_policy(settings, edition)
        assert policy.auth_enabled is False

    def test_creator_only(self) -> None:
        policy = load_edition_policy(_make_settings(), _make_edition())
        assert policy.creator_only is True

    def test_batch_enabled(self) -> None:
        edition = _make_edition(batch_enabled=True)
        policy = load_edition_policy(_make_settings(), edition)
        assert policy.batch_enabled is True

    def test_batch_disabled(self) -> None:
        edition = _make_edition(batch_enabled=False)
        policy = load_edition_policy(_make_settings(), edition)
        assert policy.batch_enabled is False

    def test_to_dict(self) -> None:
        policy = load_edition_policy(_make_settings(), _make_edition())
        d = policy.to_dict()
        assert d["edition_name"] == "creator"
        assert "auth_enabled" in d


class TestBuildAuthReason:
    def test_enabled(self) -> None:
        reason = build_auth_reason(
            _make_settings(auth_enabled=True),
            _make_edition(auth_enabled=True),
            enabled=True,
        )
        assert "已启用" in reason

    def test_edition_disabled(self) -> None:
        reason = build_auth_reason(
            _make_settings(auth_enabled=True),
            _make_edition(auth_enabled=False),
            enabled=False,
        )
        assert "未启用" in reason

    def test_settings_disabled(self) -> None:
        reason = build_auth_reason(
            _make_settings(auth_enabled=False),
            _make_edition(auth_enabled=True),
            enabled=False,
        )
        assert "web.yaml" in reason


class TestBuildCreatorOnlyReason:
    def test_contains_display_name(self) -> None:
        reason = build_creator_only_reason(_make_edition(display_name="测试版"))
        assert "测试版" in reason
