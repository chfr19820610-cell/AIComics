"""管线清单（Pipeline Manifest）声明化加载器 — ACOM-0.6.0 P0-1.

把 AIComics 硬编码在 Python 里的 8 步流水线，升级为 config/pipelines/*.yaml
声明式管线清单。引擎读 YAML 驱动阶段流转，改管线=改 YAML，不动代码。

合规：独立 Apache-2.0 自建，借鉴业界通用"声明式管线"架构模式（非外部代码）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from aicomic.core.config import ProjectPaths

# 与旧代码兼容的默认管线（无清单文件时的兜底）。
# 注意：清单文件存在时，此常量仅为纯文本默认，不参与实际流转。
LEGACY_DEFAULT_PIPELINE_STEPS = [
    "project_setup",
    "story_bible",
    "episode_outline",
    "shot_breakdown",
    "asset_generation",
    "tts_subtitle",
    "preview_render",
    "publish_pack",
]

# 需要人工审核门禁的阶段 id（硬门禁，awaiting_human 时不可推进）。
HUMAN_APPROVAL_STAGES: frozenset[str] = frozenset({"shot_breakdown", "asset_generation"})

# 阶段状态（checkpoint 用）
CHECKPOINT_IN_PROGRESS = "in_progress"
CHECKPOINT_AWAITING_HUMAN = "awaiting_human"
CHECKPOINT_COMPLETED = "completed"
CHECKPOINT_FAILED = "failed"
CHECKPOINT_STATUSES = frozenset(
    {CHECKPOINT_IN_PROGRESS, CHECKPOINT_AWAITING_HUMAN, CHECKPOINT_COMPLETED, CHECKPOINT_FAILED}
)

# 未完成即不可推进的"完成态"（用于断点续跑判定）
CHECKPOINT_TERMINAL_STATUSES = frozenset({CHECKPOINT_COMPLETED, CHECKPOINT_FAILED})


class PipelineManifestError(ValueError):
    """管线清单格式/一致性错误。"""


class PipelineStage:
    """单个管线阶段，承载契约与审核门配置。"""

    __slots__ = (
        "id",
        "produces",
        "review_focus",
        "success_criteria",
        "human_approval_default",
        "next",
    )

    def __init__(
        self,
        stage_id: str,
        produces: list[str],
        review_focus: list[str],
        success_criteria: str,
        human_approval_default: bool,
        next_stages: list[str],
    ) -> None:
        self.id = stage_id
        self.produces = list(produces)
        self.review_focus = list(review_focus)
        self.success_criteria = success_criteria
        self.human_approval_default = bool(human_approval_default)
        self.next = list(next_stages)

    @property
    def requires_human_approval(self) -> bool:
        return self.human_approval_default or self.id in HUMAN_APPROVAL_STAGES

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "produces": list(self.produces),
            "review_focus": list(self.review_focus),
            "success_criteria": self.success_criteria,
            "human_approval_default": self.human_approval_default,
            "next": list(self.next),
        }


def _validate_stage(raw: dict[str, object], index: int) -> PipelineStage:
    stage_id = raw.get("id")
    if not isinstance(stage_id, str) or not stage_id.strip():
        raise PipelineManifestError(f"stages[{index}].id 必须是非空字符串")
    stage_id = stage_id.strip()

    produces = _as_str_list(raw.get("produces"), f"stages[{index}].produces")
    review_focus = _as_str_list(raw.get("review_focus"), f"stages[{index}].review_focus")
    success_criteria = raw.get("success_criteria", "")
    if not isinstance(success_criteria, str) or not success_criteria.strip():
        raise PipelineManifestError(f"stages[{index}]({stage_id}).success_criteria 必须是非空字符串")
    human_approval_default = raw.get("human_approval_default", False)
    if not isinstance(human_approval_default, bool):
        raise PipelineManifestError(f"stages[{index}]({stage_id}).human_approval_default 必须是布尔")

    # 顺序由 stages 数组顺序决定；next 显式声明供一致性校验（可选）。
    next_stages = _as_str_list(raw.get("next", []), f"stages[{index}].next")
    return PipelineStage(
        stage_id=stage_id,
        produces=produces,
        review_focus=review_focus,
        success_criteria=success_criteria,
        human_approval_default=human_approval_default,
        next_stages=next_stages,
    )


def _as_str_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PipelineManifestError(f"{field} 必须是字符串列表")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PipelineManifestError(f"{field} 的元素必须是字符串")
        result.append(item.strip())
    return result


class PipelineManifest:
    """已解析的管线清单。"""

    def __init__(self, pipeline_id: str, version: str, description: str, stages: list[PipelineStage]) -> None:
        self.pipeline_id = pipeline_id
        self.version = version
        self.description = description
        self.stages = stages
        self._by_id: dict[str, PipelineStage] = {stage.id: stage for stage in stages}

    @property
    def step_ids(self) -> list[str]:
        return [stage.id for stage in self.stages]

    def get_stage(self, stage_id: str) -> PipelineStage | None:
        return self._by_id.get(stage_id)

    def stage(self, stage_id: str) -> PipelineStage:
        stage = self._by_id.get(stage_id)
        if stage is None:
            raise PipelineManifestError(f"未知管线阶段: {stage_id}")
        return stage

    def requires_human_approval(self, stage_id: str) -> bool:
        return self.stage(stage_id).requires_human_approval

    def index_of(self, stage_id: str) -> int:
        try:
            return self.step_ids.index(stage_id)
        except ValueError as exc:
            raise PipelineManifestError(f"未知管线阶段: {stage_id}") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "pipeline_id": self.pipeline_id,
            "version": self.version,
            "description": self.description,
            "stages": [stage.to_dict() for stage in self.stages],
        }


def _load_from_path(path: Path) -> PipelineManifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # 统一为 PipelineManifestError，保证清单损坏也能走 legacy 兜底（不崩 ParserError）。
        raise PipelineManifestError(f"{path} YAML 解析失败: {exc}") from exc
    if not isinstance(raw, dict):
        raise PipelineManifestError(f"{path} 顶层必须是映射（mapping）")
    pipeline_id = str(raw.get("pipeline_id") or "pipeline")
    version = str(raw.get("version") or "0.0.0")
    description = str(raw.get("description") or "")
    raw_stages = raw.get("stages")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise PipelineManifestError(f"{path} 缺少非空 stages 列表")
    stages = [_validate_stage(stage, index) for index, stage in enumerate(raw_stages)]

    ids = [stage.id for stage in stages]
    if len(ids) != len(set(ids)):
        raise PipelineManifestError(f"{path} stages 存在重复 id")

    # next_order 一致性校验（如声明了）
    raw_next_order = raw.get("next_order")
    if raw_next_order is not None:
        next_order = _as_str_list(raw_next_order, "next_order")
        if next_order != ids:
            raise PipelineManifestError(
                f"{path} next_order 与 stages 顺序不一致: next_order={next_order}, stages={ids}"
            )
    return PipelineManifest(pipeline_id, version, description, stages)


def load_pipeline_manifest(path: Path | None = None) -> PipelineManifest:
    """加载管线清单；缺失时退回 LEGACY_DEFAULT_PIPELINE_STEPS 构造默认清单。"""
    manifest_path = path or ProjectPaths.config_dir() / "pipelines" / "manhua_episode.yaml"
    if manifest_path.is_file():
        return _load_from_path(manifest_path)
    stages = [
        PipelineStage(
            stage_id=step,
            produces=[],
            review_focus=[],
            success_criteria=f"{step} 完成",
            human_approval_default=step in HUMAN_APPROVAL_STAGES,
            next_stages=[],
        )
        for step in LEGACY_DEFAULT_PIPELINE_STEPS
    ]
    return PipelineManifest("manhua_episode", "legacy", "legacy fallback", stages)


@lru_cache(maxsize=8)
def get_pipeline_manifest() -> PipelineManifest:
    """带缓存的清单加载。"""
    return load_pipeline_manifest()


def reset_pipeline_cache() -> None:
    get_pipeline_manifest.cache_clear()
