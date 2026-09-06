# AIComics 图像生成 Pipeline 执行方案
## 抠图 → 生图 → 放大 → 合成 → 输出

> 编写: 小h CEO | 日期: 2026-08-19 | 版本: v1.0
> 来源层级: 代码实勘(L5) + 本机环境(L4) + 技术认知(L3)

---

## 一、可行性结论：✅ 完全可行

### 现有基础

| 组件 | 状态 | 证据 |
|------|------|------|
| ComfyUI v0.33.0 | ✅ 已运行 | `local_providers/comfyui_runtime/ComfyUI/` (launchd 守护) |
| SDXL 基础模型 | ✅ 已下载 | `sd_xl_base_1.0.safetensors` |
| ComfyUI Provider | ✅ 已实现 | `comfyui_provider.py` (build_request → execute → poll) |
| 图像一致性 | ✅ 已实现 | `image_consistency.py` (pHash 锁脸) |
| 单集产线 | ✅ 已实现 | `one_shot_pipeline.py` (母版→出帧→门禁→成片) |
| Workflow JSON | ✅ 已有 | `image_workflow_sdxl.json` (7节点: CheckpointLoader→KSampler→VAEDecode→SaveImage) |

### 缺失能力

| 能力 | 现状 | 需要做的 |
|------|------|---------|
| 抠图/背景去除 | ❌ 无 | 接入 RMBG-2.0 (ComfyUI 节点) |
| 放大/超分辨率 | ❌ 无 | 接入 Real-ESRGAN (ComfyUI 节点) |
| ControlNet 控制 | ❌ 模型目录空 | 下载 ControlNet 模型 + 构建工作流 |
| Flux 支持 | ❌ 无 | 下载 Flux.1-dev GGUF + 构建工作流 |
| 图层合成 | ❌ 无 | Pillow alpha 合成 (已有 Pillow 依赖) |
| Pipeline 编排 | ❌ 只有单步出图 | 编排 5 阶段串联 |

---

## 二、技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIComics 图像生成 Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  输入: 角色 prompt + 场景 prompt + 参考图(可选)                     │
│    │                                                             │
│    ▼                                                             │
│  ① 抠图 (Matting)                                                │
│    │  RMBG-2.0 via ComfyUI → 输出前景 PNG (alpha channel)         │
│    │  输入: 参考图 / 立绘母版                                      │
│    │  输出: 透明背景角色图                                         │
│    │                                                             │
│    ▼                                                             │
│  ② 生图 (Generation)                                             │
│    │  SDXL / Flux.1-dev via ComfyUI                               │
│    │  + ControlNet (canny/depth/openpose) 控制构图                │
│    │  + 角色一致性 prompt injection (已有 prompt_injector.py)       │
│    │  输入: text prompt + ControlNet 条件图 + 种子                 │
│    │  输出: 1024×1024 或 1024×1536 原始图                          │
│    │                                                             │
│    ▼                                                             │
│  ③ 放大 (Upscaling)                                              │
│    │  Real-ESRGAN 4x via ComfyUI                                 │
│    │  输入: ② 的输出图                                            │
│    │  输出: 4096×4096 或 4096×6144 高清图                          │
│    │                                                             │
│    ▼                                                             │
│  ④ 合成 (Composite)                                              │
│    │  Pillow alpha blending (已有 Pillow 12.2 依赖)               │
│    │  输入: ① 的透明前景 + ③ 的放大背景 + 场景图层                   │
│    │  输出: 合成 PNG (角色+场景+特效层)                              │
│    │                                                             │
│    ▼                                                             │
│  ⑤ 输出 (Output)                                                 │
│    │  保存到项目目录 + 元数据 (种子/prompt/参数)                     │
│    │  触发图像一致性门禁 (已有 image_consistency.py)                │
│    │  输出: 最终 PNG + JSON manifest                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、模型选型

### 3.1 抠图 — RMBG-2.0

