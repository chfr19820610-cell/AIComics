# CHANGELOG

All notable changes to AIComics are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

---

## [v0.3.0] — 2026-07-19

> **AI 视频品质升级 · 20+ Agent 全线整合 · 1080p/30fps 高清输出 · 双风格视频工厂 · 一站式安全审计**

v0.3.0 是一次大规模全线整合发布，覆盖 **17 个提交 + 5 个未提交文件修改 + 20+ Agent 产出整合**。系统从 v0.2.0 的基础管线升级为具备高清视频、自动风格轮换、多 Provider 协同、社区基础设施的完整一人公司视频工厂。

### ✨ 核心功能升级

#### 🎬 视频品质升级 (P0)
- **1080p/30fps 高清输出** — 从 720p/24fps 升级至全高清，添加 LUT 色彩校正，修复 CRF 不一致问题
- **Phase D 合成管线修复** — 修复视频合成管线的关键 bug，确保端到端生产稳定性
- **视频工厂实际产出 MP4** — E01_full 33 秒 1280×720 全流程验证通过
- **HQ 高清重制版** — Painterly 3D Noir 风格所有 5 集产生 _hq.mp4 重制版

#### 🔄 无限自循环 v3.0
- **vf_master_loop v3.0** — 视频合成无限循环 + 自动风格轮换引擎（Painterly 3D Noir → Hybrid Comic Pop）
- **双风格产出** — 已产出 Painterly 3D Noir 全 5 集 + Hybrid Comic Pop E01/E02
- **demo_reel.mp4** — AIComics 精选演示短片

#### 🔌 Provider 生态扩展
- **Kling AI (快手可灵) 视频 Provider** — `text2video` + `image2video` + JWT 认证，快手 SOTA 视频生成
- **Seedance 2.0 视频集成** — 云端生图→视频，替换 FFmpeg 纯拼接，无 key 自动降级
- **local_comfyui_video_fast** — 新增快速工作流（256×144, 6fps, 12帧），预览速度提升 ~2-2.5x
- **云端优先 + 本地备用架构** — openai 不可用时自动切换到 local_comfyui/piper
- **VidGenMixin 合并重构** — Seedance/Kling 共享基类，消除重复代码

#### 📋 20+ Agent 产出整合
| Agent | 产出 | 说明 |
|-------|------|------|
| 🎬 视频导演审查 | `docs/video_director_review.md` | Phase D 品质审查 + 427 行深度分析 |
| 🎨 品质 Prompt 模板 | `docs/quality_prompt_template.md` | DALL-E 3 / gpt-image-1.5 统一品质模板 |
| ⚡ ComfyUI 加速 | `docs/comfyui_speed_optimization.md` | 推理速度 2x+ 方案 + TeaCache 兼容性评估 |
| 🎥 视频工作流指南 | `docs/comfyui_video_workflow_guide.md` | AnimateDiff / SVD / Wan2.1 全方案对比 |
| 🔷 Blender 集成可行性 | `docs/blender_integration_feasibility.md` | Blender Provider 架构评估 (438行) |
| 🔒 安全审计 | `product_assets/security_audit_report.md` | 9 项安全检视 (strix + pentest) |
| 📊 视频生产报告 | `product_assets/video_production_report.md` | 全量审计 5 集视频明细 |
| 🔧 social-auto-upload 修复 | `docs/FIX_social-auto-upload-deps.md` | venv 依赖修复 |
| 📈 竞品分析 | `reports/competitor_analysis_2026.md` | 开源 AI 漫画市场扫描 |
| 💰 变现策略 | `reports/monetization_strategy.md` | 多通道变现方案 |
| 📢 开源发布 | `reports/open_source_launch_posts.md` | 社交媒体发布文案 |
| 📱 社交发布指南 | `reports/social_publish_guide.md` | 小红书/抖音/B站发布流程 |
| 🖥️ UX 审计 | `reports/ux_audit_report.md` | 前端用户体验评估 |
| 🏷️ Gumroad 上架 | `reports/gumroad_listing_guide.md` | 数字商品上架指南 |
| 💸 赚钱机会 | `reports/money_opportunities.md` | AI 漫画变现机会图谱 |
| 📋 品质追踪 | `reports/quality_tracker.md` | 质量指标追踪看板 |
| 📋 PRD 文档 | `reports/prd/` | 产品需求文档 |
| 📋 Review 记录 | `reports/reviews/` | 各轮审查记录 |
| 📄 趋势差距分析 | `docs/AI漫画开源趋势差距分析报告_20260719.md` | 社区趋势 + 差距分析 |
| 📄 下一轮功能清单 | `docs/AIComics下一轮迭代功能清单_20260719.md` | 迭代路线图 |

