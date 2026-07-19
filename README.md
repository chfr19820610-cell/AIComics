# 🎬 AIComics — AI 漫剧自动生成系统

> **写故事 → 拆镜头 → AI 生成 → 配音 → 发布，全自动一人公司视频工厂**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-brightgreen)](.python-version)
[![Tests](https://img.shields.io/badge/Tests-640%2F640-passing-brightgreen)]()
[![ComfyUI](https://img.shields.io/badge/ComfyUI-v0.26.0-important)]()
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey)]()

---

## ✨ 它能做什么

AIComics 是一个**全本地运行**的 AI 漫剧创作系统。你只需要有一个故事想法，系统会帮你：

| 环节 | 说明 | 技术 |
|------|------|------|
| 📝 **写剧本** | 设定世界观、角色、剧情，自动生成分镜脚本 | 大语言模型 |
| 🎨 **出画面** | 每个分镜生成动漫风格的关键帧图片 | ComfyUI + SDXL |
| 🔊 **配配音** | 每个分镜生成中文语音旁白 | Piper TTS |
| 🎬 **做视频** | 图片+配音合成完整剧集 | FFmpeg |
| 📡 **发平台** | 一键发布到小红书/B站/抖音 | social-auto-upload |

**当前成品示例：** 《我变成僵尸后全校跪求我别死》E01-E03（18 张关键帧 + 18 段配音）

---

## 🚀 快速开始

### 前置要求

- Python 3.12+
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) + SDXL 模型
- [Piper TTS](https://github.com/rhasspy/piper) 中文语音模型

### 安装

```bash
# 1. 克隆
git clone https://github.com/chfr19820610-cell/AIComics.git
cd AIComics

# 2. 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements-lock.txt

# 4. 配置 ComfyUI 路径
# 编辑 config/aicomic_comfyui_paths.yaml，指向你的 ComfyUI models 目录

# 5. 初始化
PYTHONPATH="src" .venv/bin/python -m aicomic.cli.main init-demo-db

# 6. 启动
bash scripts/start.sh
```

### 启动后访问

- **创作台：** http://localhost:8000/login
- **API：** http://localhost:7860/api/health
- **ComfyUI：** http://localhost:8188

默认账号：`creator` / `your-password-here`

---

## 🏗️ 系统架构

```
AIComics/
├── src/aicomic/           ← 核心引擎
│   ├── cli/               ← CLI 入口
│   ├── core/              ← 业务逻辑 (项目/剧集/分镜/分镜版本)
│   ├── providers/         ← Provider 抽象层 (ComfyUI/Piper/OpenAI/Seedance)
│   ├── characters/        ← 角色系统 (定义/一致性/提示词注入)
│   ├── video_synthesis/   ← 视频合成管线
│   └── utils/             ← 工具函数
├── web/                   ← Web 服务
│   ├── backend/           ← FastAPI 后端
│   └── frontend/          ← React SPA 前端
├── config/                ← 配置文件
├── scripts/               ← 运维脚本
├── tests/                 ← 640 个测试用例
├── local_providers/       ← Provider 运行目录
└── pyproject.toml         ← 项目配置
```

### 生产管线

```
故事蓝图 → episode_manifest.json → build-season-jobs
  → build-provider-requests → execute-provider-requests
  → 图片 + 配音 + 视频 → 发布包
```

---

## 📊 当前状态

| 指标 | 值 |
|------|----|
| 测试通过率 | **640/640** (100%) |
| 验证脚本 | **39/39** (100%) |
| API 端点 | **52** 个 |
| Python 版本 | **3.12** |
| 许可证 | **Apache 2.0** |

---

## 🧪 运行测试

```bash
PYTHONPATH="src" .venv/bin/python -m pytest tests/ -v
```

---

## 🔄 无限自循环

系统自带轻量后台循环引擎，自动监控生产状态并补充资产：

```bash
# 启动生产 + 赚钱循环
PYTHONPATH="src" .venv/bin/python scripts/vf_master_loop.py &
```

定时任务会被自动发现和补充，无需手动干预。

---

## ✨ v0.2.0 新功能

| 功能 | 说明 |
|------|------|
| **🧩 供应商抽象层** | 统一的 Provider 接口，支持 ComfyUI / OpenAI / Seedance / 手动 等多种图片生成后端，可热切换 |
| **👤 角色系统** | 角色定义、一致性检测、提示词注入、参考图管理，让同一角色在不同分镜中保持外形统一 |
| **📋 分镜版本管理** | 分镜可创建多个版本，对比选择最佳效果，支持回滚 |
| **🎬 视频合成管线** | 端到端视频合成：图片→场景→字幕→配音→合成，支持批量处理 |
| **✅ 640 测试覆盖** | 从 314 提升至 640 测试，新增 Provider 抽象层、角色系统、分镜版本管理等专项测试，验证脚本 39/39 全通过 |

---

## 🛤️ 路线图

- [x] 基础漫剧管线 (故事→分镜→图片→配音)
- [x] CLI + Web API + SPA 三端入口
- [x] 640 测试全通过
- [x] 供应商抽象层 (ComfyUI/Piper/OpenAI/Seedance)
- [x] 角色系统 (定义/一致性/提示词注入/参考图)
- [x] 分镜版本管理
- [ ] 漫剧专用模板系统
- [ ] 小说→漫剧一站式管道
- [ ] 多语言配音 & 字幕
- [ ] 发布平台自动集成
- [ ] 云端轻量模式

---

## 📄 许可证

Apache 2.0 © 2026 [Eric Chen](https://github.com/chfr19820610-cell)

---

## 🤝 贡献

Issues 和 PR 都欢迎！提交前请确保测试通过。

```bash
PYTHONPATH="src" .venv/bin/python -m pytest tests/ -q
```
