---
name: aicomics
description: "AI漫剧生产系统 — 从剧本到成片全自动。基于ComfyUI+Piper+FFmpeg管线。"
version: 1.0.0
author: 小h智能科技
platforms: [macos, linux]
---

# AIComics — AI漫剧生产系统

AI漫剧一键生产管线：剧本→分镜→AI出图→配音→字幕→BGM→合成→发布。

## 触发条件

用户要求生成AI漫剧、竖屏短剧、动画视频时使用。
关键词：漫剧/短剧/动画/AI视频/AIComics/分镜/出片。

## 安装

```bash
cd ~/Desktop/hermes/AlComics
uv sync --frozen
# 确保 ComfyUI 运行在 localhost:8188
# 确保 FFmpeg 已安装 (brew install ffmpeg)
```

## 完整使用流程

### 1. 初始化项目
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main init-project --name "我的漫剧" --code MYCOMIC
```

### 2. 创建恐怖/职场剧本
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main horror-blueprint --code MYCOMIC --theme "都市职场"
```

### 3. 构建分镜任务
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main build-jobs --code MYCOMIC --episode EP01
```

### 4. 规划provider
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main plan-providers --code MYCOMIC
```

### 5. 构建provider请求
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main build-provider-requests --code MYCOMIC --episode EP01
```

### 6. 执行provider请求（出图+配音）
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main execute-provider-requests --code MYCOMIC --episode EP01
```

### 7. 渲染预览
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main render-preview --code MYCOMIC --episode EP01
```

### 8. 渲染正式版
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main render-release --code MYCOMIC --episode EP01
```

### 9. 构建发布包
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main build-publish-pack --code MYCOMIC --episode EP01
```

### 10. 批量生产
```bash
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main build-batch --code MYCOMIC
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main run-batch --code MYCOMIC
```

## Provider配置

编辑 `config/providers.yaml`：
- 图像: `openai_image` / `local_comfyui_image` / `manual_web`
- 视频: `local_comfyui_video` / `seedance` / `kling` / `manual_web`
- TTS: `openai_tts` / `local_piper_tts` / `windows_tts` / `edge_tts`(新增免费)
- 素材: `stock_material`(新增 Pexels/Pixabay)
- 发布: `social_auto_upload`(国内) / `international`(新增 YouTube/TikTok/IG)

## 新增功能（MPT蒸馏）

| 功能 | 模块 | 说明 |
|------|------|------|
| 在线素材搜索 | `providers/stock_material.py` | Pexels/Pixabay API搜索+下载+缓存 |
| BGM混音 | `video_synthesis/bgm_mixer.py` | 随机/指定BGM+音量平衡 |
| 视频转场 | `video_synthesis/transitions.py` | Fade/Slide/Zoom/Shuffle 7种转场 |
| Edge TTS | `providers/edge_tts_provider.py` | 免费微软TTS，无需API Key |
| 字幕样式 | `video_synthesis/subtitle_styler.py` | 字体/颜色/描边/背景全可配 |
| 国际发布 | `publish/international.py` | YouTube/TikTok/Instagram |
| Agent Skill | `SKILL.md` | 本文件 — 让AI Agent直接操作 |

## 常见问题

### ComfyUI连接失败
确保ComfyUI运行在 `localhost:8188`。检查 `config/providers.yaml` 里的 `comfyui_base_url`。

### Piper TTS找不到模型
确保Piper模型文件在 `assets/piper_models/` 目录下。备用方案：用 `edge_tts`（免费）。

### FFmpeg合成失败
确保FFmpeg已安装：`brew install ffmpeg`。检查 `config/render.yaml` 的路径配置。

### 出图质量不够
在 `config/providers.yaml` 里把 `openai_image.quality` 设为 `high`（每张约$0.20）。
