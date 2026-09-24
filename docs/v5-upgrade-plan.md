# AIComics v5.0 升级规划

> 基于：v4.0深度代码审计(15个缺陷) + GitHub竞品调研(8个项目) + 2025-2026技术趋势调研(6大趋势)
> 日期：2026-09-23

---

## 一、现状诊断

### 代码审计发现（15个缺陷）

| # | 缺陷 | 严重度 |
|---|------|--------|
| 1 | `template_loader.py` 写了但0个importer — 死代码 | 🔴 |
| 2 | `lora_config.py` 写了但0个importer — 死代码 | 🔴 |
| 3 | drift_gate/consistency/lora/cloud_mode 4个v4.0功能无Web API | 🟡 |
| 4 | Wan provider是`_StubLoader`空壳 | 🟡 |
| 5 | i18n翻译是placeholder，没接LLM | 🔴 |
| 6 | selenium不在requirements里 — 发布模块无法运行 | 🔴 |
| 7 | google-api-python-client/edge-tts被注释掉 | 🔴 |
| 8 | openai包没装 — cloud_mode默认provider无法工作 | 🔴 |
| 9 | 75个模块>50行无测试覆盖 | 🟡 |
| 10 | cli/main.py 1097行最大文件零测试 | 🟡 |
| 11 | 无视频缩略图自动生成 | 🟢 |
| 12 | 前端无DriftGate/Consistency/LoRA页面 | 🟡 |
| 13 | 无API Key管理/限流/轮转 | 🟡 |
| 14 | 发布集成依赖selenium(易碎)而非API | 🟡 |
| 15 | 无监控/可观测性 | 🟢 |

### 竞品对比

| 竞品 | Stars | AIComics核心差距 |
|------|-------|-----------------|
| MoneyPrinterTurbo | 99.5K | agent-first架构、100+工具生态、7维provider评分、真实素材库、ffprobe质量门 |
| OpenMontage | 55.9K | 12条生产管线、700+agent技能、生产知识库 |
| CogVideo | 13K+ | 自研视频模型、V2V、fine-tuning框架、学术背书 |
| StoryDiffusion | 6K+ | Consistent Self-Attention学术方法、漫画demo |
| AIComicBuilder | 1.6K | 四视图角色参考表实际集成、首尾帧关键帧、Next.js 16现代前端 |
| LumenX(阿里) | 711 | 大厂工程化、小说→视频全链路 |
| MangstoonAI | 高星 | 自拍→角色映射、scroll式webtoon |

---

## 二、v5.0 升级规划（4大方向 · 16项）

### 方向一：修复v4.0死代码和断裂管线（P0 — 必须做）

> 目标：让已有代码真正跑起来，不做新功能

| # | 任务 | 具体内容 | 产出 |
|---|------|---------|------|
| 1 | **接线template_loader** | 让`pipeline_coordinator`在创建项目时自动调用`load_genre_template()`，而非只有CLI能手动指定 | 模板自动注入管线 |
| 2 | **接线lora_config** | 让`character_workshop`在角色创建时调用`build_lora_training_config()`生成训练配置，并写入角色目录 | LoRA配置自动产出 |
| 3 | **修复i18n翻译** | 接入真实LLM翻译(OpenAI/Gemini API)，替换placeholder。中→英/日/韩字幕翻译真正可用 | 真实多语言字幕 |
| 4 | **修复依赖缺失** | un-comment google-api-python-client/edge-tts，加入selenium和openai到requirements | 发布和云端模式可运行 |
| 5 | **实现Wan provider** | 将`_StubLoader`替换为真实Wan API适配器，或移除Wan路由只保留Kling/Seedance | 视频路由无空壳 |

### 方向二：质量控制体系（P1 — 竞品核心差距）

> 目标：对标MoneyPrinterTurbo的ffprobe质量门 + 学术界的伪影检测

