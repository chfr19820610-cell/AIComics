"""管线清单声明化测试 — ACOM-0.6.0 P0-1."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aicomic.core.config import ProjectPaths
from aicomic.core.creator_bootstrap import (
    DEFAULT_PIPELINE_STEPS,
    build_creator_profile,
    resolve_pipeline_steps,
)
from aicomic.core.pipeline_manifest import (
    HUMAN_APPROVAL_STAGES,
    PipelineManifestError,
    _load_from_path,
    load_pipeline_manifest,
)


MANIFEST_SAMPLE = """
pipeline_id: manhua_episode
version: "1.0.0"
description: "test"
stages:
  - id: project_setup
    produces: ["a"]
    review_focus: ["x"]
    success_criteria: "done"
    human_approval_default: false
  - id: shot_breakdown
    produces: ["b"]
    review_focus: ["y"]
    success_criteria: "done"
    human_approval_default: true
  - id: asset_generation
    produces: ["c"]
    review_focus: ["z"]
    success_criteria: "done"
    human_approval_default: true
next_order:
  - project_setup
  - shot_breakdown
  - asset_generation
"""


def _write_manifest(tmp: Path, content: str) -> Path:
    path = tmp / "pipelines" / "manhua_episode.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadPipelineManifest:
    def test_loads_real_manifest(self) -> None:
        m = load_pipeline_manifest()
        assert m.pipeline_id == "manhua_episode"
        assert len(m.step_ids) == 8
        assert m.step_ids[0] == "project_setup"
        assert m.step_ids[-1] == "publish_pack"
        assert m.requires_human_approval("shot_breakdown")
        assert m.requires_human_approval("asset_generation")
        assert not m.requires_human_approval("project_setup")

    def test_manifest_file_under_config_pipelines(self) -> None:
        assert (ProjectPaths.config_dir() / "pipelines" / "manhua_episode.yaml").is_file()

    def test_parses_sample(self, tmp_path: Path) -> None:
        path = _write_manifest(tmp_path, MANIFEST_SAMPLE)
        m = _load_from_path(path)
        assert m.step_ids == ["project_setup", "shot_breakdown", "asset_generation"]
        shot = m.get_stage("shot_breakdown")
        assert shot is not None
        assert shot.requires_human_approval

    def test_duplicate_id_rejected(self, tmp_path: Path) -> None:
        dup = MANIFEST_SAMPLE.replace(
            "id: shot_breakdown", "id: project_setup", 1
        )
        path = _write_manifest(tmp_path, dup)
        with pytest.raises(PipelineManifestError):
            _load_from_path(path)

    def test_next_order_mismatch_rejected(self, tmp_path: Path) -> None:
        bad = MANIFEST_SAMPLE.replace(
            "- shot_breakdown\n  - asset_generation", "- asset_generation\n  - shot_breakdown", 1
        )
        path = _write_manifest(tmp_path, bad)
        with pytest.raises(PipelineManifestError):
            _load_from_path(path)

    def test_empty_stages_rejected(self, tmp_path: Path) -> None:
        path = _write_manifest(tmp_path, "pipeline_id: p\nstages: []\n")
        with pytest.raises(PipelineManifestError):
            _load_from_path(path)

    def test_corrupt_yaml_raises_manifest_error(self, tmp_path: Path) -> None:
        """M2 回归：YAML 语法损坏 → 抛 PipelineManifestError（统一异常，走 legacy 兜底），而非裸 ParserError。"""
        path = _write_manifest(tmp_path, "stages: [broken")
        with pytest.raises(PipelineManifestError):
            _load_from_path(path)


class TestCreatorBootstrapIntegration:
    def test_pipeline_steps_come_from_manifest(self) -> None:
        assert resolve_pipeline_steps() == DEFAULT_PIPELINE_STEPS
        assert resolve_pipeline_steps() == load_pipeline_manifest().step_ids

    def test_profile_pipeline_steps_match_manifest(self) -> None:
        profile = build_creator_profile(
            project_name="P", genre="g", style="s", logline="l",
            protagonist_name="小明", target_audience="18-35",
            tone="t", season_hook="h", episode_target_count=6,
        )
        assert profile["pipeline_steps"] == load_pipeline_manifest().step_ids


class TestHumanApprovalStages:
    def test_only_two_stages_are_gates(self) -> None:
        assert HUMAN_APPROVAL_STAGES == {"shot_breakdown", "asset_generation"}
