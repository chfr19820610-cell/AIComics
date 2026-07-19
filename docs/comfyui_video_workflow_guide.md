# ComfyUI 视频工作流指南：让 AIComics 输出动态视频帧

> **目标：** 取代 AIComics 当前只做 Ken Burns 缩放的静态帧方案，改为使用 ComfyUI 生成真正有动态效果的视频帧。
> **适用风格：** Painterly 3D Noir → Hybrid Comic Pop

---

## 目录

1. [现状分析](#1-现状分析)
2. [ComfyUI 视频生成方案选型](#2-comfyui-视频生成方案选型)
3. [方案 A：AnimateDiff（已就绪，推荐）](#3-方案-aanimatediff已就绪推荐)
4. [方案 B：Stable Video Diffusion (SVD)（已就绪）](#4-方案-bstable-video-diffusion-svd已就绪)
5. [方案 C：Frame-by-Frame + 帧插值（进阶）](#5-方案-cframe-by-frame--帧插值进阶)
6. [方案 D：Wan2.1 原生视频模型（未安装）](#6-方案-dwan21-原生视频模型未安装)
7. [AIComics Providers 集成指南](#7-aicomcs-providers-集成指南)
8. [API 格式 Workflow JSON 详解](#8-api-格式-workflow-json-详解)
9. [性能与资源建议](#9-性能与资源建议)
10. [故障排查](#10-故障排查)
11. [附录：节点参考](#11-附录节点参考)

---

## 1. 现状分析

### 1.1 当前 AIComics 视频流水线

```
配置路径: local_providers/comfyui/workflows/
当前文件:
  ✅ image_workflow.json          → 静态图生成（不可用于视频）
  ✅ image_workflow_live_smoke.json → 静态图测试
  ❌ video_workflow.json          → 不存在！（需要创建）
```

### 1.2 现有 ComfyUI 安装

```
安装路径: /Users/eric/Documents/comfy/ComfyUI/
已安装的视频相关自定义节点:
  ✅ ComfyUI-AnimateDiff-Evolved  → 动画/视频生成
  ✅ ComfyUI-VideoHelperSuite     → 视频编解码/合并

已安装的视频相关模型:
  ✅ animatediff_models/mm_sd_v15_v2.ckpt   → AnimateDiff 运动模型 (SD1.5)
  ✅ checkpoints/svd.safetensors           → Stable Video Diffusion
  ✅ checkpoints/anythingV5.safetensors    → SD1.5 checkpoint (兼容 AD)
  ✅ checkpoints/animagine-xl-4.0-opt.safetensors → SDXL checkpoint
  ❌ diffusion_models/           → 为空（可放 Wan2.1/Hunyuan）
  ❌ frame_interpolation/        → 为空（可放 RIFE/FILM）

已配的 providers.yaml video 配置:
  width: 320, height: 192, steps: 4, cfg: 4
  video_length: 9 frames, fps: 8
```

### 1.3 当前 `image_workflow.json` 结构（纯静态图）

```json
{
  "3":  { "class_type": "KSampler", ... },
  "4":  { "class_type": "CheckpointLoaderSimple", ... },
  "5":  { "class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1} },
  "6":  { "class_type": "CLIPTextEncode", ... },
  "7":  { "class_type": "CLIPTextEncode", ... },
  "8":  { "class_type": "VAEDecode", ... },
  "9":  { "class_type": "SaveImage", ... }
}
```

核心问题：`batch_size: 1` 且没有运动模型注入 — 输出只有 1 帧静态图。

---

## 2. ComfyUI 视频生成方案选型

| 方案 | 所需安装 | 已就绪？ | 动态效果 | 风格适配 | 适合 AIComics？ |
|------|---------|---------|---------|---------|----------------|
| **A. AnimateDiff** | custom node + motion model | ✅ | 强（角色/镜头运动） | 好（SD1.5/SDXL） | **⭐ 首选** |
| **B. SVD** | checkpoint 已有 | ✅ | 中（图像→视频） | 一般（偏向真实） | 备选，适合 I2V |
| **C. Frame-by-Frame + Interp.** | frame_interp 模型 | ⚠️ 无 | 灵活 | 最好（完全控制） | 进阶，需要 LoRA |
| **D. Wan2.1** | 扩散模型 + 自定义节点 | ❌ | 最强 | 优秀 | 未来升级目标 |

### 决策树

```
需要什么动态效果？
├── 角色微动（呼吸、眨眼、头发飘动）
│   └── → AnimateDiff (方案 A)
├── 镜头运动（推进、平移、旋转）
│   └── → AnimateDiff + CameraCtrl (方案 A 进阶)
├── 静态图变视频（输入参考图，输出动态镜头）
│   └── → SVD (方案 B) or AnimateDiff img2video
├── 逐帧精确控制（Comic Pop 风格卡点）
│   └── → Frame-by-Frame + 插值 (方案 C)
└── 高质量端到端视频生成
    └── → Wan2.1 (方案 D，需要额外安装)
```

---

## 3. 方案 A：AnimateDiff（已就绪，推荐）

### 3.1 核心节点链

```
CheckpointLoaderSimple  ──────┐
                              ├─→ KSampler ─→ VAEDecode ─→ VHS_VideoCombine (输出 MP4)
LoadAnimateDiffModel ─────────┤
AnimateDiffLoader (Context) ───┘
CLIPTextEncode (positive) ────→ KSampler.positive
CLIPTextEncode (negative) ────→ KSampler.negative
EmptyLatentImage ─────────────→ KSampler.latent_image (batch_size > 1!)
```

### 3.2 关键参数

- **`EmptyLatentImage.batch_size`** = 帧数（推荐 16–32 帧）
- **`ADE_LoadAnimateDiffModel.model_name`** = `mm_sd_v15_v2.ckpt`
- **`ADE_UseEvolvedSampling`** — 替代标准 KSampler，插入 AnimateDiff context
- **`ADE_AnimateDiffLoaderWithContext`** — 上下文长度控制（通常 16 帧）

### 3.3 最小化 API Workflow JSON（`video_workflow.json`）

这是 `local_comfyui_video` provider 可执行的 API 格式 JSON 模板。

```json
{
  "1": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "anythingV5.safetensors"
    }
  },
  "2": {
    "class_type": "ADE_LoadAnimateDiffModel",
    "inputs": {
      "model_name": "mm_sd_v15_v2.ckpt"
    }
  },
  "3": {
    "class_type": "ADE_AnimateDiffLoaderWithContext",
    "inputs": {
      "model": ["2", 0],
      "context_options": ["12", 0],
      "latent_size": ["4", 0]
    }
  },
  "4": {
    "class_type": "EmptyLatentImage",
    "inputs": {
      "width": 320,
      "height": 192,
      "batch_size": 16
    }
  },
  "5": {
    "class_type": "ADE_UseEvolvedSampling",
    "inputs": {
      "model": ["1", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["4", 0],
      "animatediff": ["3", 0],
      "seed": 123456789,
      "steps": 20,
      "cfg": 7.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0
    }
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "masterpiece, best quality, comic book style, dynamic action pose, dramatic lighting, ink lines, bold colors, hybrid comic pop style, vibrant",
      "clip": ["1", 1]
    }
  },
  "7": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, ugly, deformed, disfigured, poorly drawn",
      "clip": ["1", 1]
    }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["5", 0],
      "vae": ["1", 2]
    }
  },
  "9": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "frame_rate": 8,
      "loop_count": 1,
      "filename_prefix": "aicomic_video",
      "pingpong": false,
      "format": "video/h264-mp4",
      "images": ["8", 0]
    }
  },
  "12": {
    "class_type": "ADE_LoopedUniformContextOptions",
    "inputs": {
      "context_length": 16,
      "context_stride": 1,
      "context_overlap": 4,
      "fuse_method": "flat",
      "use_on_equal_length": true
    }
  }
}
```

> ⚠️ **注意：** 以上 JSON 中的节点 ID（`1`, `2`, `3`, ...）在提交前可能需要根据本地 ComfyUI 的节点 schema 调整。生产用的 JSON 应从 ComfyUI 界面「Export (API Format)」导出后注入参数。

### 3.4 参数注入映射（`providers.yaml` vs workflow）

| providers.yaml 字段 | Workflow 节点 | 说明 |
|-------------------|---------------|------|
| `width` | `EmptyLatentImage.width` | 宽（建议 320–512） |
| `height` | `EmptyLatentImage.height` | 高（建议 192–320） |
| `seed` | `ADE_UseEvolvedSampling.seed` | 随机种子 |
| `steps` | `ADE_UseEvolvedSampling.steps` | 采样步数 |
| `cfg` | `ADE_UseEvolvedSampling.cfg` | CFG 强度 |
| `video_length` | `EmptyLatentImage.batch_size` | 帧数 |
| `fps` | `VHS_VideoCombine.frame_rate` | 输出帧率 |
| `output_prefix` | `VHS_VideoCombine.filename_prefix` | 文件名前缀 |
| `negative_prompt` | `CLIPTextEncode` (negative).text | 负面提示词 |

### 3.5 AnimateDiff 调优技巧

| 需求 | 调整 |
|------|------|
| **更流畅的运动** | 增加 `batch_size`（24–32）+ 降低 `fps`（8） |
| **更稳定的角色** | 使用 ControlNet OpenPose 作为帧间约束 |
| **镜头推进/平移** | 添加 `ADE_CameraCtrlPoseBasic` 节点 + 运动 LoRA |
| **更快的生成** | 降低 `steps` 到 8–10（配合 LCM/蒸馏模型） |
| **Hybrid Comic Pop 风格** | 使用 Comic/Anime 风格 LoRA + 高 CFG (7–10) |
| **循环动画** | `VHS_VideoCombine.loop_count=0, pingpong=true` |

---

## 4. 方案 B：Stable Video Diffusion (SVD)（已就绪）

### 4.1 SVD 核心节点链

```
LoadImage (输入参考帧)
  ↓
SVD_ImageToVideo_Conditioning
  ↓
KSampler (使用 svd.safetensors checkpoint)
  ↓
VAEDecode → VHS_VideoCombine
```

### 4.2 SVD API Workflow 模板

```json
{
  "1": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "svd.safetensors"
    }
  },
  "2": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "input_frame.png"
    }
  },
  "3": {
    "class_type": "SVD_ImageToVideo_Conditioning",
    "inputs": {
      "video_frames": 14,
      "motion_bucket_id": 127,
      "fps": 6,
      "augmentation_level": 0.0,
      "clip_vision_config": ["1", 1],
      "images": ["2", 0]
    }
  },
  "4": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 123456789,
      "steps": 25,
      "cfg": 3.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0,
      "model": ["1", 0],
      "positive": ["3", 0],
      "negative": ["3", 1],
      "latent_image": ["3", 2]
    }
  },
  "5": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["4", 0],
      "vae": ["1", 2]
    }
  },
  "6": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "frame_rate": 6,
      "loop_count": 1,
      "filename_prefix": "aicomic_svd",
      "format": "video/h264-mp4",
      "images": ["5", 0]
    }
  }
}
```

### 4.3 SVD 适用场景

- **图像→视频**：输入 AIComics 生成的静态帧 → 输出简短视频
- **镜头运动**：motion_bucket_id（0–255）控制运动强度
- **短片段（≤14帧）**：SVD 原生只支持 14 帧
- ⚠️ SVD 不擅长剧烈运动，更适合平滑过渡

---

## 5. 方案 C：Frame-by-Frame + 帧插值（进阶）

### 5.1 流水线架构

```
Batch Prompt Gen → Frame-by-Frame KSampler (with ControlNet) → Frame Interpolation → VideoCombine
     ↑                     ↑                                         ↑
 分帧提示词           种子一致 + ControlNet 深度约束             RIFE/FILM 模型
```

这种方式适合 **Comic Pop 风格**的精确卡点动画。

### 5.2 需要安装的模型

```bash
# RIFE 帧插值模型
cd /Users/eric/Documents/comfy/ComfyUI/models/frame_interpolation
wget https://huggingface.co/John6666/RIFE-model/resolve/main/flownet.pkl
# 或安装 ComfyUI-Frame-Interpolation 自定义节点
comfy node install ComfyUI-Frame-Interpolation
```

### 5.3 关键技巧

| 技巧 | 说明 |
|------|------|
| **种子固定** | 所有帧使用同一 seed（或相邻 seed）保证一致性 |
| **ControlNet** | Canny/Depth 约束保持角色轮廓稳定 |
| **提示词渐进** | 帧间提示词微调（如 "hand raising, frame 1" → "... frame 5"） |
| **帧插值** | 4 帧 → RIFE 插值 → 30 帧 → 60fps 输出 |

---

## 6. 方案 D：Wan2.1 原生视频模型（未安装）

### 6.1 安装步骤

```bash
# 1. 安装自定义节点
comfy node install ComfyUI-WanVideoWrapper
comfy node install comfyui-wan

# 2. 下载模型（放 diffusion_models/）
comfy model download \
  --url "https://huggingface.co/Wan-AI/Wan2.1-T2V-14B/resolve/main/wan2.1_t2v_14B_fp16.safetensors" \
  --relative-path models/diffusion_models

# 3. 下载 VAE 和 CLIP
comfy model download \
  --url "https://huggingface.co/Wan-AI/Wan2.1-T2V-14B/resolve/main/wan2.1_vae.safetensors" \
  --relative-path models/vae
```

### 6.2 适用场景

- 端到端文生视频（无需中间帧）
- 高质量长视频（60 帧以上）
- 需要 **14GB+ VRAM** 或 Apple Silicon 32GB+ Unified Memory

---

## 7. AIComics Providers 集成指南

### 7.1 当前 providers.yaml 配置

```yaml
local_comfyui_video:
  base_url: http://127.0.0.1:8188
  workflow_path: ../local_providers/comfyui/workflows/video_workflow.json
  model_root: ../local_providers/comfyui/models
  width: 320
  height: 192
  seed: 123456789
  steps: 4
  cfg: 4
  video_length: 9
  fps: 8
  output_prefix: aicomic_video
  negative_prompt: low quality, blurry, watermark, flicker, ...
```

### 7.2 参数注入流程（`local_adapter.py`）

1. 加载 `video_workflow.json`
2. 从 `providers.yaml` 读取 video 参数
3. 注入到对应节点：
   - `EmptyLatentImage.width` / `.height` / `.batch_size`
   - `KSampler` / `ADE_UseEvolvedSampling` 的 seed/steps/cfg
   - `CLIPTextEncode` 的提示词文本
   - `VHS_VideoCombine` 的 frame_rate
4. 通过 `POST /api/prompt` 提交到 ComfyUI
5. 轮询 `/history/{prompt_id}` 获取输出
6. 调用 `VHS_VideoCombine` 的输出路径 → 下载 MP4

### 7.3 集成注意事项

| 问题 | 解决方案 |
|------|---------|
| Workflow 中没有 `ADE_UseEvolvedSampling` | 用标准 `KSampler` + `ADE_ApplyAnimateDiffModel` 替代 |
| batch_size 需要 ≥2 | `video_length` 必须 > 1 |
| 首次运行需 warmup | 先提交一个 4 帧低步数任务 "预热" 模型 |
| 超时 | `poll_timeout_seconds: 7200`（视频比图片慢很多） |

### 7.4 推荐 providers.yaml 视频参数（Hybrid Comic Pop）

```yaml
local_comfyui_video:
  base_url: http://127.0.0.1:8188
  workflow_path: ../local_providers/comfyui/workflows/video_workflow.json
  model_root: ../local_providers/comfyui/models
  model_manifest_path: ../local_providers/comfyui/model_requirements.json
  timeout_seconds: 60
  poll_timeout_seconds: 7200
  poll_interval_seconds: 5
  width: 512
  height: 288
  seed: -1               # -1 = 自动随机
  steps: 20
  cfg: 7.5
  video_length: 24       # 24 帧 ≈ 3 秒 @ 8fps
  fps: 8
  output_prefix: aicomic_video
  negative_prompt: low quality, blurry, watermark, flicker, distorted hands, text, subtitles, captions, Chinese characters, letters, logo, bad anatomy, bad proportions, disfigured, deformed, ugly, jpeg artifacts
```

---

## 8. API 格式 Workflow JSON 详解

### 8.1 编辑格式 vs API 格式

```
编辑格式（不可提交）:     API 格式（可提交）:
{                       {
  "nodes": [...],         "3": { "class_type": "KSampler", "inputs": {...} },
  "links": [...],         "4": { "class_type": "CheckpointLoaderSimple", "inputs": {...} },
  "groups": [...],         ...
  "config": {...}        }
}
```

**如何获得 API 格式：**
1. 在 ComfyUI 界面打开 workflow
2. 菜单 → **Workflow → Export (API Format)**
3. 保存为 `.json` → 放到 `local_providers/comfyui/workflows/`

### 8.2 可注入的参数模式

| 参数模式 | 对应节点类型 | 注入方式 |
|---------|-------------|---------|
| `prompt` / `positive_prompt` | `CLIPTextEncode.text` | 追踪 positive 输入 |
| `negative_prompt` | `CLIPTextEncode.text` | 追踪 negative 输入 |
| `seed` | `*Sampler.seed` | 直接替换 |
| `steps` | `*Sampler.steps` | 直接替换 |
| `cfg` | `*Sampler.cfg` | 直接替换 |
| `width` / `height` | `Empty*Image.width/height` | 必须 8 的倍数 |
| `video_length` | `Empty*.batch_size` | 帧数 |
| `fps` | `VHS_VideoCombine.frame_rate` | 输出帧率 |

### 8.3 视频工作流的 common node types

| class_type | 来源 | 作用 |
|-----------|------|------|
| `ADE_LoadAnimateDiffModel` | AnimateDiff Evolved | 加载运动模型 |
| `ADE_AnimateDiffLoaderWithContext` | AnimateDiff Evolved | 配置上下文/滑动窗口 |
| `ADE_UseEvolvedSampling` | AnimateDiff Evolved | 演化采样（替代 KSampler） |
| `ADE_LoopedUniformContextOptions` | AnimateDiff Evolved | 循环上下文选项 |
| `VHS_VideoCombine` | VideoHelperSuite | 输出 MP4/GIF |
| `VHS_LoadVideo` | VideoHelperSuite | 输入视频（video2video） |
| `VHS_VAEEncodeBatched` | VideoHelperSuite | 批量 VAE 编码 |
| `VHS_VAEDecodeBatched` | VideoHelperSuite | 批量 VAE 解码 |

---

## 9. 性能与资源建议

### 9.1 当前硬件（Apple Silicon Mac）

| 配置 | 建议 |
|------|------|
| M1/M2/M3/M4 (16GB) | AnimateDiff SD1.5 16帧 OK；SVD 14帧 OK |
| M2/M3/M4 (32GB+) | AnimateDiff SDXL 可能可行；Wan2.1 待测试 |
| 分辨率 | 320×192（现有配置）→ 可尝试 512×288 |
| 帧数 | 16-24 帧 → 8fps → 2-3 秒视频 |

### 9.2 速度优化技巧

| 技巧 | 效果 |
|------|------|
| 使用 `steps: 4-8`（LCM） | 快 3-5x |
| 降低分辨率到 320×192 | 快 2x |
| 减少 batch_size 到 8-12 | 省 VRAM |
| 首次推理后不卸载模型 | 后续快 50% |
| 使用 fp16 模型 | 省 50% VRAM |

### 9.3 推荐的视频参数组合

```yaml
# 快速迭代（草稿用）
fast_draft:
  steps: 4
  cfg: 4
  video_length: 8
  fps: 8
  width: 320
  height: 192

# 生产用（Hybrid Comic Pop）
production:
  steps: 20
  cfg: 7.5
  video_length: 24
  fps: 10
  width: 512
  height: 288
```

---

## 10. 故障排查

### 10.1 AnimateDiff 常见问题

| 症状 | 原因 | 解决 |
|------|------|------|
| `Class type not found: ADE_LoadAnimateDiffModel` | 未安装自定义节点 | `comfy node install comfyui-animatediff-evolved` |
| `mm_sd_v15_v2.ckpt not found` | 运动模型缺失 | 手动下载到 `models/animatediff_models/` |
| 输出只有一帧 | `batch_size=1` | 设置 `video_length ≥ 16` |
| 画面闪烁 | context 太小 | 增大 `context_length` 到 16，增加 `context_overlap` |
| 人物变形 | 模型不兼容 | 使用 SD1.5 基础模型（如 anythingV5） |
| OOM (out of memory) | 分辨率太高 | 降低 width/height，降低 batch_size |

### 10.2 视频输出问题

| 症状 | 原因 | 解决 |
|------|------|------|
| `VHS_VideoCombine` 输出为空 | ffmpeg 未安装 | `brew install ffmpeg`（macOS） |
| MP4 无法播放 | 编码格式问题 | 设置 `format: video/h264-mp4` |
| 视频太短 | `video_length` 太小 + fps 太高 | 增加帧数或降低 fps |
| AnimateDiff 不生效 | KSampler 不是 ADE 版本 | 用 `ADE_UseEvolvedSampling` 替代 |

### 10.3 排查命令

```bash
# 检查 ComfyUI 服务状态
curl -s http://127.0.0.1:8188/system_stats | python3 -m json.tool | grep -E "device|memory"

# 检查节点是否安装（AnimateDiff）
curl -s http://127.0.0.1:8188/object_info | python3 -c "import json,sys;d=json.load(sys.stdin);print([k for k in d if 'ADE' in k or 'AnimateDiff' in k])"

# 检查 VideoHelperSuite
curl -s http://127.0.0.1:8188/object_info | python3 -c "import json,sys;d=json.load(sys.stdin);print([k for k in d if 'VHS' in k])"

# 查看队列
curl -s http://127.0.0.1:8188/queue

# 测试生成（4 帧快速测试）
python3 -c "
import json, urllib.request
wf = json.load(open('local_providers/comfyui/workflows/video_workflow.json'))
# 注入 4 帧快速参数
for nid, node in wf.items():
    if node['class_type'] in ('EmptyLatentImage', 'ADE_EmptyLatentImageLarge'):
        node['inputs']['batch_size'] = 4
req = urllib.request.Request(
    'http://127.0.0.1:8188/api/prompt',
    data=json.dumps({'prompt': wf}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(req).read())
print('Prompt ID:', resp.get('prompt_id'))
"
```

---

## 11. 附录：节点参考

### 11.1 AnimateDiff Evolved Node Class Types（按功能分组）

**加载与注入：**
| class_type | 说明 |
|-----------|------|
| `ADE_LoadAnimateDiffModel` | 加载运动模型（推荐） |
| `ADE_AnimateDiffLoaderWithContext` | 加载 + 上下文配置（推荐） |
| `ADE_ApplyAnimateDiffModel` | 应用运动模型到基础模型 |
| `ADE_ApplyAnimateDiffModelSimple` | 简化版注入 |

**采样：**
| class_type | 说明 |
|-----------|------|
| `ADE_UseEvolvedSampling` | 增强采样节点（替代 KSampler） |
| `ADE_AnimateDiffSamplingSettings` | 采样设置（FreeInit 等） |

**上下文控制：**
| class_type | 说明 |
|-----------|------|
| `ADE_LoopedUniformContextOptions` | 循环均匀上下文 |
| `ADE_StandardUniformContextOptions` | 标准均匀上下文 |
| `ADE_StandardStaticContextOptions` | 标准静态上下文 |
| `ADE_BatchedContextOptions` | 批处理上下文 |

**关键帧：**
| class_type | 说明 |
|-----------|------|
| `ADE_AnimateDiffKeyframe` | 关键帧控制 |
| `ADE_LoraHookKeyframe` | LoRA 关键帧 |
| `ADE_CustomCFGKeyframe` | CFG 关键帧 |

**LoRA：**
| class_type | 说明 |
|-----------|------|
| `ADE_AnimateDiffLoRALoader` | 运动 LoRA 加载器 |

**相机控制（CameraCtrl）：**
| class_type | 说明 |
|-----------|------|
| `ADE_CameraPoseBasic` | 基本相机姿态 |
| `ADE_CameraPoseCombo` | 组合相机姿态 |
| `ADE_CameraPoseAdvanced` | 高级相机姿态 |
| `ADE_CameraManualPoseAppend` | 手动附加姿态帧 |

### 11.2 VideoHelperSuite Node Class Types

**输出：**
| class_type | 说明 |
|-----------|------|
| `VHS_VideoCombine` | 合并帧为视频/动画（关键输出节点） |

**输入/加载：**
| class_type | 说明 |
|-----------|------|
| `VHS_LoadVideo` | 上传加载视频 |
| `VHS_LoadVideoPath` | 路径加载视频 |
| `VHS_LoadImages` | 上传加载图片序列 |
| `VHS_LoadImagesPath` | 路径加载图片序列 |

**批量处理：**
| class_type | 说明 |
|-----------|------|
| `VHS_VAEEncodeBatched` | 批量 VAE 编码 |
| `VHS_VAEDecodeBatched` | 批量 VAE 解码 |
| `VHS_SplitLatents/Images/Masks` | 拆分批次 |
| `VHS_MergeLatents/Images/Masks` | 合并批次 |
| `VHS_SelectEveryNth*` | 抽样选择 |

---

## 快速开始清单

- [ ] 确认 ComfyUI 服务运行：`curl http://127.0.0.1:8188/system_stats`
- [ ] 确认 AnimateDiff 节点已安装：`comfy node show installed | grep AnimateDiff`
- [ ] 确认视频模型存在：`ls /Users/eric/Documents/comfy/ComfyUI/models/animatediff_models/`
- [ ] 创建 `video_workflow.json`（参考 §3.3 模板）
- [ ] 在 ComfyUI 界面加载 workflow，保存 API 格式
- [ ] 修改 `providers.yaml` 中 `local_comfyui_video` 参数
- [ ] 运行 live smoke 测试：`hermes aicomic provider live-smoke --providers local_comfyui_video`
- [ ] 检查输出 MP4 是否在 `state/comfyui_real_output/` 下

---

> **文档版本:** v1.0  
> **编写日期:** 2026-07-19  
> **适用项目:** AIComics (Painterly 3D Noir → Hybrid Comic Pop)  
> **ComfyUI 路径:** `/Users/eric/Documents/comfy/ComfyUI/`  
> **AnimateDiff 版本:** Evolved (已安装)  
> **VideoHelperSuite:** 已安装