#### 🔧 技术债务清理
- **代码精简 -49%** — 从 v0.1.0 到 v0.2.0+ 整体瘦身
- **删除 video_factory_loop 旧脚本** — 全面迁移至 vf_master_loop
- **global.yaml Windows 路径修复** — 跨平台兼容
- **旧 main.py 引用清理** — 消除废弃导入
- **NAME_MAP 去重** — 消除冗余映射

#### 🌐 社区基础设施
- **CI/CD 工作流** — `ci.yml` + `daily-upgrade.yml` 自动化
- **Issue 模板** — Bug report + Feature request
- **PR 模板** — 规范的 Pull Request 模板
- **README 全面增强** — Mermaid 架构图 + 演示截图 + 安装指南 + 640 测试徽章

#### 🖥️ 前端 UX 修复
- 空态提示（空白状态友好展示）
- Review 版本对比功能（并排 diff）
- 导航高亮（路由联动）
- 页面标题差异化（每个页面独特标题）

### 📦 配置文件变更

- **`config/providers.yaml`** — 新增 `local_comfyui_video_fast` provider（预览快速模式），Kling 配置完善
- **`config/global.yaml`** — Windows 路径修复
- **`pyproject.toml`** — 版本升级 0.1.0 → 0.3.0

### 💾 状态 / 产出

- `state/produced_videos/` — 双风格产出 (Painterly 3D Noir E01-E05 + Hybrid Comic Pop E01-E02)
- `state/releases/` — 5 集完整 MP4, 总计 **4分24秒**, **37.66 MB**
- 1080p HQ 重制版 (`*_hq.mp4`) 已就绪
- `AIComics_demo_reel.mp4` 精选演示短片

### 📜 完整 Commit 日志

```
86aea79 feat(video): upgrade quality to 1080p/30fps with LUT + fix CRF inconsistency
ecc91d9 docs(community): 建立社区基础设施 — Issue 模板 + PR 模板 + CI 增强
5b2c15b docs: 增强 README — Mermaid 架构图+演示截图+安装指南+640测试徽章
89f58ad P1代码审查修复: 提取VidGenMixin合并Seedance/Kling+路径硬编码修复+NAME_MAP去重
98c832c 技术债务清理: 删video_factory_loop旧脚本+修global.yaml Windows路径+更新旧main.py引用
ce66cdd fix(video-factory): repair Phase D synthesis pipeline
ae690fc 视频工厂实际产出MP4: E01_full 33秒 1280×720 + Provider配置微调
a62bb16 Phase B自动发布: social-auto-upload推小红书/抖音,未安装优雅降级
1e05a4d Kling AI视频Provider: 快手可灵接入, text2video+image2video+JWT认证
a3db42e 前端UX修复: 空态提示+Review版本对比+导航高亮+页面标题差异化(正确目录)
0eaa982 Revert "前端UX修复: 空态提示+Review版本对比+导航高亮+页面标题差异化"
ae892a5 前端UX修复: 空态提示+Review版本对比+导航高亮+页面标题差异化
01d38e7 Seedance 2.0视频集成: 云端生图→视频替换FFmpeg拼接,无key自动降级
2e74711 vf_master_loop v3.0: 视频合成无限循环+风格轮换+FFmpeg管线
625bc58 云端优先+本地备用: openai不可用时自动切local_comfyui/piper
889ea9c 默认云端: openai_image + seedance + openai_tts via JieYou(GPT-5.5)
af9caca 默认切换到云端模型: openai_image + seedance + openai_tts
```

