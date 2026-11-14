# MiniMax-H3 视频生成在本机 M4 上的实测结论

> 2026-11-14 实测。硬件：Apple M4 / 32GB 统一内存 / macOS。

## 结论先行

**本机 ComfyUI 完全能生成 H3 真视频**（不是图片推拉）。实测产出
`h3_small_00001_.mp4`（512×768 / 24fps / 0.92s / 22 帧），三帧抽检可见
头部角度、身体重心、手部位置的连续变化。

## 为什么之前"跑不起来"

两个独立问题叠加：

1. **`video_workflow.json` / `video_workflow_fast.json` 是假的**
   它们的节点是 `KSampler` + `EmptyLatentImage` + `SaveImage` —— 这是**图片**
   工作流，只是文件名带 video。真正的 H3 节点在 `comfy_extras/nodes_minimax_h3.py`。

2. **内存不够**（M4 32GB 是硬约束）
   - DiT（`MiniMax-H3-fl2va-Q4_0.gguf`）加载后 **19.4 GB**
   - Video VAE **9.9 GB**
   - `H3AutoReserve` 额外 reserve **8 GB**
   - 合计已超 32GB → **swap 爆到 37 GB / 37.9 GB**，free 仅 87 MB
   - 后果：每步 224 秒（4 分钟），4 步 **21 分 42 秒**

## 正确的最小可用 workflow（API 格式）

```json
{
  "1": {"class_type": "H3ModelLoaderAny", "inputs": {"model_name": "MiniMax-H3-fl2va-Q4_0.gguf"}},
  "2": {"class_type": "H3ClipLoaderAny", "inputs": {"clip_name": "MiniMax-H3-encoder-Q4_K_M.gguf", "type": "stable_diffusion"}},
  "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
  "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
  "5": {"class_type": "LoadImage", "inputs": {"image": "你的首帧.png"}},
  "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
      "clip": ["2", 0], "vae": ["3", 0], "prompt": "英文提示词",
      "width": 512, "height": 768, "length": 22, "first_frame": ["5", 0]}},
  "7": {"class_type": "H3SigmasByName", "inputs": {"model": ["1",0], "scheduler": "simple", "steps": 4, "denoise": 1.0}},
  "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
  "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}},
  "10": {"class_type": "BasicGuider", "inputs": {"model": ["1",0], "conditioning": ["6",0]}},
  "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9",0], "guider": ["10",0], "sampler": ["8",0], "sigmas": ["7",0], "latent_image": ["6",1]}},
  "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11",0], "vae": ["3",0]}},
  "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11",0], "vae": ["4",0]}},
  "14": {"class_type": "CreateVideo", "inputs": {"images": ["12",0], "fps": 24.0}},
  "15": {"class_type": "SaveVideo", "inputs": {"video": ["14",0], "filename_prefix": "h3", "format": "mp4"}}
}
```

## 三个坑（实测踩过）

| 坑 | 现象 | 修复 |
|---|---|---|
| 图片放错目录 | `Invalid image file` | input 是 `state/comfyui_real_input`，**不是** `ComfyUI/input` |
| 扩展名骗人 | 同样报 Invalid | 用 PIL 显式 `convert('RGB').save(..., format='PNG')` |
| 旧任务 swap 不释放 | 新任务"0 models unloaded"后又 reserve 8GB | **必须重启 ComfyUI**（free 从 86MB → 21.3GB） |

## 参数限制（来自节点定义）

- `width` / `height`：必须是 **32 的倍数**
- `length`：帧数，按 **17k+5** 网格，`124` ≈ 5 秒；22 = 0.92 秒
- `H3SamplerByName` 是 `forceInput` 型节点，API 里用 `KSamplerSelect` 代替
- 有效帧数：[22, 39, 56, 107, 243, 362]

## 速度现实（M4 / 32GB）

| 配置 | 每步耗时 | 总耗时 |
|---|---|---|
| 512×768 / 22帧 / 4步 | ~224s | **21m42s** |
| 768×1152 / 39帧 / 8步 | 未完成（swap 爆） | — |

**要做 12 集 × 6 镜 × 5 秒 ≈ 360 秒视频**：
`360 / 0.92 × 21.7 分钟 ≈ 141 小时` —— **不可行**。

## 三条可行路线

1. **MiniMax 官方 API**（ComfyUI 自带 `ComfyCloudMiniMaxH3*` 节点）
   按秒计费，几秒出片。适合做成品。

2. **h3.c-int8**（`Shedrackeze002/h3.c-int8`，antirez 的 h3.c Metal 引擎 fork）
   int8 峰值内存 **16.8 GB**，官方 README 称"fits a 32GB machine with room to spare"。
   需要 build（`make -j8`）+ 下载 int8 DiT(19.5GB) + text encoder(62GB)。
   **本机现有是 int4 GGUF，不直接兼容**。

3. **换更轻量的本地模型**
   - Wan 2.2 TI2V 5B（GGUF，社区有 Mac 实测）
   - LTX-Video MLX（`tanis2000/comfyui-ltx2-mlx`）

## 本机 H3 资产盘点

| 组件 | 路径 | 大小 |
|---|---|---|
| DiT | `models/fl2va/MiniMax-H3-fl2va-Q4_0.gguf` | 18G |
| Text encoder | `models/text_encoders/MiniMax-H3-encoder-Q4_K_M.gguf` | 18G |
| Video VAE | `models/vae/minimax_h3_video_vae_fp16.safetensors` | 4.8G |
| Audio VAE | `models/vae/minimax_h3_audio_vae_fp32.safetensors` | 577M |
| Turbo LoRA ×5 | `ComfyUI/models/loras/minimax_h3_turbo_*` | 592M each |

⚠️ `ComfyUI/models/{text_encoders,vae}/` 下有几个 **113–119 字节的坏文件**，
真正可用的在 `models/` 目录（通过 `aicomic_extra_model_paths.yaml` 挂载）。
