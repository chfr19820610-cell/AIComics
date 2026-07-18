from __future__ import annotations

from pathlib import Path

import pytest

from web.backend.settings import (
    _require_jwt_secret,
    load_web_config_map,
    load_web_settings,
    parse_scalar,
)


class TestParseScalarWeb:
    def test_boolean_true(self) -> None:
        assert parse_scalar("true") is True
        assert parse_scalar("True") is True
        assert parse_scalar("TRUE") is True

    def test_boolean_false(self) -> None:
        assert parse_scalar("false") is False
        assert parse_scalar("False") is False

    def test_integer(self) -> None:
        assert parse_scalar("42") == 42
        assert parse_scalar("0") == 0

    def test_string(self) -> None:
        assert parse_scalar("hello") == "hello"

    def test_env_var_expanded(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_HOST", "0.0.0.0")
        assert parse_scalar("$MY_HOST") == "0.0.0.0"


class TestRequireJwtSecret:
    def test_present(self) -> None:
        assert _require_jwt_secret({"jwt_secret": "my-secret"}) == "my-secret"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="JWT secret"):
            _require_jwt_secret({})

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            _require_jwt_secret({"jwt_secret": "   "})


class TestLoadWebConfigMap:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_web_config_map(tmp_path / "nonexistent.yaml") == {}

    def test_parses_sections(self, tmp_path: Path) -> None:
        content = """
server:
  host: 0.0.0.0
  port: 8080

auth:
  auth_enabled: true
  jwt_secret: test-secret
"""
        p = tmp_path / "web.yaml"
        p.write_text(content, encoding="utf-8")
        config = load_web_config_map(p)
        assert config["server"]["host"] == "0.0.0.0"
        assert config["server"]["port"] == 8080
        assert config["auth"]["auth_enabled"] is True

    def test_skips_comments(self, tmp_path: Path) -> None:
        content = """# comment
server:
  host: localhost
"""
        p = tmp_path / "web.yaml"
        p.write_text(content, encoding="utf-8")
        config = load_web_config_map(p)
        assert config["server"]["host"] == "localhost"
