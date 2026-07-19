# AI 编剧引擎设计方案

> 对应路线图 `docs/roadmap.md` — **P0#1: AI 编剧引擎**
> 生成日期：2026-07-19
> 目标：利用 JieYou GPT-5.5 自动生成剧本 + 分镜 manifest

---

## 1. 现状分析

### 1.1 当前管线缺陷

| 环节 | 当前实现 | 问题 |
|------|---------|------|
| 剧本生成 | 手动编写或外部工具 | 无自动化，依赖人工创作 |
| 分镜清单 | 预设 `episode_manifest.json` | Shot-by-shot 数据需逐条手写 |
| LLM 能力 | 仅为图片/TTS 使用 API | 未复用 OpenAI 兼容 API 做文本生成 |
| 故事→分镜 | 硬编码管线 | 无独立编剧引擎模块，无法灵活切换 |

### 1.2 现有基础设施（可直接复用）

```
providers.yaml
├── openai_api.base_url → https://api.jieyouai.it.com/v1   # JieYou API
├── openai_image → gpt-image-1.5                            # 图片模型
├── openai_tts  → gpt-4o-mini-tts                           # TTS 模型
└── (现有但未使用)   ← 可以复用同一个 endpoint 调用 GPT-5.5
```

**关键发现**：`providers.yaml` 中的 `openai_api` 段已配置 JieYou API base URL。当前仅用于 DALL-E 图片和 TTS。JieYou GPT-5.5 是 **OpenAI 兼容 API**，可以直接通过同一个 `OPENAI_API_KEY` 调用文本 completions 端点。

### 1.3 现有 Manifest 格式（输出目标）

管线数据模型（现有）：
```
project_manifest.json       ← 项目元数据 + creator_profile
  └── season_manifest.json  ← 季信息 + 剧集列表
       └── episode_manifest.json  ← 完整分镜清单
            ├── episode.title / genre / style
            ├── episode.creator_goal / ending_hook
            └── shots[]  ← 每镜：scene, characters, visual, action, dialogue, emotion, camera, narration, ai_video
```

**当前 Pipeline 状态机**：`idea → script_ready → shotlist_ready → prompt_ready → jobs_ready → ...`

当前 **script_ready** 和 **shotlist_ready** 状态之间无自动化——这正是 AI 编剧引擎要填补的空白。

### 1.4 现有 Provider 抽象模式

```
IProvider (base.py)
├── validate_config()    → 检查环境/配置就绪
├── build_request()      → 构造请求载荷
├── execute_request()    → 执行并返回结果
└── get_provider_info()  → 元数据

ProviderRegistry (provider_registry.py)
├── register(cls)        → 注册提供者类
├── resolve_for_job()    → 按名称路由
└── resolve_with_fallback() → 云端优先 + 本地回退
```

---

## 2. 架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────┐
│                   用户输入                              │
│  题材 + 风格 + 梗概  (题材=科幻, 风格=赛璐珞, 梗概=...)  │
└──────────┬───────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────┐
│              ScreenplayEngine (抽象接口)                │
│  ├─ ScreenplayEngine.validate_config()               │
│  ├─ ScreenplayEngine.generate_screenplay(input)       │
│  ├─ ScreenplayEngine.generate_shotlist(screenplay)    │
│  └─ ScreenplayEngine.get_provider_info()              │
├──────────────────────────────────────────────────────┤
│                 实现层                                  │
│  ┌─────────────────────────────────────────────┐      │
│  │  LLMScreenplayEngine                         │      │
│  │  - 路由 JieYou GPT-5.5 (OpenAI 兼容 API)     │      │
│  │  - Prompt 模板系统                             │      │
│  │  - 结构化 JSON 输出                             │      │
│  └─────────────────────────────────────────────┘      │
├──────────────────────────────────────────────────────┤
│                 输出层                                  │
│  ┌─────────────────────────────────────────────┐      │
│  │  ScreenplaySchema (剧本结构)                  │      │
│  │  → ShotSchema (分镜清单)                     │      │
│  │  → episode_manifest.json (复用现有格式)       │      │
│  └─────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────┐
│          下游管线（无需变更）                            │
│  job_builder → provider_planner → executor → render  │
└──────────────────────────────────────────────────────┘
```

### 2.2 核心抽象接口

```python
# src/aicomic/script/engine.py