| 属性 | 值 |
|------|---|
| 模型 | `RMBG-2.0` (briaai/RMBG-2.0) |
| 大小 | ~550MB (FP16) |
| 输入 | RGB 图像 (任意分辨率) |
| 输出 | RGBA PNG (alpha=前景 mask) |
| 速度 | M4 Mac: ~0.5s/图 (1024×1024) |
| ComfyUI 节点 | `ComfyUI-BRIA-RMBG` 或 `ComfyUI-Image-Filters` |
| 优势 | SOTA 背景去除，发丝级精度，无需 trimap |

### 3.2 生图 — SDXL + Flux.1-dev

| 模型 | 大小 | 用途 | 速度 |
|------|------|------|------|
| `sd_xl_base_1.0.safetensors` | 6.5GB (已有) | 通用动漫风 | ~3s/图 (M4, 20步) |
| `animagineXL_v4.safetensors` | 6.5GB | 动漫专用风格 | ~3s/图 |
| `flux.1-dev-Q4_0.gguf` | ~6GB | 高质量写实/电影感 | ~8s/图 (GGUF量化) |
| `flux.1-schnell-Q4_0.gguf` | ~6GB | 快速预览 (4步) | ~2s/图 |

### 3.3 ControlNet

| 类型 | 模型 | 用途 |
|------|------|------|
| Canny 边缘 | `controlnet-canny-sdxl-1.0` | 线稿控制构图 |
| Depth 深度 | `controlnet-depth-sdxl-1.0` | 深度图控制层次 |
| OpenPose | `controlnet-openpose-sdxl-1.0` | 姿态控制 |
| IP-Adapter | `ip-adapter-plus_sdxl_vit-h` | 参考图风格迁移 (角色一致性核心) |

### 3.4 放大 — Real-ESRGAN

| 属性 | 值 |
|------|---|
| 模型 | `RealESRGAN_x4plus.pth` (通用4x) + `RealESRGAN_x4plus_anime_6B.pth` (动漫专用) |
| 大小 | ~67MB (通用) + ~6MB (动漫) |
| 放大倍率 | 4x (1024→4096) |
| 速度 | M4: ~1s/图 (1024×1024) |
| ComfyUI 节点 | 内置 `UpscaleImage` (需下载模型到 `models/upscale_models/`) |

---

## 四、ComfyUI Workflow 设计

### 4.1 完整 Pipeline Workflow (JSON 节点结构)

```
节点编排:
  [1] CheckpointLoaderSimple (SDXL/Flux)
  [2] CLIPTextEncode (正向 prompt)
  [3] CLIPTextEncode (负向 prompt)
  [4] EmptyLatentImage / LoadImage (文生图 / 图生图)
  [5] ControlNetApply (Canny/Depth/IP-Adapter)
  [6] LoadControlNetModel
  [7] KSampler (20步 / DPM++ 2M)
  [8] VAEDecode
  [9] RMBG-2.0 Node (背景去除)
  [10] UpscaleImage (Real-ESRGAN 4x)
  [11] SaveImage (最终输出)
```

### 4.2 分阶段 Workflow（灵活组合）

| Workflow JSON | 阶段 | 可独立运行 |
|--------------|------|-----------|
| `wf_matting.json` | ① 抠图 | ✅ |
| `wf_generate.json` | ② 生图(+ControlNet) | ✅ |
| `wf_upscale.json` | ③ 放大 | ✅ |
| `wf_full_pipeline.json` | ①→②→③→④→⑤ 全链路 | ✅ |

---

## 五、代码实现方案

### 5.1 新增模块: `src/aicomic/image_pipeline/`

```
src/aicomic/image_pipeline/
├── __init__.py          # 导出
├── pipeline.py          # ImagePipeline 主编排器
├── matting.py           # 抠图 (RMBG-2.0 via ComfyUI)
├── generation.py        # 生图 (SDXL/Flux + ControlNet)
├── upscaling.py         # 放大 (Real-ESRGAN via ComfyUI)
├── composite.py         # 合成 (Pillow alpha blending)
├── workflows.py         # ComfyUI workflow JSON 构建器
└── models.py            # 模型路径管理 + 下载检查
```

### 5.2 核心接口设计

