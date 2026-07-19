"""LLMScreenplayEngine — JieYou GPT-5.5 实现的 AI 编剧引擎。

通过 OpenAI 兼容 API 调用 JieYou GPT-5.5 实现剧本生成和分镜展开。
使用 httpx 作为 HTTP 客户端。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, ClassVar

import httpx

from aicomic.script_engine.engine import IScreenplayEngine, Scene, Screenplay

# ── Default configuration ──────────────────────────────────────────────────

DEFAULT_BASE_URL = "https://api.jieyouai.it.com/v1"
DEFAULT_MODEL = "gpt-5.5-turbo"
DEFAULT_TEMPERATURE = 0.8
DEFAULT_MAX_TOKENS = 8192
FALLBACK_MODEL = "gpt-4o"
FALLBACK_TEMPERATURE = 0.3
MAX_RETRIES = 2

# ── Prompt templates ───────────────────────────────────────────────────────

SCREENPLAY_SYSTEM_PROMPT = """你是一位专业的漫画/短剧编剧，擅长{genre}题材的创作。

<任务>
根据以下信息创作一集短剧剧本（{num_shots_est}个镜头，约30秒）。输出必须是与现有 episode_manifest 兼容的 JSON。
</任务>

<输入>
- 题材：{genre}
- 视觉风格：{style}
- 梗概：{logline}
{extra_hints}
</输入>

<写作要求>
1. 必须有清晰的开端→发展→反转（或高潮）→结尾钩子
2. 视觉描述以"{style}风格。"开头，不少于80字
3. 对白符合角色性格，不冗长
4. narration 为旁白/内心独白，不能与 dialogue 重复
5. ending_hook 要制造"下一集还想看"的悬念
6. 镜头要多样化：中景、特写、广角、过肩、俯拍等交替使用
7. ai_video=true 的镜头需要有足够的动态元素
</写作要求>

严格按照以下 JSON Schema 输出，不要添加额外字段：
{{
  "title": "短剧标题（中文，有网感）",
  "publish_title": "发布标题（更具吸引力）",
  "cover_text": "封面文案",
  "logline": "一句话梗概",
  "creator_goal": "创作目标描述",
  "ending_hook": "结尾钩子",
  "theme": "主题思想",
  "tone": "叙事基调",
  "target_audience": "目标受众",
  "character_descriptions": [
    {{"name": "角色名", "age": "年龄", "archetype": "角色原型", "traits": "性格特征"}}
  ],
  "plot_summary": "三幕式剧情概要",
  "scenes_preview": ["场景1概要", "场景2概要"]
}}"""

SHOTLIST_SYSTEM_PROMPT = """根据以下剧本，生成分镜清单。要求每个分镜有完整的 scene/visual/action/dialogue/emotion/camera/narration。

<剧本>
题材：{genre}
视觉风格：{style}
剧本标题：{title}
剧情梗概：{logline}
创作者目标：{creator_goal}
结尾钩子：{ending_hook}
角色描述：{character_descriptions}
剧情概要：{plot_summary}
</剧本>

请生成 {num_shots} 个分镜，每个分镜 4-6 秒。

<写作要求>
1. visual 字段以"{style}风格。"开头，包含环境/光线/色彩/角色造型/构图，不少于80字
2. dialogue 标注角色名："{{角色名}}：{{对白}}"
3. narration（旁白）使用第一人称或第三人称，与剧情情绪一致，不能与 dialogue 重复
4. 6 镜中至少使用 3 种不同运镜方式
5. camera 运镜使用中文术语：推/拉/摇/移/跟/升/降/俯拍/仰拍/特写/过肩/广角/航拍
6. ai_video=true 的镜头需要有动作/物体运动/镜头运动等动态元素
7. ending_hook 最后一句要制造悬念
</写作要求>