@dataclass(frozen=True, slots=True)
class Screenplay:
    """标准化剧本数据模型"""
    title: str                              # 剧集标题
    genre: str                              # 题材类型
    style: str                              # 视觉风格
    logline: str                            # 一句话梗概
    creator_goal: str                       # 创作目标
    ending_hook: str                        # 结尾钩子
    scenes: list[Scene]                     # 场景列表
    theme: str = ""                         # 主题思想
    tone: str = ""                          # 叙事基调
    target_audience: str = ""

@dataclass(frozen=True, slots=True)
class Scene:
    """场景/分镜数据模型"""
    shot_id: str                            # S01, S02...
    duration: int                           # 秒
    scene: str                              # 场景描述
    characters: list[str]                   # 角色列表
    visual: str                             # 视觉描述（含风格提示）
    action: str                             # 动作描述
    dialogue: str                           # 对白/旁白
    emotion: str                            # 情绪基调
    camera: str                             # 运镜描述
    narration: str                          # 旁白文案
    ai_video: bool                          # 是否需要 AI 视频生成
    priority: str                           # high / medium / low

class IScreenplayEngine(ABC):
    """AI 编剧引擎抽象接口——复用 Provider 层设计模式"""

    engine_name: ClassVar[str]
    display_name: ClassVar[str]

    @abstractmethod
    def validate_config(self) -> dict[str, Any]:
        """验证配置就绪（API key、endpoint 可达性等）"""
        ...

    @abstractmethod
    def generate_screenplay(
        self,
        genre: str,
        style: str,
        logline: str,
        prompt_template: str | None = None,
        **kwargs,
    ) -> Screenplay:
        """生成剧本：题材 + 风格 + 梗概 → 结构化剧本"""
        ...

    @abstractmethod
    def expand_to_shotlist(
        self,
        screenplay: Screenplay,
        num_shots: int = 6,
    ) -> list[Scene]:
        """将剧本展开为完整分镜清单"""
        ...

    @abstractmethod
    def get_engine_info(self) -> dict[str, Any]:
        """返回引擎元数据"""
        ...

    def is_ready(self) -> bool:
        return bool(self.validate_config().get("ready", False))
```

### 2.3 JieYou GPT-5.5 实现

```python
# src/aicomic/script/llm_engine.py

class LLMScreenplayEngine(IScreenplayEngine):
    """基于 JieYou GPT-5.5 的 AI 编剧引擎"""

    engine_name: ClassVar[str] = "jieyou_gpt55"
    display_name: ClassVar[str] = "JieYou GPT-5.5 编剧引擎"

    # ── 从 providers.yaml 读取配置 ──
    # openai_api.base_url → https://api.jieyouai.it.com/v1
    # OPENAI_API_KEY 环境变量 → JieYou API key
    # 模型: gpt-5.5 (JieYou GPT-5.5)

    def validate_config(self) -> dict[str, Any]:
        return self._check_env_vars("OPENAI_API_KEY")

    def generate_screenplay(self, genre, style, logline, **kwargs) -> Screenplay:
        prompt = self._build_screenplay_prompt(genre, style, logline)
        raw = self._call_llm(prompt)
        return self._parse_to_screenplay(raw, genre, style)

    def expand_to_shotlist(self, screenplay, num_shots=6) -> list[Scene]:
        prompt = self._build_shotlist_prompt(screenplay, num_shots)
        raw = self._call_llm(prompt)
        return self._parse_to_scenes(raw)

    def _call_llm(self, prompt: str) -> dict:
        """通过 JieYou API (OpenAI 兼容) 调用 GPT-5.5"""
        # POST {base_url}/v1/chat/completions
        # body: {model: "gpt-5.5", messages: [...], response_format: {type: "json_object"}}
        ...
```

**API 调用细节**：

| 参数 | 值 | 说明 |
|------|-----|------|
| URL | `{openai_api.base_url}/v1/chat/completions` | 复用 JieYou 端点 |
| 模型 | `gpt-5.5` | JieYou GPT-5.5 |
| Auth | `Bearer $OPENAI_API_KEY` | 与图片/TTS 共享 key |
| `response_format` | `{"type": "json_object"}` | 强制结构化 JSON 输出 |
| `temperature` | 0.8 | 剧本创作需要一定创造力 |
| `max_tokens` | 8192 | 足够生成 6-8 镜的完整分镜 |

### 2.4 Prompt 模板系统

#### 2.4.1 剧本生成 Prompt

```
你是一位专业的漫画/短剧编剧。根据以下要求创作一部短剧剧本。

