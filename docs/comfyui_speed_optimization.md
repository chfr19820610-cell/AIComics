# ComfyUI AnimateDiff 推理速度优化方案

> 目标：推理速度提升 2x  
> 适用场景：AIComics `local_comfyui_video` provider（SD1.5 + AnimateDiff）  
> 创建日期：2026-07-19

---

## 1. 优化策略总览

| 策略 | 预期加速 | 质量影响 | 是否侵入性 |
|------|---------|---------|-----------|
| 降低分辨率 320×192 → 256×144 | ~1.4x | 预览可接受 | 无（新 workflow） |
| 减少帧数 16 → 12 | ~1.25x | 视频缩短 | 无（新 workflow） |
| 降低 fps 8 → 6 | 同等帧数视频更短 | 流畅度略降 | 无（新 workflow） |
| DPM++ 2M Karras (低步数质量更好) | ~1.15x (同等步数质量更高) | 与 Euler 等同 | 无（新 workflow） |
| 缩小 context_overlap 4→2 | ~1.1x | 边缘帧衔接略差 | 无（新 workflow） |
| 复用模型 / 不卸载 warmup | ~1.5x (后续推理) | 无 | 配置级 |
| **合计（叠加）** | **~2.0-2.5x** | 预览质量（后续可选切回生产） | — |

---

## 2. TeaCache 兼容性评估

### 结论：TeaCache 不适用于当前 SD1.5 + AnimateDiff 工作流

**TeaCache**（ComfyUI-TeaCache, welltop-cn/ComfyUI-TeaCache）是一个针对扩散模型推理的缓存加速方案，但**仅在以下模型架构上受支持**：

| 支持的模型 | 架构类型 | 预期加速 |
|-----------|---------|---------|
| FLUX / FLUX-Kontext | DiT | ~2x |
| HiDream-I1 (Full/Dev/Fast) | DiT | ~1.7-2x |
| HunyuanVideo | Video DiT | ~1.9x |
| LTX-Video | Video DiT | ~1.7x |
| Wan2.1 (T2V/I2V) | Video DiT | ~1.6-2.3x |
| CogVideoX | Video DiT | ~2x |
| Lumina-Image-2.0 | DiT | ~1.7x |

**不支持：** SD1.5 / SDXL 等 UNet 架构。TeaCache 通过注入 DiT transformer block 的 forward 函数实现缓存，而 SD1.5 使用的是 UNet + cross-attention 架构，不存在对应的 `double_blocks`/`single_blocks` 注入点。

### 何时可用 TeaCache

若后续项目迁移到 TeaCache 支持的模型（如 Wan2.1、LTX-Video），可在 workflow 中如下接入：

```
Load Diffusion Model → [TeaCache node] → ... → KSampler
```

推荐参数（基于官方文档）：
- 对于 Wan2.1 模型：`rel_l1_thresh: 0.2`, `start_percent: 0`, `end_percent: 1`
- 对于 HunyuanVideo：`rel_l1_thresh: 0.15`, `start_percent: 0`, `end_percent: 1`

---

## 3. `video_workflow_fast.json` — 快速版 Workflow

### 3.1 变更对比

| 参数 | 原版 (video_workflow.json) | 快速版 (video_workflow_fast.json) | 变更理由 |
|------|--------------------------|----------------------------------|---------|
| Width | 320 | **256** | 分辨率降低 80% → 像素数减少 56%，推理速度 ~1.4x |
| Height | 192 | **144** | 同上 |
| batch_size (帧数) | 16 | **12** | 减少 25% 帧数 → ~1.25x 加速 |
| steps | 20/4 * | **4** | 4 步 + DPM++ 比 4 步 Euler 质量更好 |
| cfg | 7.0/4.0 * | **4.0** | 低 cfg 配合低步数 |
| sampler_name | euler | **dpmpp_2m** | DPM++ 在低步数收敛更快，4 步质量优于 Euler |
| scheduler | normal | **karras** | Karras 噪声调度在低步数效果更好 |
| context_length | 16 | **12** | 对齐 batch_size |
| context_overlap | 4 | **2** | 减少 overlap → 降低上下文计算量 |
| frame_rate | 8 | **6** | 同等帧数视频时长更短 |
| denoise | 1.0 | 1.0 | 不变（text2video 保持全噪点） |

> * providers.yaml 中 steps=4, cfg=4 会注入覆盖 JSON 中的值。

### 3.2 快速版 workflow 文件位置

```
local_providers/comfyui/workflows/video_workflow_fast.json
```

可通过 `providers.yaml` 中切换 `workflow_path` 指向该文件，或将 `video_workflow.json` 的采样参数手工替换为快速版参数。

### 3.3 预计性能

