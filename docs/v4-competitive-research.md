# AIComics v4.0 竞品调研报告

调研时间：2026-09-06
数据来源：GitHub API + web_extract（实地抓取 README）

---

## 一、竞品全景

### 1. 直接竞品 — AI 漫剧/漫画生成平台

| 项目 | ⭐ | 技术栈 | 核心能力 | 值得学习 |
|------|-----|--------|----------|----------|
| **AIComicBuilder** (LingyiChen-AI) | 25+ | Next.js 16 + React 19 + Drizzle ORM + SQLite | 剧本导入→角色四视图→分镜→首尾帧→视频生成→合成 | ✅ 角色四视图（正/3/4/侧/背）确保一致性；✅ Docker 一键部署；✅ 多语言(中/英/日/韩)；✅ 多模型(OpenAI/Gemini/Kling/Seedance/Veo)；✅ 分镜工作流三种视图 |
| **ai-comic-drama-platform** (kingdoja) | 10 | Python/FastAPI + PostgreSQL + Next.js 14 | 7-stage agent pipeline + 状态机 + 89%测试覆盖 | ✅ Workflow-First 架构；✅ Artifact-First 状态管理；✅ 防偏移机制(多层一致性检查)；✅ Hypothesis 基于属性的测试 |
| **manga-studio** (bo961386926) | 8 | React + Electron + Vitest | Script→Asset→Keyframe 工作台 | ✅ Electron 桌面端；✅ StageDirector 组件；✅ 测试策略分层(纯函数→adapter→组件→集成) |
| **ai-comic-drama-director-skills** (djyy1031) | N/A | Codex Skills (纯提示词) | 6个专业Skill: 导演/资产接入/表演/场景/镜头执行/连续性 | ✅ STORYBOARD_PROMPTS_ONLY 模式；✅ 成品资产接入与空间锚定；✅ Seedance 2.5 适配；✅ 跨集一致性校验脚本 |

### 2. 角色一致性技术

| 项目 | ⭐ | 方案 |
|------|-----|------|
| **Anima-LoRA-Factory** | 73 | GUI 工具训练角色 LoRA — **我们只有 seed+IP-Adapter，缺 LoRA 训练** |
| **style-consistency-ai** | 7 | Claude skills 风格一致性 |
| **character-anchor-skill** | 3 | 角色锚定工作流 + golden reference |
| **nano-banana-2-ai** | 5 | Gemini 4K 图像 + 5角色一致性 |

### 3. AI 漫画/Manga 工具

| 项目 | ⭐ | 核心能力 |
|------|-----|----------|
| **AI-Manga-Studio** (MontaCoder) | 36 | 端到端 manga 创作 |
| **auto-voice-over-tool** | 24 | 漫画/网文→旁白视频 |
| **AI-Comic-Generator** (Dapeng960208) | 12 | 文本故事→漫画 |

### 4. Story→Video 管线

| 项目 | ⭐ | 核心能力 |
|------|-----|----------|
| **ai-video-production-editor** | 37 | 开源 AI 视频制作编辑器(React+Electron) |
| **ai-video-generation-pipeline** | 6 | Script→Storyboard→Characters→Video 端到端 |
| **director-desk** | 4 | AI Showrunner 自主短剧 |

---

## 二、我们 vs 竞品 — 能力对比矩阵

