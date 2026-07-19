# AIComics 视频管线迁移方案

> 创建日期: 2026-07-19  
> 状态: 方案文档  
> 目标: 从 AnimateDiff (SD1.5) 迁移到 Wan2.2 / LTX-2.3 / HunyuanVideo

---

## 1. 现状

### 当前 ComfyUI 节点情况

| 节点 | 状态 | 用途 |
|------|------|------|
| **ComfyUI-AnimateDiff-Evolved** | ✅ 已安装 (3.3k⭐) | AIComics 视频管线核心 |
| **ComfyUI-VideoHelperSuite** | ✅ 已安装 | 视频编解码辅助 |
| comfyui-openai-api | ✅ 已安装 | OpenAI API 兼容层 |
| comfyui-zhipu | ✅ 已安装 | 智谱 API |
| **Wan2.2** | ❌ 未安装 | — |
| **LTXVideo / LTX-2.3** | ❌ 未安装 | — |
| **HunyuanVideo** | ❌ 未安装 | — |

### 当前 AIComics 视频管线架构

- **Workflow**: `local_providers/comfyui/workflows/video_workflow.json` + `video_workflow_fast.json`
- **模型**: anythingV5.safetensors (SD1.5 checkpoint) + mm_sd_v15_v2.ckpt (MotionModule)
- **节点**: `ADE_LoadAnimateDiffModel` → `ADE_AnimateDiffLoaderWithContext` → `ADE_UseEvolvedSampling` → `VAEDecode` → `VHS_VideoCombine`
- **部署**: Docker ComfyUI sidecar (`Dockerfile.comfyui-sidecar`)
- **限制**: SD1.5 基础模型，输出分辨率低 (256×144)，运动幅度有限，画质上限低

### 仓库中已有模型

| 目录 | 内容 |
|------|------|
| `models/diffusion_models/` | 几乎为空 (仅 z_image_turbo_bf16.safetensors) |
| `models/vae/` | 几乎为空 (仅 ae.safetensors) |

---

## 2. 推荐迁移路径

### 方案 A：Wan2.2 优先（推荐，质量最高）

**Wan2.2 官方原生支持**（ComfyUI 内置核心节点，无需额外 custom_node）

| 模型 | 参数 | VRAM | 适合场景 |
|------|------|------|----------|
| Wan2.2-TI2V-5B | 5B | ~8GB | **推荐** — 同时支持 T2V + I2V，低显存友好 |
| Wan2.2-T2V-A14B | 14B | ~16GB | 纯文生视频，高画质 |
| Wan2.2-I2V-A14B | 14B | ~16GB | 图生视频，高画质 |

#### 安装步骤

```bash
# 1. 更新 ComfyUI 到最新版本（自带 Wan2.2 核心节点）
cd /Users/eric/Documents/comfy/ComfyUI
git pull origin master

# 2. 安装 Kijai 的 WanVideoWrapper（可选，用于 GGUF 低显存版本）
cd custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
pip install -r ComfyUI-WanVideoWrapper/requirements.txt

# 3. 下载模型（5B 推荐，8GB VRAM 可用）
# 从 HuggingFace Comfy-Org/Wan_2.2_ComfyUI_Repackaged 下载
```

#### 模型下载清单（5B TI2V 版）

```
ComfyUI/models/
├── diffusion_models/
│   └── wan2.2-ti2v-5b.safetensors       # 主模型 ~5GB
├── text_encoders/
│   ├── clip_l.safetensors                # ~246MB
│   ├── t5xxl_fp16.safetensors            # ~2.5GB（可选 FP8 版本减半）
│   └── wan2.2_vae.safetensors            # VAE
└── vae/
    └── wan2.2_vae.safetensors
```

#### 关键特性

- ✅ ComfyUI **原生核心节点**（`WanVideoToVideo`、`WanImageToVideo`），无需 custom_node
- ✅ 支持 **Text-to-Video** + **Image-to-Video** 双模式
- ✅ 电影级画质，大运动幅度
- ✅ Apache 2.0 开源，可商用
- ✅ 5B 版本 8GB VRAM 可运行
- ⚠️ 模型体积大（5B ~4.5GB，14B ~24GB）
- ⚠️ GGUF 量化版：`QuantStack/Wan2.2-GGUF` + `City96/ComfyUI-GGUF`

---

### 方案 B：LTX-2.3（极速，低显存友好）

**官方节点**: `github.com/Lightricks/ComfyUI-LTXVideo` (4k⭐)

| 特性 | 值 |
|------|-----|
| 显存需求 | 低至 4GB（GGUF 版），推荐 8GB |
| 生成速度 | 极快（5-10秒 121帧 768x512） |
| 适用场景 | 快速预览、批量生产、低配硬件 |
| 模型大小 | ~2GB（FP8）/ ~1GB（GGUF） |

#### 安装

```bash
cd /Users/eric/Documents/comfy/ComfyUI/custom_nodes
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
# 或安装 Kijai 的 LTXV2 版
git clone https://github.com/kijai/ComfyUI-LTXVideo.git
```

---

### 方案 C：HunyuanVideo（腾讯开源，画质优秀）