题材（Genre）：{genre}
视觉风格（Style）：{style}
故事梗概（Logline）：{logline}
{可选参数：角色设定、世界观、情绪基调...}

请严格按照以下 JSON Schema 输出，不要添加额外字段：

{
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
    {"name": "角色名", "age": 年龄, "archetype": "角色原型", "traits": "性格特征"}
  ],
  "plot_summary": "三幕式剧情概要",
  "scenes_preview": ["场景1概要", "场景2概要", "..."]
}
```

#### 2.4.2 分镜展开 Prompt

```
根据以下剧本，生成分镜清单。要求每个分镜有完整的 scene/visual/action/dialogue/emotion/camera/narration。

题材：{genre}
视觉风格：{style}
剧本标题：{title}
剧情梗概：{logline}
创作者目标：{creator_goal}
结尾钩子：{ending_hook}
角色描述：{character_descriptions}
剧情概要：{plot_summary}
{可选：上一集的 ending_hook（连载时使用）}

请生成 {num_shots} 个分镜，每个分镜 4-6 秒。

严格按照以下 JSON Schema 输出（与 episode_manifest.json 兼容）：

{
  "episode_code": "{E01}",
  "title": "...",
  "genre": "...",
  "style": "...",
  "publish_title": "...",
  "cover_text": "...",
  "creator_goal": "...",
  "ending_hook": "...",
  "shots": [
    {
      "shot_id": "S01",
      "duration": 4,
      "scene": "场景描述",
      "characters": ["角色1", "角色2"],
      "visual": "详细视觉描述（含风格提示词风格）",
      "action": "本镜动作",
      "dialogue": "对白（含角色名标注）",
      "emotion": "情绪基调",
      "camera": "运镜方式",
      "narration": "旁白文案（第一人称或第三人称，与剧中角色语气一致）",
      "ai_video": true,
      "priority": "high"
    }
  ]
}
```

**视觉描述生成规则**：
1. `visual` 字段必须包含风格前缀（从 `style` 参数派生），如 "Liquid Glass 风格。"、"Hybrid Comic Pop 风格。"
2. 必须包含场景环境、光线、色彩基调
3. 必须包含角色外貌和着装细节
4. 对 AI 视频生成的关键帧提供构图指导

---

## 3. 数据流

### 3.1 端到端流程

```
User Input (题材 + 风格 + 梗概)
    │
    ▼
[ScreenplayEngine.generate_screenplay()]
    │  调用 JieYou GPT-5.5 → 结构化剧本
    │  输出: Screenplay (title, logline, character_descs, plot_summary...)
    ▼
[ScreenplayEngine.expand_to_shotlist()]
    │  调用 JieYou GPT-5.5 → 分镜清单
    │  输出: list[Scene] (shot_id → narration 全字段)
    ▼
[Manifest Writer]
    │  组装 episode_manifest.json (复用现有 write_json 逻辑)
    │  填充: project_manifest → season_manifest → episode_manifest
    ▼
[Pipeline: job_builder → provider_planner → executor → render]
    │  无需变更——manifest 格式完全兼容
    ▼
[Final Output: 漫画/漫剧视频]
```

### 3.2 状态机扩展

当前管道状态增加两个自动化子状态：

```
idea
  ├─ (手动) → script_ready         # 现有流程
  └─ (AI 编剧引擎) → script_ready  # 新：自动剧本生成
       ↓
script_ready
  ├─ (手动) → shotlist_ready        # 现有流程
  └─ (AI 编剧引擎) → shotlist_ready # 新：自动分镜展开
       ↓
shotlist_ready → prompt_ready → jobs_ready → ...
```

**新增自动步骤注册**（在 `project_manifest.creator_profile.pipeline_steps` 中）：

```yaml
pipeline_steps:
  - project_setup
  - story_bible              # 新增：AI 编剧 → 剧本
  - episode_outline          # 新增：AI 编剧 → 分镜
  - shot_breakdown           # 现有：保持不动
  - asset_generation
  - tts_subtitle
  - preview_render
  - publish_pack
