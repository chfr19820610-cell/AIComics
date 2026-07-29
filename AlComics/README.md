# 🌙 星落之夜 · AI 视觉小说互动游戏 (AIComics)

> 一款用 **AI 生成剧情**的免费在线视觉小说 / AI 漫剧——在浏览器中体验奇幻对话冒险，无需下载安装。

![Deploy to GitHub Pages](https://github.com/chfr19820610-cell/ai-vn-game/actions/workflows/deploy.yml/badge.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)
![Play Online](https://img.shields.io/badge/▶-play_online-brightgreen.svg)
![中文](https://img.shields.io/badge/语言-中文-red.svg)
![Stars](https://img.shields.io/github/stars/chfr19820610-cell/ai-vn-game?style=social)

**中文** | [English](#-english)

---

## ▶️ 立即游玩

👉 **[在线体验](https://chfr19820610-cell.github.io/ai-vn-game/)**

无需安装，打开即玩。推荐桌面浏览器全屏体验。

---

## 📖 项目简介

**星落之夜**是一款基于 **AI 生成剧情**的互动视觉小说（AI 漫剧）游戏。故事发生在一座奇幻村庄——"星落之夜"即将降临，黑暗势力蠢蠢欲动。玩家通过与村民对话、做出选择，逐步揭开隐藏在星象背后的秘密。

本项目是 AIComics 系列的第一个开源作品，旨在探索 **AI + 视觉小说**的叙事可能性。所有剧情对话由 AI 生成，结合传统视觉小说的交互形式，为玩家带来独一无二的沉浸式体验。

---

## 🚀 生产管线部署 (v2.0)

> AIComics 生产管线包括：3层Agent编排系统 + Seedance 2.0 AI视频生成 + TTS配音 + 视频合成。

### 前置要求

- Docker & Docker Compose v2+
- NVIDIA GPU (ComfyUI 可选，不强制)
- 至少 8GB 可用磁盘空间

### 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/chfr19820610-cell/ai-vn-game.git
cd ai-vn-game

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 SEEDANCE_API_KEY

# 3. 一键启动
./run.sh up

# 4. 查看日志
./run.sh logs

# 5. 执行 EP01 管线
./run.sh episode 01
```

### 环境变量

详见 [.env.example](.env.example)，关键变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SEEDANCE_API_KEY` | Seedance 2.0 API Key | **(必填)** |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://ollama:11434` |
| `COMFY_URL` | ComfyUI 服务地址 | `http://comfyui:8188` |
| `BLENDER_BIN` | Blender 可执行路径 | `/usr/bin/blender` |

### 架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AIComics      │────▶│    Ollama       │     │    ComfyUI      │
│   (Python 3.11) │     │    (LLM 推理)   │     │  (图像/视频生成) │
│                 │     │    port 11434   │     │    port 8188     │
│   port 8080     │     └─────────────────┘     └─────────────────┘
│                 │
│  3层Agent系统   │
│  决策→执行→监督 │
└─────────────────┘
```

### 命令参考

```bash
./run.sh              # 默认启动
./run.sh build        # 重新构建
./run.sh episode 02   # 执行 EP02
./run.sh logs         # 查看日志
./run.sh stop         # 停止
./run.sh cleanup      # 清理数据卷
```

---

## ✨ 功能列表

- 🤖 **AI 驱动剧情** —— 对话与分支由 AI 生成，每次游玩体验不同
- 🎭 **多角色互动** —— 点击 NPC 角色进行深度对话，每个角色有独特性格与故事线
- 🎨 **AI 漫剧风格** —— 视觉小说 × AI 生成美术，打造独特的视觉体验
- 🌐 **浏览器即玩** —— 纯前端实现，无需下载安装，跨平台兼容
- 📱 **移动端适配** —— 响应式设计，支持触摸操作
- 🔓 **开源免费** —— Apache 2.0 协议，欢迎 Fork、二次创作和商业使用
- 🛠️ **零构建步骤** —— 纯静态文件，clone 后直接打开 `index.html` 即可运行

---

## 🎭 角色介绍

| 角色 | 身份 | 简介 |
|:---:|:---:|:---|
| 🧝‍♀️ 莉拉 | 银发少女 | 神秘的星象观测者，似乎知道"星落之夜"的真相 |
| 👴 凯尔 | 村长 | 守护村庄多年的长者，对黑暗势力心存忧虑 |
| 🔨 马库斯 | 铁匠 | 沉默寡言的武器匠人，也许能提供关键帮助 |

---

## 🛠️ 技术栈

| 技术 | 说明 |
|:---|:---|
| **游戏引擎** | [Kaboom.js](https://kaboomjs.com/) v2000 — 轻量级 JavaScript 游戏编程库 |
| **AI 剧情** | 3层Agent编排 (决策→执行→监督) + Ollama 本地LLM |
| **视频生成** | Seedance 2.0 API (doubao-seedance) |
| **图像生成** | ComfyUI (可选 GPU 加速) |
| **TTS 配音** | edge-tts (中文旁白) |
| **视频合成** | ffmpeg + imageio-ffmpeg |
| **容器化** | Docker Compose (AIComics + Ollama + ComfyUI) |
| **部署** | GitHub Pages (前端) + Docker (生产管线) |
| **协议** | Apache License 2.0 |

---

## 🚀 快速开始（前端开发）

### 在线游玩

直接访问 **[在线体验地址](https://chfr19820610-cell.github.io/ai-vn-game/)**，无需安装任何环境。

### 本地开发

```bash
# 无需构建步骤，直接打开
open index.html
```

---

## 📂 项目结构 (v2.0)

```
ai-vn-game/
├── index.html              # 前端游戏入口
├── README.md               # 本文档
├── .env.example            # 环境变量模板
├── Dockerfile              # Docker 构建文件
├── docker-compose.yaml     # 服务编排 (AIComics+Ollama+ComfyUI)
├── docker-entrypoint.sh    # 容器入口
├── requirements.txt        # Python 依赖
├── run.sh                  # 一键启动脚本
│
├── aicomic-3layer.sh       # 三层Agent编排器
├── decision_agent.py       # 决策层 Agent
├── execution_agent.py      # 执行层 Agent
├── supervision_agent.py    # 监督层 Agent
│
├── seedance_client.py      # Seedance 2.0 API 客户端
├── batch_generate.py       # 批量视频生成器
├── compose_video.py        # 视频合成管线 (v3.0, 全3D)
├── compose_video_seedance.py # Seedance 视频合成管线
│
├── agents/                 # Agent 副本目录
│   ├── aicomic-3layer.sh
│   ├── decision_agent.py
│   ├── execution_agent.py
│   └── supervision_agent.py
│
├── episodes/               # 播出剧本/发布文案
├── manifests/              # 分镜 JSON 文件
├── output/                 # 最终成品输出
├── source_frames/          # 生成的视频素材
├── audio/                  # TTS 音频
├── tasks/                  # Agent 任务清单
├── supervision/            # Agent 监督裁决
└── local_providers/        # ComfyUI/Blender 脚本
```

---

## 📝 许可证

[Apache License 2.0](LICENSE)
