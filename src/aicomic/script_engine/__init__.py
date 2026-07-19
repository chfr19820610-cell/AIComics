"""AI 编剧引擎 — 自动生成剧本与分镜 manifest。

基于 JieYou GPT-5.5 (OpenAI 兼容 API) 的 AI 编剧引擎。
实现从「题材+风格+梗概」到完整 episode_manifest.json 的全自动管线。
"""

from aicomic.script_engine.engine import (
    IScreenplayEngine,
    Scene,
    Screenplay,
    ScreenplayInput,
)
from aicomic.script_engine.llm_engine import LLMScreenplayEngine
from aicomic.script_engine.manifest_writer import write_screenplay_to_episode_manifest
from aicomic.script_engine.registry import (
    ScreenplayEngineRegistry,
    get_script_engine,
    reset_script_engine_registry,
)

__all__ = [
    "IScreenplayEngine",
    "Scene",
    "Screenplay",
    "ScreenplayInput",
    "LLMScreenplayEngine",
    "ScreenplayEngineRegistry",
    "get_script_engine",
    "reset_script_engine_registry",
    "write_screenplay_to_episode_manifest",
]