```

### 3.3 多题材支持策略

不同题材需要不同的 Prompt 风格和结构参数：

| 题材 | 分镜数 | 节奏 | Prompt 特点 |
|------|--------|------|-------------|
| 悬疑推理 | 6-8 | 慢→快，推进反转 | 强调伏笔、误导、信息差 |
| 赛博朋克动作 | 6 | 快节奏，动作密度高 | 强调义体描写、霓虹光影、打斗动作 |
| 校园温情 | 6 | 舒缓情绪推进 | 强调细节、微表情、日常感 |
| 古风奇幻 | 6 | 诗意叙事 | 强调水墨/工笔视觉、文言对白感 |
| 科幻太空 | 6-8 | 冷峻悬疑 | 强调硬科幻细节、视效描述、谜团递进 |
| 喜剧 | 5-6 | 密集笑点 | 强调反转、吐槽、夸张表情 |

**实现方式**：每个题材对应一个 Prompt 模板文件，存放在 `src/aicomic/script/prompts/` 目录，运行时按 `genre` 参数加载。

---

## 4. 文件结构

### 4.1 新增文件

```python
src/aicomic/script/
├── __init__.py                 # 包定义
├── engine.py                   # IScreenplayEngine 抽象接口 + 数据模型
├── llm_engine.py               # LLMScreenplayEngine (JieYou GPT-5.5 实现)
├── manifest_writer.py          # 将 Screenplay/Scene → 写入 manifest JSON
├── registry.py                 # ScreenplayEngineRegistry
├── prompts/
│   ├── __init__.py
│   ├── screenplay.j2           # 剧本生成 Jinja2 模板
│   ├── shotlist.j2             # 分镜展开 Jinja2 模板
│   ├── genre_config.yaml       # 各题材参数配置
│   └── examples/               # Few-shot 示例
│       ├── suspense_screenplay.json
│       ├── cyberpunk_shotlist.json
│       └── ...
└── tests/
    ├── test_engine.py
    ├── test_llm_engine.py
    └── test_manifest_writer.py
```

### 4.2 次要修改

```python
src/aicomic/providers/provider_registry.py
    # 在 _create_default_registry() 中注册剧本引擎
    #（或通过独立的 registry.ScreenplayEngineRegistry）

config/providers.yaml
    # 可选：新增 screenplay provider 配置段（如果需要独立模型）
    # screenplay:
    #   default: jieyou_gpt55
    #   available:
    #     - jieyou_gpt55
    #   jieyou_gpt55:
    #     model: gpt-5.5
    #     temperature: 0.8
    #     max_tokens: 8192
```

### 4.3 设计文档

```python
docs/ai_script_engine_design.md  ← 当前文档
```

---

## 5. 与现有系统的集成点

### 5.1 Provider 抽象层复用

| 现有组件 | 复用方式 |
|----------|---------|
| `providers.yaml` → `openai_api.base_url` | 直接复用 JieYou API 端点和 key |
| `openai_provider.py` → OpenAI 兼容 API 调用模式 | 参考 execute_request 实现 LLM call |
| `provider_registry.py` → registry 模式 | 新建 ScreenplayEngineRegistry，复用相同设计 |
| `manifest.py` → load_json / write_json | 直接复用到 manifest_writer |

### 5.2 无需改动的组件

- `job_builder.py` — 只需标准 episode_manifest.json，格式不改
- `provider_planner.py` — 分发逻辑不变
- `executor.py` — 执行逻辑不变
- `render/*` — 渲染管线不变
- `models.py` — 数据模型兼容

### 5.3 输出兼容性

AI 编剧引擎的输出 `episode_manifest.json` 与现有格式**字段级兼容**：

```json
{
  "project_id": "auto_gen_project",
  "season": 1,
  "episodes": [
    {
      "episode_code": "E01",
      "title": "镜中倒影",          ← Screenplay.title
      "genre": "悬疑推理",          ← 输入参数
      "style": "Liquid Glass",      ← 输入参数
      "status": "shotlist_ready",   ← 管线自动推进
      "publish_title": "...",       ← Screenplay.publish_title
      "cover_text": "...",          ← Screenplay.cover_text
      "shot_count": 6,
      "creator_goal": "...",        ← Screenplay.creator_goal
      "ending_hook": "...",         ← Screenplay.ending_hook
      "shots": [                    ← expand_to_shotlist() 输出
        { /* 全兼容现有字段 */ }
      ]
    }
  ]
}
```

---

## 6. Prompt 设计原则

### 6.1 系统提示词结构

```
[角色定义] 你是一位专业的漫画/短剧编剧，擅长{genre}题材创作。
[输出约束] 严格按照 JSON Schema 输出，不添加额外字段。
[风格注入] 视觉描述需要以"{style}风格。"开头。
[质量要求] visual 字段不少于 80 字，包含环境/光线/色彩/角色造型/构图。
[节奏控制] 短剧节奏：每 4-6 秒一个镜头，总长度 30-60 秒。
[格式规范] narration 使用第一人称或第三人称，与剧情情绪一致。
```

### 6.2 质量控制策略

1. **JSON Schema 强制约束** — 使用 OpenAI 兼容的 `response_format: {type: "json_object"}` 确保输出是合法 JSON
2. **字段验证** — 每镜 visual ≥ 80 字；dialogue 标注角色名；narration 与 emotion 一致
3. **少样本示例** — 在 Prompt 中提供 1-2 个已有优质分镜作为 few-shot 参考
4. **重试机制** — 解析失败时自动重试（最多 2 次），temperature 从 0.8 降至 0.3
5. **格式校验器** — `_validate_scene(scene)` 检查必填字段、字段类型、枚举值

### 6.3 用于 JieYou GPT-5.5 的 JSON mode

```python
def _call_llm(self, messages: list[dict], response_schema: dict) -> dict:
    """调用 JieYou GPT-5.5 并确保结构化 JSON 输出"""
    body = {
        "model": "gpt-5.5",
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
        "max_tokens": 8192,
    }
    # POST {base_url}/v1/chat/completions
    response = self._http_post(body)
    raw = json.loads(response["choices"][0]["message"]["content"])
    return self._validate_against_schema(raw, response_schema)