| # | 任务 | 具体内容 | 产出 |
|---|------|---------|------|
| 6 | **ffprobe视频质量门** | 每个产出的MP4自动跑ffprobe检查：分辨率/帧率/比特率/时长/音视频同步。不达标自动标记重生成 | 质量门模块 |
| 7 | **AI伪影检测器** | 基于Artifact-Bench三级分类法，检测：角色变形(手指/面部)、文字乱码、色彩异常、时序不连续。用轻量CNN或MLLM做帧级检测 | 伪影检测模块 |
| 8 | **自动重试循环** | 检测到伪影的shot自动触发重生成：prompt精炼→模型切换→重试→再检测。最多3轮 | 自愈生产循环 |
| 9 | **Drift Gate Web API** | 暴露`/api/drift/check`端点，前端可视化显示drift_score和PASS/WARN/FAIL | API + 前端页面 |
| 10 | **Consistency Web API** | 暴露`/api/consistency/cross-episode`端点，前端显示跨集一致性报告 | API + 前端页面 |

### 方向三：MLLM驱动的智能创作层（P2 — 技术趋势引领）

> 目标：从模板填空升级到多模态大模型编排

| # | 任务 | 具体内容 | 产出 |
|---|------|---------|------|
| 11 | **MLLM故事理解引擎** | 接入GPT-5/Gemini/Claude做故事→分镜规划：输入故事文本，MLLM输出结构化分镜(场景描述/角色/情绪/运镜/镜头时长)，而非YAML模板填空 | MLLM编排层 |
| 12 | **角色Content Anchor** | 基于Gloria/SlotMem论文思路：每个角色建立结构化锚帧集(正面/侧面/背面/45°/表情集)，跨集维护角色记忆，生成时注入参考 | 角色锚帧系统 |
| 13 | **Provider智能路由** | 7维评分(质量/速度/成本/可用性/限额/延迟/成功率)自动选择最佳provider。失败自动降级到次优 | 智能路由模块 |

### 方向四：生态和工程化（P3 — 长期竞争力）

> 目标：对标OpenMontage的工具生态 + 提升开发者体验

| # | 任务 | 具体内容 | 产出 |
|---|------|---------|------|
| 14 | **视频缩略图+预览** | 每个产出的MP4自动提取关键帧缩略图，Web前端展示视频预览而非文件名 | 预览系统 |
| 15 | **API Key管理面板** | 统一管理所有外部provider的API key(加密存储)，支持key轮转/限额监控/失败告警 | Key管理模块 |
| 16 | **测试补全计划** | 优先补cli/main.py(1097行)、prompt_enhancer.py(724行)、character_views.py(622行)的测试。目标：90%核心模块有测试 | 测试覆盖提升 |

---

## 三、优先级和排期

```
P0 (Week 1-2): #1-5  — 修复死代码和断裂管线
P1 (Week 3-4): #6-10 — 质量控制体系 + Web API暴露
P2 (Week 5-7): #11-13 — MLLM智能创作层
P3 (Week 8+):  #14-16 — 生态和工程化
```

## 四、技术选型

| 组件 | v4.0 | v5.0 |
|------|------|------|
| 故事→分镜 | YAML模板填空 | MLLM编排(GPT-5/Gemini API) |
| 角色一致性 | Triple-Lock(IPAdapter+ControlNet+FaceDetailer) | + Content Anchor锚帧记忆 |
| 质量控制 | 无 | ffprobe门 + AI伪影检测 + 自动重试 |
| Provider路由 | 静态配置 | 7维动态评分 + 自动降级 |
| 视频模型 | Kling/Seedance/Wan(stub) | + Wan(真实API)/Kling 2.0/Hunyuan Video |
| 翻译 | placeholder | LLM翻译(OpenAI/Gemini) |
| 发布 | selenium(易碎) | 优先API(YouTube Data API), selenium降级方案 |
| 前端 | React SPA (umijs/max) | 保持，逐步加v5.0页面 |

## 五、验收标准

- [ ] P0: 5个死代码/断裂全部修复，已有功能全部可用
- [ ] P1: 产出的视频通过ffprobe质量门，伪影检测准确率>80%
- [ ] P2: MLLM生成的分镜质量≥模板填空(人工AB测试)
- [ ] P3: 核心模块测试覆盖>90%，视频预览可用
- [ ] 全程：1036个现有测试零回归