**官方节点**: `github.com/kijai/ComfyUI-HunyuanVideoWrapper`

| 版本 | 来源 | 节点 |
|------|------|------|
| ComfyUI 原生 | Comfy-Org/HunyuanVideo_repackaged | 内置核心节点 |
| Kijai 版 | Kijai/HunyuanVideo_comfy | ComfyUI-HunyuanVideoWrapper |
| GGUF 版 | city96/HunyuanVideo-I2V-gguf | ComfyUI-GGUF |

HunyuanVideo 主打 **Image-to-Video**，2025年3月发布 I2V 模型后质量显著提升，适合漫画画面转视频。

---

## 3. 推荐迁移策略

### 短期（1-2周）：安装 Wan2.2 5B + GGUF 版

```
优先级:
  1. 更新 ComfyUI 到 Nightly（获取 Wan2.2 原生节点）
  2. 下载 Wan2.2-TI2V-5B（5B 混合模型）
  3. 下载 GGUF 量化版作为低显存备选
  4. 创建 Wan2.2 workflow JSON 替代现有 AnimateDiff workflow
```

### 中期（2-4周）：增加 LTX-2.3 作为快速通道

```
  - 安装 ComfyUI-LTXVideo 节点
  - 创建 "快速预览" 管线（替代 video_workflow_fast.json）
  - 低质量场景使用 LTX-2.3，高质量场景使用 Wan2.2
```

### 长期策略

```
  管线矩阵:
  ┌─────────────┬──────────────┬──────────────┐
  │             │  高质量输出   │  快速预览     │
  ├─────────────┼──────────────┼──────────────┤
  │ Text2Video  │ Wan2.2 14B   │ Wan2.2 5B    │
  │ Image2Video │ Wan2.2 14B   │ LTX-2.3      │
  │  或 Hunyuan │              │              │
  └─────────────┴──────────────┴──────────────┘
```

---

## 4. AIComics 集成改动清单

### 需要修改的文件

| 文件 | 改动内容 |
|------|----------|
| `Dockerfile.comfyui-sidecar` | 更新基础镜像或增加模型下载步骤 |
| `local_providers/comfyui/workflows/video_workflow.json` | 替换为 Wan2.2 workflow |
| `local_providers/comfyui/workflows/video_workflow_fast.json` | 替换为 LTX-2.3 或 Wan2.2 5B 快速版 |
| `local_providers/comfyui/model_requirements.json` | 更新模型依赖清单 |
| `docker-compose.local-providers.yml` | 更新 ComfyUI 环境变量（调整 GPU 设置） |
| `scripts/run_comfyui_sidecar.py` | 验证容器内 COMFYUI_ROOT 路径兼容性 |
| `state/comfyui_docker_extra_model_paths.yaml` | 确认额外模型路径 |

### 需要新增的 workflow JSON 模板

1. **`video_workflow_wan22.json`** — Wan2.2 5B TI2V 主管线
   - ComfyUI 原生节点: `WanVideoToVideo` / `WanImageToVideo`
   - 支持 Text-to-Video + Image-to-Video
2. **`video_workflow_fast_ltx.json`** — LTX-2.3 快速预览管线
   - 低步数 (4-8步)，低分辨率，快速出片

### 向后兼容

> AnimateDiff workflow 可以保留，通过配置选择使用哪条管线：
> - `comfyui/video_engine: animatediff`（旧，默认）
> - `comfyui/video_engine: wan22`（新）
> - `comfyui/video_engine: ltx23`（快速）

---

## 5. 验证步骤

```bash
# 1. 确认节点安装
ls /Users/eric/Documents/comfy/ComfyUI/custom_nodes/ | grep -iE "wan|ltx|hunyuan"

# 2. 确认模型已下载
ls /Users/eric/Documents/comfy/ComfyUI/models/diffusion_models/ | grep -iE "wan|ltx|hunyuan"

# 3. 启动 ComfyUI 验证节点加载
cd /Users/eric/Documents/comfy/ComfyUI && python main.py --cpu

# 4. 通过 API 测试 workflow 执行
# curl -X POST http://localhost:8188/prompt -d @workflow.json
```

---

## 6. 参考资源

| 资源 | 链接 |
|------|------|
| Wan2.2 官方 ComfyUI 文档 | https://docs.comfy.org/tutorials/video/wan/wan2_2 |
| LTXVideo 官方节点 | https://github.com/Lightricks/ComfyUI-LTXVideo |
| LTX-2.3 ComfyUI 教程 | https://aistudynow.com/ltx-2-3-in-comfyui-workflow/ |
| Kijai WanVideoWrapper | https://github.com/kijai/ComfyUI-WanVideoWrapper |
| Kijai HunyuanVideoWrapper | https://github.com/kijai/ComfyUI-HunyuanVideoWrapper |
| HunyuanVideo I2V 教程 | https://comfyui-wiki.com/en/tutorial/advanced/hunyuan-image-to-video-workflow-guide-and-example |
| Wan2.2 GGUF 量化版 | https://huggingface.co/collections/QuantStack/wan22-ggufs-6887ec891bdea453a35b95f3 |
| ComfyUI-GGUF 节点 | https://github.com/city96/ComfyUI-GGUF |
