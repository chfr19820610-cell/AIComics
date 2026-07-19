# Wan2.2 安装状态报告

> 生成日期: 2026-07-19 18:32
> 目标: 在 ComfyUI 中安装 Wan2.2 wrapper 节点 + 下载 5B 模型

---

## 1. WanVideoWrapper 节点安装

| 项目 | 状态 | 详情 |
|------|------|------|
| **仓库** | ✅ 已克隆 | `kijai/ComfyUI-WanVideoWrapper` (6.6k⭐) |
| **安装路径** | — | `/Users/eric/Documents/comfy/ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper/` |
| **Git reference** | — | main branch, 1439 commits, Apache 2.0 license |
| **Python 依赖** | ✅ 已安装 | 核心依赖: diffusers>=0.33.0, peft>=0.17.0, gguf>=0.17.1, accelerate>=1.2.1, opencv-python, scipy, sentencepiece, ftfy, einops, protobuf, pyloudnorm |

### 节点覆盖功能
- Wan2.1 / Wan2.2 Text-to-Video
- Wan2.1 / Wan2.2 Image-to-Video
- GGUF 量化模型支持
- VAE 编解码
- 多模型 (14B HIGH/LOW, 5B, Turbo 等)

---

## 2. 模型下载状态

### 5B 扩散模型 (主模型)

| 项目 | 状态 | 详情 |
|------|------|------|
| **模型文件** | ⏳ **下载中** | `wan2.2_ti2v_5B_fp16.safetensors` (~9.5GB) |
| **来源** | — | `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` |
| **下载 URL** | — | `https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors` |
| **目标路径** | — | `ComfyUI/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors` |
| **下载速度** | — | ~48 MB/s (预计剩余 ~4 分钟) |
| **如果下载中断** | — | 使用 `curl -L -o /Users/eric/Documents/comfy/ComfyUI/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"` |

### 额外所需模型 (尚未下载)

以下模型是运行 Wan2.2 的辅助模型，需要额外下载：

| 模型 | 来源 | 目标路径 | 大小 |
|------|------|----------|------|
| **VAE** | `Kijai/WanVideo_comfy` → `Wan2_2_VAE_bf16.safetensors` | `ComfyUI/models/vae/` | ~300MB |
| **Text Encoder** | `Kijai/WanVideo_comfy` → `umt5-xxl-enc-bf16.safetensors` | `ComfyUI/models/text_encoders/` | ~4GB |
| **CLIP** | *(可选, 用于 I2V)* | `ComfyUI/models/text_encoders/` | ~250MB |

---

## 3. 当前 ComfyUI 节点全景

| 节点 | 状态 | 用途 |
|------|------|------|
| ComfyUI-AnimateDiff-Evolved | ✅ 已安装 | 原视频管线核心 (SD1.5) |
| ComfyUI-VideoHelperSuite | ✅ 已安装 | 视频编解码辅助 |
| **ComfyUI-WanVideoWrapper** | ✅ **已安装** | **Wan2.2 视频生成** |
| comfyui-openai-api | ✅ 已安装 | OpenAI API 兼容层 |
| comfyui-zhipu | ✅ 已安装 | 智谱 API |
| LTXVideo | ❌ 未安装 | — |
| HunyuanVideo | ❌ 未安装 | — |

---

## 4. 下一步 (根据迁移方案)

1. ✅ **完成**: WanVideoWrapper 节点安装 + 依赖
2. ⏳ **进行中**: 下载 5B 扩散模型 (~9.5GB, ~48MB/s)
3. ❌ **待办**: 下载 VAE + Text Encoder 辅助模型
4. ❌ **待办**: 创建 Wan2.2 workflow JSON (替代 AnimateDiff workflow)
5. ❌ **待办**: 更新 `model_requirements.json` 和 `Dockerfile.comfyui-sidecar`
6. ❌ **待办**: 启动 ComfyUI 验证节点加载

---

## 5. 手动下载命令 (备用)

如果自动下载失败，可以在终端中手动执行以下命令：

```bash
# 5B 主模型 (~9.5GB)
# 如果本报告显示下载已完成请跳过
curl -L -o /Users/eric/Documents/comfy/ComfyUI/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"

# VAE (~300MB)
curl -L -o /Users/eric/Documents/comfy/ComfyUI/models/vae/Wan2_2_VAE_bf16.safetensors \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_2_VAE_bf16.safetensors"

# Text Encoder (~4GB)
curl -L -o /Users/eric/Documents/comfy/ComfyUI/models/text_encoders/umt5-xxl-enc-bf16.safetensors \
  "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors"
```
