# 🎮 AI视觉小说引擎

> v0.1.0 · 全网唯一 · 10/10方案 · 79/79测试通过

## 版本日志

| 版本 | 日期 | 变更 |
|:--|:--|:-----|
| v0.1.0 | 07-12 | 核心引擎:WorldState+DialogEngine+游戏场景 |

## 运行
```bash
npm run dev      # 启动游戏 http://localhost:8080
npm test         # 73个单元测试
npm run test:e2e # 6个E2E测试
npm run test:all # 全部测试
```

## 目录
```
src/
├── engine/WorldState.js    # NPC记忆系统(192行)
├── ai/DialogueEngine.js    # AI对话引擎(509行)
├── ui/                     # UI组件
├── scenes/                 # 游戏场景
└── data/                   # 数据层
tests/
├── unit/         # 73个单元测试
└── e2e/          # 6个Playwright测试
assets/
├── characters/   # ComfyUI生成角色
├── scenes/       # 场景背景
└── ui/           # UI元素
docs/             # 设计文档
workflows/        # ComfyUI工作流
```

## 🎬 九转丹霄 — AI漫剧全12集

> 中国玄幻修仙 AI 漫剧 · 全自动生产 · edge-tts 中文旁白

### 📺 观看

| 集 | 标题 | 时长 | 链接 |
|----|------|------|------|
| E01 | 凡尘少年 | 2:18 | [观看](episodes/E01_九转丹霄_第1集_旁白版.mp4) |
| E02 | 仙缘初现 | 2:02 | [观看](episodes/E02_九转丹霄_第2集_旁白版.mp4) |
| E03 | 灵根觉醒 | 2:10 | [观看](episodes/E03_九转丹霄_第3集_旁白版.mp4) |
| E04 | 青云入门 | 2:07 | [观看](episodes/E04_九转丹霄_第4集_旁白版.mp4) |
| E05 | 百炼成钢 | 2:18 | [观看](episodes/E05_九转丹霄_第5集_旁白版.mp4) |
| E06 | 秘境试炼 | 2:00 | [观看](episodes/E06_九转丹霄_第6集_旁白版.mp4) |
| E07 | 暗流涌动 | 1:42 | [观看](episodes/E07_九转丹霄_第7集_旁白版.mp4) |
| E08 | 丹霞之劫 | 2:04 | [观看](episodes/E08_九转丹霄_第8集_旁白版.mp4) |
| E09 | 绝地逢生 | 2:47 | [观看](episodes/E09_九转丹霄_第9集_旁白版.mp4) |
| E10 | 寻仙问道 | 2:40 | [观看](episodes/E10_九转丹霄_第10集_旁白版.mp4) |
| E11 | 天外有天 | 1:28 | [观看](episodes/E11_九转丹霄_第11集_旁白版.mp4) |
| E12 | 九转归一 | 1:26 | [观看](episodes/E12_九转丹霄_第12集_旁白版.mp4) |

### 📖 剧情简介

**九域大陆**——一个以灵气为根基的修真世界。少年林霄身怀失传的"混沌灵根"，从山村孤儿到逆天修真者，与暗影殿和上界使者展开终极对决。以凡人之躯撼动天规。

### 🛠️ 技术栈

- **分镜脚本**: 14镜头/集 · ComfyUI Prompt + Seed
- **旁白配音**: edge-tts zh-CN-YunxiNeural
- **视频合成**: ffmpeg · Ken Burns + crossfade · 1080×1920 竖屏
- **生产方式**: 11个AI Agent并行制作 · superpowers+gstack方法