```python
# pipeline.py — 主编排器
class ImagePipeline:
    """AI图像生成Pipeline: 抠图→生图→放大→合成→输出"""

    def __init__(self, comfyui_base_url: str = "http://127.0.0.1:8188"):
        self.comfyui = ComfyUIClient(comfyui_base_url)

    def run(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1536,  # 竖版漫画
        seed: int = -1,
        steps: int = 20,
        cfg: float = 7.0,
        checkpoint: str = "sd_xl_base_1.0.safetensors",
        controlnet_type: str | None = None,
        controlnet_image: Path | None = None,
        reference_image: Path | None = None,  # 抠图参考
        upscale: bool = True,
        upscale_model: str = "RealESRGAN_x4plus.pth",
        upscale_scale: int = 4,
        composite_bg: Path | None = None,  # 合成背景
        output_dir: Path = Path("output"),
    ) -> dict[str, Any]:
        """执行完整 pipeline, 返回输出路径 + 元数据."""

        # ① 抠图 (如果有参考图)
        foreground = None
        if reference_image:
            foreground = self.matting(reference_image)

        # ② 生图 (+ControlNet)
        raw_image = self.generate(prompt, negative_prompt, width, height,
                                   seed, steps, cfg, checkpoint,
                                   controlnet_type, controlnet_image)

        # ③ 放大
        if upscale:
            raw_image = self.upscale(raw_image, upscale_model, upscale_scale)

        # ④ 合成
        if foreground and composite_bg:
            final = self.composite(foreground, raw_image, composite_bg)
        else:
            final = raw_image

        # ⑤ 输出
        return self.save_output(final, prompt, seed, ...)

    def matting(self, image: Path) -> Path:
        """RMBG-2.0 抠图 → 透明背景 PNG"""

    def generate(self, prompt, ..., controlnet_type, controlnet_image) -> Path:
        """SDXL/Flux 生图 + ControlNet"""

    def upscale(self, image: Path, model: str, scale: int) -> Path:
        """Real-ESRGAN 放大"""

    def composite(self, foreground: Path, background: Path, ...) -> Path:
        """Pillow alpha 合成"""
```

### 5.3 与现有系统集成

| 现有模块 | 集成方式 |
|---------|---------|
| `one_shot_pipeline.py` | `generate_frames()` 增加调用 `ImagePipeline.run()` |
| `image_consistency.py` | pipeline 输出后自动触发一致性门禁 |
| `comfyui_provider.py` | 复用 ComfyUI HTTP 客户端 |
| `prompt_injector.py` | 生图前注入角色一致性 prompt |
| `template_engine.py` | 模板可指定 pipeline_override (模型/controlnet/放大倍率) |

---

## 六、模型下载清单

```bash
# 1. ControlNet 模型 (~1.5GB total)
cd local_providers/comfyui_runtime/ComfyUI/models/controlnet/
curl -LO "https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/canny-sdxl-controlnet.safetensors"
curl -LO "https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/depth-sdxl-controlnet.safetensors"
curl -LO "https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/openpose-sdxl-controlnet.safetensors"

# 2. IP-Adapter (~300MB)
cd ../ipadapter/
curl -LO "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"

# 3. Real-ESRGAN (~67MB)
cd ../upscale_models/
curl -LO "https://github.com/xinntex/Real-ESRGAN/releases/download/0.2.5/RealESRGAN_x4plus.pth"
curl -LO "https://github.com/xinntex/Real-ESRGAN/releases/download/0.2.5/RealESRGAN_x4plus_anime_6B.pth"

# 4. RMBG-2.0 ComfyUI 节点
cd ../custom_nodes/
git clone https://github.com/briaai/ComfyUI-BRIA-RMBG.git

# 5. (可选) Flux.1-dev GGUF (~6GB)
cd ../unet/
curl -LO "https://huggingface.co/Quantization/flux.1-dev/resolve/main/flux.1-dev-Q4_0.gguf"
```

**总下载量**: ~2.5GB (不含 Flux) / ~8.5GB (含 Flux)

---

## 七、执行计划