```

JieYou API 的 `gpt-5.5` 模型是 OpenAI 兼容的 Chat Completions 接口，支持 `response_format` 参数。如不支持，可以改用 `json.loads()` 加重试的 fallback 方案。

---

## 7. 配置设计

### 7.1 providers.yaml 扩展（可选）

```yaml
# 在现有 providers.yaml 中新增 screenplay 节
screenplay_providers:
  default: jieyou_gpt55
  available:
    - jieyou_gpt55

jieyou_gpt55:
  model: gpt-5.5
  temperature: 0.8
  max_tokens: 8192
  # 复用 openai_api.base_url 和 OPENAI_API_KEY
  # 无需额外配置
```

### 7.2 题材参数配置

```yaml
# src/aicomic/script/prompts/genre_config.yaml
genres:
  悬疑推理:
    default_shots: 6-8
    pacing: slow_burn
    prompt_keywords: [伏笔, 误导, 反转, 信息差]
    visual_emphasis: [光影对比, 构图暗示, 细节特写]

  赛博朋克动作:
    default_shots: 6
    pacing: fast
    prompt_keywords: [义体, 霓虹, 高速动作, 打击感]
    visual_emphasis: [高对比, 速度线, 赛璐珞着色, 网点阴影]

  校园温情:
    default_shots: 6
    pacing: gentle
    prompt_keywords: [暗恋, 日常, 细节, 微表情]
    visual_emphasis: [柔和光影, 暖色调, 印象派笔触]

  古风奇幻:
    default_shots: 6
    pacing: poetic
    prompt_keywords: [修仙, 狐妖, 宿命, 诗意]
    visual_emphasis: [水墨留白, 工笔细描, 金箔渐变]

  科幻太空:
    default_shots: 6-8
    pacing: cold_mystery
    prompt_keywords: [深空, 时间悖论, 硬科幻, 信号]
    visual_emphasis: [冷蓝光, 黄金分割, 视效描述, 狭小空间]

  喜剧:
    default_shots: 5-6
    pacing: punchy
    prompt_keywords: [反转, 吐槽, 夸张, 谐音梗]
    visual_emphasis: [Q版表情, 夸张动作, 分割画面]
