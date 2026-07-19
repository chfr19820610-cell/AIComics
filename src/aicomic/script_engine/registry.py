"""ScreenplayEngineRegistry — AI 编剧引擎注册中心。

与 provider_registry.py 的 ProviderRegistry 设计模式一致。
支持注册、获取、默认引擎、重置等生命周期管理。
"""

from __future__ import annotations

from typing import Any, ClassVar

from aicomic.script_engine.engine import IScreenplayEngine
from aicomic.script_engine.llm_engine import LLMScreenplayEngine


class ScreenplayEngineRegistry:
    """中央编剧引擎注册表。

    引擎按 engine_name 注册。提供工厂方法和生命周期管理。
    """

    def __init__(self) -> None:
        self._engines: dict[str, type[IScreenplayEngine]] = {}
        self._instances: dict[str, IScreenplayEngine] = {}

    def register(self, cls: type[IScreenplayEngine]) -> None:
        """注册一个编剧引擎类。"""
        name: str = getattr(cls, "engine_name", "")
        if not name:
            raise ValueError(f"Engine {cls.__name__} has no engine_name")
        self._engines[name] = cls

    def get(self, name: str, **kwargs: Any) -> IScreenplayEngine | None:
        """按 engine_name 获取引擎实例（缓存单例）。"""
        if name in self._instances:
            return self._instances[name]

        cls = self._engines.get(name)
        if cls is None:
            return None

        instance = cls(**kwargs)
        self._instances[name] = instance
        return instance

    def get_or_fail(self, name: str, **kwargs: Any) -> IScreenplayEngine:
        """类似 get()，但没找到时抛出 KeyError。"""
        engine = self.get(name, **kwargs)
        if engine is None:
            raise KeyError(f"No engine registered for: {name}")
        return engine

    def get_default(self, **kwargs: Any) -> IScreenplayEngine:
        """获取默认引擎（LLMScreenplayEngine）。"""
        return self.get_or_fail("jieyou_gpt55", **kwargs)

    def list_registered(self) -> list[str]:
        """返回所有已注册引擎名称（排序后）。"""
        return sorted(self._engines.keys())

    def unregister(self, name: str) -> None:
        """移除已注册的引擎。"""
        self._engines.pop(name, None)
        self._instances.pop(name, None)


# ── Default registry singleton ─────────────────────────────────────────────

_DEFAULT_REGISTRY: ScreenplayEngineRegistry | None = None


def _create_default_registry() -> ScreenplayEngineRegistry:
    """创建并填充默认注册表。"""
    registry = ScreenplayEngineRegistry()
    registry.register(LLMScreenplayEngine)
    return registry


def get_script_engine(name: str | None = None, **kwargs: Any) -> IScreenplayEngine:
    """获取编剧引擎实例。

    不指定 name 时返回默认引擎（LLMScreenplayEngine / JieYou GPT-5.5）。

    Args:
        name: 引擎名称（如 "jieyou_gpt55"）
        **kwargs: 传递给引擎构造函数的参数

    Returns:
        IScreenplayEngine 实例
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _create_default_registry()

    if name is not None:
        return _DEFAULT_REGISTRY.get_or_fail(name, **kwargs)
    return _DEFAULT_REGISTRY.get_default(**kwargs)


def reset_script_engine_registry() -> None:
    """重置全局注册表（用于测试）。"""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
