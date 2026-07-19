# Blender 作为 AIComics Provider 可行性分析报告

> 生成时间：2026-07-19
> 调研范围：Blender Python API、AIComics Provider 架构、aicg-handbook 管线知识

---

## 一、执行摘要

| 维度 | 结论 |
|------|------|
| **可行性** | ✅ **技术可行**，但需要先安装 Blender |
| **集成难度** | 中等 — 需实现一个 `IProvider` 子类 + 渲染脚本模板 |
| **安装状态** | ❌ 本地未安装 Blender（不在 PATH，不在 Homebrew） |
| **推荐优先级** | **P1** — 值得投入，但不紧急。先 P0 完成 Seedance/Kling 视频集成 |
| **预期价值** | 高质量三渲二视觉效果、精确摄像机控制、完整的场景与光照管线 |

---

## 二、本地 Blender 安装检查

### 2.1 当前状态

| 检查项 | 结果 |
|--------|------|
| `which blender` | ❌ 未找到 |
| `blender --version` | ❌ 未找到 |
| `brew list blender` | ❌ 未通过 Homebrew 安装 |
| `brew info blender` | ❌ Homebrew 不存在 blender formula（仅 `blender@4` 在第三方仓库） |

### 2.2 安装方案

#### 方案 A：官网下载（推荐）

```bash
# 访问 https://www.blender.org/download/ 下载 macOS ARM64 dmg
# 或通过 brew 安装（需要 cask）
brew install --cask blender
```

安装后默认路径：
- `/Applications/Blender.app/Contents/MacOS/Blender`
- 符号链接: `/usr/local/bin/blender`（brew cask 会自动处理）

#### 方案 B：Blender 作为 Python 模块（bpy）

Blender 的 `bpy` 模块无法通过 pip 安装。但 Blender 捆绑了自己的 Python 解释器，可以通过以下方式使用：

```bash
# 使用 Blender 内置的 Python
/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -c "import bpy; print(bpy.app.version_string)"
```

> **注意**：pip install bpy 在 macOS 上不支持。必须通过 Blender 应用分发。

---

## 三、AIComics Provider 架构分析

### 3.1 现有 Provider 架构

AIComics 的 Provider 系统设计成熟，Blender 集成可以直接复用：

```
IProvider (抽象基类)
├── ComfyUIProvider    — 图片/视频生成
├── OpenAIProvider     — API 图片/TTS
├── SeedanceProvider   — 云视频生成
├── KlingProvider      — 云视频生成
├── ManualProvider     — 人工导入
└── PiperTTSProvider   — 本地配音
```

**关键集成点：**

1. **注册** — `src/aicomic/providers/provider_registry.py::_create_default_registry()`
2. **配置** — `config/providers.yaml` 中的 provider 段落
3. **路由** — `src/aicomic/providers/provider_planner.py::PROVIDER_PROFILES`
4. **执行** — `IProvider.execute_request()` 返回 `{"provider", "output_path", "content_type"}`
5. **能力声明** — `ProviderCapability(job_types, dispatch_channel, ...)`

### 3.2 Blender Provider 定位

| 属性 | 值 |
|------|-----|
| Provider Name | `local_blender_video` / `local_blender_image` |
| Job Types | `video`（主）、`image`（辅） |
| Dispatch Channel | `local` |
| Run Mode | 本地 Blender 渲染（Cycles / EEVEE） |
| Auth Required | 否 |

---

## 四、Blender Python API 技术评估

### 4.1 核心能力

| 能力 | 支持的 API | AIComics 应用场景 |
|------|-----------|-----------------|
| **场景搭建** | `bpy.ops.mesh.*`, `bpy.data.objects` | 从 JSON 配置自动搭建 3D 场景 |
| **摄像机控制** | `bpy.data.cameras`, `bpy.data.objects["Camera"]` | 精确分镜控制（推/拉/摇/移/升降） |
| **三渲二着色** | Shader to RGB → ColorRamp 节点 | Arcane 风格的 cel shading |
| **Freestyle 线稿** | `bpy.data.scenes["Scene"].render.use_freestyle` | 动漫风格的轮廓线 |
| **光照系统** | `bpy.data.lights` | 三点布光、电影级光照预设 |
| **材质系统** | `bpy.data.materials`, ShaderNodeTree | Painterly 3D Noir 风格材质 |
| **头渲染** | `bpy.ops.render.render(write_still=True)` | 静帧输出 |
| **动画渲染** | `bpy.ops.render.render(animation=True)` | 镜头动画输出为视频帧序列 |
| **合成** | `bpy.context.scene.use_nodes = True` | 后期特效（光晕、色彩校正） |
| **Python 脚本** | `blender -b -P script.py -- --args` | 无头批处理渲染 |