```

---

## 8. 实现计划

### 8.1 工期估算：4-6 天

| 阶段 | 内容 | 工时 |
|------|------|------|
| **D1** | 定义 `IScreenplayEngine` 接口 + 数据模型（Screenplay, Scene） | 0.5 天 |
| **D1-D2** | 实现 `LLMScreenplayEngine` — JieYou GPT-5.5 调用 + Prompt 模板 | 1 天 |
| **D2-D3** | 实现 `ManifestWriter` — Screenplay → episode_manifest.json 写入 | 0.5 天 |
| **D3-D4** | Prompt 模板优化 — 各题材 prompt 调优 + few-shot 示例 | 1 天 |
| **D4-D5** | 单元测试 + 集成测试（mock JieYou API） | 1 天 |
| **D5-D6** | 集成到管线 + 端到端验证（2-3 个题材案例） | 1 天 |

### 8.2 前置依赖

- ✅ JieYou API 可用（`openai_api.base_url` 已配置）
- ✅ `OPENAI_API_KEY` 已设置（与 DALL-E / TTS 共用）
- ⚪ Provider 抽象层（已立项，长期依赖）
- ⚪ Prompt 模板需在测试中迭代优化

### 8.3 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| GPT-5.5 JSON mode 不稳定 | 输出格式异常 | 备用方案：`json.loads()` + 重试，降 temperature |
| 视觉描述不够"漫画感" | 生成素材风格偏移 | Prompt 中嵌入"AIComics 风格提示词规范" |
| 长上下文超出 token 限制 | 分镜数受限 | 分批生成：先剧本 → 再逐镜展开；max_tokens=8192 |
| API 调用成本 | 每集生成约消耗 4K-8K tokens | 缓存已生成的 manifest，支持手工修改后继续 |
| 多题材 prompt 泛化不足 | 部分题材质量差 | 每题材独立 prompt 模板，持续迭代 |

---

## 9. 使用示例

### 9.1 Python API 使用

```python
from pathlib import Path
from aicomic.script.engine import IScreenplayEngine
from aicomic.script.llm_engine import LLMScreenplayEngine
from aicomic.script.manifest_writer import write_screenplay_to_episode_manifest
from aicomic.script.registry import get_script_engine

# 方式 1：获取默认引擎
engine = get_script_engine()  # → LLMScreenplayEngine (JieYou GPT-5.5)

# 方式 2：直接实例化
# engine = LLMScreenplayEngine()

# 验证配置
status = engine.validate_config()
assert status["ready"], "JieYou API key 未配置"

# 第一步：生成剧本
screenplay = engine.generate_screenplay(
    genre="悬疑推理",
    style="Liquid Glass",
    logline="女主发现镜子里的倒影动作和自己不同步——但医生说这只是失眠引起的幻觉。"
)

# 第二步：展开为分镜清单
scenes = engine.expand_to_shotlist(screenplay, num_shots=6)

# 第三步：写入 manifest（复用现有输出格式）
project_root = Path("projects/my_mystery")
manifest_path = write_screenplay_to_episode_manifest(
    project_root=project_root,
    project_id="my_mystery",
    season=1,
    episode_code="E01",
    screenplay=screenplay,
    scenes=scenes,
)
# → 输出: projects/my_mystery/manifests/episode_manifest.json
#    (文件中包含 "episode_code": "E01", "shots": [...] 等全字段)
```

### 9.2 CLI 使用（设想）

```bash
# 一键生成：题材 + 风格 + 梗概 → 完整 manifest
python -m aicomic.script.generate \
  --genre "悬疑推理" \
  --style "Liquid Glass" \
  --logline "女主发现镜子里的倒影动作和自己不同步" \
  --shots 6 \
  --output ./manifests/

# 从现有剧本文件生成分镜
python -m aicomic.script.expand \
  --screenplay ./drafts/screenplay.json \
  --shots 6 \
  --output ./manifests/

# 管线集成
python -m aicomic.pipeline run \
  --step story_bible \
  --genre "赛博朋克动作" \
  --style "Hybrid Comic Pop" \
  --logline "义体维修师不想打架"