| 能力维度 | AIComics v3.0 (我们) | AIComicBuilder | ai-comic-drama-platform | manga-studio | director-skills |
|----------|----------------------|----------------|------------------------|--------------|-----------------|
| 剧本导入 | ✅ novel_splitter | ✅ TXT/DOCX/PDF | ✅ 网文 | ❌ | ✅ 剧本/章节 |
| 角色一致性 | ⚠️ Triple-Lock(seed+LoRA+IP-Adapter) plan_only | ✅ 角色四视图 | ✅ 防偏移检查 | ❌ | ✅ 资产锚定 |
| LoRA 训练 | ❌ 缺 | ❌ | ❌ | ❌ | ❌ |
| 分镜系统 | ✅ shot_breakdown | ✅ 智能分镜 | ✅ 7-stage pipeline | ✅ StageDirector | ✅ 专业分镜 |
| 首尾帧插值 | ✅ FLF interpolator | ✅ 首尾帧模式 | ❌ | ❌ | ❌ |
| 视频生成 | ⚠️ video_router(JieYou 401) | ✅ Seedance/Kling/Veo | ❌ | ❌ | ✅ Seedance 2.5 |
| 三线渲染 | ✅ 2D/2.5D/3D | ❌ | ❌ | ❌ | ❌ |
| TTS 配音 | ✅ Piper/Edge/OpenAI | ❌ | ❌ | ❌ | ✅ 声音设计 |
| 字幕 | ✅ SRT/ASS(中文) | ✅ 字幕烧录 | ❌ | ❌ | ❌ |
| 多语言 | ❌ 缺 | ✅ 中/英/日/韩 | ❌ | ❌ | ❌ |
| 发布分发 | ⚠️ 骨架(international.py) | ❌ | ❌ | ❌ | ❌ |
| Web UI | ✅ Creator控制台 | ✅ Next.js | ✅ Next.js | ✅ React | ❌ |
| 桌面端 | ❌ | ❌ | ❌ | ✅ Electron | ❌ |
| Docker | ✅ | ✅ | ✅ | ✅ | ❌ |
| 测试 | ✅ 992 passed | ❌ | ✅ 89%覆盖 | ✅ Vitest | ✅ 校验脚本 |
| 模板系统 | ⚠️ 硬编码 horror/romance | ❌ | ❌ | ❌ | ✅ 6专业Skill |
| 防偏移检查 | ❌ 缺 | ❌ | ✅ 多层一致性 | ❌ | ✅ 连续性检查 |

---

## 三、竞品核心亮点深挖

### 3.1 AIComicBuilder — 我们最接近的竞品

**他们比我们强的：**
1. **角色四视图**：每个角色生成 正面/3/4侧面/侧面/背面 四视图，后续所有帧引用这些参考图 → 一致性从源头解决
2. **多语言**：中/英/日/韩 四语言 UI + 内容
3. **多模型视频**：Seedance/Kling/Veo 三家可切换
4. **Docker Hub 镜像**：`docker run twwch/aicomicbuilder:latest` 一键跑

**我们比他们强的：**
1. **三线渲染**（2D/2.5D/3D）— 他们完全没有
2. **SOP 8阶段管线** — 更完整的工程化
3. **992 测试** — 他们没测试
4. **提示词意图识别** — 6类意图分类增强
5. **Python 技术栈** — 对 ComfyUI 生态更友好

### 3.2 ai-comic-drama-platform — 架构最先进

**他们比我们强的：**
1. **Workflow-First 架构** — 显式工作流编排 vs 我们的 pipeline_coordinator
2. **Artifact-First 状态管理** — 状态来自结构化产物 vs 聊天上下文
3. **防偏移机制** — 多层一致性检查防止内容偏离
4. **Temporal 工作流编排** — 企业级工作流引擎（计划中）
5. **Hypothesis 基于属性的测试** — 比普通单元测试更强

### 3.3 director-skills — 分镜最专业

**他们比我们强的：**
1. **6个专业 Skill** — 导演/资产接入/表演/场景/镜头执行/连续性，每个都是领域专家
2. **成品资产接入与空间锚定** — 先看真实资产再设计镜头
3. **跨集一致性校验** — 自动检查角色/场景/道具跨集一致
4. **Seedance 2.5 深度适配** — 全局提示词/资产绑定/画质参数

---

## 四、v4.0 升级方向建议

### P0 — 竞品有的我们没有（必须补齐）