### 4.2 无头渲染模式

```bash
# 核心命令模式
blender -b /path/to/scene.blend -P render_script.py -o /output/frame_### -f 1

# 参数传递
blender -b -P script.py -- --scene-id S01 --output-dir /tmp/output

# 动画渲染
blender -b scene.blend -P camera_anim.py -o /output/frame_### -a
```

### 4.3 关键限制

| 限制 | 说明 | 缓解方案 |
|------|------|---------|
| **macOS 无 GPU Cycles** | Apple Silicon 上 Cycles 渲染器不支持 NVIDIA CUDA，只能走 Metal | 使用 EEVEE 实时渲染器（足够三渲二质量） |
| **bpy 不可 pip 安装** | 必须使用 Blender 内置 Python | subprocess 调用 `blender -b -P script.py` |
| **启动延迟** | Blender 启动约 3-8 秒 | 脚本复用同一进程批量渲染多个分镜 |
| **.blend 文件分发** | 需要维护场景模板 (.blend) | 模板放在 `local_providers/blender/templates/` |
| **内存占用** | 单个渲染进程约 500MB-2GB | 确保 M4 32GB 足够 |

---

## 五、集成方案设计

### 5.1 目录结构

```
local_providers/blender/
├── templates/                 # .blend 场景模板
│   ├── scene_default.blend    # 默认三渲二场景
│   ├── cel_shading.blend      # Cel Shading 预设场景
│   └── noir_scene.blend       # Painterly 3D Noir 场景
├── scripts/                   # Blender Python 渲染脚本
│   ├── render_frame.py        # 单帧渲染入口
│   ├── render_animation.py    # 动画序列渲染入口
│   ├── setup_scene.py         # 场景搭建脚本
│   └── camera_presets.py      # 分镜卡片摄像机预设
├── outputs/                   # 渲染输出目录
├── assets/                    # 共享资产
│   ├── materials/             # 材质库
│   ├── hdris/                 # HDR 环境贴图
│   └── models/                # 基础 3D 模型
└── README.md                  # 安装与使用说明
```

### 5.2 Provider 代码结构

```python
# src/aicomic/providers/blender_provider.py

from pathlib import Path
from typing import Any, ClassVar
from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo

class BlenderVideoProvider(IProvider):
    provider_name: ClassVar[str] = "blender"
    display_name: ClassVar[str] = "Blender 三渲二"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("video", "image"),
        dispatch_channel="local",
        auth_required=False,
        required_env=(),
    )

    def validate_config(self) -> dict[str, Any]:
        # 1. 检查 blender 是否在 PATH
        # 2. 检查模板文件是否存在
        # 3. 检查 bpy 可导入（通过 --background 模式）
        ...

    def build_request(self, request_item, providers_config_path) -> dict[str, Any]:
        # 构建渲染脚本命令
        ...

    def execute_request(self, request_item, providers_config_path) -> dict[str, Any]:
        # 调用 subprocess 执行 blender -b -P render_animation.py
        # 返回输出视频/帧序列路径
        ...

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name="blender",
            display_name="Blender 三渲二",
            capabilities=self.capabilities,
            run_mode="本地 Blender 三渲二渲染",
            notes="基于 Blender Python API 的本地三渲二视频生成。"
                   "支持 Cel Shading / Freestyle 线稿 / 精确摄像机控制。",
        )
```

### 5.3 配置 `config/providers.yaml`

```yaml
local_blender_video:
  blender_path: /Applications/Blender.app/Contents/MacOS/Blender
  template_path: ../local_providers/blender/templates/scene_default.blend
  scripts_path: ../local_providers/blender/scripts/
  engine: EEVEE
  resolution_x: 1280
  resolution_y: 720
  fps: 24
  output_prefix: blender_scene
  timeout_seconds: 600
  render_samples: 64
  use_freestyle: true
```

