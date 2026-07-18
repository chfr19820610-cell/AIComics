from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure src/ is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Fixtures: sample data objects used across test modules
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_project_manifest() -> dict:
    """A realistic episode manifest for job-builder tests."""
    return {
        "project_id": "test_project_001",
        "project_name": "测试项目",
        "genre": "horror",
        "episodes": [
            {
                "episode_code": "E01",
                "title": "第一集",
                "shots": [
                    {
                        "shot_id": "S001",
                        "dialogue": "你好，世界",
                        "ai_video": True,
                    },
                    {
                        "shot_id": "S002",
                        "dialogue": "",
                        "ai_video": False,
                    },
                    {
                        "shot_id": "S003",
                        "dialogue": "测试对话",
                        "ai_video": False,
                    },
                ],
            },
            {
                "episode_code": "E02",
                "title": "第二集",
                "shots": [
                    {
                        "shot_id": "S001",
                        "dialogue": "欢迎",
                        "ai_video": True,
                    },
                ],
            },
        ],
    }


@pytest.fixture
def sample_edition_yaml(tmp_path: Path) -> Path:
    """Write a temporary edition.yaml config and return its path."""
    content = """edition:
  name: creator
  auth_enabled: true
  batch_enabled: true
  default_database: sqlite
"""
    config_path = tmp_path / "edition.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


@pytest.fixture
def providers_config_path(tmp_path: Path) -> Path:
    """Empty providers config file for executor tests."""
    path = tmp_path / "providers.yaml"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture
def sample_edition_yaml_custom(tmp_path: Path) -> Path:
    """A non-default edition config with some overrides."""
    content = """edition:
  name: creator
  auth_enabled: true
  oidc_enabled: true
  rbac_enabled: true
  audit_enabled: true
  batch_enabled: true
  distributed_queue_enabled: true
  enterprise_storage_enabled: true
  cost_control_enabled: true
  default_database: postgresql
  default_storage: s3
  deployment_mode: k8s_cluster
"""
    config_path = tmp_path / "edition.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path