### 📂 未提交 / 新增文件 (本批整合)

| 文件 | 大小 | 说明 |
|------|------|------|
| `docs/comfyui_speed_optimization.md` | 7.6 KB | ComfyUI 推理速度优化方案 |
| `docs/comfyui_video_workflow_guide.md` | 22.9 KB | 视频工作流完整指南 (698行) |
| `docs/quality_prompt_template.md` | 9.7 KB | 统一品质 Prompt 模板 |
| `docs/video_director_review.md` | 15.7 KB | Phase D 视频品质审查报告 |
| `docs/blender_integration_feasibility.md` | 16.1 KB | Blender Provider 可行性分析 |
| `docs/FIX_social-auto-upload-deps.md` | 1.9 KB | 发布依赖修复记录 |
| `docs/AI漫画开源趋势差距分析报告_20260719.md` | 13.2 KB | 社区趋势分析 |
| `docs/AIComics下一轮迭代功能清单_20260719.md` | 14.9 KB | 迭代路线图 |
| `product_assets/video_production_report.md` | 8.0 KB | 全量生产审计报告 |
| `product_assets/security_audit_report.md` | 9.2 KB | 安全审计报告 (9项检查) |
| `reports/competitor_analysis_2026.md` | — | 竞品分析报告 |
| `reports/gumroad_listing_guide.md` | — | Gumroad 上架指南 |
| `reports/monetization_strategy.md` | — | 变现策略报告 |
| `reports/open_source_launch_posts.md` | — | 开源发布文案 |
| `reports/quality_tracker.md` | — | 质量指标追踪 |
| `reports/social_publish_guide.md` | — | 社交发布指南 |
| `reports/ux_audit_report.md` | — | UX 审计报告 |
| `reports/prd/` | — | PRD 产品需求文档 |
| `reports/reviews/` | — | 审查记录 |
| `scripts/run_style_batch.py` | — | 风格批量运行脚本 |
| `src/aicomic/video_synthesis/audio_mix.py` | — | 音频混音模块 |

### 🛠️ 未提交文件修改 (本批)

| 文件 | 变更行数 | 说明 |
|------|---------|------|
| `pyproject.toml` | 11 | 版本升级 + 描述更新 |
| `scripts/vf_master_loop.py` | 497+ | vf_master_loop v3.0 完整实现 |
| `src/aicomic/providers/executor.py` | 83+ | Provider 执行器增强 |
| `src/aicomic/providers/openai_adapter.py` | 8+ | OpenAI adapter 修复 |
| `src/aicomic/video_synthesis/pipeline.py` | 25+ | 视频合成管线增强 |

---

## [v0.2.0] — 2026-07-19

> **极简重构 + 角色系统 + 供应商层 + 分镜管理 + 640 测试**

v0.2.0 是一次重大功能迭代，覆盖供应商层、角色系统、分镜管理、视频工厂和前端 UX 五大领域，共 **17 个 commits**。代码精简 **-49%**，测试全绿 **640/640**。

### ✨ 主要功能

- **云端优先 + 本地备用供应商层**：默认云端 openai_image + seedance + openai_tts via JieYou(GPT-5.5)；故障自动降级到 local_comfyui/piper
- **角色管理系统**：角色 workshop 编辑、一致性校验、多视图管理
- **分镜版本管理**：diff 对比、版本回滚 (rollback)、分镜面板 (board) 浏览
- **视频工厂 v3.2**：FFmpeg 管线合成、AnimateDiff 集成、风格轮换
- **前端 UX 修复**：空态提示、Review 版本对比、导航高亮、页面标题差异化
- **极简重构**：代码精简 -49%、技术债务清理
- **基础设施**：CI/CD、Issue 模板、Daily upgrade 检测

---

## [v1.0] — 2026-05-06

> 🎬 AIComics v1.0 — AI 漫剧自动生成系统

初始版本发布。基础管线：故事→分镜→图片→配音→视频合成。CLI + Web API + SPA 三端入口。
