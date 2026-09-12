"""v4.0 P2/P3 integration tests — LoRA training GUI, Docker deployment,
novel-to-comic pipeline, Electron desktop scaffold.

Tests that the v4.0 P2/P3 upgrades are properly wired:
  - P2-9:  LoRA training config builder (CLI-accessible, not heavy GUI)
  - P2-10: Docker one-click deploy (Dockerfile + compose verified)
  - P3-11: Novel→Comic pipeline (import_novel → split → manifest → produce)
  - P3-12: Electron desktop package.json scaffold
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestLoRATrainingConfig:
    """P2-9: LoRA training config builder."""

    def test_lora_config_builder_importable(self):
        """lora_config module should be importable."""
        from aicomic.core.lora_config import build_lora_training_config

        assert callable(build_lora_training_config)

    def test_lora_config_generates_valid_dict(self):
        """Config builder should return a dict with required keys."""
        from aicomic.core.lora_config import build_lora_training_config

        config = build_lora_training_config(
            character_name="test_char",
            training_images_dir="/tmp/test_images",
            output_dir="/tmp/test_output",
        )
        assert isinstance(config, dict)
        assert "character_name" in config
        assert "training_images_dir" in config
        assert "output_dir" in config
        assert "lora_rank" in config
        assert "learning_rate" in config
        assert "max_train_steps" in config

    def test_lora_config_defaults_reasonable(self):
        """Default LoRA params should be reasonable for SDXL character training."""
        from aicomic.core.lora_config import build_lora_training_config

        config = build_lora_training_config(
            character_name="test",
            training_images_dir="/tmp/imgs",
            output_dir="/tmp/out",
        )
        assert 4 <= config["lora_rank"] <= 128
        assert 1e-6 <= config["learning_rate"] <= 1e-3
        assert 100 <= config["max_train_steps"] <= 10000


class TestDockerDeployment:
    """P2-10: Docker one-click deployment."""

    def test_dockerfile_exists(self):
        """Dockerfile should exist at project root."""
        project_root = Path(__file__).resolve().parent.parent
        assert (project_root / "Dockerfile").exists()

    def test_docker_compose_exists(self):
        """docker-compose.yml should exist at project root."""
        project_root = Path(__file__).resolve().parent.parent
        assert (project_root / "docker-compose.yml").exists()

    def test_dockerfile_uses_python(self):
        """Dockerfile should be Python-based."""
        project_root = Path(__file__).resolve().parent.parent
        content = (project_root / "Dockerfile").read_text()
        assert "python" in content.lower()

    def test_compose_has_aicomic_service(self):
        """docker-compose.yml should define an aicomic service."""
        project_root = Path(__file__).resolve().parent.parent
        content = (project_root / "docker-compose.yml").read_text()
        assert "aicomic" in content or "aicom" in content.lower() or "app" in content.lower()

    def test_dockerignore_exists(self):
        """.dockerignore should exist to keep image lean."""
        project_root = Path(__file__).resolve().parent.parent
        assert (project_root / ".dockerignore").exists()


class TestNovelToComicPipeline:
    """P3-11: Novel → Comic full pipeline."""

    def test_novel_pipeline_importable(self):
        """novel_pipeline module should be importable."""
        from aicomic.core.novel_pipeline import import_novel, run_full_pipeline

        assert callable(import_novel)
        assert callable(run_full_pipeline)

    def test_novel_splitter_importable(self):
        """novel_splitter module should be importable."""
        from aicomic.core.novel_splitter import split_novel_to_episodes

        assert callable(split_novel_to_episodes)

    def test_import_novel_text(self):
        """import_novel should accept raw text and return a dict."""
        from aicomic.core.novel_pipeline import import_novel

        result = import_novel(text="第一章 醒来\n他睁开眼睛，发现自己在一个陌生的房间里。")
        assert isinstance(result, dict)
        assert "episodes" in result or "episode_count" in result

    def test_split_novel_to_episodes(self):
        """split_novel_to_episodes should split text into episode chunks."""
        from aicomic.core.novel_splitter import split_novel_to_episodes

        text = "第一章 开端\n" + "内容内容内容。" * 50 + "\n第二章 发展\n" + "更多内容。" * 50
        episodes = split_novel_to_episodes(text, target_shots_per_ep=3)
        assert isinstance(episodes, list)
        assert len(episodes) >= 1

    def test_generate_episode_plan(self):
        """generate_episode_plan should produce a production plan."""
        from aicomic.core.novel_pipeline import generate_episode_plan

        blueprint = {
            "characters": [{"name": "主角", "description": "年轻人"}],
            "setting": "现代都市",
            "premise": "一个普通人的不平凡一天",
        }
        plan = generate_episode_plan(blueprint, shots_per_episode=5)
        assert isinstance(plan, dict)

    def test_build_season_production_plan(self):
        """build_season_production_plan should produce a season plan."""
        from aicomic.core.novel_pipeline import build_season_production_plan

        episodes = [
            {"episode_code": "EP001", "title": "第一集"},
            {"episode_code": "EP002", "title": "第二集"},
        ]
        plan = build_season_production_plan(episodes)
        assert isinstance(plan, dict)

    def test_count_novel_stats(self):
        """count_novel_stats should return word/char counts."""
        from aicomic.core.novel_pipeline import count_novel_stats

        stats = count_novel_stats("这是一段测试文本。")
        assert isinstance(stats, dict)
        assert "char_count" in stats or "chars" in stats


class TestElectronDesktopScaffold:
    """P3-12: Electron desktop app scaffold."""

    def test_electron_package_json_exists(self):
        """package.json for Electron should exist in desktop/ directory."""
        project_root = Path(__file__).resolve().parent.parent
        pkg_path = project_root / "desktop" / "package.json"
        assert pkg_path.exists(), f"Expected {pkg_path}"

    def test_electron_package_json_valid(self):
        """package.json should be valid JSON with Electron config."""
        project_root = Path(__file__).resolve().parent.parent
        pkg_path = project_root / "desktop" / "package.json"
        data = json.loads(pkg_path.read_text())
        assert "name" in data
        assert "main" in data
        assert "electron" in str(data.get("devDependencies", {})).lower() or \
               "electron" in str(data.get("dependencies", {})).lower()

    def test_electron_main_script_exists(self):
        """Electron main process script should exist."""
        project_root = Path(__file__).resolve().parent.parent
        main_path = project_root / "desktop" / "main.js"
        assert main_path.exists(), f"Expected {main_path}"
