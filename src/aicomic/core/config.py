from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    @staticmethod
    def project_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def config_dir() -> Path:
        return ProjectPaths.project_root() / "config"

    @staticmethod
    def manifest_dir() -> Path:
        return ProjectPaths.project_root() / "manifests"

    @staticmethod
    def state_dir() -> Path:
        override_path = os.environ.get("AICOMIC_STATE_DIR", "").strip()
        if override_path:
            return Path(override_path)
        return ProjectPaths.project_root() / "state"

    @staticmethod
    def reports_dir() -> Path:
        return ProjectPaths.project_root() / "reports"

    @staticmethod
    def default_database_path() -> Path:
        override_path = os.environ.get("AICOMIC_DATABASE_PATH", "").strip()
        if override_path:
            return Path(override_path)
        return ProjectPaths.state_dir() / "aicomic_demo.db"

    @staticmethod
    def demo_assets_dir() -> Path:
        return ProjectPaths.state_dir() / "demo_assets"

    @staticmethod
    def preview_outputs_dir() -> Path:
        return ProjectPaths.state_dir() / "preview_outputs"

    @staticmethod
    def jobs_output_dir() -> Path:
        return ProjectPaths.project_root() / "jobs"

    @staticmethod
    def templates_dir() -> Path:
        return ProjectPaths.project_root() / "templates"

    @staticmethod
    def generated_projects_dir() -> Path:
        return ProjectPaths.state_dir() / "generated_projects"

    @staticmethod
    def render_config_path() -> Path:
        return ProjectPaths.config_dir() / "render.yaml"

    @staticmethod
    def project_config_path() -> Path:
        return ProjectPaths.config_dir() / "project.yaml"

    @staticmethod
    def providers_config_path() -> Path:
        return ProjectPaths.config_dir() / "providers.yaml"