| # | 方向 | 参考竞品 | 预估工作量 | 价值 |
|---|------|----------|-----------|------|
| 1 | **角色四视图系统** | AIComicBuilder | 3天 | 从源头解决角色一致性，比 Triple-Lock 更前置 |
| 2 | **多模型视频切换** | AIComicBuilder | 2天 | Seedance/Kling/Veo 可切换，不依赖单一 API |
| 3 | **防偏移一致性检查** | ai-comic-drama-platform | 3天 | 多层检查防止内容偏离原始创意 |
| 4 | **多语言 UI + 内容** | AIComicBuilder | 2天 | 出海必备，中/英/日/韩 |

### P1 — 竞品有我们更强（差异化深化）

| # | 方向 | 参考竞品 | 预估工作量 | 价值 |
|---|------|----------|-----------|------|
| 5 | **Workflow-First 架构** | ai-comic-drama-platform | 5天 | 显式工作流编排，状态可追踪可回滚 |
| 6 | **跨集一致性校验** | director-skills | 2天 | 自动检查角色/场景/道具跨集一致 |
| 7 | **LoRA 训练 GUI** | Anima-LoRA-Factory(73⭐) | 5天 | 角色风格永久锁定，从 plan_only 到实际可用 |
| 8 | **成品资产接入** | director-skills | 2天 | 先看真实资产再设计镜头，避免"盲拍" |

### P2 — 现有 ROADMAP 继续

| # | 方向 | 来源 | 预估工作量 | 价值 |
|---|------|------|-----------|------|
| 9 | **发布平台集成** | v3.0 ROADMAP ④ | 7天 | 直接赚钱 |
| 10 | **模板系统** | v3.0 ROADMAP ① | 6天 | 标准化生产 |
| 11 | **小说→漫剧管道** | v3.0 ROADMAP ② | 6天 | 内容供给 |
| 12 | **多语言配音** | v3.0 ROADMAP ③ | 5天 | 出海 |

### P3 — 创新差异化

| # | 方向 | 参考竞品 | 预估工作量 | 价值 |
|---|------|----------|-----------|------|
| 13 | **Electron 桌面端** | manga-studio | 3天 | 离线使用，不依赖服务器 |
| 14 | **Docker Hub 镜像** | AIComicBuilder | 1天 | `docker run aicomics:latest` 一键部署 |
| 15 | **Hypothesis 属性测试** | ai-comic-drama-platform | 2天 | 测试质量升级 |

---

## 五、推荐 v4.0 升级路线（按优先级排序）

### 第一阶段（1-2周）：补齐差距
1. **角色四视图系统** — P0，从源头解决一致性
2. **多模型视频切换** — P0，解决 JieYou 401 被卡问题
3. **防偏移一致性检查** — P0，质量保证
4. **多语言 UI** — P0，出海基础

### 第二阶段（2-3周）：差异化深化
5. **Workflow-First 架构重构** — P1，架构升级
6. **跨集一致性校验** — P1，专业度提升
7. **发布平台集成** — P2，直接赚钱
8. **模板系统** — P2，标准化

### 第三阶段（3-4周）：创新突破
9. **LoRA 训练 GUI** — P1，角色锁定终极方案
10. **Docker Hub 镜像** — P3，一键部署
11. **小说→漫剧管道** — P2，内容供给
12. **Electron 桌面端** — P3，离线使用

---

## 六、关键发现

1. **AIComicBuilder 是最直接的竞品** — 功能高度重合，但他们有角色四视图和多语言我们没有
2. **我们的三线渲染是独家优势** — 所有竞品都没有 2.5D/3D 能力
3. **角色一致性是行业痛点** — 73⭐的 Anima-LoRA-Factory 说明市场需求大
4. **Workflow-First 是架构趋势** — ai-comic-drama-platform 的设计理念值得借鉴
5. **Seedance 2.5 是当前视频生成主流** — 多个竞品都在用，我们应该接入
6. **Docker Hub 一键部署已成标配** — AIComicBuilder 和 manga-studio 都有