严格按照以下 JSON Schema 输出：
{{
  "shots": [
    {{
      "shot_id": "S01",
      "duration": 4,
      "scene": "场景描述",
      "characters": ["角色1", "角色2"],
      "visual": "{style}风格。详细视觉描述（含环境/光线/色彩/角色造型/构图）",
      "action": "本镜动作",
      "dialogue": "角色名：对白",
      "emotion": "情绪基调",
      "camera": "运镜方式（使用中文术语）",
      "narration": "旁白文案（不可与 dialogue 重复）",
      "ai_video": true,
      "priority": "high"
    }}
  ]
}}"""


# ── LLM Engine ─────────────────────────────────────────────────────────────


class LLMScreenplayEngine(IScreenplayEngine):
    """基于 JieYou GPT-5.5 (OpenAI 兼容 API) 的 AI 编剧引擎。

    从 OPENAI_API_KEY 环境变量读取 API key。
    支持自定义 base_url 和 model。
    """

    engine_name: ClassVar[str] = "jieyou_gpt55"
    display_name: ClassVar[str] = "JieYou GPT-5.5 编剧引擎"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = http_client or httpx.Client(timeout=httpx.Timeout(120.0))

    # ── Config validation ─────────────────────────────────────────────────

    def validate_config(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        if not self._api_key:
            errors.append("Missing OPENAI_API_KEY environment variable")

        # Check base URL reachability (lightweight HEAD if needed)
        return {
            "ready": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "api_key_configured": bool(self._api_key),
            "base_url": self._base_url,
            "model": self._model,
        }

    # ── Screenplay generation ─────────────────────────────────────────────

    def generate_screenplay(
        self,
        genre: str,
        style: str,
        logline: str,
        prompt_template: str | None = None,
        **kwargs: Any,
    ) -> Screenplay:
        extra_hints = ""
        if kwargs.get("character_hints"):
            extra_hints += f"\n- 角色提示：{kwargs['character_hints']}"
        if kwargs.get("world_hints"):
            extra_hints += f"\n- 世界观：{kwargs['world_hints']}"
        if kwargs.get("extra_instructions"):
            extra_hints += f"\n- 额外指令：{kwargs['extra_instructions']}"

        prompt = (prompt_template or SCREENPLAY_SYSTEM_PROMPT).format(
            genre=genre,
            style=style,
            logline=logline,
            num_shots_est="6-8",
            extra_hints=extra_hints,
        )

        response_data = self._call_llm(prompt)
        return self._parse_to_screenplay(response_data, genre, style, logline)

    # ── Shot list expansion ───────────────────────────────────────────────

    def expand_to_shotlist(
        self,
        screenplay: Screenplay,
        num_shots: int = 6,
    ) -> list[Scene]:
        char_desc_str = json.dumps(
            screenplay.character_descriptions, ensure_ascii=False, indent=2
        )

        prompt = SHOTLIST_SYSTEM_PROMPT.format(
            genre=screenplay.genre,
            style=screenplay.style,
            title=screenplay.title,
            logline=screenplay.logline,
            creator_goal=screenplay.creator_goal,
            ending_hook=screenplay.ending_hook,
            character_descriptions=char_desc_str,
            plot_summary=screenplay.plot_summary,
            num_shots=num_shots,
        )

        response_data = self._call_llm(prompt)
        return self._parse_to_scenes(response_data, num_shots)

    # ── Metadata ──────────────────────────────────────────────────────────

    def get_engine_info(self) -> dict[str, Any]:
        return {
            "engine_name": self.engine_name,
            "display_name": self.display_name,
            "base_url": self._base_url,
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "api_configured": bool(self._api_key),
        }

    # ── Internal: LLM call ────────────────────────────────────────────────

    def _call_llm(self, prompt: str, fallback: bool = False) -> dict[str, Any]:
        """调用 LLM API，支持重试和退温 fallback。"""
        temperature = FALLBACK_TEMPERATURE if fallback else self._temperature
        model = FALLBACK_MODEL if fallback else self._model

        messages = [
            {
                "role": "system",
                "content": "You are a professional comic/short-drama scriptwriter. Always respond in valid JSON matching the requested schema.",
            },
            {"role": "user", "content": prompt},
        ]

        body = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": self._max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()
                raw = response.json()
                content = raw["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return parsed  # type: ignore[return-value]
            except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError,
                    KeyError, TypeError) as exc:
                if attempt < MAX_RETRIES:
                    # Retry with lower temperature
                    body["temperature"] = FALLBACK_TEMPERATURE
                    body["model"] = FALLBACK_MODEL
                    continue
                raise RuntimeError(
                    f"LLM call failed after {MAX_RETRIES + 1} attempts: {exc}"
                ) from exc

        raise RuntimeError("LLM call failed unexpectedly")

    # ── Internal: Parsing ─────────────────────────────────────────────────

    def _parse_to_screenplay(
        self,
        data: dict[str, Any],
        genre: str,
        style: str,
        logline: str,
    ) -> Screenplay:
        return Screenplay(
            title=str(data.get("title", logline[:30])),
            genre=genre,
            style=style,
            logline=logline,
            publish_title=str(data.get("publish_title", "")),
            cover_text=str(data.get("cover_text", "")),
            creator_goal=str(data.get("creator_goal", "")),
            ending_hook=str(data.get("ending_hook", "")),
            theme=str(data.get("theme", "")),
            tone=str(data.get("tone", "")),
            target_audience=str(data.get("target_audience", "")),
            character_descriptions=list(data.get("character_descriptions", [])),
            plot_summary=str(data.get("plot_summary", "")),
            scenes_preview=list(data.get("scenes_preview", [])),
        )

    def _parse_to_scenes(
        self,
        data: dict[str, Any],
        expected_count: int = 6,
    ) -> list[Scene]:
        raw_shots = data.get("shots", [])
        if not raw_shots and "episode" in data:
            raw_shots = data["episode"].get("shots", [])

        scenes: list[Scene] = []
        for item in raw_shots:
            scene = Scene(
                shot_id=str(item.get("shot_id", f"S{len(scenes) + 1:02d}")),
                duration=int(item.get("duration", 4)),
                scene=str(item.get("scene", "")),
                characters=list(item.get("characters", [])),
                visual=str(item.get("visual", "")),
                action=str(item.get("action", "")),
                dialogue=str(item.get("dialogue", "")),
                emotion=str(item.get("emotion", "")),
                camera=str(item.get("camera", "")),
                narration=str(item.get("narration", "")),
                ai_video=bool(item.get("ai_video", True)),
                priority=str(item.get("priority", "medium")),
            )
            scenes.append(scene)

        return scenes

    def __del__(self) -> None:
        if hasattr(self, "_client") and self._client is not None:
            self._client.close()
