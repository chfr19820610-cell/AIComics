"""Template marketplace tests — install/uninstall/share templates."""
from __future__ import annotations

import pytest

from aicomic.core.template_market import (
    validate_template_yaml,
    install_template_from_dict,
    install_template_from_url,
    uninstall_template,
    share_template_url,
    list_installed_templates,
)


class TestValidateTemplateYaml:
    def test_valid_template_passes(self):
        t = {
            "template_id": "test_genre",
            "genre": "测试题材",
            "acts": [{"act_id": "A1", "title": "开场", "beat": "open"}],
            "locations": ["场景A"],
            "characters": [{"name": "主角", "role": "主视角", "visual_rule": "x"}],
        }
        assert validate_template_yaml(t) is True

    def test_missing_template_id_fails(self):
        t = {"genre": "x", "acts": [], "locations": [], "characters": []}
        assert validate_template_yaml(t) is False

    def test_missing_acts_fails(self):
        t = {"template_id": "x", "genre": "x", "locations": [], "characters": []}
        assert validate_template_yaml(t) is False

    def test_missing_characters_fails(self):
        t = {"template_id": "x", "genre": "x", "acts": [], "locations": []}
        assert validate_template_yaml(t) is False

    def test_empty_acts_fails(self):
        t = {"template_id": "x", "genre": "x", "acts": [], "locations": ["x"], "characters": [{"name": "x", "role": "x", "visual_rule": "x"}]}
        assert validate_template_yaml(t) is False

    def test_non_dict_fails(self):
        assert validate_template_yaml("not a dict") is False
        assert validate_template_yaml(None) is False


class TestInstallFromDict:
    def test_install_creates_yaml_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aicomic.core.template_market._templates_dir", lambda: tmp_path)
        t = {
            "template_id": "custom_genre",
            "genre": "自定义题材",
            "acts": [{"act_id": "A1", "title": "开场", "beat": "open"}],
            "locations": ["场景A"],
            "characters": [{"name": "主角", "role": "主视角", "visual_rule": "x"}],
        }
        result = install_template_from_dict(t, templates_dir=tmp_path)
        assert result["success"] is True
        assert (tmp_path / "custom_genre.yaml").exists()

    def test_install_overwrites_existing(self, tmp_path):
        t = {
            "template_id": "existing",
            "genre": "x",
            "acts": [{"act_id": "A1", "title": "x", "beat": "x"}],
            "locations": ["x"],
            "characters": [{"name": "x", "role": "x", "visual_rule": "x"}],
        }
        install_template_from_dict(t, templates_dir=tmp_path)
        t["genre"] = "updated"
        result = install_template_from_dict(t, templates_dir=tmp_path)
        assert result["success"] is True
        assert result["overwritten"] is True

    def test_install_invalid_template_fails(self, tmp_path):
        result = install_template_from_dict({"template_id": "x"}, templates_dir=tmp_path)
        assert result["success"] is False
        assert "validation" in result["error"]


class TestUninstall:
    def test_uninstall_existing(self, tmp_path):
        (tmp_path / "to_remove.yaml").write_text("test", encoding="utf-8")
        result = uninstall_template("to_remove", templates_dir=tmp_path)
        assert result["success"] is True
        assert not (tmp_path / "to_remove.yaml").exists()

    def test_uninstall_nonexistent_fails(self, tmp_path):
        result = uninstall_template("nonexistent", templates_dir=tmp_path)
        assert result["success"] is False


class TestShareUrl:
    def test_share_returns_gist_format(self):
        t = {
            "template_id": "test_share",
            "genre": "x",
            "acts": [{"act_id": "A1", "title": "x", "beat": "x"}],
            "locations": ["x"],
            "characters": [{"name": "x", "role": "x", "visual_rule": "x"}],
        }
        result = share_template_url(t)
        assert result["format"] == "gist"
        assert "yaml_base64" in result
        assert "install_command" in result
        assert "test_share" in result["install_command"]


class TestInstallFromUrl:
    def test_install_from_url_success(self, tmp_path, monkeypatch):
        """Mock URL fetch → install template."""
        import base64
        t = {
            "template_id": "url_installed",
            "genre": "URL安装测试",
            "acts": [{"act_id": "A1", "title": "开场", "beat": "open"}],
            "locations": ["场景A"],
            "characters": [{"name": "主角", "role": "主视角", "visual_rule": "x"}],
        }
        yaml_content = yaml_dump(t)
        encoded = base64.b64encode(yaml_content.encode()).decode()

        # Mock urllib
        from unittest.mock import patch, MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = encoded.encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *a: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = install_template_from_url("https://example.com/template.b64", templates_dir=tmp_path)
        assert result["success"] is True
        assert (tmp_path / "url_installed.yaml").exists()

    def test_install_from_url_invalid_content_fails(self, tmp_path):
        from unittest.mock import patch, MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = b"not_valid_yaml_or_base64"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *a: None
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = install_template_from_url("https://example.com/bad", templates_dir=tmp_path)
        assert result["success"] is False


class TestListInstalled:
    def test_list_shows_builtin_and_custom(self, tmp_path, monkeypatch):
        monkeypatch.setattr("aicomic.core.template_market._templates_dir", lambda: tmp_path)
        (tmp_path / "builtin1.yaml").write_text("test", encoding="utf-8")
        (tmp_path / "custom1.yaml").write_text("test", encoding="utf-8")
        result = list_installed_templates(templates_dir=tmp_path)
        assert "builtin1" in result
        assert "custom1" in result


def yaml_dump(t):
    import yaml
    return yaml.dump(t, allow_unicode=True, default_flow_style=False)