### Phase 1: 基础 Pipeline (3天)

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 创建 `image_pipeline/` 模块骨架 | 6个 .py 文件 |
| 1.2 | 实现 `models.py` 模型路径管理 | 检查+下载提示 |
| 1.3 | 实现 `workflows.py` ComfyUI JSON 构建 | 4个 workflow 模板 |
| 1.4 | 实现 `matting.py` RMBG-2.0 调用 | 抠图功能 |
| 1.5 | 实现 `generation.py` SDXL+ControlNet | 生图功能 |
| 1.6 | 实现 `upscaling.py` Real-ESRGAN | 放大功能 |
| 1.7 | 实现 `composite.py` Pillow 合成 | 图层合成 |
| 1.8 | 实现 `pipeline.py` 主编排器 | 5阶段串联 |
| 1.9 | 单元测试 (每模块 mock 测试) | 30+ tests |

### Phase 2: 模型下载 + 真实运行 (2天)

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 下载 ControlNet + Real-ESRGAN + RMBG | ~2.5GB |
| 2.2 | 安装 RMBG ComfyUI 节点 | custom_nodes |
| 2.3 | 真实运行完整 pipeline | 首张 AI 生成图 |
| 2.4 | 调参优化 (步数/CFG/采样器) | 最佳参数 |
| 2.5 | 与 one_shot_pipeline 集成 | 替换 mock 出帧 |

### Phase 3: CLI + API + 前端 (2天)

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | CLI: `aicomic image-pipeline --prompt "..." --controlnet canny` | 命令行工具 |
| 3.2 | Web API: `POST /api/image/pipeline` | API 端点 |
| 3.3 | 前端: 图像生成页面 | UI |
| 3.4 | 端到端测试 | 10+ tests |
| 3.5 | 文档更新 | README + CHANGELOG |

### Phase 4: 高级功能 (3天)

| 步骤 | 内容 | 产出 |
|------|------|------|
| 4.1 | Flux.1-dev 支持 | 第二生图引擎 |
| 4.2 | IP-Adapter 角色一致性 | 参考图→保持角色 |
| 4.3 | 批量生成 (整季分镜) | 12集×10镜=120张 |
| 4.4 | 模板→Pipeline 参数联动 | 题材自动选模型 |
| 4.5 | 性能优化 (并发提交) | 3x 加速 |

**总工期: 10天**

---

## 八、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| RMBG-2.0 ComfyUI 节点不兼容 v0.33 | 中 | 高 | 备选: `rembg` Python 库 (pip install) |
| M4 Mac 显存不足跑 Flux | 中 | 中 | 用 Q4 量化 GGUF, 或跳过 Flux 只用 SDXL |
| ControlNet 模型下载慢 | 低 | 低 | huggingface 镜像加速 |
| ComfyUI 节点 API 变更 | 低 | 中 | 锁定 ComfyUI 版本 |
| Pillow alpha 合成质量不够 | 低 | 低 | 备选: ComfyUI 内合成节点 |

---

## 九、预期产出

### 代码
- 7 个新 Python 模块 (~800 行)
- 4 个 ComfyUI workflow JSON
- 40+ 个新测试
- 1 个新 CLI 命令
- 1 个新 Web API 端点
- 1 个新前端页面

### 模型
- 3 个 ControlNet 模型 (~1.5GB)
- 2 个 Real-ESRGAN 模型 (~73MB)
- 1 个 RMBG-2.0 模型 (~550MB)
- (可选) 1 个 Flux GGUF (~6GB)

### 文档
- README v2.1 功能表更新
- CHANGELOG v2.1.0
- ROADMAP 新增图像 Pipeline 项

---

## 十、总结

**完全可行。** AIComics 已有 ComfyUI 基础设施 (provider/service/workflow/一致性门禁)，只需要：
1. 下载 4 类模型 (~2.5GB)
2. 新建 1 个模块 (7个文件)
3. 构建 4 个 ComfyUI workflow
4. 编排 5 阶段 pipeline

核心价值：把分散的 AI 模型编排成**一键出图**的产品体验，从"单步生图"升级为"抠图→生图→放大→合成→输出"全链路自动化。
