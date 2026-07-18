from __future__ import annotations

from pathlib import Path

from aicomic.core.config import ProjectPaths


class TestProjectRoot:
    def test_project_root_returns_path(self) -> None:
        root = ProjectPaths.project_root()
        assert isinstance(root, Path)

    def test_project_root_is_absolute(self) -> None:
        assert ProjectPaths.project_root().is_absolute()

    def test_config_dir(self) -> None:
        d = ProjectPaths.config_dir()
        assert d.name == "config"

    def test_manifest_dir(self) -> None:
        d = ProjectPaths.manifest_dir()
        assert d.name == "manifests"

    def test_state_dir_default(self) -> None:
        d = ProjectPaths.state_dir()
        assert d.name == "state"

    def test_reports_dir(self) -> None:
        d = ProjectPaths.reports_dir()
        assert d.name == "reports"

    def test_default_database_path(self) -> None:
        p = ProjectPaths.default_database_path()
        assert str(p).endswith(".db")

    def test_templates_dir(self) -> None:
        d = ProjectPaths.templates_dir()
        assert d.name == "templates"

    def test_render_config_path(self) -> None:
        p = ProjectPaths.render_config_path()
        assert p.name == "render.yaml"

    def test_providers_config_path(self) -> None:
        p = ProjectPaths.providers_config_path()
        assert p.name == "providers.yaml"

    def test_project_config_path(self) -> None:
        p = ProjectPaths.project_config_path()
        assert p.name == "project.yaml"

    def test_state_dir_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("AICOMIC_STATE_DIR", "/tmp/override_state")
        assert str(ProjectPaths.state_dir()) == "/tmp/override_state"

    def test_database_path_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("AICOMIC_DATABASE_PATH", "/tmp/custom.db")
        assert str(ProjectPaths.default_database_path()) == "/tmp/custom.db"