### 5.4 注册 Provider

在 `src/aicomic/providers/provider_registry.py` 中：

```python
from aicomic.providers.blender_provider import BlenderVideoProvider

def _create_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    # ... 现有注册 ...
    registry.register(BlenderVideoProvider)
    return registry
```

### 5.5 Provider 路由配置

在 `src/aicomic/providers/provider_planner.py::PROVIDER_PROFILES` 中：

```python
"local_blender_video": ProviderProfile(
    provider="local_blender_video",
    supported_job_types=["video"],
    dispatch_channel="local",
    queue_name="video_local",
    run_mode="本地 Blender 三渲二视频渲染",
    auth_required=False,
    required_env=[],
    notes="适合三渲二动画风格视频生成。需要安装 Blender 4.x。"
          "支持 Cel Shading / Freestyle 线稿 / 精确摄像机控制。",
),
```

### 5.6 写入 video_providers 列表

```yaml
video_providers:
  default: local_comfyui_video
  available:
    - seedance
    - kling
    - local_blender_video       # ← 新增
    - manual_web
    - local_comfyui_video
```

---

## 六、生产管线集成方案

### 6.1 AIComics + Blender 管线图

```
┌──────────────────────────────────────────────────────┐
│                    AIComics 引擎                       │
│  故事 → 分镜 JSON → Provider 路由 → 视频合成 → 发布   │
└──────────────────┬───────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  blender_provider    │
        │  (IProvider 实现)    │
        └──────────┬──────────┘
                   │ subprocess
        ┌──────────▼──────────┐
        │  blender -b -P ...  │
        │  (无头渲染模式)      │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  Blender Python API  │
        │  (bpy 模块)          │
        ├─────────────────────┤
        │ 1. 加载 .blend 模板  │
        │ 2. 设置摄像机位置/动画│
        │ 3. 设置三渲二材质     │
        │ 4. 渲染帧序列 → PNG  │
        │ 5. FFmpeg 合成 MP4   │
        └─────────────────────┘
```

### 6.2 从分镜 JSON 到 Blender 场景

aicg-handbook 中的分镜 JSON 模板可以直接映射到 Blender 摄像机预设：

```json
{
  "shot_id": 1,
  "camera": "EW, low angle",
  "duration": 4,
  "frames": 96,
  "description": "雨中的校园"
}
```

→ 映射到 Blender 摄像机脚本

```python
# camera_presets.py 中的预设
CAMERA_PRESETS = {
    "EW_low_angle": {
        "location": (0, -20, 5),
        "rotation": (0.6, 0, 0),
        "focal_length": 35,
    },
    # ... 9 种分镜卡片摄像机预设
}
```

### 6.3 渲染输出对接现有视频管线

Blender 渲染输出 PNG 帧序列 → 现有管线可以复用：

1. **帧序列 → FFmpeg 视频合成**（现有 `video_synthesis/` 支持）
2. **音频合成**（现有 Piper TTS 输出 + 场景音频混音）
3. **字幕烧录**（现有 ASS/SRT 支持）

这意味着 Blender 渲染输出 **可以替换当前 Ken Burns 静图+缩放** 流程。

---

## 七、与现有 Provider 对比

| 特性 | ComfyUI | Seedance/Kling | Blender (提案) |
|------|---------|---------------|----------------|
| **视觉效果** | AI 生成（质量不稳定） | AI 生成（质量好） | 三渲二（质量可控） |
| **摄像机控制** | 无（由 AI 决定） | Motion Control 有限 | 精确自由控制 |
| **角色一致性** | 依赖 ControlNet | 依赖参考图 | 3D 模型天然一致 |
| **场景重复利用** | 每次重新生成 | 每次重新生成 | 场景模板可复用 |
| **渲染速度** | 快（秒级） | 中（分钟级） | 中（分钟级） |
| **离线可用** | ✅ 是 | ❌ 需要 API | ✅ 完全本地 |
| **风格一致性** | 低（seed 依赖） | 中 | **高**（渲染参数固定） |
| **硬件要求** | GPU（ComfyUI） | 无 | M4 32GB ✅ |
| **开发成本** | 已有 | 低（API 调用） | 中（脚本开发） |
| **运维成本** | 低 | 高（API 费用） | 低 |

