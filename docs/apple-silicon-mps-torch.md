# Apple Silicon / MPS 出图质量事故与修复（2026-11-13）

## 症状

同一 prompt、同一 workflow、同一模型（SDXL Base 1.0），出图出现：

| 现象 | 观察值 |
|---|---|
| 画面结构崩坏 | 人物肢体/面部扭曲，局部出现成团色块 |
| 出图极慢或卡死 | 1024×1536 / 25 步：进程 CPU 4.8%、**48 分钟不完成** |
| 内存紧张 | 卡死时 `free` 仅 109MB |

当时 `cpu` 几乎为 0 却在 `running`，看起来像死锁，实为 MPS 侧的数值/内存异常。

## 根因：PyTorch 版本落在 MPS 缺陷区间

上游社区已系统整理该问题
（[vulca-visual-control-sdk: apple-silicon-mps-comfyui-guide](https://github.com/vulca-org/vulca-visual-control-sdk/blob/master/docs/apple-silicon-mps-comfyui-guide.md)）：

| torch 版本 | SDXL on MPS | 说明 |
|---|---|---|
| 2.4.1 | ✅ 稳定 | 最后完整验证版本 |
| 2.5.x | ⚠️ 降级 | 内存 +50%、速度 −60% |
| 2.6 / 2.7 | ⚠️ 部分 | SDPA 若干问题 |
| 2.8.0 | ❌ 坏 | SDPA 非连续张量回归（pytorch#163597） |
| **2.9.0** | **✅ sweet spot** | Metal 迁移前，默认 attention slicing 掩盖 SDPA bug |
| 2.10.0 | ❌ 坏 | M3 Ultra 黑图（ComfyUI#10681） |
| 2.11.0 | ❌ 坏 | M5 黑图/噪点 |

本项目事故时 ComfyUI venv 为 **torch 2.13.0**，处于缺陷区间内。

## 修复

```bash
PY=local_providers/comfyui_runtime/.venv-h3/bin/python
$PY -m pip install "torch==2.9.0"          # 74.5MB
$PY -m pip install "torchvision==0.24.0"   # 必须同步降，否则报
                                           # RuntimeError: operator torchvision::nms does not exist
$PY -c "import torch, torchvision; print(torch.__version__, torchvision.__version__)"
# 期望: 2.9.0 0.24.0
```

然后重启 ComfyUI：`python scripts/manage_comfyui_service.py restart`

## 实测对比（同一 prompt / workflow）

| 指标 | torch 2.13.0 | torch 2.9.0 |
|---|---|---|
| 512×768 / 8 步 | 结构崩坏、成团色块 | 画面干净、比例正常 |
| 1024×1536 / 28 步 | **48 分钟不完成** | **376 秒完成** |
| 1024×1536 成片 | 不可用 | 可交付（雨夜霓虹、人物结构完整） |

## 约束与注意事项

1. **不要升级 ComfyUI venv 的 torch 到 2.8+**，除非上游 bug 已修并有验证证据。
2. `torch` 与 `torchvision` **必须成对**（2.9.0 ↔ 0.24.0），单升单个会报 `nms` 算子缺失。
3. 若必须用新版 torch，可尝试缓解项（效果有限，不能修复正确性 bug）：
   - `--cpu-vae`：把 VAE 解码放 CPU（绕开 MPS 解码缺陷）
   - `--force-fp32`：仅缓解 NaN，**不能**修复 stride/正确性问题
   - `PYTORCH_ENABLE_MPS_FALLBACK=1`
   - 换 fp16-fix VAE：`madebyollin/sdxl-vae-fp16-fix`
4. 本项目主 venv 的 torch（2.15.0，供 Piper/g2pw 用）与 ComfyUI venv 的 torch **互相独立**，
   两者不必一致；ComfyUI 只认自己 venv 里的版本。