```

---

## 10. 验证方案

### 10.1 单元测试

| 测试 | 内容 |
|------|------|
| `test_screenplay_schema` | 验证 Screenplay 数据模型字段完整性 |
| `test_scene_schema` | 验证 Scene 数据模型与现有 manifest shot 字段兼容 |
| `test_llm_engine_prompt` | Mock HTTP 调用，验证 prompt 构建正确 |
| `test_llm_engine_parse` | Mock API 响应，验证 JSON 解析和冲突处理 |
| `test_manifest_writer` | 验证写入的 JSON 与现有 manifest schema 一致 |
| `test_genre_config` | 验证所有题材配置都包含必需字段 |

### 10.2 集成测试

| 测试 | 内容 |
|------|------|
| `test_e2e_suspense` | 悬疑推理题材：完整生成 → 写入 → 校验 manifest |
| `test_e2e_scifi` | 科幻题材：同上 |
| `test_e2e_comedy` | 喜剧题材：同上 |
| `test_manifest_pipeline_compat` | 生成的 manifest 能被 `job_builder.py` 正常解析 |

### 10.3 人工审查标准

| 维度 | 检查点 | Pass 标准 |
|------|--------|-----------|
| 叙事完整性 | 有起承转合 | 三幕结构清晰或悬念递进合理 |
| 视觉质量 | visual 字段细节 | ≥ 80 字，包含环境/光照/角色/构图 |
| 对白自然度 | dialogue 是否口语化 | 符合角色设定，无"AI 味"过重措辞 |
| 镜头多样性 | camera 运镜 | 6 镜中至少 3 种不同运镜方式 |
| 风格一致性 | 视觉描述中包含风格前缀 | 每镜 visual 开头包含 `"{style}风格。"` |
| 长度合规 | 总时长 | 6 镜 × 4-6 秒 = 24-36 秒，适合短剧平台 |

---

## 11. 长远规划

### 11.1 版本路线

| 版本 | 内容 | 时间 |
|------|------|------|
| v1.0 | JieYou GPT-5.5 单引擎 + 5 题材 Prompt | 本周 |
| v1.1 | 多 LLM 供应商支持（DeepSeek / Claude / 本地模型） | 下一迭代 |
| v1.2 | 连载连续性（前集 ending_hook → 后集起始状态传递） | 后续 |
| v2.0 | 用户反馈循环（生成的剧本可在线编辑、重新生成、对比版本） | Q3 |

### 11.2 多供应商扩展

```python
# registers.py
register(LLMScreenplayEngine)      # JieYou GPT-5.5
register(DeepSeekScreenplayEngine)  # DeepSeek（未来）
register(ClaudeScreenplayEngine)    # Claude（未来）
register(LocalScreenplayEngine)     # 本地 LLM（未来）
```

多供应商路由策略与 `ProviderRegistry.resolve_with_fallback()` 一致：云端优先 → 本地回退。

---

## 附录 A：与 Toonflow 架构对比

| 维度 | Toonflow (11.6k⭐) | AIComics (本方案) |
|------|-------------------|-------------------|
| 剧本 Agent | ScriptAgent + Skill 文件化 | IScreenplayEngine 抽象接口 |
| LLM 路由 | 内置路由，不可切换 | Provider 层路由，可扩展 |
| 输出格式 | 内部 DSL | 标准 episode_manifest.json |
| 复用性 | 紧耦合 | 松耦合，可独立测试 |
| 视觉风格注入 | 通过 Skill 系统 | 通过 Prompt 模板 + style 参数 |

## 附录 B：Prompt 模板示例 (Jinja2)

**`prompts/screenplay.j2`**:

```jinja2
你是一位专业的{{genre}}题材短剧编剧。你的作品需要符合{{style}}视觉风格。

<任务>
根据以下信息创作一集短剧剧本（1集，6个镜头，约30秒）：
</任务>

<输入>
- 题材：{{genre}}
- 视觉风格：{{style}}
- 梗概：{{logline}}
{% if character_hints %}
- 角色提示：{{character_hints}}
{% endif %}
{% if world_hints %}
- 世界观：{{world_hints}}
{% endif %}
</输入>

<写作要求>
1. 必须有清晰的开端→发展→反转（或高潮）→结尾钩子
2. 每镜 visual 字段以"{{style}}风格。"开头，不少于80字
3. 对白符合角色性格，不冗长
4. narration 为旁白/内心独白，不能与 dialogue 重复
5. ending_hook 要制造"下一集还想看"的悬念
6. 镜头要多样化：中景、特写、广角、过肩、俯拍等交替使用
7. ai_video=true 的镜头需要有足够的动态元素（动作/物体运动/镜头运动）
</写作要求>

<输出格式>
严格按照以下 JSON Schema：
{{schema}}
</输出格式>
```

---

*本文档为 AIComics P0#1 AI 编剧引擎的设计方案。实现完成后更新此文档。*