---

## 八、实施路线图

### Phase 0 — 前提条件（1 天）

- [ ] 安装 Blender 4.x: `brew install --cask blender`
- [ ] 验证: `blender --version`
- [ ] 验证无头渲染: `blender -b --python-expr "import bpy; print(bpy.app.version_string)"`

### Phase 1 — MVP Provider（2-3 天）

- [ ] 创建 `local_providers/blender/templates/scene_default.blend`（含默认三渲二场景）
- [ ] 创建 `local_providers/blender/scripts/render_frame.py`
- [ ] 创建 `src/aicomic/providers/blender_provider.py`
- [ ] 注册 Provider（registry + profiles）
- [ ] 配置 `providers.yaml`
- [ ] 测试: `blender` provider 能渲染第一帧

### Phase 2 — 分镜摄像机系统（3-5 天）

- [ ] 实现 `camera_presets.py`（9 种分镜卡片预设）
- [ ] 实现从分镜 JSON 到 Blender 场景的自动映射
- [ ] 实现动画渲染（帧序列输出）
- [ ] FFmpeg 帧序列 → MP4 合成脚本

### Phase 3 — 风格管线（3-5 天）

- [ ] Painterly 3D Noir Cel Shading 材质预设
- [ ] Freestyle 线稿轮廓渲染
- [ ] HDR 环境照明预设
- [ ] 风格参数化（色调/线宽/阴影硬度）

### Phase 4 — 生产集成（2-3 天）

- [ ] 与现有视频合成管线对接（音频 + 字幕）
- [ ] 回退逻辑（Blender 失败 → 降级到 FFmpeg 静图）
- [ ] 并发渲染队列管理
- [ ] 渲染进度监控

---

## 九、风险与注意事项

| 风险 | 严重程度 | 缓解措施 |
|------|---------|---------|
| Blender 渲染速度慢 | 🟡 中 | EEVEE 实时渲染器（非 Cycles）；渲染农场队列 |
| macOS Metal 限制 | 🟢 低 | EEVEE 在 Apple Silicon 上表现良好 |
| 3D 场景搭建成本 | 🟡 中 | 模板复用；针对漫画场景简化几何体 |
| 角色模型资产缺乏 | 🔴 高 | 初期用 Manbogi/低多边形基础模型；后续接入角色系统 |
| 与现有 ComfyUI 流程的冲突 | 🟢 低 | Blender 作为独立 Provider，不替代 ComfyUI |
| 学习曲线 | 🟡 中 | 借助 aicg-handbook 已有知识；所有脚本模板化 |

---

## 十、结论与建议

### 可行性结论

**技术可行**。Blender Python API 提供的能力与 AIComics 的场景需求高度匹配：

1. **三渲二渲染管线**完整可用（EEVEE + Freestyle 线稿 + Cel Shading）
2. **Provider 架构**对接点清晰（`IProvider` 子类 + 注册 + 配置 + 路由）
3. **aicg-handbook** 已提供分镜卡片摄像机预设和风格模板可以直接复用
4. **现有视频管线**的音频/字幕模块可以直接对接

### 建议

1. **先完成 P0 任务**（Seedance 视频集成、角色系统）— 这些是行业标配缺口
2. **Blender 集成定位为 P1** — 差异化优势，让 AIComics 在竞品中脱颖而出
3. **初期聚焦短视频场景**（3-8 秒单镜头动画），与 Seedance/Kling 互补
4. **Blender 不替代现有管线**，而是作为 ComfyUI/Seedance 之外的第三个视频选项
5. **利用 aicg-handbook 资产**加速开发（camera_presets.py 是第一个可交付物）

### 投入产出评估

| 指标 | 估算 |
|------|------|
| 总开发时间 | ~10-16 天 |
| 硬件成本 | 0（已有 M4 32GB） |
| 软件成本 | 0（Blender 开源免费） |
| 关键依赖 | Blender 4.x |
| 第一个可用镜头 | Phase 1 完成后（2-3 天） |
| 生产就绪 | Phase 4 完成后（~4 周） |
