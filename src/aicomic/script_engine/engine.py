"""AI 编剧引擎 — 抽象接口与数据模型。

定义 Screenplay / Scene 数据模型和 IScreenplayEngine 抽象接口。
复用 Provider 层设计模式（validate_config → execute → metadata）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


# ── Data Models ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScreenplayInput:
    """AI 编剧引擎的输入参数。"""

    genre: str  # 题材，如"悬疑推理"
    style: str  # 视觉风格，如"Liquid Glass"
    logline: str  # 一句话梗概
    character_hints: str = ""  # 可选角色提示
    world_hints: str = ""  # 可选世界观
    extra_instructions: str = ""  # 额外创作指令


@dataclass
class Scene:
    """单个分镜/镜头数据模型。

    字段与现有 episode_manifest.json → shots[] 完全兼容。
    """

    shot_id: str  # S01, S02...
    duration: int  # 秒，通常 4-6
    scene: str  # 场景描述
    characters: list[str]  # 角色列表
    visual: str  # 视觉描述（含风格提示词前缀）
    action: str  # 本镜动作
    dialogue: str  # 对白（含角色名标注）
    emotion: str  # 情绪基调
    camera: str  # 运镜方式
    narration: str  # 旁白文案
    ai_video: bool = True  # 是否需要 AI 视频生成
    priority: str = "medium"  # high / medium / low


@dataclass
class Screenplay:
    """标准化剧本数据模型。

    generate_screenplay() 的完整输出，包含剧集元数据和剧情结构。
    """

    title: str  # 剧集标题
    genre: str  # 题材类型
    style: str  # 视觉风格
    logline: str  # 一句话梗概
    publish_title: str = ""  # 发布标题
    cover_text: str = ""  # 封面文案
    creator_goal: str = ""  # 创作目标
    ending_hook: str = ""  # 结尾钩子
    theme: str = ""  # 主题思想
    tone: str = ""  # 叙事基调
    target_audience: str = ""  # 目标受众
    character_descriptions: list[dict[str, Any]] = field(default_factory=list)
    plot_summary: str = ""  # 三幕式剧情概要
    scenes_preview: list[str] = field(default_factory=list)  # 场景概要列表


# ── Abstract Interface ─────────────────────────────────────────────────────


class IScreenplayEngine(ABC):
    """AI 编剧引擎抽象接口——与 Provider 层设计模式一致。"""

    engine_name: ClassVar[str]
    display_name: ClassVar[str]

    @abstractmethod
    def validate_config(self) -> dict[str, Any]:
        """验证配置就绪（API key、endpoint 可达性等）。

        返回:
            {"ready": bool, "errors": list[str], "warnings": list[str]}
        """
        ...

    @abstractmethod
    def generate_screenplay(
        self,
        genre: str,
        style: str,
        logline: str,
        prompt_template: str | None = None,
        **kwargs: Any,
    ) -> Screenplay:
        """生成剧本：题材 + 风格 + 梗概 → 结构化 Screenplay。

        Args:
            genre: 题材类型
            style: 视觉风格
            logline: 一句话梗概
            prompt_template: 可选自定义 prompt 模板
            **kwargs: 扩展参数（character_hints, world_hints, extra_instructions）

        Returns:
            Screenplay 完整剧本
        """
        ...

    @abstractmethod
    def expand_to_shotlist(
        self,
        screenplay: Screenplay,
        num_shots: int = 6,
    ) -> list[Scene]:
        """将剧本展开为完整分镜清单。

        Args:
            screenplay: 已生成的剧本
            num_shots: 目标分镜数

        Returns:
            list[Scene] 分镜列表（与现有 manifest shots[] 兼容）
        """
        ...

    @abstractmethod
    def get_engine_info(self) -> dict[str, Any]:
        """返回引擎元数据。"""
        ...

    def is_ready(self) -> bool:
        """Quick readiness check."""
        return bool(self.validate_config().get("ready", False))