| 项目 | 原版 (@ steps=20) | 原版 (@ steps=4) | 快速版 |
|------|------------------|-----------------|-------|
| 分辨率 | 320×192 (61,440 px) | 320×192 | **256×144 (36,864 px)** |
| 帧数 | 16 | 16 | **12** |
| 像素·帧数 (总负载) | 983,040 | 983,040 | **442,368 (55%)** |
| 采样器 | Euler / normal | Euler / normal | **DPM++ 2M Karras** |
| 上下文重叠 | 4 | 4 | **2** |
| **相对速度** | 1x | ~2.5x | **~3.0-3.5x** |

---

## 4. providers.yaml 快速配置推荐

### 4.1 使用快速版 workflow

```yaml
local_comfyui_video_fast:
  base_url: http://127.0.0.1:8188
  workflow_path: ../local_providers/comfyui/workflows/video_workflow_fast.json
  model_root: ../local_providers/comfyui/models
  model_manifest_path: ../local_providers/comfyui/model_requirements.json
  timeout_seconds: 60
  poll_timeout_seconds: 1800        # 快速版超时可缩短
  poll_interval_seconds: 2          # 更快轮询
  width: 256
  height: 144
  seed: 123456789
  steps: 4
  cfg: 4
  video_length: 12
  fps: 6
  output_prefix: aicomic_video_fast
  negative_prompt: low quality, blurry, watermark, flicker, distorted hands, text, subtitles, captions, Chinese characters, letters, logo
```

### 4.2 模型预热缓存（最大单项加速）

若 ComfyUI 服务长时间运行（非每次重启），可通过以下配置让模型常驻内存，后续推理加速 50%+：

- 设置 ComfyUI `--dont-upcast-attention` 启动参数（fp16 推理更快）
- 确保 `extra_model_options` 中 `--highvram` 或 `--normalvram`（不卸载模型）
- 首次提交一个 4 帧任务"预热"模型后，后续任务跳过加载时间

---

## 5. 其他加速技巧

| 技巧 | 说明 | 加速 |
|------|------|------|
| xformers / sdp 优化 | ComfyUI 默认启用，确保 `--force-sdp` 启动 | ~1.2x |
| fp16 模型 | SD1.5 的 fp16 版本省 ~50% VRAM 和 ~20% 推理时间 | ~1.2x |
| ADE 上下文 stride >1 | 跳过间隔帧的上下文处理（质量损失大） | ~1.5x+ |
| LoRA 融合 | 预融合 LoRA 到模型，避免每步动态加载 | ~1.1x |
| 降低 CFG 到 2-3 | 减少 CFG 可少跑一遍 UNet（负向引导） | ~1.8x |
| 使用 LCM LoRA | 配合 LCM 调度器，1-4 步出图（需额外下载 LoRA） | ~4x |

---

## 6. 长期优化路径

### 路线 A：当前 SD1.5 + AnimateDiff 优化（本文方案）
- 适用：现立即需要加速
- 限制：无法使用 TeaCache，但通过分辨率和帧数降级实现 2x 目标

### 路线 B：迁移到 TeaCache 兼容模型（推荐长期）
- Wan2.1-1.3B (+ TeaCache) → 约 2x 加速 + 更高画质
- LTX-Video (+ TeaCache) → 约 1.7x 加速 + 原生视频模型
- HunyuanVideo (+ TeaCache) → 约 1.9x 加速
- **优势**：TeaCache 提供 30-50% 额外加速，叠加分辨率/帧数优化可达 3x 以上

### 路线 C：模型编译（torch.compile）
- 在 TeaCache 节点包中也提供了 `CompileModel` 节点
- 首次推理慢（编译耗时），后续加速约 1.3x
- 兼容路线 B 中的 DiT 模型

---

## 7. 性能基准测试建议

验证加速效果时，请使用如下方法：

```bash
# 方法 1：通过 ComfyUI API 提交并计时
time curl -X POST http://127.0.0.1:8188/api/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": <workflow_json>}'

# 方法 2：使用 AIComics 命令行
hermes aicomic test video \
  --workflow video_workflow_fast.json \
  --prompt "test, comic style, action scene"

# 方法 3：从 ComfyUI 日志读取 timing 信息
# 日志中会输出每个节点执行耗时
```

---

## 8. 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `local_providers/comfyui/workflows/video_workflow.json` | ❌ 不改动 | 原版 workflow |
| `local_providers/comfyui/workflows/video_workflow_fast.json` | ✅ 新增 | 快速版 workflow (本文档) |
| `config/providers.yaml` | ❌ 不改动 | 现有配置 |
| `docs/comfyui_speed_optimization.md` | ✅ 新增 | 本文档 |
