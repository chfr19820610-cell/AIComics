# OpenSpace 与 AIComics 集成可行性分析

> 评估日期：2026-07-19
> 范围：检查 OpenSpace (HKUDS ⭐6.7K) 能否取代或增强 AIComics 的 upgrade_pipeline

---

## 目录

1. [现状分析](#1-现状分析)
2. [OpenSpace 核心能力](#2-openspace-核心能力)
3. [AIComics 管线结构](#3-aicomics-管线结构)
4. [集成可能性评估](#4-集成可能性评估)
5. [推荐方案](#5-推荐方案)
6. [实施路线图](#6-实施路线图)

---

## 1. 现状分析

### 1.1 AIComics 项目概览

| 维度 | 值 |
|------|------|
| 定位 | AI 漫剧自动生成系统 (Creator 个人创作者版) |
| 主代码目录 | `10_System/` |
| 核心语言 | Python 3.12 |
| 渲染引擎 | FFmpeg (libx264) + ComfyUI (图片) |
| 管线类型 | Job-driven batch pipeline |
| 当前状态 | 32/32 验证通过，7 个前端路由巡检通过 |

### 1.2 关于 "upgrade_pipeline"

**关键发现：AIComics 中不存在名为 `upgrade_pipeline` 的模块或文件。** 搜索项目目录无匹配结果。

"upgrade_pipeline" 是一个**概念性术语**，指代 AIComics 中与质量升级相关的多条管线：

| 概念管线 | 实际文件 | 说明 |
|----------|----------|------|
| 视频质量升级 | `docs/video_quality_upgrade.md` | 1080p/CRF18/30fps/LUT/字幕美化方案 |
| 生产循环 | `scripts/vf_master_loop.py` | 视频工厂主循环 — 并行生产+缓存跳过+预览模式 |
| 质量门禁 | `scripts/quality_gate_loop.py` | 生成→审查→发布无限质量门禁循环 |
| 合成管线 | `src/aicomic/video_synthesis/pipeline.py` | FFmpeg 场景合成、字幕烧录、输出验证 |
| 批次管线 | `src/aicomic/batch/coordinator.py` | 批次定义→preflight→执行→报告 |
| Job 管线 | `src/aicomic/core/job_builder.py`, `job_control.py` | 任务构建、过滤、重试、调度 |

### 1.3 OpenSpace 安装状态

| 项 | 状态 |
|------|------|
| 代码目录 | `/Users/eric/Desktop/herness/OpenSpace/` — 已安装 |
| Python 虚拟环境 | `.venv/` — 存在 |
| MCP Server (localhost:8765) | ❌ 未运行 (curl health 无响应) |
| 最新版本 | v2 (2026-07-17 release) |
| 核心功能 | Skill Hub + 技能演化引擎 + MCP Server + 本地服务 |

---

## 2. OpenSpace 核心能力

### 2.1 技能演化引擎 (Skill Evolution Engine)

这是 OpenSpace 与 AIComics 集成最相关的子系统。

**演化流程：**

```
EvidenceEvent → TriggerEngine → TriggerJob
    → EvidencePacket → DecisionEngine → Decision
    → AdmissionPolicy → Admission
    → CandidateStore → Candidate
    → AuthoringBackend → StagedSkillEdit
    → Validator → ValidationResult
    → BehaviorEval → SkillBehaviorEvalResult
    → Commit → SkillRecord
```

**支持三种演化模式：**
- `audit_only`：只记录决策，不执行
- `fix_only`：仅允许修复操作
- `autonomous`：全自动演化

**关键模块位置：**

| 模块 | 路径 | 职责 |
|------|------|------|
| Evolution Engine | `openspace/skill_engine/evolution/engine.py` | 编排完整演化流程 (2095 行) |
| Admission | `.../admission.py` | 规则驱动的准入闸门 (1263 行) |
| Candidates | `.../candidates.py` | SQLite 持久化候选存储 (1184 行) |
| Authoring | `.../authoring.py` | 带证据的分阶段编辑 (996 行) |
| Validator | `.../validator.py` | 确定性验证 (1180 行) |
| Behavior Eval | `.../behavior_eval.py` | 行为评估闸门 (2093 行) |
| Decision Engine | `skill_engine/decision/engine.py` | 基于证据的决策 (357 行) |
| Trigger Engine | `skill_engine/triggers/engine.py` | 事件驱动的触发任务 (261 行) |

### 2.2 证据系统 (Evidence Store)

- `EvidenceEvent` → `EvidencePacket` → `EvidenceStore`
- 支持多种证据类型：runtime_snapshot, tool_result, file_history, quality_signal_ref 等
- 可用于跟踪 AIComics 渲染质量指标

### 2.3 技能管理

- 技能注册/搜索/排名 (`registry.py`, `skill_ranker.py`)
- 技能补丁/差异分析 (`patch.py`)
- 捕获合约 (`capture_contract.py`)

### 2.4 MCP Server / 本地 HTTP 服务

- Flask 应用，监听 127.0.0.1:8765
- 支持 MCP 协议 (stdio/SSE/streamable HTTP)
- 提供健康检查、验证、计算机使用 API
- 可作为 AIComics 的集成接口层

---

## 3. AIComics 管线结构

### 3.1 当前管线拓扑

```
故事蓝图 (horror_pipeline.py)
  → Episode Manifest
  → Job Builder (job_builder.py) → Jobs JSON
  → Dispatch (dispatcher.py) → Dispatch Report
  → Provider Requests (providers/) → Provider Execution
  → Asset Scan (qc/asset_scanner.py) → Scan Report
  → Preview Render (render/preview_renderer.py) → Preview Video
  → Subtitle/Audio (render/subtitle_audio.py) → SRT + WAV
  → Release Render (render/release_renderer.py) → Release Video
  → Quality Gate (scripts/quality_gate_loop.py) → PASS/FAIL
  → Publish (publish/) → Publish Pack
  → Season Summary (publish/season_summary.py) → Season Report
```

### 3.2 CL I 命令映射

| 命令 | 功能 |
|------|------|
| `horror-blueprint` | 生成故事蓝图 |
| `build-jobs` | 构建任务包 |
| `dispatch-jobs` | 调度任务 |
| `render-preview` / `render-release` | 渲染视频 |
| `scan-assets` | 扫描素材完整性 |
| `quality-gate` (scripts) | 质量门禁 |
| `run-batch` | 执行批次 |

### 3.3 当前升级方式

- **手动修改**: 修改 `config.py` 或 `render.yaml` 中的参数 (CRF, 分辨率等)
- **脚本级修复**: `scripts/quality_gate_loop.py` 检测到问题后人工介入
- **文档驱动**: `video_quality_upgrade.md` 记录升级方案
- **无自动化演化**: 所有参数调整需人工评估

---

## 4. 集成可能性评估

### 4.1 能否取代 AIComics 管线？

| 能力 | OpenSpace | AIComics 需要 | 取代? |
|------|-----------|---------------|-------|
| 视频渲染/合成 | ❌ 无 | ✅ FFmpeg + ComfyUI | ❌ |
| 资产生成 (图片/TTS) | ❌ 无 | ✅ ComfyUI/Piper | ❌ |
| 批次调度 | ❌ 无 | ✅ Batch Coordinator | ❌ |
| 故事/脚本生成 | ❌ 无 | ✅ Horror Pipeline | ❌ |
| 发布流程 | ❌ 无 | ✅ Publish Pack | ❌ |
| **技能/提示词演化** | **✅ 核心能力** | ⚠️ 手动 | **✅ 可增强** |
| **质量跟踪** | **✅ Evidence Store** | ⚠️ 简单脚本 | **✅ 可增强** |
| **参数优化** | **✅ 演化引擎** | ⚠️ 手动调整 | **✅ 可增强** |
| **触发式自动化** | **✅ Trigger Engine** | ⚠️ 无 | **✅ 可增强** |

**结论：不能取代** — OpenSpace 不是视频渲染引擎或资产生成系统。

### 4.2 能否增强 AIComics？

**可以，在以下具体方向：**

#### 方向 1：渲染参数演化 (高价值)

**现状**：AIComics 的视频参数 (CRF、分辨率、帧率、码率、LUT) 写在 `config.py` 和 `render.yaml` 中，调整需人工评估效果。

**集成方案**：
- OpenSpace 将渲染参数包装为 "参数技能" (Parameter Skills)
- AIComics 渲染后将质量指标 (SSIM/PSNR/VMAF、文件大小、渲染耗时) 作为 `EvidenceEvent` 推送给 OpenSpace
- OpenSpace 的 Evolution Engine 根据质量证据驱动参数演化：
  - `decision → admission → candidate → authoring → validation → behavior_eval → commit`
- 演化结果 (新的参数组合) 写回 `config.py` 或 `render.yaml`

#### 方向 2：提示词/风格技能演化 (中价值)

**现状**：AIComics 的风格色板 (`vf_master_loop.py` 中的 `STYLE_PALETTES`)、恐怖故事模板 (`horror_pipeline.py`) 是硬编码的。

**集成方案**：
- 将风格色板、钩子模板、故事结构注册为 OpenSpace skills
- 每次渲染完成后，将输出反馈作为证据提交
- OpenSpace 自动演化出更高点击率/更短生产周期的风格组合

#### 方向 3：质量门禁增强 (中价值)

**现状**：`quality_gate_loop.py` 是一个简单脚本，只检查文件大小和命名规范。

**集成方案**：
- OpenSpace 的 `TriggerEngine` 监听 AIComics 的证据事件
- 当质量指标异常时，自动生成 `TriggerJob` → 触发重新渲染或参数调整
- 使用 `BehaviorEval` replay gate 对比不同参数组合的实际渲染效果

#### 方向 4：管线健康度监控 (低价值)

**现状**：`scripts/` 下有大量 `validate_*` 脚本手动运行。

**集成方案**：
- OpenSpace 的 `EvidenceStore` 持久化管线运行指标
- 定期 checkpoint 触发 OpenSpace evolution jobs 来自动修复验证失败

### 4.3 当前技术限制

| 限制 | 说明 | 影响 |
|------|------|------|
| OpenSpace MCP 未运行 | `curl :8765/health` 无响应 | 无法立即测试 API 集成 |
| 概念鸿沟 | OpenSpace 管理"技能"，AIComics 是"视频管线" | 需要中间适配层 |
| 无共享数据模型 | 两者 Schema 完全不同 | 需要桥接模块 |
| 缺少已有前例 | 未见 OpenSpace 集成视频管线的案例 | 创新性工作 |

---

## 5. 推荐方案

### 5.1 不建议：大范围改造

- ❌ 不要用 OpenSpace 重写 AIComics 管线
- ❌ 不要在 OpenSpace 里管理视频渲染状态
- ❌ 不要将 batch coordinator 迁移到 OpenSpace

### 5.2 推荐：轻量桥接模式 (Bridge Pattern)

```
┌─────────────────────┐     证据事件      ┌─────────────────────┐
│                     │ ────────────────> │                     │
│    AIComics         │                    │    OpenSpace        │
│                     │ <──────────────── │                     │
│  (视频生产管线)       │   演化决策/新参数   │  (技能演化引擎)       │
└─────────────────────┘                    └─────────────────────┘
```

**核心思路**：
1. AIComics 保持完整的视频生产管线不变
2. 在关键决策点 (渲染参数选择、质量门禁、风格选择) 插入 OpenSpace 接口
3. OpenSpace 负责：参数优化建议、质量证据存储、演化触发
4. 集成点用 MCP API 调用实现

### 5.3 具体实施建议

#### 第一阶段：API 桥接 (1-2 天)

1. 启动 OpenSpace MCP Server
2. 在 AIComics 中创建 `openspace_bridge.py` 模块
3. 实现基础的 HTTP/MCP 客户端 → OpenSpace
4. 验证连通性

#### 第二阶段：参数演化 (2-3 天)

1. 定义 `AiComicsRenderSkill` OpenSpace skill
2. AIComics 渲染后将质量证据 POST 到 OpenSpace
3. OpenSpace 输出优化后的参数配置供 AIComics 使用
4. 实现 `aicomic openspace-evolve` CLI 命令

#### 第三阶段：触发的自动修复 (3-5 天)

1. 配置 OpenSpace TriggerPolicy 监听 AIComics 质量事件
2. 当渲染失败或质量未达标时自动触发演化
3. 演化结果自动应用到下一次运行

---

## 6. 后续行动

### 立即行动
1. ~~`curl :8765/health` → ❌ 未运行~~ → 需先启动 OpenSpace
2. 阅读 OpenSpace 启动文档 (`openspace/local_server/run.sh`)

### 文件说明

| 文件 | 用途 |
|------|------|
| `openspace_integration.md` | 本报告 — 集成可行性分析 |
| `openspace_bridge.py` | (待创建) OpenSpace ↔ AIComics 桥接模块 |
| `skills/openspace_render_evolution.py` | (待创建) OpenSpace 渲染演化 skill |

### 关键联系人/参考

- OpenSpace GitHub: https://github.com/HKUDS/OpenSpace (⭐6.7k)
- OpenSpace 本地路径: `/Users/eric/Desktop/herness/OpenSpace/`
- OpenSpace MCP 端口: 127.0.0.1:8765
- AIComics 系统入口: `10_System/src/aicomic/`

---

> **总结**: OpenSpace **不能取代** AIComics 的升级管线 (它们解决的问题不同)，但可以**有效增强** AIComics 的渲染参数优化、提示词演化和质量监控能力。建议以轻量桥接模式集成，保持两系统独立。
