# 本地 Provider 启用指南（ComfyUI / Piper 中文 TTS）

> 2026-11-13 实测通过。目标：让 `local_comfyui_image` / `local_comfyui_video` / `local_piper_tts`
> 三个 provider 从 `setup_required` 变成 `ready`，把 `production-risk-register` 清零。

## 0. 一句话验收

```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main production-risk-register
# 期望：status=ready_for_production  risk_count=0  blocking_count=0
```

## 1. ComfyUI（图像 + 视频）

### 1.1 启动

```bash
PYTHONPATH=src .venv/bin/python scripts/manage_comfyui_service.py start --wait-timeout-seconds 180
# 期望：status_after=ready, base_url=http://127.0.0.1:8188
```

验证：`curl -s http://127.0.0.1:8188/system_stats`

### 1.2 模型清单必须是 `providers` 结构

文件：`local_providers/comfyui_runtime/model_requirements.json`

```json
{
  "providers": {
    "local_comfyui_image":      [{"filename": "sd_xl_base_1.0.safetensors", "subdir": "checkpoints"}],
    "local_comfyui_video":      [{"filename": "minimax_h3_fl2va_pruned_int4_convrot.safetensors", "subdir": "diffusion_models"}],
    "local_comfyui_video_fast": [{"filename": "minimax_h3_fl2va_pruned_int4_convrot.safetensors", "subdir": "diffusion_models"}]
  }
}
```

> ⚠️ 旧的扁平格式 `{"checkpoints": [...], "diffusion_models": [...]}` **不会被读取**，
> 会导致 `No model requirements for provider`。2026-11-13 已修正。
>
> `subdir` 相对 `model_root`（默认 `local_providers/comfyui_runtime/ComfyUI/models`）。

## 2. Piper 中文 TTS

### 2.1 为什么中文要额外依赖

piper 的 `zh_CN` 语音走 `PhonemeType.PINYIN`，需要 `g2pw` 做多音字消歧；
而 `g2pw` 通过 `transformers` 加载 BERT，**间接需要 torch**。英文/欧洲语音不需要。

```bash
.venv/bin/python -m pip install -e ".[local-tts-zh]"   # 含 torch，约 +1GB
```

### 2.2 下载语音模型（许可证必须明确）

```bash
mkdir -p local_providers/piper/models
BASE=https://hf-mirror.com/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium
curl -L -o local_providers/piper/models/zh_CN-chaowen-medium.onnx      "$BASE/zh_CN-chaowen-medium.onnx"
curl -L -o local_providers/piper/models/zh_CN-chaowen-medium.onnx.json "$BASE/zh_CN-chaowen-medium.onnx.json"
```

**语音选择依据（商用许可）**

| 语音 | 数据集许可证 | 可否商用 |
|---|---|---|
| `zh_CN/chaowen/medium` | **CC0**（公有领域） | ✅ 可，无署名要求 |
| `zh_CN/huayan/medium` | Unknown | ❌ 不可，无法通过商用审查 |

### 2.3 模型卡与许可审批

`local_providers/piper/models/MODEL_CARD` 里必须有 `* License: CC0` 这样的行——
`inspect_piper_license()` 只解析这一行；缺失会判 `license_status=review_required`。
同目录的 `LICENSE_REVIEW.json` 提供 `production_use_approved` 审批位。

### 2.4 验收

```bash
echo "这是一段测试旁白。" | PYTHONPATH=src .venv/bin/python scripts/run_local_piper.py \
  --model local_providers/piper/models/zh_CN-chaowen-medium.onnx \
  --output_file /tmp/piper_test.wav
# 期望：/tmp/piper_test.wav 约 200KB，6 秒左右，22050Hz mono
```

## 3. 两个已修的坑（踩过，别再踩）

1. **`model_root_is_file` 判断反转**（`local_adapter.py`）
   原代码 `elif not model_root_is_file: error="must be a directory"` —— 目录（`is_file=False`）
   必然命中这个分支，于是合法目录被报错、所有模型被标 missing，
   `local_comfyui_*` **永远不会 ready**。已改为正判，扫描也改为 `not is_file`。

2. **模型清单格式迁移**（`model_requirements.json`）
   扁平结构 → `providers` 分组结构，否则 `required_models_ready` 恒 False。
