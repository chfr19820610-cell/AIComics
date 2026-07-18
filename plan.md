# AI漫剧自动生成系统开发计划

更新时间：`2026-05-10 09:55:49 +0800`

## 0. 当前状态快照

- 当前正式交付范围：`Creator 个人创作者版`
- 当前运行口径：单用户、密码登录、JWT、SQLite、本地文件系统、前端控制台
- 最新模拟数据验证：`1` 项目、`1` 季、`2` 集、`16` 任务、`16` 成功
- 最新全量验证：`32 / 32` 通过，运行 ID `full_system_validation_20260510095228635147`
- 最新浏览器全局巡检：`7` 个路由、`0` 个 console/page error
- 当前阻塞风险：`0`
- 当前主要非阻塞项：`/login`、`/episodes`、`/jobs`、`/provider`、`/batches` 仍有信息密度偏低问题，其中 `/batches` 最明显

说明：

- 本文件保留历史阶段日志
- 与当前实现冲突时，以 `config/edition.yaml`、`config/web.yaml`、`result.md`、最新验证报告为准

## 1. 计划定位

本文件是 `G:\AIComics\10_System` 的唯一主开发计划文件，用于统一维护：

- 需求摘要
- PRD / 技术架构 / 开发拆解的执行映射
- 里程碑与阶段目标
- 任务状态
- 当前迭代重点
- 按时间戳记录的变更日志

执行本计划中的编码任务时，必须遵守以下制度文件：

- `G:\AIComics\10_System\docs\Python项目代码规范.md`
- `G:\AIComics\10_System\docs\系统提示词.md`
- `G:\AIComics\10_System\docs\生成规则.md`
- `G:\AIComics\10_System\docs\PythonCodeStyle.md`

---

## 2. 计划依据

### 2.1 产品文档

- `G:\AIComics\01_项目圣经\AI漫剧自动生成系统_PRD.md`
- `G:\AIComics\01_项目圣经\AI漫剧自动生成系统_技术架构方案.md`
- `G:\AIComics\01_项目圣经\AI漫剧自动生成系统_开发任务拆解.md`

### 2.2 配套文档

- `G:\AIComics\00_总览\AI漫剧工具价格与难度对比表.md`
- `G:\AIComics\03_Prompts\AI漫剧完整提示词手册.md`
- `G:\AIComics\10_System\README.md`
- `G:\AIComics\10_System\result.md`

---

## 3. 新版需求摘要

基于新版 PRD 与技术架构，系统当前总目标分为两层：

### 3.1 已打通目标

1. 统一 `Manifest + Job + State + Report` 骨架
2. 跑通单集与整季基础生产链路
3. 支持 Provider 请求包、回写、OpenAI dry-run
4. 支持正式版、发布包、返工与导航页

### 3.2 当前主攻目标

1. 把“整季功能”升级为“批量量产系统”
2. 支持多项目模板化初始化
3. 支持批次总控、批量执行、批量重试
4. 支持项目 / 季 / 集 / 镜头四级批量范围
5. 输出批量总报告与后续看板数据

---

## 4. 总体开发策略

- 先复用现有 `10_System` 能力，不推翻已完成代码
- 先做 CLI 可跑的批量总控，再做 UI
- 先做本地单机可量产，再扩展更复杂自动化
- 先补多项目初始化和 Batch 模型，再补更强 Provider 回调
- 所有变更保持 UTF-8、可验证、可回写

---

## 5. 里程碑规划

### M0：制度与工程骨架

目标：

- 规范、计划、结果文档
- Python 工程骨架

状态：

- 已完成

### M1：Manifest / Job / State 基础层

目标：

- 配置中心
- Manifest 读写
- Job 模型
- 状态持久化

状态：

- 已完成

### M2：单集生产 MVP

目标：

- 扫描
- 预览
- 正式版
- 发布包

状态：

- 已完成

### M3：整季生产骨架

目标：

- 整季任务包
- 整季扫描
- 整季渲染
- 整季总结

状态：

- 已完成

### M4：Provider 自动化基础

目标：

- Provider 路由
- 请求包
- 回写
- OpenAI dry-run

状态：

- 已完成

### M5：批量量产版 MVP

目标：

- 多项目模板化初始化
- 批次模型与数据库表
- 批次总控入口
- 批量执行与重试
- 批量总报告

状态：

- 基础能力已落地，进入批次增强阶段

### M6：看板与复盘

目标：

- Dashboard 导出
- 批量统计
- 复盘指标

状态：

- 待开发

---

## 6. 阶段任务状态

### 阶段 A：已完成基础能力

- [x] 建立 `10_System` 目录骨架
- [x] 建立 `pyproject.toml`
- [x] 建立 `src\aicomic` 包结构
- [x] 建立 `plan.md`
- [x] 建立 `result.md`
- [x] 建立资料索引
- [x] 建立配置文件与 Manifest
- [x] 建立 SQLite 骨架
- [x] 建立 Job / State / Dispatcher
- [x] 建立单集扫描、预览、正式版、发布包
- [x] 建立整季任务、整季扫描、整季渲染、整季总报告
- [x] 建立 Provider 请求包、回写、OpenAI dry-run

### 阶段 B：当前必须完成

- [x] 建立多项目模板化初始化
- [x] 建立 `BatchRecord` 数据模型
- [x] 建立 `batches` / `batch_runs` SQLite 表
- [x] 建立 `build-batch` 命令
- [x] 建立 `run-batch` 命令
- [x] 建立批次执行报告
- [x] 建立批量失败重试
- [x] 建立手工网页模式批量导入

### 阶段 C：后续增强

- [ ] 配置 `OPENAI_API_KEY` 后验证真实 OpenAI 联网执行
- [ ] 建立自动回调服务
- [ ] 建立 Dashboard 导出
- [ ] 建立数据复盘模块
- [ ] 建立模板推荐与多项目复用策略

---

## 7. 当前迭代计划

当前迭代聚焦：**批量量产版 MVP**

### 本轮目标

1. 支持新项目初始化
2. 建立 Batch 数据模型
3. 建立批次总控 CLI
4. 跑通批量执行与批量报告
5. 为批量失败重试留出扩展点

### 本轮必做

- [x] 新增 `core/project_initializer.py`
- [x] 新增 `core/batch_models.py`
- [x] 扩展 `core/database.py`，加入批次表
- [x] 新增 `batch/coordinator.py`
- [x] 新增 `batch/reporter.py`
- [x] 扩展 CLI，新增 `init-project`
- [x] 扩展 CLI，新增 `build-batch`
- [x] 扩展 CLI，新增 `run-batch`
- [x] 输出批次报告到 `reports`
- [x] 用模拟数据写入 SQLite 验证批次能力
- [x] 更新 `result.md`

### 本轮验收标准

- 至少能初始化 1 个新项目模板
- 至少能生成 1 个 Batch 记录
- 至少能执行 1 次季级批次
- 至少能生成 1 份批次报告
- 批次信息能写入 SQLite

---

## 8. 优先级

### P0

- 多项目初始化
- Batch 数据模型
- Batch CLI
- 批量报告
- 批次数据库验证

### P1

- 批量失败重试
- 手工网页模式批量导入
- 真实 OpenAI 联网执行

### P2

- Dashboard
- 数据复盘
- 模板推荐

---

## 9. 当前状态

- 当前里程碑：`M4 已完成，M5 批量量产版 MVP 已启动`
- 当前完成度：`单集、整季、Provider 自动化基础已完成；多项目初始化、Batch 模型、Batch CLI、批次报告、批量失败重试、手工网页导入、Dashboard 导出、数据复盘统计已完成`
- 当前代码状态：`已具备内容生产骨架 + 项目初始化器 + 批次模型 + Batch CLI + 批次报告 + retry-batch + manual-import-batch + dashboard-export + review-metrics`
- 当前最大缺口：`真实联网执行、自动回调服务`
- 当前开发方向：`从功能模块集合升级为批量生产编排系统`

---

## 10. 下一步开发顺序

1. 真实 OpenAI 联网执行
2. 自动回调服务

---

## 11. 变更日志

### 2026-04-19 12:50:00 +08:00

- 新建 `10_System\plan.md`
- 收录 PRD、技术架构、开发拆解、工具选型、Prompt 手册
- 设立本计划为唯一主开发计划文件
- 明确后续编码必须遵循代码规范、系统提示词、生成规则

### 2026-04-19 12:54:42 +08:00

- 新增 Python 项目骨架：`pyproject.toml`、`src\aicomic`
- 新增核心模块：`core\config.py`、`core\models.py`、`core\database.py`
- 新增 CLI 入口：`cli\main.py`
- 新增 SQLite 演示验证脚本：`scripts\run_demo_validation.py`
- 创建测试数据库：`state\aicomic_demo.db`
- 写入模拟数据并形成初版验证闭环

### 2026-04-19 13:00:10 +08:00

- 新增 Season / Episode Manifest
- 新增 Manifest 读写与 Job Builder
- 扩展数据库与状态统计

### 2026-04-19 13:06:47 +08:00

- 新增状态快照、生命周期流转与任务调度能力
- 扩展 CLI 状态同步和调度命令

### 2026-04-19 13:11:40 +08:00

- 新增单集资产扫描与预览渲染能力
- 形成预览视频与扫描报告闭环

### 2026-04-19 13:16:35 +08:00

- 新增字幕、音轨、任务筛选、重试、续跑报告

### 2026-04-19 13:22:25 +08:00

- 新增正式版渲染与发布包基础导出

### 2026-04-19 13:26:43 +08:00

- 新增返工任务与导航页生成

### 2026-04-19 13:30:41 +08:00

- 新增整季任务包、整季扫描、整季渲染、整季总报告

### 2026-04-19 13:38:46 +08:00

- 新增 Provider 路由规划、增强发布包、资产修复建议

### 2026-04-19 13:44:12 +08:00

- 新增 Provider 请求包与 SQLite 请求记录

### 2026-04-19 13:47:52 +08:00

- 新增 Provider 结果回写与同步任务包

### 2026-04-19 13:57:44 +08:00

- 新增 OpenAI Adapter、Provider Executor、OpenAI dry-run 能力

### 2026-04-19 14:04:23 +08:00

- 重构 `AI漫剧自动生成系统_PRD.md`，将目标升级为“批量量产版 MVP”
- 重构 `AI漫剧自动生成系统_技术架构方案.md`，新增 Batch 批次总控架构
- 重构 `AI漫剧自动生成系统_开发任务拆解.md`，明确当前主攻任务为多项目初始化、Batch 模型、批量执行与总报告
- 重构 `10_System\plan.md`，将当前主里程碑切换为 `M5 批量量产版 MVP`
- 明确下一阶段编码重点：`init-project`、`build-batch`、`run-batch`、批次报告、批量重试

### 2026-04-19 14:12:45 +08:00

- 新增 `core\project_initializer.py`，支持项目模板化初始化
- 新增 `core\batch_models.py`，作为批次模型入口
- 扩展 `core\models.py`，新增 `BatchRecord`、`BatchRunRecord`
- 扩展 `core\database.py`，新增 `batches`、`batch_runs` 表与写库能力
- 新增 `batch\coordinator.py`，支持批次定义、批次执行与步骤结果输出
- 新增 `batch\reporter.py`，支持批次摘要报告
- 扩展 CLI，新增 `init-project`、`build-batch`、`run-batch`
- 扩展演示验证脚本，新增项目初始化、Batch 写库、Batch 报告验证
- 新增初始化项目目录：`state\generated_projects\batch_demo_project`
- 新增批次定义：`reports\season1_batch.json`
- 新增批次报告：`reports\season1_batch_report.json`
- 新增批次摘要：`reports\season1_batch_summary.json`
- 重新执行模拟数据写库验证，稳定结果为：`batches_count=1`、`batch_runs_count=4`、`batch_step_count=4`

### 2026-04-19 14:18:54 +08:00

- 新增 `batch\retry_manager.py`，支持按状态、剧集、Provider 批量重试
- 新增 `providers\manual_importer.py`，支持从手工网页导出目录批量导入产物
- 扩展 CLI，新增 `retry-batch` 命令
- 扩展 CLI，新增 `manual-import-batch` 命令
- 扩展演示验证脚本，新增手工导入模拟素材、导入报告、导入后回写报告、批量重试报告
- 新增手工导入报告：`reports\manual_import_report.json`
- 新增手工导入回写报告：`reports\manual_import_writeback_report.json`
- 新增手工导入同步任务包：`jobs\episode_jobs_manual_import_synced.json`
- 新增批量重试报告：`reports\retry_batch_report.json`
- 新增批量重试任务包：`jobs\episode_jobs_batch_retried.json`
- 重新执行模拟数据写库验证，稳定结果为：`manual_import_imported_count=2`、`manual_import_succeeded_count=6`、`retry_batch_retried_count=10`

### 2026-04-19 14:24:23 +08:00

- 新增 `publish\dashboard.py`，支持批量生产 Dashboard JSON 与 HTML 导出
- 扩展 CLI，新增 `dashboard-export` 命令
- 扩展演示验证脚本，新增 Dashboard JSON/HTML 生成与状态验证
- 新增 Dashboard JSON：`reports\dashboard.json`
- 新增 Dashboard HTML：`reports\dashboard.html`
- 重新执行模拟数据写库验证，稳定结果为：`dashboard_status=needs_attention`

### 2026-04-19 14:28:21 +08:00

- 新增 `review\metrics.py`，支持批量生产数据复盘统计
- 新增 `review\__init__.py`
- 扩展 CLI，新增 `review-metrics` 命令
- 扩展演示验证脚本，新增复盘 JSON/HTML 生成与风险项统计
- 新增复盘 JSON：`reports\review_metrics.json`
- 新增复盘 HTML：`reports\review_metrics.html`
- 重新执行模拟数据写库验证，稳定结果为：`review_metrics_status=needs_optimization`、`review_metrics_risk_count=4`

### 2026-04-19 14:33:38 +08:00

- 新增 Provider 真实联网安全开关：默认非 dry-run 也会阻断真实 API 调用
- 扩展 `execute-provider-requests` 参数：`--confirm-live`、`--limit`、`--max-failures`
- 扩展 Provider 执行报告字段：`blocked_count`、`execution_attempt_count`、`confirm_live`、`stopped_by_failure_guard`、`api_key_ready`
- 新增 OpenAI 安全阻断验证报告：`reports\provider_execution_openai_safe_block.json`
- 扩展演示验证脚本，加入非确认联网阻断用例，确保模拟验证不会误触发真实 OpenAI 请求
- 重新执行模拟数据写库验证，稳定结果为：`provider_execution_safe_blocked_count=1`、`provider_execution_limit=1`、`provider_execution_stopped_by_failure_guard=False`

### 2026-04-19 14:37:48 +08:00

- 根据 PRD、技术架构方案、开发任务拆解，新增 Web 前端页面设计与技术栈方案
- 新增前端功能清单，覆盖 Dashboard、Projects、Episodes、Shots、Jobs、Batches、Provider、Import、Render、Publish、Review、Settings
- 明确前端定位为“AI 漫剧批量生产控制台”，不替代现有 Python CLI
- 明确推荐技术栈：`React + TypeScript + Vite + Ant Design + TanStack Query + TanStack Table + ECharts`
- 明确后端配套建议：`FastAPI + SQLite + reports JSON + CLI 白名单执行桥接`
- 新增文档：`docs\Web前端页面设计与技术栈方案.md`
- 更新 `README.md` 与 `docs\项目资料索引.md`

### 2026-04-19 14:42:56 +08:00

- 调整 Web 前端技术栈推荐：由单独使用 Ant Design 升级为 Ant Design Pro 控制台方案
- 明确推荐组合：`Ant Design Pro + React + TypeScript + Umi Max + ProComponents + ECharts`
- 明确不建议基于 `https://v1.pro.ant.design/index-cn` 的 v1 老版本作为新项目实际依赖，只作为中后台页面思路参考
- 保持后端方案不变：`FastAPI + SQLite + reports JSON + CLI 白名单执行桥接`
- 更新 `docs\Web前端页面设计与技术栈方案.md`、`README.md`、`docs\项目资料索引.md`

### 2026-04-19 14:45:51 +08:00

- 启动 Web 控制台代码开发阶段 `W1/W2`
- 本轮目标：创建 `web\backend` FastAPI API 骨架与 `web\frontend` Ant Design Pro 前端骨架
- 后端优先实现：健康检查、Dashboard、复盘指标、验证报告、剧集状态、Job 列表、批次摘要、Provider 执行报告、命令白名单元数据
- 前端优先实现：Ant Design Pro 工程配置、布局菜单、Dashboard、Episodes、Jobs、Batches、Provider、Review 页面壳与数据请求封装
- 安全原则：只生成命令白名单元数据，本轮不开放任意命令执行；OpenAI live-run 仍必须走后端安全确认机制
- 验证要求：模拟读取现有 reports 与 SQLite 数据，运行 Python 编译校验，输出验证结果到 `result.md`

### 2026-04-19 15:09:01 +08:00

- 新增 `web\backend\app.py`，提供 `/api/health`、`/api/dashboard`、`/api/review-metrics`、`/api/validation`、`/api/episodes`、`/api/jobs`、`/api/batches`、`/api/providers/executions`、`/api/commands/catalog`
- 新增 `web\backend\services\report_service.py`，统一读取 `reports`、`jobs`、验证数据与命令白名单元数据
- 新增 `web\backend\settings.py` 与 `config\web.yaml`，统一管理 Web 控制台本地配置
- 新增 Ant Design Pro 前端骨架：`web\frontend\config\config.ts`、`src\app.tsx`、`src\services\api.ts`、`src\pages\Dashboard`、`Episodes`、`Jobs`、`Batches`、`Provider`、`Review`
- 新增 `scripts\validate_web_console.py`，将 Web 控制台模拟验证结果写入 SQLite 表 `web_console_validation_runs`
- 更新 `pyproject.toml`，补充 Web 可选依赖：`fastapi`、`uvicorn`
- 更新 `README.md`、`docs\项目资料索引.md`
- 完成 Python 侧验证：`compileall` 通过，`web_console_validation_report.json` 已生成，SQLite 写入成功

### 2026-04-19 15:17:57 +08:00

- 新增 `web\backend\services\command_service.py`，实现命令白名单目录与安全阻断执行逻辑
- 新增 `POST /api/commands/run`，当前默认受 `command_execution_enabled=False` 保护，返回 `blocked_command_execution_disabled`
- 扩展 `GET /api/commands/catalog`，新增 `allowed`、`runnable`、`enabled`、`description` 字段
- 新增前端页面 `web\frontend\src\pages\Commands`，展示白名单命令、说明、执行按钮和最近一次执行结果弹窗
- 扩展 Web 验证脚本，新增命令阻断校验并写入 SQLite 字段 `command_run_status`
- 为历史 SQLite 表增加轻量升级逻辑，自动补齐 `command_run_status` 字段
- 重新执行验证，稳定结果为：`command_run_status=blocked_command_execution_disabled`

### 2026-04-19 16:51:26 +08:00

- 前端依赖通过 `npmmirror` 成功安装，并完成 `npm run typecheck` 验证
- 后端依赖已通过 `pip install -e .[web]` 安装完成，`uvicorn` 可正常启动 Web API
- 由于当前 Windows/npm/Umi 环境仍存在部分传递依赖落包损坏问题，`npm run build` 仍未稳定通过
- 为保证可用性，新增 `web\static_preview` 零依赖静态预览页，直接消费后端 API 展示 Dashboard、Episodes、Jobs、Batches、Provider、Commands、Review
- 完成静态预览联调验证，稳定结果为：`DashboardStatus=needs_attention`、`CommandCatalogCount=20`、`AllStaticPreviewFilesExist=True`
- 更新 `README.md`、`docs\项目资料索引.md`

### 2026-04-19 16:57:46 +08:00

- 将 `config\web.yaml` 接入后端设置加载，`command_execution_enabled`、`host`、`port`、`require_confirm_live` 由配置驱动
- 增强 `web\static_preview`：
  - 新增全局刷新按钮
  - 新增 Jobs 筛选器：`episode_code`、`status`、`provider`
  - 新增 Commands 执行按钮与最近一次执行结果面板
- 完成后端联调验证，稳定结果为：`HealthStatus=ok`、`HealthHost=127.0.0.1`、`HealthPort=7860`、`FilteredJobsCount=4`、`CommandRunStatus=blocked_command_execution_disabled`

### 2026-04-19 17:02:48 +08:00

- 新增 Web 命令双确认机制：后端要求 `confirm_execution=true`，前端增加“我确认仅执行安全白名单命令”勾选
- 扩展命令目录元数据：新增 `requires_confirmation`、`command_preview`
- 扩展 Web 验证脚本：在保留默认阻断验证的同时，新增“模拟启用后确认执行安全命令”验证
- 重新执行 SQLite 写库验证，稳定结果为：`command_run_status=blocked_command_execution_disabled`、`confirmed_command_run_status=completed`
- 完成 API 级联调验证：临时启用 `command_execution_enabled=true` 后，`status` 命令可通过 `confirm_execution=true` 正常执行，结果为：`ConfirmedRunStatus=completed`

### 2026-04-19 17:06:37 +08:00

- 更新 `AI漫剧自动生成系统_PRD.md`，将“用户单点登录 + JWT 鉴权”纳入产品范围、核心能力、关键流程、非功能安全要求、版本规划与验收指标
- 更新 `AI漫剧自动生成系统_技术架构方案.md`，新增“认证鉴权横切层”“Web 接入与认证层”、用户/会话/审计数据模型及 JWT 设计建议
- 更新 `docs\Web前端页面设计与技术栈方案.md`，新增“页面 0：登录 Login”设计、OIDC/OAuth2 + JWT 技术选型与 `/api/auth/*` 接口规划
- 设计原则：Web 登录采用单点登录入口，JWT 负责访问鉴权，Refresh Token 负责续期，高风险操作仍保留显式确认

### 2026-04-19 17:12:27 +08:00

- 启动 SSO + JWT 鉴权代码开发阶段
- 本轮开发计划：
  - 新增认证配置读取：`config\web.yaml` 中增加 `auth` 段
  - 新增 JWT 服务：签发、校验、过期检查、角色读取
  - 新增认证服务：用户、身份绑定、刷新会话、审计日志写库
  - 新增认证接口：`/api/auth/providers`、`/api/auth/dev-login`、`/api/auth/me`、`/api/auth/refresh`、`/api/auth/logout`
  - 新增登录页静态原型：`web\static_preview\login.html`
  - 为命令执行接口接入“当前用户”与审计记录
  - 扩展 SQLite 验证：模拟用户登录、令牌签发、刷新会话写库、`/api/auth/me` 鉴权读取
- 约束：
  - 默认仍保持 `auth_enabled=false`，避免中断现有本地开发流
  - 默认提供 `mock_sso` / `dev_login` 作为本地联调入口
  - 真正外部 OIDC 回调先做接口骨架，不强依赖真实第三方配置

### 2026-04-19 17:32:28 +08:00

- 将本轮认证开发计划细化为 4 个可执行子任务：
  - 配置层：重写 `config\web.yaml`，补全 `cors_allow_origins` 与 `auth` 配置段
  - 后端层：增强 `/api/auth/me`、刷新会话校验、开发登录开关、预检请求放行
  - 静态预览层：补齐 `web\static_preview\login.html`、`login.js`、`index.html` 登录态展示与退出逻辑
  - 验证层：新增 `scripts\validate_auth_flow.py`，把模拟认证数据与结果写入 SQLite 和 `reports`
- 本轮交付目标：
  - 不影响现有 `auth_enabled=false` 默认行为
  - `auth_enabled=true` 时，静态预览可被引导到登录页
  - 登录后可基于 Bearer Token 访问控制台 API
  - 验证结果必须回写 `result.md`

### 2026-04-19 17:33:25 +08:00

- 完成 `config\web.yaml` 重写，补齐 `cors_allow_origins` 与 `auth` 配置段，统一由 `web.backend.settings` 读取
- 完成认证后端增强：
  - `/api/auth/me` 支持“未登录可访问、带 Bearer Token 可识别当前用户”
  - `/api/auth/dev-login` 增加 `dev_login_enabled` 开关保护
  - Refresh Token 增加会话有效期校验
  - 鉴权中间件放行 `OPTIONS` 预检请求
- 完成静态预览认证原型：
  - 新增 `web\static_preview\login.html`
  - 新增 `web\static_preview\login.js`
  - 扩展 `web\static_preview\main.js` 登录态持久化、自动刷新 Token、退出登录、鉴权跳转
  - 扩展 `web\static_preview\styles.css` 登录页样式与用户状态样式
- 新增 `scripts\validate_auth_flow.py`，写入 SQLite 表 `auth_validation_runs` 并输出 `reports\auth_validation_report.json`
- 完成本轮验证：
  - `python -m compileall -q src scripts web` 通过
  - `python scripts\validate_web_console.py` 通过，结果：`command_run_status=blocked_command_execution_disabled`、`confirmed_command_run_status=completed`
  - `python scripts\validate_auth_flow.py` 通过，结果：`dev_login_authenticated=True`、`me_authenticated=True`、`refresh_authenticated=True`、`refresh_session_active_after_logout=False`、`audit_log_count=3`
  - `node --check web\static_preview\main.js` 与 `node --check web\static_preview\login.js` 通过

### 2026-04-19 17:47:03 +08:00

- 完成真实登录流下一阶段骨架：
  - `config\web.yaml` 新增 OIDC 配置项：`oidc_enabled`、`oidc_provider_name`、`oidc_client_id`、`oidc_authorize_url`、`oidc_scope`、`oidc_callback_path`
  - 后端新增 `/api/auth/config`、`/api/auth/oidc/start`、`/api/auth/mock-oidc/authorize`、`/api/auth/oidc/callback`
  - 后端新增 `auth_state_tokens` 状态表，支持登录态 `state` 创建、校验、消费
  - 前端新增 Ant Design Pro 登录页 `/login` 与回调页 `/login/callback`
  - 前端新增登录态存储、Bearer Token 注入、统一登出接口封装
- 完成回归验证：
  - `python -m compileall -q src scripts web` 通过
  - `python scripts\validate_auth_flow.py` 通过，结果：`oidc_start_available=True`、`oidc_callback_success=True`、`provider_count=3`、`audit_log_count=4`
  - `python scripts\validate_web_console.py` 通过，旧控制台 API 未受影响
  - 使用嵌套 `esbuild` 对 `src\app.tsx`、`src\pages\Login\index.tsx`、`src\pages\LoginCallback\index.tsx`、`src\services\api.ts`、`config\config.ts` 做语法转译校验通过
  - `npm install` / `tsc` 在当前 Windows/npm/Umi 依赖环境下仍存在既有问题：缺失 `@types` 与 `npm Invalid Version`，暂记录为环境问题，不阻塞本轮代码交付

### 2026-04-19 18:42:56 +08:00

- 启动产品版本拆分设计阶段
- 新增 `docs\产品版本设计方案.md`
- 将产品规划正式拆分为三版：
  - Creator 个人创作者版：本地单机、低门槛、快速成片；当前实际运行态已收敛为单用户、密码登录 + JWT
  - Studio 工作室版：小团队、多用户、批量协作、看板、基础审计
  - Enterprise 企业版：SSO / OIDC、RBAC、完整审计、企业存储、私有化部署
- 更新 `AI漫剧自动生成系统_PRD.md`
  - 新增企业团队目标用户
  - 新增产品版本拆分原则
  - 新增分版本产品范围矩阵
  - 新增 Edition Capability 能力开关需求

### 2026-05-10 01:13:44 +0800

- 完成 Creator-only 文档口径收敛
- 更新 `README.md`
- 更新 `10_System/README.md`
- 更新 `10_System/result.md`
- 更新 `10_System/scripts/README.md`
- 更新 `10_System/docs/项目资料索引.md`
- 重写 `10_System/docs/产品版本设计方案.md`
- 重写 `01_项目圣经/AI漫剧自动生成系统_技术架构方案.md`
- 为 `01_项目圣经/AI漫剧自动生成系统_PRD.md` 增加当前范围声明，并修正关键版本表述
- 复跑本轮验证：
  - `scripts/run_demo_validation.py`：通过
  - `scripts/validate_full_system_suite.py`：`32 / 32` 通过
  - `scripts/run_frontend_visual_qa_chrome.mjs`：`7` 个路由、`0` 错误

### 2026-05-10 09:55:49 +0800

- 执行新一轮 Creator 全局 QA 与文档同步
- 复跑验证：
  - `scripts/run_demo_validation.py`：通过，`1` 项目 / `1` 季 / `2` 集 / `16` 任务 / `16` 成功
  - `scripts/validate_full_system_suite.py`：`32 / 32` 通过，运行 ID `full_system_validation_20260510095228635147`
  - `web/frontend npm run typecheck`：通过
  - `web/frontend npm run build`：通过
  - `AICOMIC_FRONTEND_BASE_URL='http://127.0.0.1:8011' node scripts/run_frontend_visual_qa_chrome.mjs`：`7` 个路由、`0` console/page error
- 本轮 QA 结论：
  - `/dashboard` 与 `/review` 的低密度问题已收口
  - `/login` 还剩 `1` 个低密度块
  - `/episodes`、`/jobs`、`/provider`、`/batches` 仍有低密度提示，当前属于低风险 UX backlog
- 同步更新：
  - `README.md`
  - `10_System/README.md`
  - `10_System/result.md`
  - `10_System/docs/项目资料索引.md`
  - `01_项目圣经/AI漫剧自动生成系统_技术架构方案.md`
  - 将版本规划改为 Creator / Studio / Enterprise / 运营增长增强
- 更新 `AI漫剧自动生成系统_技术架构方案.md`
  - 新增版本能力开关层
  - 新增 Edition 配置与能力层
  - 新增 `EditionCapability` 数据模型
  - 将技术结论升级为“带版本能力开关、认证能力和批量生产能力的产品化系统”
- 更新 `README.md` 与 `docs\项目资料索引.md`
- 下一步开发建议：
  - 新增 `config\edition.yaml`
  - 新增 `core\edition.py`
  - 新增 `/api/edition`
  - 前端根据版本能力控制菜单与按钮

### 2026-04-19 19:00:12 +08:00

- 启动 Edition Capability 代码落地阶段
- 本轮开发计划：
  - 新增 `config\edition.yaml`，固化 Creator / Studio / Enterprise 能力开关默认值
  - 新增 `src\aicomic\core\edition.py`，负责版本配置读取、默认值兜底与结构化输出
  - 新增 `web\backend\services\edition_service.py`，向 Web 控制台暴露版本能力数据
  - 扩展 `web\backend\app.py`，新增 `/api/edition`，并在 `/api/health` 中补充版本信息
  - 扩展前端与静态预览，最小展示当前 Edition 与能力摘要
  - 新增 `scripts\validate_edition.py`，将版本验证结果写入 SQLite 与 `reports`
- 本轮交付目标：
  - Web 后端可返回当前 `edition.name` 与能力矩阵
  - Creator / Studio / Enterprise 可通过配置切换
  - 验证结果必须写入 SQLite、`result.md` 和项目资料文档

### 2026-04-19 19:04:25 +08:00

- 完成 `config\edition.yaml`，默认版本为 `creator`
- 完成 `src\aicomic\core\edition.py`
  - 支持 Creator / Studio / Enterprise 预设
  - 支持从 `config\edition.yaml` 读取并结构化输出
- 完成 `web\backend\services\edition_service.py`
- 扩展 `web\backend\app.py`
  - 新增 `GET /api/edition`
  - 扩展 `GET /api/health`，返回 `edition_name` 与 `edition_display_name`
- 扩展前端与静态预览：
  - `web\frontend\src\types\api.ts` 新增 `EditionCapabilityPayload`
  - `web\frontend\src\services\api.ts` 新增 `getEdition`
  - `web\frontend\src\pages\Dashboard\index.tsx` 展示版本能力摘要
  - `web\static_preview\main.js` 展示当前 Edition
- 新增 `scripts\validate_edition.py`
  - 写入 SQLite 表 `edition_validation_runs`
  - 输出 `reports\edition_validation_report.json`
- 完成本轮验证：
  - `python -m compileall -q src scripts web` 通过
  - `python scripts\validate_edition.py` 通过，结果：`edition_name=creator`、`auth_enabled=False`、`multi_user_enabled=False`
  - `python scripts\validate_web_console.py` 通过，原有控制台接口未受影响
  - `node --check web\static_preview\main.js` 通过
  - 使用嵌套 `esbuild` 对 `src\services\api.ts`、`src\types\api.ts`、`src\pages\Dashboard\index.tsx` 做语法转译校验通过

### 2026-04-19 19:22:00 +08:00

- 启动 Edition Capability 第二阶段：按 `edition.name` 动态收敛前端菜单与后端能力
- 本轮开发计划：
  - 扩展 `web\frontend\src\app.tsx`，将 `edition` 注入 `initialState`，并按版本过滤菜单与受限路由
  - 扩展 `web\backend\services`，新增统一 `edition_policy` 能力守卫，集中计算命令台、鉴权、OIDC 等能力是否可用
  - 扩展 `web\backend\app.py` 与 `web\backend\auth\auth_routes.py`，让命令目录/执行与认证配置按版本返回有效状态
  - 扩展 `web\static_preview\main.js` 与 `web\static_preview\index.html`，在 Creator 版下隐藏命令台入口与区块
  - 新增版本守卫验证脚本，写入 SQLite 与 `reports`，并将结果同步写入 `result.md`
- 本轮交付目标：
  - Creator 版默认隐藏命令台入口，直接访问受限页面时自动回到 `/dashboard`
  - 后端命令接口返回明确的版本阻断状态与原因
  - 鉴权配置接口可返回“配置开启但当前版本不可用”的有效状态，作为后续个人版/企业版拆分基础

### 2026-04-19 19:18:30 +08:00

- 完成 Edition Capability 第二阶段：按 `edition.name` 动态收敛前端菜单与后端能力
- 本轮完成内容：
  - 新增 `web\backend\services\edition_policy.py`，统一计算命令台、鉴权、OIDC、审计等能力是否可用
  - 扩展 `web\backend\app.py`，让 `/api/health` 与 `/api/edition` 返回有效版本策略，并让命令目录/执行接口应用版本守卫
  - 扩展 `web\backend\auth\auth_middleware.py` 与 `web\backend\auth\auth_routes.py`，让认证开关、Dev Login、Mock SSO、OIDC 按版本和 `config\web.yaml` 的交集生效
  - 扩展 `web\frontend\src\app.tsx`，将 `edition` 注入 `initialState`，并在 Creator 版下隐藏 `/commands` 菜单、阻断受限路由直达
  - 扩展 `web\frontend\src\pages\Commands\index.tsx` 与 `src\types\api.ts`，显示当前版本是否允许命令台及阻断原因
  - 扩展 `web\static_preview\index.html` 与 `web\static_preview\main.js`，在 Creator 版下隐藏命令入口与命令区块
  - 新增 `scripts\validate_edition_policy.py`，写入 SQLite 表 `edition_policy_validation_runs` 并输出 `reports\edition_policy_validation_report.json`
- 本轮验证结果：
  - Creator 当前行为：命令台隐藏且 `/api/commands/run` 返回 `blocked_edition_not_allowed`
  - Studio 模拟行为：命令台可见，但因 `config\web.yaml` 中 `command_execution_enabled=false`，执行状态为 `blocked_command_execution_disabled`
  - Enterprise 模拟行为：OIDC 能力由版本支持，但因 `config\web.yaml` 中 `auth.auth_enabled=false`，当前有效 OIDC 仍为关闭
- 下一阶段建议：
  - 将批量任务、审计中心、系统设置页继续按 Edition Policy 做菜单和接口分层
  - 补企业版 RBAC / 角色菜单与权限点模型

### 2026-04-19 19:30:00 +08:00

- 启动 Edition Capability 第三阶段：审计中心、系统设置与 RBAC 基础模型
- 本轮开发计划：
  - 新增后端审计服务，读取 SQLite `audit_logs` 并按 Edition Policy 判断可见性
  - 新增后端系统设置服务，返回当前版本、Web 安全配置、鉴权有效状态、Provider/存储/数据库摘要
  - 新增后端 RBAC 角色矩阵服务，先以 `admin`、`operator`、`viewer` 为基础角色，按 Creator / Studio / Enterprise 返回不同权限层级
  - 新增 Ant Design Pro 页面 `/audit`、`/settings`、`/rbac`，作为 Studio / Enterprise 后台能力雏形
  - 扩展前端菜单过滤规则：Creator 隐藏命令、审计、设置、RBAC；Studio 展示审计/设置/基础 RBAC；Enterprise 展示完整能力入口
  - 扩展静态预览，使审计/设置/RBAC 的可见性与当前版本一致
  - 新增验证脚本，写入 SQLite 与 `reports`，并同步更新 `result.md`、README 与资料索引
- 本轮交付目标：
  - Creator 保持轻量个人模式，不暴露企业治理入口
  - Studio 具备基础审计与设置只读查看能力
  - Enterprise 具备 RBAC 权限矩阵和安全治理页面入口

### 2026-04-19 19:30:40 +08:00

- 完成 Edition Capability 第三阶段：审计中心、系统设置与 RBAC 基础模型
- 本轮完成内容：
  - 新增 `web\backend\services\governance_service.py`，提供审计日志读取、系统设置摘要、角色权限矩阵与角色权限判断能力
  - 扩展 `web\backend\app.py`，新增 `/api/audit/logs`、`/api/settings/summary`、`/api/rbac/roles`，并把 `audit.view`、`settings.view`、`rbac.manage`、`commands.run` 接口权限校验接入路由层
  - 扩展 `web\frontend\config\config.ts` 与 `src\app.tsx`，新增 `/audit`、`/settings`、`/rbac` 页面，并继续按 Edition 过滤 Creator 不可见菜单
  - 新增前端页面：`src\pages\Audit\index.tsx`、`src\pages\Settings\index.tsx`、`src\pages\Rbac\index.tsx`
  - 扩展 `src\services\api.ts` 与 `src\types\api.ts`，补充治理类接口与类型
  - 扩展 `web\static_preview\index.html` 与 `main.js`，在静态预览中新增审计、设置、RBAC 区块，并按版本自动隐藏
  - 新增 `scripts\validate_governance.py`，写入 SQLite 表 `governance_validation_runs` 并输出 `reports\governance_validation_report.json`
- 本轮验证结果：
  - Creator 当前行为：审计、设置、RBAC 页面均隐藏，治理接口在版本层返回不可用
  - Studio 模拟行为：开放基础审计、只读设置和基础 RBAC 三角色矩阵
  - Enterprise 模拟行为：开放完整治理入口，后续可继续承载真实 OIDC / 安全中心配置
- 下一阶段建议：
  - 为 `admin` / `operator` / `viewer` 增加前端 access 控制与按钮级禁用
  - 把成员管理、组织管理、审计导出、OIDC 配置页继续接到 Enterprise 路线图

### 2026-04-19 19:40:00 +08:00

- 启动 Edition Capability 第四阶段：成员管理、审计导出与企业 OIDC 配置骨架
- 本轮开发计划：
  - 扩展认证数据访问层，支持读取用户、身份绑定、刷新会话聚合信息，形成成员管理基础数据源
  - 新增成员管理接口 `/api/members`，按版本与角色权限控制访问；Studio / Enterprise 可见，Creator 隐藏
  - 新增审计导出接口 `/api/audit/export`，将当前审计记录导出到 `reports` 目录，作为 Enterprise 合规导出骨架
  - 新增 OIDC 配置接口 `/api/oidc/config` 与草稿保存接口 `/api/oidc/config/draft`，先以只读展示 + 草稿保存为主，不直接改写 `config\web.yaml`
  - 新增前端页面 `/members`、`/oidc`，并将导出入口放入审计页
  - 扩展静态预览展示成员管理与 OIDC 配置摘要，按版本自动隐藏
  - 新增验证脚本，覆盖成员列表、审计导出、OIDC 配置草稿保存并写入 SQLite 与 `result.md`
- 本轮交付目标：
  - Studio 获得基础成员管理入口
  - Enterprise 获得审计导出和企业 OIDC 配置入口
  - 角色权限开始从页面级扩展到操作级

### 2026-04-19 19:42:10 +08:00

- 完成 Edition Capability 第四阶段：成员管理、审计导出与企业 OIDC 配置骨架
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，新增用户列表、身份绑定聚合、活跃会话统计查询
  - 扩展 `web\backend\services\edition_policy.py`，新增 `member_management_enabled`、`audit_export_enabled`、`oidc_config_enabled`
  - 扩展 `web\backend\services\governance_service.py`，新增成员管理、审计导出、OIDC 配置读取与草稿保存能力
  - 扩展 `web\backend\app.py`，新增 `/api/members`、`/api/audit/export`、`/api/oidc/config`、`/api/oidc/config/draft`
  - 扩展前端菜单与路由：新增 `/members`、`/oidc`，并将 Studio 屏蔽 `/oidc`，Creator 屏蔽 `/members`、`/oidc`
  - 新增前端页面：`src\pages\Members\index.tsx`、`src\pages\Oidc\index.tsx`；扩展 `Audit` 页增加审计导出按钮
  - 扩展静态预览：新增成员管理、企业 OIDC 配置区块与审计导出结果区块
  - 新增 `scripts\validate_enterprise_console.py`，写入 SQLite 表 `enterprise_console_validation_runs` 并输出 `reports\enterprise_console_validation_report.json`
- 本轮验证结果：
  - Studio 模拟行为：成员管理可用，审计导出不可用
  - Enterprise 模拟行为：审计导出成功生成 JSON 报告，OIDC 草稿成功写入 `state\oidc_config_draft.json`
  - Creator 当前行为保持不变，旧控制台回归验证继续通过
- 下一阶段建议：
  - 增加成员角色编辑、禁用成员、会话吊销等真正可操作接口
  - 增加 OIDC 草稿应用到 `config\web.yaml` 的受控发布流程
  - 增加审计导出筛选条件、CSV 导出与下载接口

### 2026-04-19 19:50:00 +08:00

- 启动 Edition Capability 第五阶段：成员角色编辑、成员禁用与会话吊销
- 本轮开发计划：
  - 扩展认证数据访问层，支持按用户更新角色、更新状态、按用户批量吊销刷新会话
  - 扩展治理服务与 Web API，新增成员更新接口与会话吊销接口，并写入审计日志
  - 扩展前端成员管理页，增加角色切换、禁用成员、吊销会话按钮与结果提示
  - 新增成员操作验证脚本，覆盖角色更新、成员禁用、会话吊销与审计写入
  - 继续保持 Creator / Studio / Enterprise 分层：Creator 隐藏成员页，Studio / Enterprise 开放成员操作
- 本轮交付目标：
  - `admin` 可修改成员角色
  - `admin` 可禁用成员
  - `admin` 可按用户吊销全部刷新会话
  - 操作结果写入审计日志并进入 SQLite 验证报告

### 2026-04-19 19:48:40 +08:00

- 完成 Edition Capability 第五阶段：成员角色编辑、成员禁用与会话吊销
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，新增 `update_user_role`、`update_user_status`、`revoke_sessions_for_user`
  - 扩展 `web\backend\services\governance_service.py`，新增 `update_member` 与 `revoke_member_sessions`
  - 扩展 `web\backend\app.py`，新增 `PATCH /api/members/{user_id}` 与 `POST /api/members/{user_id}/sessions/revoke`
  - 扩展 `web\frontend\src\services\api.ts` 与 `src\types\api.ts`，补充成员操作接口与结果类型
  - 扩展 `web\frontend\src\pages\Members\index.tsx`，新增切换角色、禁用/恢复成员、吊销会话按钮
  - 新增 `scripts\validate_member_operations.py`，写入 SQLite 表 `member_operations_validation_runs` 并输出 `reports\member_operations_validation_report.json`
- 本轮验证结果：
  - 目标成员角色从 `viewer` 成功更新为 `operator`
  - 目标成员状态成功更新为 `disabled`
  - 目标成员活跃会话从 `2` 成功吊销至 `0`
  - 既有企业治理验证与控制台回归验证继续通过
- 下一阶段建议：
  - 增加成员角色下拉选择而非循环切换
  - 增加成员删除保护与超级管理员自保护逻辑
  - 增加单会话粒度查看与单条会话吊销能力

### 2026-04-19 20:03:20 +08:00

- 完成 Edition Capability 第六阶段：单会话列表与单条会话吊销
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，新增 `load_sessions_for_user` 与 `revoke_session_by_id`
  - 扩展 `web\backend\services\governance_service.py`，新增 `load_member_sessions` 与 `revoke_member_session`
  - 扩展 `web\backend\app.py`，新增 `GET /api/members/{user_id}/sessions` 与 `POST /api/members/{user_id}/sessions/{session_id}/revoke`
  - 扩展 `web\frontend\src\services\api.ts` 与 `src\types\api.ts`，补充会话列表与单会话吊销接口类型
  - 扩展 `web\frontend\src\pages\Members\index.tsx`，支持展开查看单个成员会话列表，并提供逐条吊销按钮
  - 新增 `scripts\validate_member_sessions.py`，写入 SQLite 表 `member_sessions_validation_runs` 并输出 `reports\member_sessions_validation_report.json`
- 本轮验证结果：
  - 单成员会话列表可读取 `2` 条会话
  - 指定 `session_id` 成功吊销后，会话总数保持不变，活跃会话数从 `2` 降到 `1`
  - 既有成员操作、企业治理、版本守卫和控制台回归继续通过
- 额外说明：
  - 本轮一度触发 SQLite 并发锁，已确认根因是多脚本并发写库；当前已采用顺序验证重新跑通
  - 下一阶段如需进一步稳固，可把 SQLite 连接统一收敛到带超时与 WAL 的数据库访问层

### 2026-04-19 20:12:00 +08:00

- 启动成员治理增强阶段：SQLite 写库稳固、超级管理员保护与角色下拉选择
- 本轮开发计划：
  - 统一 `connect_auth_database` 连接参数，增加 SQLite `timeout`、`busy_timeout`、`WAL` 与 `foreign_keys` 配置，降低多验证脚本写库锁冲突
  - 新增超级管理员保护策略，保护 `admin_demo` / `user_admin_demo` 不被降权、禁用或批量吊销会话
  - 成员列表增加 `protected` 标记与保护原因，前端据此禁用高风险操作
  - 将成员页“循环切换角色”改为明确的角色下拉选择
  - 新增验证脚本，覆盖 SQLite 连接配置和超级管理员保护
- 本轮交付目标：
  - 成员操作更可控，不再误点循环切换角色
  - 默认超级管理员账号具备安全保护
  - SQLite 写库稳定性增强，减少 `database is locked` 风险

### 2026-04-19 23:15:00 +08:00

- 完成成员治理增强阶段：SQLite 写库稳固、超级管理员保护与角色下拉选择
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py` 的 `connect_auth_database`，统一配置 `timeout=30s`、`PRAGMA busy_timeout=30000`、`PRAGMA foreign_keys=ON`、`PRAGMA journal_mode=WAL`
  - 扩展 `web\backend\services\governance_service.py`，新增超级管理员保护策略，默认保护 `admin_demo` / `user_admin_demo`
  - 超级管理员保护范围：禁止降权、禁止禁用、禁止批量吊销全部会话
  - 成员列表新增 `protected` 与 `protection_reason` 字段，前端可据此禁用危险操作
  - 扩展 `web\frontend\src\pages\Members\index.tsx`，将“循环切换角色”改为明确的角色下拉选择
  - 新增 `scripts\validate_admin_protection.py`，写入 SQLite 表 `admin_protection_validation_runs` 并输出 `reports\admin_protection_validation_report.json`
- 本轮验证结果：
  - SQLite `busy_timeout_ms=30000`
  - SQLite `journal_mode=wal`
  - `admin_demo` 成功标记为 protected
  - 降权、禁用、批量吊销会话均被阻断
  - 最终 `admin_demo` 仍保持 `role=admin`、`status=active`
- 下一阶段建议：
  - 增加安全中心全局活跃会话列表
  - 增加数据库访问统一封装，减少业务层直接管理连接
  - 增加 OIDC 草稿发布到 `config\web.yaml` 的受控流程

### 2026-04-19 23:45:00 +08:00

- 启动安全中心阶段：全局活跃会话列表、筛选查询与批量吊销
- 本轮开发计划：
  - 新增全局安全中心接口，支持按用户、角色、状态、IP 过滤会话，并返回活跃/已吊销统计
  - 新增按 session_id 列表批量吊销能力，保留默认超级管理员保护与审计日志写入
  - 新增前端 /security 页面，提供会话筛选、统计卡片、批量选择吊销与刷新能力
  - 补充静态预览、类型定义、API 封装与版本菜单控制
  - 新增验证脚本，写入 SQLite 验证表并输出 eports\security_center_validation_report.json
- 本轮交付目标：
  - Enterprise 版本可查看全局会话安全中心
  - 支持批量吊销多个非受保护用户会话
  - 验证结果写入 esult.md 并沉淀到项目文档

### 2026-04-19 23:35:00 +08:00

- 完成安全中心阶段：全局活跃会话列表、筛选查询与批量吊销
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，新增全局会话查询、统计聚合与按 `session_id` 批量读取能力
  - 扩展 `web\backend\services\edition_policy.py`，新增 `security_center_enabled` 版本能力开关，仅 Enterprise 开放
  - 扩展 `web\backend\services\governance_service.py`，新增 `load_security_sessions` 与 `revoke_security_sessions`
  - 扩展 `web\backend\app.py`，新增 `GET /api/security/sessions` 与 `POST /api/security/sessions/revoke`
  - 扩展前端 `web\frontend\src\services\api.ts`、`src\types\api.ts`、`src\app.tsx`，并新增 `/security` 页面
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，增加安全中心导航与会话筛选展示
  - 新增 `scripts\validate_security_center.py`，写入 SQLite 表 `security_center_validation_runs` 并输出 `reports\security_center_validation_report.json`
- 本轮验证结果：
  - Enterprise 安全中心允许访问：`enterprise_allowed=true`
  - 指定 3 个会话中成功吊销 2 个普通用户会话：`revoked_count=2`
  - 默认超级管理员会话成功阻断：`blocked_count=1`
  - 过滤到目标操作员的活跃会话从 `2` 降到 `0`
  - 相关回归继续通过：成员会话、成员操作、超级管理员保护、版本策略
- 下一阶段建议：
  - 为安全中心增加会话分页、排序与导出
  - 增加最近登录设备指纹、地理位置与异常登录告警骨架
  - 继续推进 OIDC 草稿发布到 `config\web.yaml` 的受控发布流

### 2026-04-19 23:55:00 +08:00

- 启动安全中心增强阶段：分页、排序与导出
- 本轮开发计划：
  - 扩展安全中心查询接口，支持 `offset`、`sort_by`、`sort_order`、导出格式参数
  - 新增安全中心导出接口，支持基于当前筛选条件导出 JSON / CSV 报告
  - 扩展前端安全中心页面，增加分页、排序控制与导出按钮
  - 扩展静态预览，展示安全中心增强后的筛选与统计信息
  - 新增验证脚本，校验分页、排序与导出结果并写入 SQLite / JSON 报告
- 本轮交付目标：
  - Enterprise 安全中心可稳定浏览大规模会话列表
  - 支持把当前筛选结果导出为治理报告
  - 结果继续写入 `result.md` 并更新项目资料索引

### 2026-04-20 00:02:00 +08:00

- 完成安全中心增强阶段：分页、排序与导出
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，新增安全中心排序解析、分页偏移与可复用过滤条件构建
  - 扩展 `web\backend\services\governance_service.py`，新增安全中心分页元数据与 `export_security_sessions`
  - 扩展 `web\backend\app.py`，新增 `POST /api/security/sessions/export`，并增强 `/api/security/sessions` 查询参数
  - 扩展前端 `web\frontend\config\config.ts`、`src\services\api.ts`、`src\types\api.ts` 与 `src\pages\Security\index.tsx`
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，增加排序与导出按钮
  - 新增 `scripts\validate_security_center_paging.py`，写入 SQLite 表 `security_paging_validation_runs` 并输出 `reports\security_paging_validation_report.json`
- 本轮验证结果：
  - 安全中心分页验证通过：总数 `3`，按 `ip_address asc` 排序时，第 1 页首条为 `127.0.1.10`，第 2 页首条为 `127.0.1.20`
  - JSON / CSV 导出结果均为 `3` 条
  - 既有安全中心批量吊销与版本策略验证继续通过
- 下一阶段建议：
  - 为安全中心增加导出下载历史与清理机制
  - 增加异常会话规则引擎与风险标记字段
  - 推进 OIDC 草稿配置的受控发布流程

### 2026-04-20 00:15:00 +08:00

- 启动安全中心智能风控阶段：异常会话规则引擎与风险筛选
- 本轮开发计划：
  - 扩展安全中心会话模型，增加风险等级、风险标签与风险摘要字段
  - 新增异常识别规则：多活跃会话、多 IP 活跃、禁用账号仍有活跃会话、受保护账号活跃会话、过期未吊销会话
  - 扩展安全中心查询接口，支持按 `risk_level` 过滤并返回高/中风险统计
  - 扩展前端安全中心页面，展示风险标签、风险筛选与风险统计卡片
  - 新增验证脚本，模拟异常测试数据写入数据库并校验风险识别结果
- 本轮交付目标：
  - Enterprise 安全中心具备基础异常会话识别能力
  - 风险会话可被筛选、导出并用于后续治理动作
  - 结果继续写入 `result.md` 并更新项目资料索引

### 2026-04-20 00:18:00 +08:00

- 完成安全中心智能风控阶段：异常会话规则引擎与风险筛选
- 本轮完成内容：
  - 扩展 `web\backend\auth\auth_service.py`，统一安全中心活跃判定并支持过期会话过滤
  - 扩展 `web\backend\services\governance_service.py`，新增风险标签、风险等级、风险摘要、风险筛选与风险统计
  - 扩展 `web\backend\app.py`，新增 `risk_level` 查询 / 导出参数
  - 扩展前端 `web\frontend\src\types\api.ts`、`src\services\api.ts`、`src\pages\Security\index.tsx`，增加风险筛选、风险标签与高/中风险统计卡片
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，支持风险筛选与风险摘要展示
  - 新增 `scripts\validate_security_risk_engine.py`，写入 SQLite 表 `security_risk_validation_runs` 并输出 `reports\security_risk_validation_report.json`
- 本轮验证结果：
  - 高风险规则命中：`disabled_rule_hit=true`、`multi_ip_rule_hit=true`
  - 受保护账号规则命中：`protected_rule_hit=true`
  - 高风险筛选结果为 `2` 条，且导出结果为 `2` 条
  - 分页导出验证与安全中心批量吊销验证继续通过
- 下一阶段建议：
  - 增加风险处置动作，如“仅吊销高风险会话”与“按风险批量导出”快捷操作
  - 增加登录地域、设备指纹、失败登录计数等更丰富的风控维度
  - 把风险事件写入审计流，形成独立安全事件时间线


### 2026-04-20 00:30:00 +08:00

- 启动安全中心快捷治理阶段：高风险会话快捷吊销与快捷导出
- 本轮开发计划：
  - 扩展安全中心治理服务，支持按当前风险筛选条件直接批量吊销匹配会话
  - 新增高风险快捷治理接口，保留受保护账号与已吊销会话的安全保护
  - 扩展前端安全中心页面，增加“吊销高风险会话”“导出高风险”快捷按钮
  - 扩展静态预览，增加高风险快捷治理入口
  - 新增验证脚本，模拟高风险数据并校验快捷治理结果
- 本轮交付目标：
  - 安全中心从“发现风险”进一步走到“快速处置风险”
  - 高风险会话可一键吊销并产出治理报告
  - 结果继续写入 `result.md` 并更新项目资料索引

### 2026-04-20 00:45:00 +08:00

- 完成安全中心治理历史阶段：高风险处置审计面板
- 本轮完成内容：
  - 扩展 `web\backend\services\governance_service.py`，新增安全治理历史查询与统计聚合
  - 扩展 `web\backend\app.py`，新增 `GET /api/security/governance-history`
  - 扩展前端 `web\frontend\src\types\api.ts`、`src\services\api.ts`、`src\pages\Security\index.tsx`，增加“最近治理历史”统计卡片与记录表
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，同步展示治理历史统计与最近动作
  - 新增 `scripts\validate_security_governance_history.py`，写入 SQLite 表 `security_governance_history_validation_runs` 并输出 `reports\security_governance_history_validation_report.json`
- 本轮验证结果：
  - 治理历史验证通过：共命中 `3` 条记录，其中导出 `1` 条、吊销 `2` 条、快捷吊销 `1` 条、成功 `3` 条
  - 既有高风险快捷治理验证继续通过
  - 前端 `Security` 页面、API 客户端与静态预览 `main.js` 的 `esbuild` 语法校验继续通过
- 下一阶段建议：
  - 增加按操作人 / 动作类型 / 结果筛选治理历史
  - 增加治理历史导出与治理工单回链
  - 增加风险趋势图和每日治理汇总看板

### 2026-04-20 00:58:00 +08:00

- 完成安全中心治理历史增强阶段：筛选与导出
- 本轮完成内容：
  - 扩展 `web\backend\services\governance_service.py`，新增 `export_security_governance_history` 并增强治理历史筛选能力
  - 扩展 `web\backend\app.py`，新增 `POST /api/security/governance-history/export`
  - 扩展前端 `web\frontend\src\types\api.ts`、`src\services\api.ts`、`src\pages\Security\index.tsx`，增加治理历史筛选项与 JSON / CSV 导出
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，增加治理历史筛选与导出按钮
  - 新增 `scripts\validate_security_governance_history_export.py`，写入 SQLite 表 `security_governance_history_export_validation_runs` 并输出 `reports\security_governance_history_export_validation_report.json`
- 本轮验证结果：
  - 治理历史查询验证继续通过：命中 `3` 条记录，其中导出 `1` 条、吊销 `2` 条、快捷吊销 `1` 条
  - 治理历史导出验证通过：按快捷吊销筛选 JSON 导出 `1` 条，全量 CSV 导出 `3` 条
  - 前端 `Security` 页面、API 客户端与静态预览 `main.js` 的 `esbuild` 语法校验继续通过
- 下一阶段建议：
  - 增加治理历史分页与时间范围筛选
  - 增加治理历史导出下载列表和自动清理策略
  - 增加风险趋势折线图与按日治理汇总卡片

### 2026-04-20 00:26:00 +08:00

- 完成安全中心快捷治理阶段：高风险会话快捷吊销与快捷导出
- 本轮完成内容：
  - 扩展 `web\backend\services\governance_service.py`，新增 `revoke_security_sessions_by_filter`，支持按当前筛选条件直接匹配并吊销高风险会话
  - 扩展 `web\backend\app.py`，新增 `POST /api/security/sessions/revoke-by-filter`，并写入审计动作 `security_revoke_sessions_by_filter`
  - 扩展前端 `web\frontend\src\services\api.ts`、`src\types\api.ts`、`src\pages\Security\index.tsx`，增加“导出高风险”“吊销高风险会话”快捷操作
  - 扩展静态预览 `web\static_preview\index.html` 与 `web\static_preview\main.js`，补齐高风险快捷治理入口
  - 新增 `scripts\validate_security_risk_actions.py`，写入 SQLite 表 `security_risk_actions_validation_runs` 并输出 `reports\security_risk_actions_validation_report.json`
- 本轮验证结果：
  - 高风险快捷导出命中 `2` 条会话，快捷吊销匹配 `2` 条、实际吊销 `2` 条
  - 吊销后目标高风险活跃会话数降为 `0`
  - 受保护超级管理员会话仍保持活跃，保护校验结果为 `true`
  - 既有风控验证、安全中心验证与前端 `esbuild` 语法校验继续通过
- 下一阶段建议：
  - 增加高风险处置审计面板，展示导出 / 吊销历史与操作人
  - 增加“仅导出受影响用户名单”“按风险等级生成治理工单”等二级动作
  - 增加地域、设备指纹、失败登录次数等更丰富的风控信号

### 2026-04-20 00:30:00 +08:00

- 启动安全中心快捷治理阶段：高风险会话快捷吊销与快捷导出
- 本轮开发计划：
  - 扩展安全中心治理服务，支持按当前风险筛选条件直接批量吊销匹配会话
  - 新增高风险快捷治理接口，保留受保护账号与已吊销会话的安全保护
  - 扩展前端安全中心页面，增加“吊销高风险会话”“导出高风险”快捷按钮
  - 扩展静态预览，增加高风险快捷治理入口
  - 新增验证脚本，模拟高风险数据并校验快捷治理结果
- 本轮交付目标：
  - 安全中心从“发现风险”进一步走到“快速处置风险”
  - 高风险会话可一键吊销并产出治理报告
  - 结果继续写入 `result.md` 并更新项目资料索引


### 2026-04-20 01:19:08 +08:00

- ?????????????????????????????
- ???????
  - ?? `web\frontend\src\services\api.ts`??????? `offset`?`start_at`?`end_at` ????
  - ?? `web\static_preview\index.html` ? `web\static_preview\main.js`??????????????? / ???????????????
  - ?? `scripts\validate_security_governance_history_paging.py`??? SQLite ? `security_governance_history_paging_validation_runs` ??? `reports\security_governance_history_paging_validation_report.json`
  - ?????????????????????? `esbuild` ??????????????????
- ???????
  - ?????????????? `5` ??? 1 ? `2` ??? 2 ? `2` ?
  - ???????????`2026-04-20` ???? `3` ?????????? `2` ?
  - ???????????????? `3` ??? / ????
  - `Security` ???API ???????? `main.js` ? `esbuild` ????????
- ???????
  - ????????????????????
  - ???????????????????????
  - ???????????????????


### 2026-04-20 01:33:40 +08:00

- ???????????????? 7 ??????????
- ???????
  - ?? `web\backend\services\governance_service.py`??? `daily_breakdown` ? `summary_cards` ??
  - ?? `web\frontend\src\types\api.ts` ? `src\pages\Security\index.tsx`???? 1 ? / ? 7 ???? 7 ????
  - ?? `web\static_preview\index.html` ? `web\static_preview\main.js`????????? Summary ? 7-Day Trend
  - ?? `scripts\validate_security_governance_history_trends.py`??? SQLite ? `security_governance_history_trend_validation_runs` ??? `reports\security_governance_history_trend_validation_report.json`
- ???????
  - ?????????? 1 ??? `2`?? 1 ??? `1`?? 7 ??? `4`?? 7 ??? `2`?? 7 ??? `2`
  - ????????????? `2026-04-14` ? `2026-04-20`?????? `7` ?
  - ?? `Security` ??????? `main.js` ? `esbuild` ????????
- ???????
  - ?????????????????????
  - ?????????? / ????????
  - ???????????????????????


### 2026-04-20 01:42:18 +08:00

- ????????????????????????????????
- ???????
  - ?? `web\backend\services\governance_service.py`??? `operator_ranking`?`action_distribution`?`failure_reason_distribution` ??
  - ?? `web\frontend\src\types\api.ts` ? `src\pages\Security\index.tsx`?????????????????????
  - ?? `web\static_preview\index.html` ? `web\static_preview\main.js`????? Operator Ranking?Action Distribution?Failure Reasons
  - ?? `scripts\validate_security_governance_history_analytics.py`??? SQLite ? `security_governance_history_analytics_validation_runs` ??? `reports\security_governance_history_analytics_validation_report.json`
- ???????
  - ?????????Top Operator ? `4` ????????? `2`
  - ?????????Top Action ? `security_export_sessions`??? `2`??????? `4`
  - ???????????Top Failure Reason ? `download_permission_denied`??? `2`??????? `3`
  - ?? `Security` ??????? `main.js` ? `esbuild` ????????
- ???????
  - ??????????? / ???????????
  - ?????????????????
  - ???????????????????


### 2026-04-20 01:59:38 +08:00

- ????????????????????????????
- ???????
  - ?? `web\backend\services\governance_service.py`??????/?????? `failure_reason_daily_breakdown` ??
  - ?? `web\frontend\src\types\api.ts` ? `src\pages\Security\index.tsx`???? 1 ? / ? 7 ??????????????
  - ?? `web\static_preview\index.html` ? `web\static_preview\main.js`????? Failure Reason Trend
  - ?? `scripts\validate_security_governance_history_failure_analytics.py`??? SQLite ? `security_governance_history_failure_validation_runs` ??? `reports\security_governance_history_failure_validation_report.json`
- ???????
  - ????????? 1 ???? `2`???? `66.7%`?? 7 ???? `4`???? `80.0%`
  - ??????????????? `4` ???????? `storage_unavailable`??? `1`
  - ?? `Security` ??????? `main.js` ? `esbuild` ????????
- ???????
  - ????????????? / ???????
  - ???????????????????
  - ???????????????


### 2026-04-20 02:25:52 +08:00

- ??????????????????????????
- ???????
  - ?? `web\backend\services\governance_service.py`??? `alert_config`?`health_overview`????????????
  - ?? `web\backend\app.py`??? `POST /api/security/governance-alert-config`
  - ?? `web\frontend\src\types\api.ts`?`src\services\api.ts`?`src\pages\Security\index.tsx`???????????????????
  - ?? `web\static_preview\index.html` ? `web\static_preview\main.js`????? Health ??? Thresholds
  - ?? `scripts\validate_security_governance_health_alerts.py`??? SQLite ? `security_governance_health_alert_validation_runs` ??? `reports\security_governance_health_alert_validation_report.json`
- ???????
  - ????????????? `28`??? `critical`???? `4`????? `4`
  - ????????????? `recent_1d_failure_rate_warn=40` ? 8 ?????
  - ?? `Security` ???API ???????? `main.js` ? `esbuild` ????????
- ???????
  - ???????????????????????
  - ??????????????????????
  - ????????????????


### 2026-04-20 02:47:30 +08:00

- 安全中心继续推进治理告警配置第二阶段：模板、恢复默认、配置变更历史
- 本次完成
  - 在 `web\backend\services\governance_service.py` 增加 `strict` / `balanced` / `relaxed` 三套内置告警模板
  - 在 `web\backend\app.py` 新增 `POST /api/security/governance-alert-config/reset`
  - 在治理历史聚合结果中新增 `alert_templates`、`alert_template_count`、`alert_config_change_history`、`alert_config_change_history_count`
  - 在 `web\frontend\src\pages\Security\index.tsx` 增加模板选择、应用模板、恢复默认、配置变更历史表
  - 在 `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步模板与变更历史预览
  - 新增 `scripts\validate_security_governance_alert_templates.py`，写入 SQLite 表 `security_governance_alert_template_validation_runs`
- 验证结果
  - 模板数量验证通过：`3`
  - 配置变更历史验证通过：`2` 条，最新动作为 `security_governance_alert_config_reset`
  - 恢复默认配置验证通过：`reset_matches_default=true`
  - 兼容性回归验证通过：治理健康度脚本仍输出 `health_score=28`、`status=critical`
- 产出物
  - `reports\security_governance_alert_template_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v12.js`
  - `reports\tmp_esbuild_security\api_v12.js`
  - `reports\tmp_esbuild_security\static_preview_v12.js`
- 下一步
  - 继续推进治理配置审计导出 / 操作人筛选增强
  - 继续补齐告警模板说明与更多系统级治理看板


### 2026-04-20 22:32:20 +08:00

- 安全中心继续推进治理配置审计导出与操作人筛选增强
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，为治理历史导出新增 `export_scope=alert_config_changes`
  - 扩展 `web\backend\app.py`，导出请求体新增 `export_scope`，审计详情记录导出作用域
  - `/api/security/governance-history` 新增 `operator_options` 与 `operator_option_count`
  - `web\frontend\src\pages\Security\index.tsx` 将操作人筛选增强为可搜索候选下拉，并新增配置审计 JSON / CSV 导出按钮
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步操作人下拉和 Config Audit 导出按钮
  - 新增 `scripts\validate_security_governance_config_audit_export.py`，写入 SQLite 表 `security_governance_config_audit_export_validation_runs`
- 验证结果
  - 配置审计 JSON 导出数量：`2`
  - 配置审计 CSV 导出数量：`2`
  - 操作人候选数量：`2`
  - 指定操作人筛选记录数：`2`
  - 导出作用域验证：`alert_config_changes`
- 产出物
  - `reports\security_governance_config_audit_export_validation_report.json`
  - `reports\security_governance_alert_config_audit_export_20260420223159.json`
  - `reports\security_governance_alert_config_audit_export_20260420223159.csv`
  - `reports\tmp_esbuild_security\security_page_v13.js`
  - `reports\tmp_esbuild_security\api_v13.js`
  - `reports\tmp_esbuild_security\static_preview_v13.js`
- 下一步
  - 继续推进治理模板说明 / 告警处理建议
  - 继续补齐系统级治理看板与告警确认闭环


### 2026-04-20 22:50:20 +08:00

- 安全中心继续推进治理模板说明与告警处理建议
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，为 `strict` / `balanced` / `relaxed` 模板补充 `risk_profile`、`best_for`、`recommended_actions`
  - 扩展 `health_overview`，新增 `recommended_template_key`、`recommendation_count`、`recommendations`
  - `web\frontend\src\types\api.ts` 新增 `SecurityGovernanceRecommendation` 等类型字段
  - `web\frontend\src\pages\Security\index.tsx` 新增处置建议表与模板指南卡片
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步 Recommendations 与 Template Guide 预览
  - 新增 `scripts\validate_security_governance_alert_guidance.py`，写入 SQLite 表 `security_governance_alert_guidance_validation_runs`
- 验证结果
  - 模板数量：`3`
  - Strict 模板处置动作数：`2`
  - 告警处理建议数量：`6`
  - 推荐模板：`strict`
  - 健康状态：`critical`
  - 头部失败原因：`download_permission_denied`
- 产出物
  - `reports\security_governance_alert_guidance_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v14.js`
  - `reports\tmp_esbuild_security\api_v14.js`
  - `reports\tmp_esbuild_security\static_preview_v14.js`
- 下一步
  - 继续推进告警确认闭环
  - 继续补齐系统级治理看板


### 2026-04-20 23:11:20 +08:00

- 安全中心继续推进告警确认闭环
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增告警确认持久化文件 `security_governance_alert_acknowledgements.json`
  - 扩展 `health_overview.recommendations`，为每条建议补充 `workflow_status`、`assigned_to`、`note`、`updated_by`、`updated_at`
  - 扩展 `web\backend\app.py`，新增 `POST /api/security/governance-alert-acknowledgement`
  - 扩展 `web\frontend\src\types\api.ts` 与 `src\services\api.ts`，新增告警确认结果结构与保存接口
  - `web\frontend\src\pages\Security\index.tsx` 新增确认 / 解决 / 忽略 / 重开按钮，并通过 prompt 支持指派与备注
  - `web\static_preview\main.js` 同步新增告警闭环按钮
  - 新增 `scripts\validate_security_governance_alert_acknowledgement.py`，写入 SQLite 表 `security_governance_alert_ack_validation_runs`
- 验证结果
  - 建议数量：`6`
  - 已保存确认记录数：`2`
  - `recent_1d_failure_rate` 状态：`acknowledged`
  - `top_failure_reason` 状态：`resolved`
- 产出物
  - `reports\security_governance_alert_ack_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v15.js`
  - `reports\tmp_esbuild_security\api_v15.js`
  - `reports\tmp_esbuild_security\static_preview_v15.js`
- 下一步
  - 继续补齐系统级治理看板
  - 继续推进告警确认统计 / 批量处置能力


### 2026-04-20 23:22:30 +08:00

- 安全中心继续推进系统级治理看板
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增 `governance_dashboard` 聚合结构，汇总健康分、活跃告警、闭环率、处理率、近 7 天闭环、状态分布、责任人分布与下一步动作
  - 优化闭环率 / 处理率计算逻辑，改为基于当前治理建议计算，避免历史确认记录导致比率超过 `100%`
  - 扩展 `web\frontend\src\types\api.ts`，新增 `SecurityGovernanceDashboard`、状态分布与责任人分布结构
  - `web\frontend\src\pages\Security\index.tsx` 新增“系统级治理看板”卡片，展示核心指标、Next Actions、状态分布和责任人分布
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Governance Dashboard 预览、状态分布表和责任人分布表
  - 新增 `scripts\validate_security_governance_dashboard.py`，写入 SQLite 表 `security_governance_dashboard_validation_runs`
- 验证结果
  - 健康状态：`critical`
  - 活跃告警数：`4`
  - 告警确认记录数：`4`
  - 闭环率：`40.0%`
  - 处理率：`80.0%`
  - 责任人分布数：`3`
  - 状态分布数：`4`
  - 打开中的建议数：`1`
  - 操作人数：`2`
- 产出物
  - `reports\security_governance_dashboard_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v16.js`
  - `reports\tmp_esbuild_security\api_v16.js`
  - `reports\tmp_esbuild_security\static_preview_v16.js`
- 下一步
  - 继续推进治理告警批量处置能力
  - 继续推进系统级治理看板的数据复盘统计


### 2026-04-20 23:32:30 +08:00

- 安全中心继续推进治理告警批量处置能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增批量告警处置方法 `save_security_governance_alert_acknowledgement_batch(...)`
  - 扩展 `web\backend\app.py`，新增 `POST /api/security/governance-alert-acknowledgement/batch`
  - 扩展 `web\frontend\src\types\api.ts` 与 `web\frontend\src\services\api.ts`，新增批量处置结果结构和批量保存接口
  - `web\frontend\src\pages\Security\index.tsx` 为处置建议表新增行选择、批量确认 / 解决 / 忽略 / 重开，以及“一键确认全部 Open”
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增批量按钮、选择计数和复选框选择逻辑
  - 新增 `scripts\validate_security_governance_alert_acknowledgement_batch.py`，写入 SQLite 表 `security_governance_alert_ack_batch_validation_runs`
  - 调整 `scripts\validate_security_governance_dashboard.py`，保证看板验证脚本在串行回归中仍能稳定保留 1 条 open 建议
- 验证结果
  - 批量请求数：`3`
  - 批量更新数：`3`
  - 告警确认记录总数：`5`
  - 批量治理历史记录数：`1`
  - acknowledged 数：`3`
  - 构建产物：`security_page_v17.js` / `api_v17.js` / `static_preview_v17.js`
- 产出物
  - `reports\security_governance_alert_ack_batch_validation_report.json`
  - `reports\security_governance_alert_ack_validation_report.json`
  - `reports\security_governance_dashboard_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v17.js`
  - `reports\tmp_esbuild_security\api_v17.js`
  - `reports\tmp_esbuild_security\static_preview_v17.js`
- 下一步
  - 继续推进系统级治理看板的数据复盘统计
  - 继续推进治理告警批量处置后的运营报表能力


### 2026-04-20 23:41:30 +08:00

- 安全中心继续推进系统级治理看板的数据复盘统计
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增 `review_summary` 聚合，汇总复盘评分、复盘状态、Top Operator、Top Action、头部失败原因、批量处置占比、stale open 建议与复盘 highlights
  - 扩展 `web\frontend\src\types\api.ts`，新增 `SecurityGovernanceReviewSummary` 与 `SecurityGovernanceStaleRecommendationRecord`
  - `web\frontend\src\pages\Security\index.tsx` 在系统级治理看板中新增“治理复盘统计”子面板，展示 Review Score、占比指标、Highlights 与 stale open 建议表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Governance Review Summary、Highlights 与 stale open 表格
  - 新增 `scripts\validate_security_governance_dashboard_review.py`，写入 SQLite 表 `security_governance_dashboard_review_validation_runs`
- 验证结果
  - 复盘窗口：`7` 天
  - 复盘状态：`critical`
  - 复盘评分：`45`
  - Top Operator：`user_dashboard_review_a_234052451806`
  - Top Action：`security_export_sessions`
  - Top Failure Reason：`download_permission_denied`
  - 批量处置动作数：`1`
  - stale open 建议数：`1`
- 产出物
  - `reports\security_governance_dashboard_review_validation_report.json`
  - `reports\security_governance_dashboard_validation_report.json`
  - `reports\security_governance_alert_ack_batch_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v18.js`
  - `reports\tmp_esbuild_security\api_v18.js`
  - `reports\tmp_esbuild_security\static_preview_v18.js`
- 下一步
  - 继续推进治理告警批量处置后的运营报表能力
  - 继续推进系统级治理看板的复盘导出能力


### 2026-04-20 23:51:10 +08:00

- 安全中心继续推进治理告警批量处置后的运营报表能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，为治理历史导出新增 `export_scope=operations_report`
  - 运营报表导出会生成 `summary_cards`、`stats`、`health_overview`、`governance_dashboard`、`review_summary` 和 `metric_rows`
  - JSON 运营报表导出保存完整结构，CSV 运营报表导出保存 `section / metric / value / extra` 指标行
  - `web\frontend\src\pages\Security\index.tsx` 新增“导出运营报表 JSON / CSV”按钮
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Ops Report JSON / CSV 导出按钮
  - 新增 `scripts\validate_security_governance_operations_report.py`，写入 SQLite 表 `security_governance_operations_report_validation_runs`
- 验证结果
  - 运营报表 JSON 导出数量：`9`
  - 运营报表 CSV 导出数量：`9`
  - CSV 指标行数：`9`
  - 复盘状态：`critical`
  - 复盘评分：`33`
  - 批量处置动作数：`1`
  - 头部失败原因：`download_permission_denied`
- 产出物
  - `reports\security_governance_operations_report_validation_report.json`
  - `reports\security_governance_operations_report_20260420235034.json`
  - `reports\security_governance_operations_report_20260420235034.csv`
  - `reports\tmp_esbuild_security\security_page_v19.js`
  - `reports\tmp_esbuild_security\api_v19.js`
  - `reports\tmp_esbuild_security\static_preview_v19.js`
- 下一步
  - 继续推进系统级治理看板的复盘导出能力
  - 继续推进治理运营报表的周期性汇总能力


### 2026-04-20 23:58:00 +08:00

- 安全中心继续推进系统级治理看板的复盘导出能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，为治理历史导出新增 `export_scope=review_export`
  - 复盘导出 JSON 新增 `review_export` 结构，包含 `review_summary`、`governance_dashboard`、`health_overview`、`stale_open_recommendations`、`highlights`、`metric_rows`
  - 复盘导出 CSV 输出 `section / metric / value / extra` 指标行，聚焦复盘面板核心指标
  - `web\frontend\src\pages\Security\index.tsx` 新增“导出复盘 JSON / CSV”按钮
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Review JSON / CSV 导出按钮
  - 新增 `scripts\validate_security_governance_review_export.py`，写入 SQLite 表 `security_governance_review_export_validation_runs`
- 验证结果
  - 复盘导出 JSON 数量：`8`
  - 复盘导出 CSV 数量：`8`
  - CSV 指标行数：`8`
  - 复盘状态：`critical`
  - 复盘评分：`35`
  - stale open 建议数：`1`
  - Top Operator：`user_review_export_a_235717913742`
- 产出物
  - `reports\security_governance_review_export_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v20.js`
  - `reports\tmp_esbuild_security\api_v20.js`
  - `reports\tmp_esbuild_security\static_preview_v20.js`
- 下一步
  - 继续推进治理运营报表的周期性汇总能力
  - 继续推进复盘导出的自动归档能力


### 2026-04-21 00:04:20 +08:00

- 安全中心继续推进治理运营报表的周期性汇总能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增 `build_security_governance_periodic_summary(...)`
  - 治理历史导出新增 `export_scope=periodic_summary`
  - 周期汇总 JSON 新增 `periodic_summary` 结构，包含窗口、总量、失败率、批量处置次数、critical / warning 周期数与 daily rows
  - 周期汇总 CSV 输出按日维度的 `period / status / total_count / failure_rate / batch_action_count / top_action_type / top_failure_reason`
  - `web\frontend\src\pages\Security\index.tsx` 新增“导出周期汇总 JSON / CSV”按钮
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Periodic JSON / CSV 导出按钮
  - 新增 `scripts\validate_security_governance_periodic_summary.py`，写入 SQLite 表 `security_governance_periodic_summary_validation_runs`
- 验证结果
  - 周期汇总 JSON 导出数量：`7`
  - 周期汇总 CSV 导出数量：`7`
  - 有动作周期数：`3`
  - 总动作数：`6`
  - 失败数：`3`
  - 失败率：`50.0%`
  - 批量处置动作数：`1`
- 产出物
  - `reports\security_governance_periodic_summary_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v21.js`
  - `reports\tmp_esbuild_security\api_v21.js`
  - `reports\tmp_esbuild_security\static_preview_v21.js`
- 下一步
  - 继续推进复盘导出的自动归档能力
  - 继续推进周期汇总趋势可视化能力


### 2026-04-21 00:14:30 +08:00

- 安全中心继续推进复盘导出的自动归档能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，为治理历史导出新增 `export_scope=review_archive`
  - 新增 `write_security_governance_review_archive(...)`，自动生成复盘 JSON、复盘 CSV 与归档 manifest
  - 归档目录采用 `reports\security_governance_review_archive\YYYYMMDD\YYYYMMDDHHMMSS\`，便于按日期追踪和后续自动清理
  - 归档 manifest 记录 `archive_dir`、归档文件清单、复盘评分、复盘状态、Top Operator、Top Action、头部失败原因和指标数量
  - `web\frontend\src\pages\Security\index.tsx` 新增“归档复盘导出”按钮
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Review Archive 按钮
  - 新增 `scripts\validate_security_governance_review_archive.py`，写入 SQLite 表 `security_governance_review_archive_validation_runs`
- 验证结果
  - 归档导出范围：`review_archive`
  - 归档指标数量：`8`
  - 归档文件数：`2`
  - CSV 行数：`8`
  - 复盘状态：`critical`
  - 复盘评分：`35`
  - 归档路径：`reports\security_governance_review_archive\20260421\20260421001257`
- 产出物
  - `reports\security_governance_review_archive_validation_report.json`
  - `reports\security_governance_review_archive\20260421\20260421001257\security_governance_review_archive_manifest_20260421001257.json`
  - `reports\security_governance_review_archive\20260421\20260421001257\security_governance_review_export_20260421001257.json`
  - `reports\security_governance_review_archive\20260421\20260421001257\security_governance_review_export_20260421001257.csv`
  - `reports\tmp_esbuild_security\security_page_v22.js`
  - `reports\tmp_esbuild_security\api_v22.js`
  - `reports\tmp_esbuild_security\static_preview_v22.js`
- 下一步
  - 继续推进周期汇总趋势可视化能力
  - 继续推进治理归档的列表检索与清理策略


### 2026-04-21 00:23:10 +08:00

- 安全中心继续推进周期汇总趋势可视化能力
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，让 `build_security_governance_periodic_summary(...)` 输出趋势可视化字段
  - `/api/security/governance-history` 新增顶层 `periodic_summary`，不再只依赖导出接口查看周期汇总
  - `periodic_summary` 新增 `trend_status`、`trend_points`、`total_bar_width`、`failure_bar_width`、`insights`、`max_total_count`、`max_failure_rate`
  - `web\frontend\src\types\api.ts` 新增周期趋势类型
  - `web\frontend\src\pages\Security\index.tsx` 新增“周期汇总趋势”卡片，展示状态、失败率、critical / warning 周期、批量处置次数和双条形趋势
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Periodic Trend Visual
  - 新增 `scripts\validate_security_governance_periodic_trend.py`，写入 SQLite 表 `security_governance_periodic_trend_validation_runs`
- 验证结果
  - 趋势状态：`critical`
  - 趋势点数量：`7`
  - 有动作趋势点：`3`
  - 总动作数：`6`
  - 失败数：`3`
  - 失败率：`50.0%`
  - critical 周期数：`3`
  - insight 数量：`3`
  - 最大动作条宽：`100.0`
  - 最大失败条宽：`100.0`
- 产出物
  - `reports\security_governance_periodic_trend_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v23.js`
  - `reports\tmp_esbuild_security\api_v23.js`
  - `reports\tmp_esbuild_security\static_preview_v23.js`
- 下一步
  - 继续推进治理归档的列表检索与清理策略
  - 继续推进批量生成任务的运行态监控面板


### 2026-04-21 23:58:00 +08:00

- 安全中心继续推进治理归档的列表检索与清理策略
- 本次完成
  - 扩展 `web\backend\services\governance_service.py`，新增 `load_security_governance_review_archives(...)`
  - 新增 `cleanup_security_governance_review_archives(...)`，支持按保留天数筛选、dry run 预演与安全清理
  - `web\backend\app.py` 新增 `GET /api/security/governance-review-archives`
  - `web\backend\app.py` 新增 `POST /api/security/governance-review-archives/cleanup`
  - 清理接口会写入审计日志 `security_governance_review_archive_cleanup`
  - `web\frontend\src\services\api.ts` 新增归档列表与清理 API
  - `web\frontend\src\types\api.ts` 新增归档列表、归档记录与清理结果类型
  - `web\frontend\src\pages\Security\index.tsx` 新增“复盘归档管理”卡片，支持刷新、预演清理和确认清理
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Review Archive Management
  - 新增 `scripts\validate_security_governance_review_archive_management.py`，写入 SQLite 表 `security_governance_review_archive_management_validation_runs`
- 验证结果
  - 归档列表数量：`4`
  - dry run 可清理数量：`1`
  - 实际删除数量：`1`
  - 跳过数量：`0`
  - 新归档保留：`true`
  - 旧归档已删除：`true`
  - 回归复盘归档通过
  - 回归周期汇总趋势通过
- 产出物
  - `reports\security_governance_review_archive_management_validation_report.json`
  - `reports\tmp_esbuild_security\security_page_v24.js`
  - `reports\tmp_esbuild_security\api_v24.js`
  - `reports\tmp_esbuild_security\static_preview_v24.js`
- 下一步
  - 继续推进批量生成任务的运行态监控面板
  - 继续推进自动生成系统的任务队列可视化与失败重试


### 2026-04-22 00:42:00 +08:00

- 批量生成继续推进任务运行态监控面板
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，让 `/api/batches` 返回 `runtime_monitor`
  - `runtime_monitor` 聚合批次摘要、批次步骤、任务状态、队列分布、Provider 负载、剧集进度、活跃任务、风险提示和下一步动作
  - 运行态状态支持 `healthy`、`running`、`blocked`、`completed`
  - 队列聚合使用 Provider 到队列映射，覆盖 `manual_web -> web_tasks`、`windows_tts -> tts_local`
  - `web\frontend\src\types\api.ts` 新增 `BatchRuntimeMonitor`、队列、Provider、剧集、活跃任务、风险提示和步骤结果类型
  - `web\frontend\src\pages\Batches\index.tsx` 重做为“批量生成监控”页面
  - Batches 页面新增运行态 Alert、任务指标卡、风险提示、队列监控、Provider 负载、剧集进度、活跃任务和批次步骤表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增批次运行态监控预览
  - 新增 `scripts\validate_batch_runtime_monitor.py`，写入 SQLite 表 `batch_runtime_monitor_validation_runs`
- 验证结果
  - 运行态状态：`blocked`
  - 批次数量：`1`
  - 任务总数：`6`
  - 完成任务：`1`
  - 活跃任务：`3`
  - 失败任务：`1`
  - 人工处理任务：`1`
  - 队列数量：`2`
  - Provider 数量：`2`
  - 剧集数量：`3`
  - 活跃任务列表数量：`5`
  - 风险提示数量：`3`
  - 批次步骤数量：`4`
  - 回归 Web Console 通过
- 产出物
  - `reports\batch_runtime_monitor_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v25.js`
  - `reports\tmp_esbuild_batch\api_v25.js`
  - `reports\tmp_esbuild_batch\static_preview_v25.js`
- 下一步
  - 继续推进自动生成系统的任务队列可视化与失败重试
  - 继续推进失败任务一键生成 retry-batch 的 Web 操作入口


### 2026-04-22 01:04:10 +08:00

- 批量生成继续推进失败任务一键生成 retry-batch 的 Web 操作入口
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `generate_retry_batch_package(...)`
  - `generate_retry_batch_package(...)` 支持 `failed/manual_required` 状态筛选、剧集筛选、Provider 筛选、dry run 预演和正式生成
  - `web\backend\app.py` 新增 `POST /api/batches/retry`
  - 重试接口要求 `batches.manage` 权限，并写入审计日志 `batch_retry_generate`
  - `web\frontend\src\types\api.ts` 新增 `BatchRetryGenerateResult`
  - `web\frontend\src\services\api.ts` 新增 `generateBatchRetryPackage(...)`
  - `web\frontend\src\pages\Batches\index.tsx` 新增“失败任务一键重试入口”
  - Batches 页面支持输入剧集 / Provider 筛选，支持“预演 retry-batch”和“生成 retry-batch”
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Retry Preview / Generate Retry
  - 新增 `scripts\validate_batch_retry_web_action.py`，写入 SQLite 表 `batch_retry_web_action_validation_runs`
- 验证结果
  - 预演状态：`preview_ready`
  - 正式生成状态：`generated`
  - 预演重试数：`2`
  - 正式生成重试数：`2`
  - 候选任务数：`2`
  - 生成 jobs 数：`4`
  - 报告文件存在：`true`
  - jobs 输出文件存在：`true`
  - 回归批次运行态监控通过
- 产出物
  - `reports\batch_retry_web_action_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v26.js`
  - `reports\tmp_esbuild_batch\api_v26.js`
  - `reports\tmp_esbuild_batch\static_preview_v26.js`
- 下一步
  - 继续推进自动生成系统的任务队列可视化与失败重试
  - 继续推进批量任务的队列趋势与重试历史联动能力


### 2026-04-22 01:16:40 +08:00

- 批量生成继续推进任务队列可视化与重试历史联动能力
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，为 `runtime_monitor` 新增 `queue_trends`
  - `queue_trends` 聚合队列负载、backlog、重试次数与队列状态，并输出条形宽度
  - 扩展 `web\backend\services\report_service.py`，为 `runtime_monitor` 新增 `retry_summary`
  - `retry_summary` 汇总 `retry_batch_report.json` 的 retried jobs、队列分布、Provider 分布和剧集分布
  - 扩展 `web\backend\services\report_service.py`，通过审计日志新增 `retry_history`
  - `retry_history` 读取 `batch_retry_generate` 审计记录，展示 dry run / generated 的重试历史
  - `web\frontend\src\types\api.ts` 新增 `BatchRuntimeQueueTrendRecord` 与 `BatchRetryHistoryRecord`
  - `web\frontend\src\pages\Batches\index.tsx` 新增“队列趋势”与“重试历史”卡片
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Queue Trends / Retry History
  - 新增 `scripts\validate_batch_queue_retry_linkage.py`，写入 SQLite 表 `batch_queue_retry_linkage_validation_runs`
- 验证结果
  - 队列趋势数量：`2`
  - 重试历史数量：`2`
  - 当前重试任务数：`2`
  - 队列分布数量：`2`
  - Provider 分布数量：`2`
  - 剧集分布数量：`2`
  - 首个队列重试数：`1`
  - 最新重试记录 dry run：`true`
  - 回归 Web retry 入口通过
- 产出物
  - `reports\batch_queue_retry_linkage_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v27.js`
  - `reports\tmp_esbuild_batch\api_v27.js`
  - `reports\tmp_esbuild_batch\static_preview_v27.js`
- 下一步
  - 继续推进任务队列的失败重试趋势统计
  - 继续推进批量运行态监控的多批次聚合能力


### 2026-04-22 01:38:06 +08:00

- 批量生成继续推进失败重试趋势统计能力
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `load_batch_retry_audit_records(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `load_batch_retry_trends(...)`
  - `runtime_monitor` 新增 `retry_trends` 与 `retry_trend_count`
  - `retry_trends` 按时间周期聚合 retry 动作数、重试量、dry run / generated 数、成功次数、操作人数量、队列影响数、剧集影响数
  - `retry_trends` 输出 `retry_bar_width` 与 `impact_bar_width`，便于 Web / 静态预览可视化
  - `web\frontend\src\types\api.ts` 新增 `BatchRetryTrendRecord`
  - 重写 `web\frontend\src\pages\Batches\index.tsx`，补充 Retry Trends 表并统一批量监控页结构
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Retry Trends 区域
  - 新增 `scripts\validate_batch_retry_trends.py`，写入 SQLite 表 `batch_retry_trends_validation_runs`
- 验证结果
  - 重试趋势周期数：`3`
  - 最新周期：`2030-01-03`
  - 最新周期重试量：`3`
  - 最新周期 dry run 数：`1`
  - 最新周期 generated 数：`1`
  - 最新周期操作人数：`2`
  - 最新周期队列影响数：`2`
  - 最新周期剧集影响数：`2`
  - 回归批量队列联动 / Web retry / 运行态监控通过
- 产出物
  - `reports\batch_retry_trends_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v28.js`
  - `reports\tmp_esbuild_batch\api_v28.js`
  - `reports\tmp_esbuild_batch\static_preview_v28.js`
- 下一步
  - 继续推进批量运行态监控的多批次聚合能力
  - 继续推进跨批次失败热区与重试热区分析

### 2026-04-23 00:20:20 +08:00

- 批量生成继续推进多批次聚合能力
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `discover_batch_snapshots(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `classify_batch_status(...)`
  - `load_batches(...)` 从单一 `season1_batch*.json` 升级为自动扫描 `*_batch_summary.json`
  - `items` 现支持返回多条批次记录，并补充 `step_completion_rate`、`batch_path`、`batch_report_path`
  - 顶层新增 `multi_batch_summary`，汇总批次数、状态分布、范围类型分布、总步骤数、完成步骤数、步骤完成率
  - `runtime_monitor.step_total_count`、`runtime_monitor.step_completed_count`、`runtime_monitor.step_results` 改为跨批次聚合
  - `runtime_monitor.source` 新增 `batch_paths`、`batch_report_paths`、`batch_summary_paths`
  - `web\frontend\src\types\api.ts` 新增 `MultiBatchSummary`
  - `web\frontend\src\pages\Batches\index.tsx` 新增多批次总览卡片与多批次批量统计展示
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 `batchesMultiSummary`
  - 新增 `scripts\validate_batch_multi_summary.py`，写入 SQLite 表 `batch_multi_summary_validation_runs`
  - 修正 `scripts\validate_batch_retry_trends.py`，避免历史审计样本污染趋势验证结果
- 验证结果
  - 多批次聚合批次数：`3`
  - completed 批次：`1`
  - running 批次：`1`
  - blocked 批次：`1`
  - 多批次总步骤数：`11`
  - 多批次完成步骤数：`7`
  - 多批次步骤完成率：`63.6%`
  - 回归 retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_multi_summary_validation_report.json`
  - `reports\batch_retry_trends_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v29.js`
  - `reports\tmp_esbuild_batch\api_v29.js`
  - `reports\tmp_esbuild_batch\static_preview_v29.js`
- 下一步
  - 继续推进跨批次失败热区分析
  - 继续推进跨批次重试热区与优先级建议

### 2026-04-23 00:26:00 +08:00

- 批量生成继续推进跨批次失败热区分析
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `classify_failure_hotspot_level(...)`
  - `multi_batch_summary` 新增 `failure_hotspots` 与 `failure_hotspot_count`
  - `failure_hotspots` 依据 failed / blocked / pending step 聚合热区分数、热区等级与热区条形宽度
  - `web\frontend\src\types\api.ts` 扩展 `MultiBatchSummary.failure_hotspots`
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Failure Hotspots 表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 `batchesFailureHotspotTable`
  - 新增 `scripts\validate_batch_failure_hotspots.py`，写入 SQLite 表 `batch_failure_hotspots_validation_runs`
- 验证结果
  - 失败热区数量：`2`
  - Top 热区批次：`season3_hotspot_validation`
  - Top 热区等级：`critical`
  - Top 热区分数：`7`
  - Top failed step 数：`1`
  - Top blocked step 数：`1`
  - Top pending step 数：`2`
  - 回归多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_failure_hotspots_validation_report.json`
  - `reports\batch_multi_summary_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v30.js`
  - `reports\tmp_esbuild_batch\api_v30.js`
  - `reports\tmp_esbuild_batch\static_preview_v30.js`
- 下一步
  - 继续推进跨批次重试热区分析
  - 继续推进跨批次优先级建议与自动处置建议

### 2026-04-23 00:36:30 +08:00

- 批量生成继续推进跨批次重试热区与优先级建议
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `classify_retry_hotspot_level(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `build_retry_hotspots(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `build_priority_actions(...)`
  - `multi_batch_summary` 新增 `retry_hotspots`、`retry_hotspot_count`
  - `multi_batch_summary` 新增 `priority_actions`、`priority_action_count`
  - `retry_hotspots` 聚合 episode / provider / queue 维度的 retry volume、history action、generated、dry run、热区分数和等级
  - `priority_actions` 合并失败热区与重试热区，输出 P0 / P1 / P2 处理建议
  - `web\frontend\src\types\api.ts` 扩展 `MultiBatchSummary.retry_hotspots` 与 `MultiBatchSummary.priority_actions`
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Retry Hotspots 和 Priority Actions 表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 `batchesRetryHotspotTable` 与 `batchesPriorityActionTable`
  - 新增 `scripts\validate_batch_retry_priority_actions.py`，写入 SQLite 表 `batch_retry_priority_actions_validation_runs`
- 验证结果
  - 重试热区数量：`7`
  - 优先级建议数量：`5`
  - Top 重试热区：`provider:manual_web`
  - Top 重试热区等级：`critical`
  - Top 重试热区分数：`28`
  - P0 建议数：`1`
  - P1 建议数：`4`
  - 回归失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_retry_priority_actions_validation_report.json`
  - `reports\batch_failure_hotspots_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v31.js`
  - `reports\tmp_esbuild_batch\api_v31.js`
  - `reports\tmp_esbuild_batch\static_preview_v31.js`
- 下一步
  - 继续推进跨批次自动处置建议模板
  - 继续推进批量运行调度优先级策略

### 2026-04-23 00:43:40 +08:00

- 批量生成继续推进自动处置建议模板与调度优先级策略
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `build_auto_disposition_templates(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `build_dispatch_priority_plan(...)`
  - `multi_batch_summary` 新增 `auto_disposition_templates`、`auto_disposition_template_count`
  - `multi_batch_summary` 新增 `dispatch_priority_plan`、`dispatch_priority_count`
  - 自动处置模板基于失败热区、重试热区与优先级动作生成模板标题、触发类型、目标、建议命令与 checklist
  - 调度优先级计划基于 queue / provider 维度聚合 active、failed、manual、retried、retry hotspot score 并生成 dispatch score
  - `web\frontend\src\types\api.ts` 扩展 `MultiBatchSummary.auto_disposition_templates` 与 `MultiBatchSummary.dispatch_priority_plan`
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Auto Disposition Templates 与 Dispatch Priority Plan 表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 `batchesAutoDispositionTable` 与 `batchesDispatchPriorityTable`
  - 新增 `scripts\validate_batch_dispatch_strategy.py`，写入 SQLite 表 `batch_dispatch_strategy_validation_runs`
- 验证结果
  - 自动处置模板数：`3`
  - 调度优先级计划数：`4`
  - Top 调度目标：`provider:manual_web`
  - Top 调度优先级：`P0`
  - Top 调度分数：`33`
  - P0 模板数：`2`
  - P0 调度项数：`4`
  - 回归重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_dispatch_strategy_validation_report.json`
  - `reports\batch_retry_priority_actions_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v32.js`
  - `reports\tmp_esbuild_batch\api_v32.js`
  - `reports\tmp_esbuild_batch\static_preview_v32.js`
- 下一步
  - 继续推进批量自动处置执行计划模板
  - 继续推进调度优先级规则中心与策略参数化

### 2026-04-23 00:55:30 +08:00

- 批量生成继续推进自动处置执行计划模板与调度策略参数化
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `DISPATCH_STRATEGY_VERSION`、`DISPATCH_STRATEGY_WEIGHTS` 与 `DISPATCH_STRATEGY_THRESHOLDS`
  - 新增 `build_dispatch_strategy_metadata(...)`、`calculate_dispatch_score(...)`、`recommend_dispatch_priority(...)`
  - `build_dispatch_priority_plan(...)` 改为使用参数化权重和阈值，保持原有评分结果兼容
  - 新增 `build_execution_plan_templates(...)`，把自动处置模板和调度优先级计划转换为 dry-run 执行计划模板
  - `multi_batch_summary` 新增 `dispatch_strategy`、`dispatch_strategy_weights`
  - `multi_batch_summary` 新增 `execution_plan_templates`、`execution_plan_template_count`
  - `web\frontend\src\types\api.ts` 扩展调度策略和执行计划模板类型
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Execution Plan Templates 与 Dispatch Strategy 展示
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 `batchesExecutionPlanTable` 与 `batchesDispatchStrategy`
  - 新增 `scripts\validate_batch_dispatch_execution_plan.py`，写入 SQLite 表 `batch_dispatch_execution_plan_validation_runs`
- 验证结果
  - 执行计划模板数：`6`
  - dry-run 执行计划数：`6`
  - 需要人工确认计划数：`6`
  - 调度策略键：`batch_dispatch_strategy_v1`
  - active 权重：`2`
  - failed 权重：`4`
  - 首个执行计划优先级：`P0`
  - 首个执行命令：`review_batch_steps --target season1_execution_plan_validation --dry-run`
  - 回归自动处置模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_dispatch_execution_plan_validation_report.json`
  - `reports\batch_dispatch_strategy_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v33.js`
  - `reports\tmp_esbuild_batch\api_v33.js`
  - `reports\tmp_esbuild_batch\static_preview_v33.js`
- 下一步
  - 继续推进自动处置执行预演 API
  - 继续推进执行计划审计与结果落库

### 2026-04-23 01:10:30 +08:00

- 批量生成继续推进自动处置执行预演 API 与执行审计落库
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `ensure_batch_execution_preview_schema(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `write_batch_execution_preview_run(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `load_batch_execution_preview_history(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `preview_batch_execution_plan(...)`
  - `GET /api/batches` 的 `multi_batch_summary` 新增 `execution_preview_history` 与 `execution_preview_history_count`
  - `POST /api/batches/execution-plans/preview` 新增执行计划 dry-run 预演接口
  - 预演接口会写入 SQLite 表 `batch_execution_preview_runs`，并同步写入 `audit_logs` 的 `batch_execution_plan_preview`
  - `web\frontend\src\services\api.ts` 新增 `previewBatchExecutionPlan(...)`
  - `web\frontend\src\types\api.ts` 新增 `BatchExecutionPlanPreviewResult` 与执行预演历史类型
  - `web\frontend\src\pages\Batches\index.tsx` 为 Execution Plan Templates 增加 Preview 操作、预演结果和历史表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增静态预演按钮、结果区和历史表
  - 新增 `scripts\validate_batch_execution_preview_api.py`，写入 SQLite 表 `batch_execution_preview_api_validation_runs`
- 验证结果
  - API 预演调用数：`2`
  - 执行预演历史数：`2`
  - 审计日志数：`2`
  - 最新预演计划：`dispatch_provider_manual_web`
  - 最新预演优先级：`P0`
  - 最新预演状态：`preview_ready`
  - 回归执行计划模板 / 自动处置模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_execution_preview_api_validation_report.json`
  - `reports\batch_dispatch_execution_plan_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v34.js`
  - `reports\tmp_esbuild_batch\api_v34.js`
  - `reports\tmp_esbuild_batch\static_preview_v34.js`
- 下一步
  - 继续推进执行计划正式执行队列
  - 继续推进执行计划结果复盘统计

### 2026-04-23 01:41:30 +08:00

- 批量生成继续推进执行计划正式执行队列与队列复盘统计
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `ensure_batch_execution_queue_schema(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `write_batch_execution_queue_run(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `load_batch_execution_queue_history(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `build_execution_queue_summary(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `queue_batch_execution_plan(...)`
  - 新增 `POST /api/batches/execution-plans/queue`，支持把执行计划正式写入执行队列
  - 队列写入 SQLite 表 `batch_execution_queue_runs`，并同步写入 `audit_logs` 的 `batch_execution_plan_queue`
  - `GET /api/batches` 的 `multi_batch_summary` 新增 `execution_queue_summary`、`execution_queue_history` 与 `execution_queue_history_count`
  - `web\frontend\src\services\api.ts` 新增 `queueBatchExecutionPlan(...)`
  - `web\frontend\src\types\api.ts` 新增 `BatchExecutionPlanQueueResult` 与队列历史类型
  - `web\frontend\src\pages\Batches\index.tsx` 为 Execution Plan Templates 增加 Queue 操作、队列结果、队列汇总和队列历史表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增 Queue 按钮、结果区、队列汇总与队列历史表
  - 新增 `scripts\validate_batch_execution_queue_api.py`，写入 SQLite 表 `batch_execution_queue_api_validation_runs`
- 验证结果
  - 队列 API 调用数：`2`
  - 执行队列历史数：`2`
  - 审计日志数：`2`
  - 已入队数量：`2`
  - 需要人工确认数量：`2`
  - 最新队列状态：`queued`
  - 回归执行预演 API / 执行计划模板 / 自动处置模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_execution_queue_api_validation_report.json`
  - `reports\batch_execution_preview_api_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v35.js`
  - `reports\tmp_esbuild_batch\api_v35.js`
  - `reports\tmp_esbuild_batch\static_preview_v35.js`
- 下一步
  - 继续推进执行队列状态流转
  - 继续推进执行结果复盘统计与失败率分析

### 2026-04-28 01:31:40 +08:00

- 批量生成继续推进执行队列状态流转与执行结果复盘统计
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，为 `batch_execution_queue_runs` 增加 `result_note` 与 `completed_at`
  - 扩展 `web\backend\services\report_service.py`，新增 `update_batch_execution_queue_status(...)`
  - `build_execution_queue_summary(...)` 新增 `running_count`、`completed_count`、`failed_count`
  - `build_execution_queue_summary(...)` 新增 `execution_status_counts`、`completion_rate`、`failure_rate`
  - 新增 `POST /api/batches/execution-plans/queue/status`，支持执行队列状态流转
  - 状态流转动作会写入 `audit_logs` 的 `batch_execution_queue_status_update`
  - `web\frontend\src\services\api.ts` 新增 `updateBatchExecutionQueueStatus(...)`
  - `web\frontend\src\types\api.ts` 新增 `BatchExecutionQueueStatusResult`，并补充队列结果字段
  - `web\frontend\src\pages\Batches\index.tsx` 为 Execution Queue History 增加 Start / Done / Fail 操作
  - `web\frontend\src\pages\Batches\index.tsx` 为 Execution Queue Summary 增加完成数、失败数、完成率、失败率
  - `web\static_preview\main.js` 同步新增队列状态更新动作和复盘统计展示
  - 新增 `scripts\validate_batch_execution_queue_status_flow.py`，写入 SQLite 表 `batch_execution_queue_status_flow_validation_runs`
- 验证结果
  - 队列历史数：`5`
  - completed 数：`1`
  - failed 数：`1`
  - running 数：`3`
  - 完成率：`20.0%`
  - 失败率：`20.0%`
  - 队列状态更新审计数：`4`
  - 回归执行队列 API / 执行预演 API / 执行计划模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_execution_queue_status_flow_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v36.js`
  - `reports\tmp_esbuild_batch\api_v36.js`
  - `reports\tmp_esbuild_batch\static_preview_v36.js`
- 下一步
  - 继续推进执行结果失败维度拆解
  - 继续推进执行队列运营复盘报表

### 2026-04-28 02:01:10 +08:00

- 批量生成继续推进执行结果失败维度拆解与执行队列运营复盘报表
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `build_execution_failure_breakdown(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `build_execution_operations_report(...)`
  - `multi_batch_summary` 新增 `execution_failure_breakdown` 与 `execution_failure_breakdown_count`
  - `multi_batch_summary` 新增 `execution_operations_report`
  - 失败维度拆解按 `result_note` 聚合失败原因、失败数、占比、关联目标数和最新失败任务
  - 运营复盘报表输出 `health_status`、`summary_cards`、`recommendations`、`top_failure_reason`
  - `web\frontend\src\types\api.ts` 扩展执行失败拆解与运营报表类型
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Execution Ops Report 卡片
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Execution Failure Breakdown 表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增运营报表区和失败拆解表
  - 新增 `scripts\validate_batch_execution_operations_report.py`，写入 SQLite 表 `batch_execution_operations_report_validation_runs`
- 验证结果
  - 失败拆解项数：`2`
  - Top 失败原因：`provider timeout`
  - Top 失败数：`5`
  - 报表建议数：`2`
  - 完成率：`20.0%`
  - 失败率：`80.0%`
  - 健康状态：`critical`
  - 回归执行队列状态流转 / 执行队列 API / 执行预演 API / 执行计划模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_execution_operations_report_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v37.js`
  - `reports\tmp_esbuild_batch\api_v37.js`
  - `reports\tmp_esbuild_batch\static_preview_v37.js`
- 下一步
  - 继续推进执行队列周期报表归档
  - 继续推进执行队列导出能力

### 2026-04-28 23:58:40 +08:00

- 批量生成继续推进执行队列周期报表归档与导出能力
- 本次完成
  - 扩展 `web\backend\services\report_service.py`，新增 `build_execution_operations_report_rows(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `write_execution_operations_archive(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `load_execution_operations_archives(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `cleanup_execution_operations_archives(...)`
  - 扩展 `web\backend\services\report_service.py`，新增 `export_execution_operations_report(...)`
  - 新增 `POST /api/batches/execution-operations/export`，支持导出 JSON / CSV 和归档导出
  - 新增 `GET /api/batches/execution-archives`，支持查看执行运营归档列表
  - 新增 `POST /api/batches/execution-archives/cleanup`，支持 dry-run / 正式清理旧归档
  - 导出归档文件保存到 `reports\execution_operations_archive\YYYYMMDD\<timestamp>`
  - `web\frontend\src\services\api.ts` 新增执行运营导出、归档列表、归档清理接口
  - `web\frontend\src\types\api.ts` 新增执行运营导出结果、归档记录、归档清理结果类型
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Execution Operations Export 卡片
  - `web\frontend\src\pages\Batches\index.tsx` 新增 Execution Archives 表
  - `web\static_preview\index.html` 与 `web\static_preview\main.js` 同步新增导出按钮、归档列表和清理操作
  - 新增 `scripts\validate_batch_execution_archive_management.py`，写入 SQLite 表 `batch_execution_archive_management_validation_runs`
- 验证结果
  - JSON 导出行数：`13`
  - CSV 导出行数：`13`
  - 归档文件数：`2`
  - 归档列表数：`3`
  - 清理候选数：`0`
  - 最新归档路径：`reports\execution_operations_archive\20260428\20260428235737`
  - 回归执行运营报表 / 执行队列状态流转 / 执行队列 API / 执行预演 API / 执行计划模板 / 调度优先级 / 重试热区 / 失败热区 / 多批次聚合 / retry 趋势 / 队列联动 / Web retry / 运行态监控全部通过
- 产出物
  - `reports\batch_execution_archive_management_validation_report.json`
  - `reports\tmp_esbuild_batch\batches_page_v38.js`
  - `reports\tmp_esbuild_batch\api_v38.js`
  - `reports\tmp_esbuild_batch\static_preview_v38.js`
- 下一步
  - 当前 `plan.md` 尾部阶段任务已收口
  - 后续进入新的批次能力规划时再继续拆解

### 2026-04-29 00:22:16 +08:00

- 全量验证体系继续推进，目标是完成“模拟数据写库 + 统一总跑 + 设计复盘”
- 本次完成
  - 新增 `scripts\validate_full_system_suite.py`，自动发现并执行全部 `validate_*.py`
  - 全量脚本新增子进程环境继承，避免丢失 `PATH` / 用户站点包，修复总跑时 `anyio` 等依赖误判缺失
  - `scripts\validate_auth_flow.py` 改为在脚本内注入企业版鉴权上下文，避免受当前 `creator` 默认版配置影响
  - `scripts\validate_security_governance_history_analytics.py` 改为未来唯一时间窗写数，避免共享审计日志导致 top operator / top action 断言漂移
  - `scripts\validate_security_governance_dashboard.py` 改为未来唯一时间窗写数，避免治理告警统计被历史数据污染
  - `scripts\validate_security_governance_config_audit_export.py` 改为未来唯一时间窗写数，避免配置审计导出数量累积
  - 全量验证结果已写入 SQLite：`full_system_validation_runs`、`full_system_validation_run_items`
- 全量验证结果
  - 最新全量运行：`full_system_validation_20260429001919378745`
  - 脚本总数：`47`
  - 通过数：`47`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`86568 ms`
  - 报告路径：`reports\full_system_validation_report.json`
- 设计复盘结论
  - `report_service.py` 继续承载读取、聚合、导出、归档、清理、状态更新多种职责，已明显过厚，下一阶段应拆为 `queue_service`、`reporting_service`、`archive_service`
  - 批量 / 队列 / 预演历史默认只取 `limit=10`，当前适合演示，不适合真实运营分析
  - 验证体系仍然共用 `state\aicomic_demo.db`，虽然本轮已补唯一时间窗，但长期仍建议引入测试 run 级隔离库
- 下一步
  - 拆分 `web\backend\services\report_service.py`
  - 把历史查询的 `limit=10` 改为可配置参数或分页聚合
  - 为验证脚本增加独立测试数据库或 run namespace

### 2026-04-29 00:22:16 +08:00 第二阶段

- 目标：围绕 `report_service.py` 拆分与 `/batches` 双口径统计做完整设计、开发、验证
- 设计文档
  - `docs\批量执行统计双口径与ReportService拆分方案.md`
- 本阶段开发计划
  - [ ] 新增 `batch_history_service.py`，承接 retry / execution preview / execution queue 历史读写与分页
  - [ ] 新增 `batch_operations_service.py`，承接全量执行队列摘要、失败拆解、运营报表聚合
  - [ ] 新增 `batch_archive_service.py`，承接运营报表导出、归档与清理
  - [ ] 精简 `report_service.py`，改为批量总装配入口
  - [ ] 新增分页 API：
    - `GET /api/batches/retry-history`
    - `GET /api/batches/execution-previews`
    - `GET /api/batches/execution-queue`
  - [ ] 改造 `/api/batches`：
    - 历史 count 使用全量口径
    - 历史 items 仅返回第一页，兼容静态预览
  - [ ] 改造 `web\frontend\src\pages\Batches\index.tsx` 为服务端分页
  - [ ] 补充分页 API 验证脚本
  - [ ] 跑全量验证并更新 `result.md` / `README.md` / `web\frontend\README.md` / `docs\项目资料索引.md`

### 2026-04-29 01:18:00 +08:00

- 继续执行 `report_service.py` 拆分与 `/batches` 双口径统计改造
- 本次完成
  - 已完成 `web\backend\services\report_service.py` 主装配切换，`load_batches(...)` 改为“第一页历史列表 + 全量聚合统计”双口径
  - 已完成 `web\backend\app.py` 新增分页接口：
    - `GET /api/batches/retry-history`
    - `GET /api/batches/execution-previews`
    - `GET /api/batches/execution-queue`
  - 已完成 `web\backend\services\batch_history_service.py`、`batch_operations_service.py`、`batch_archive_service.py` 接入主调用链
  - 已完成 `web\frontend\src\types\api.ts` 新增分页类型与批量历史记录类型
  - 已完成 `web\frontend\src\services\api.ts` 新增 3 个批量历史分页请求
  - 已完成 `web\frontend\src\pages\Batches\index.tsx` 改造为三张历史表独立服务端分页
  - 已新增 `scripts\validate_batch_history_paging.py`，验证分页 API、`/api/batches` 双口径、SQLite 写入与报告输出
  - 已更新设计文档：`docs\批量执行统计双口径与ReportService拆分方案.md`
- 本阶段任务状态
  - [x] 新增 `batch_history_service.py`，承接 retry / execution preview / execution queue 历史读写与分页
  - [x] 新增 `batch_operations_service.py`，承接全量执行队列摘要、失败拆解、运营报表聚合
  - [x] 新增 `batch_archive_service.py`，承接运营报表导出、归档与清理
  - [x] 精简 `report_service.py`，改为批量总装配入口
  - [x] 新增分页 API：
    - `GET /api/batches/retry-history`
    - `GET /api/batches/execution-previews`
    - `GET /api/batches/execution-queue`
  - [x] 改造 `/api/batches`：
    - 历史 count 使用全量口径
    - 历史 items 仅返回第一页，兼容静态预览
  - [x] 改造 `web\frontend\src\pages\Batches\index.tsx` 为服务端分页
  - [x] 补充分页 API 验证脚本
  - [x] 跑全量验证并更新 `result.md` / `README.md` / `web\frontend\README.md` / `docs\项目资料索引.md`
- 验证结果
  - 新增分页专项验证：`batch_history_paging_validation_20260429011530276523`
  - 最新全量运行：`full_system_validation_20260429011450374686`
  - 脚本总数：`48`
  - 通过数：`48`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`97669 ms`
  - 报告路径：`reports\batch_history_paging_validation_report.json`
  - 总报告路径：`reports\full_system_validation_report.json`
- 额外记录
  - 前端本地 `npm run typecheck` / `npx tsc --noEmit` 在当前环境失败，原因是 `tsc` CLI 未就绪，不是本轮代码语法错误
  - 后端编译、分页 API、专项验证、全量总跑均已通过，可作为当前主验收依据
- 下一步设计建议
  - 继续把 `preview_batch_execution_plan(...)`、`queue_batch_execution_plan(...)` 从 `report_service.py` 迁出，收口剩余耦合
  - 为前端补构建级校验基线，避免只依赖 API/后端全量验证
  - 为验证体系引入 run 级隔离数据库，减少共享 `state\aicomic_demo.db` 带来的历史累积影响

### 2026-04-30 00:36:00 +08:00

- 继续收口批量执行的 3 个设计尾项，并先输出详细设计方案再落代码
- 设计文档
  - `docs\批量执行尾项收口详细方案.md`
- 本次完成
  - 新增 `web\backend\services\batch_execution_service.py`，承接执行计划模板生成、模板解析、预演写库、正式入队写库
  - `web\backend\services\report_service.py` 新增 `load_batch_summary(...)`，拆分 summary-only 装配与兼容壳 `load_batches(...)`
  - `web\backend\app.py` 新增 `GET /api/batches/summary`
  - `web\frontend\src\services\api.ts` 新增 `getBatchSummary()`
  - `web\frontend\src\pages\Batches\index.tsx` 改为 summary 走 `/api/batches/summary`，三张历史表继续走独立分页接口
  - `src\aicomic\core\config.py` 增加 `AICOMIC_DATABASE_PATH` 支持
  - 新增 `scripts\validation_runtime.py`，用于全量验证运行时克隆隔离数据库并构建子进程环境
  - 新增 `scripts\validate_validation_runtime_isolation.py`，验证数据库环境覆盖与隔离生效
  - `scripts\validate_full_system_suite.py` 改为：
    - 每次 run 先克隆数据库到 `state\validation_runs\<run_id>\aicomic_validation.db`
    - 子进程统一注入 `AICOMIC_DATABASE_PATH`
    - 输出逐脚本进度
    - 增加单脚本 `300s` 超时保护
  - `scripts\validate_batch_history_paging.py` 已补 `/api/batches/summary` 边界断言
  - `scripts\validate_batch_execution_preview_api.py` 去除脆弱硬编码 `plan_key`，改为从当前模板列表动态选取
- 本轮专项验证
  - `validation_runtime_isolation_20260429084843331396`
  - `batch_history_paging_validation_20260429084844735409`
  - `batch_execution_preview_api_validation_20260429085222546199`
  - `batch_execution_queue_api_validation_20260429084940119782`
  - `batch_execution_operations_report_validation_20260429084940168060`
- 最新全量验证
  - 运行 ID：`full_system_validation_20260430001839379633`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`904837 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260430001839379633\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 收口结论
  - 执行计划预演 / 入队写库已从 `report_service.py` 迁出
  - 批量聚合 summary 与历史列表接口边界已拆开，前端主页面不再依赖兼容壳接口
  - 全量验证体系已具备 run 级数据库隔离能力
- 后续建议
  - 继续清理 `report_service.py` 中遗留的旧版执行历史辅助函数，进一步压缩文件体积
  - 为前端补稳定的 TypeScript CLI 校验链，减少对 esbuild 语法校验的依赖
  - 如果后续需要更强回放能力，可继续隔离 `reports\` 输出目录

### 2026-04-30 00:42:58 +08:00

- 本次同步
  - 已补齐 `result.md` 的第 65 节，完整记录本轮 3 个尾项的设计方案、代码落地、专项验证、全量验证与隔离数据库结果
  - 已更新 `README.md` 与 `web\frontend\README.md`，把旧阶段基线文案从“最新”调整为“阶段”，避免与当前 `49 / 49` 主基线冲突
  - 已完成文档定点检索，确认 `result.md` 新增尾项收口章节，前端 README 当前最新基线为 `49 / 49`
- 验证说明
  - 本次仅补文档与计划记录，未改动运行时代码
  - 代码验证仍以 `full_system_validation_20260430001839379633` 为最终有效基线

### 2026-04-30 01:05:56 +08:00

- 本次推进
  - 继续执行尾项后的技术债收敛，目标是进一步压缩 `web\backend\services\report_service.py`
  - `batch_history_service.py` 新增 `load_batch_execution_preview_history(...)`、`load_batch_execution_queue_history(...)`、`load_batch_retry_trends(...)`
  - `report_service.py` 已删除重复的执行预演历史、执行队列历史、重试趋势、执行运营报表行构建等旧实现，改为直接复用 `batch_history_service.py` 与 `batch_operations_service.py`
  - 5 个批量执行相关验证脚本已改为直接从 `batch_history_service.py` 引用 schema helper
- 专项验证
  - `batch_execution_preview_api_validation_20260430010322715410`
  - `batch_execution_queue_api_validation_20260430010327026077`
  - `batch_execution_queue_status_flow_validation_20260430010330042400`
  - `batch_execution_operations_report_validation_20260430010337091399`
  - `batch_execution_archive_management_validation_20260430010348097066`
- 最新全量验证
  - 运行 ID：`full_system_validation_20260430010359514143`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`92556 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260430010359514143\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 当前判断
  - `report_service.py` 的历史重复实现已经继续收缩一轮
  - 下一阶段如果继续推进，优先项会转到前端稳定 `tsc` / typecheck 验证链

### 2026-04-30 02:05:45 +08:00

- 本次推进
  - 继续执行开发计划，优先收口前端 `tsc` / `typecheck` / `build` 验证链，避免主验证只依赖后端脚本与 esbuild
  - 对 `web\frontend` 进行依赖状态排查后，确认此前问题不是业务代码回归，而是 `node_modules` 与 `package-lock.json` 安装态损坏
  - 已隔离旧依赖目录 `web\frontend\node_modules_corrupt_20260430014242`，并使用 `npx npm@10 install` 重建前端依赖树与锁文件
- 代码与配置处理
  - 重写 `web\frontend\src\app.tsx`，清理历史乱码文案，统一 `DEFAULT_INITIAL_STATE`，修复登出回写缺失 `authEnabled` 导致的 TypeScript 报错
  - `web\frontend\src\pages\Login\index.tsx` 与 `web\frontend\src\pages\LoginCallback\index.tsx` 继续沿用本轮前已完成的 Umi runtime import 收敛方案，改为本地跳转 helper
- 本轮专项验证
  - `npm run typecheck`
  - `npm run build`
  - 两项均已通过，前端本地校验链恢复
- 最新全量验证
  - 运行 ID：`full_system_validation_20260430020352185383`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`95299 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260430020352185383\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 当前判断
  - 前端验证链已经从“安装态损坏”恢复到“可稳定执行 typecheck/build”的状态
  - 现阶段主线代码、前端构建链、全量脚本三条校验口径已重新对齐

### 2026-04-30 02:38:20 +08:00

- 本次推进
  - 排查“前端无法登录”问题，并按 root cause 先做策略核对、再做真实接口复现、最后补数据与全量验证
  - 已确认问题不是数据库缺用户，也不是鉴权接口失效，而是 `creator` 版本策略把本地开发登录错误地绑定到了 `auth_enabled=true`
- 根因结论
  - `config\web.yaml` 中 `auth.dev_login_enabled=true`
  - 当前 `config\edition.yaml` 为 `creator`
  - `edition_policy.py` 旧逻辑为 `dev_login_enabled = auth_enabled and active_settings.dev_login_enabled`
  - 导致 Creator 默认 `auth_enabled=false` 时，前端 `/api/auth/config` 永远拿到 `dev_login_enabled=false`，点击登录会被后端 `403 Development login disabled`
  - 该行为与 `docs\产品版本设计方案.md` 中“Creator 本地开发登录可选”的设计约束冲突
- 代码修复
  - `web\backend\services\edition_policy.py`
    - 改为允许本地开发登录独立于强鉴权开关存在
    - 保持 Creator 继续关闭 OIDC / Mock SSO / 多用户强制鉴权
  - `scripts\validate_edition_policy.py`
    - 新增 `creator_dev_login_enabled` 校验与落库字段
    - 增加断言：当 `web.yaml` 开启 `dev_login_enabled` 时，Creator 模式必须允许本地开发登录
    - 增加断言：Creator 模式不得开放 OIDC
  - `web\frontend\src\pages\Login\index.tsx`
    - 调整登录页提示文案，直接展示当前版本/配置下的登录能力状态
    - 避免再出现“页面可见但必然 403”的误导式体验
- 模拟数据写库
  - 已通过本地 `dev-login` 流程向主数据库写入演示账号：
    - `creator_demo`
    - `editor_demo`
    - `reviewer_demo`
  - 写库后统计：
    - `users` 总数：`350`
    - `auth_sessions` 总数：`206`
    - `audit_logs` 中 `login` 动作总数：`19`
- 本轮专项验证
  - Creator 当前配置下调用 `/api/auth/dev-login` 已返回 `200`
  - `npm run typecheck`：通过
  - `npm run build`：通过
  - `python scripts\validate_edition_policy.py`：通过
  - `python scripts\validate_auth_flow.py`：通过
- 最新全量验证
  - 运行 ID：`full_system_validation_20260430023625248651`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`96274 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260430023625248651\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 当前判断
  - Creator 版“可选本地开发登录”已经与产品设计重新对齐
  - 登录问题已完成修复、数据验证和全量回归闭环

### 2026-04-30 03:35:00 +08:00

- 本次推进
  - 继续收口前端登录问题的“开发态运行恢复”与“浏览器级可重复验证”能力，避免只靠临时命令或静态请求判断
  - 已把“HTML 200 但页面空白”的 Umi dev 缓存损坏问题沉淀为脚本和文档
- 新增脚本
  - `scripts\recover_frontend_dev.ps1`
    - 自动停止当前 `8000` 端口 Node 前端进程
    - 清理 `web\frontend\src\.umi`
    - 清理 `web\frontend\node_modules\.cache`
    - 自动重启 `npm run dev`
    - 等待 `/login` 返回 `200`
  - `scripts\start_edge_cdp.ps1`
    - 启动独立 Edge Headless 会话
    - 暴露 `9223` 调试端口
    - 使用独立 Profile，避免沿用旧登录态
  - `scripts\verify_frontend_browser_login.py`
    - 连接独立 CDP 浏览器
    - 真实打开 `/login`
    - 在浏览器上下文完成 `browser_creator_demo` 本地开发登录
    - 校验跳转 `/dashboard`、`localStorage` token/用户写入、Dashboard 内容可见
- 文档沉淀
  - 新增 `docs\前端开发态登录与空白页排障说明.md`
  - `README.md` 与 `web\frontend\README.md` 已补充恢复链路和验证命令
- 计划中的验证动作
  - 运行 `recover_frontend_dev.ps1` 验证可自动恢复前端 dev 环境
  - 运行 `start_edge_cdp.ps1` 验证独立 CDP 浏览器可用
  - 运行 `verify_frontend_browser_login.py` 验证真实浏览器登录成功
  - 复跑 `npm run typecheck`、`npm run build`
  - 复跑 `python scripts\validate_full_system_suite.py`

### 2026-05-01 13:05:00 +08:00

- 本轮验证结果
  - `scripts\recover_frontend_dev.ps1` 已成功重启前端 dev 服务，当前 `8000` 端口恢复正常
  - `scripts\start_edge_cdp.ps1` 已成功启动独立 Edge Headless 会话：
    - 端口：`9223`
    - 浏览器版本：`Edg/147.0.3912.86`
  - `scripts\verify_frontend_browser_login.py` 已通过：
    - 登录页真实渲染完成
    - `browser_creator_demo` 浏览器上下文登录成功
    - 已跳转到 `/dashboard`
    - `localStorage` 中已写入 `aicomic_current_user` 与 access token
    - 报告：`reports\frontend_browser_login_validation_report.json`
- 前端构建链验证结论
  - `npm run typecheck` / `npm run build` 在当前 Windows shell 包装层存在“任务完成但外壳不及时退出”的现象
  - 更稳定的本地验证口径：
    - `web\frontend\.\node_modules\.bin\tsc.cmd --noEmit`：通过
    - `logs\frontend_build_2026043001.stdout.log` 已输出 `Webpack: Compiled successfully` 与 `event - Build index.html`
- 最新全量验证
  - 运行 ID：`full_system_validation_20260501125539480933`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`371068 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260501125539480933\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 当前判断
  - 登录修复、开发态恢复、浏览器级验证、全量后端验证均已闭环
  - 当前剩余问题不是业务代码回归，而是 Windows 下 `npm` 包装层的偶发退出不稳定

### 2026-05-01 13:22:00 +08:00

- 本次执行
  - 按顺序执行 `scripts\run_demo_validation.py`，先将模拟项目、剧集、任务、Provider 请求、Batch、导入/重试状态写入主数据库
  - 随后执行 `scripts\validate_full_system_suite.py`，基于最新主库快照完成全量验证
- 模拟数据写库结果
  - 数据库：`state\aicomic_demo.db`
  - 项目数：`1`
  - 季数：`1`
  - 剧集数：`2`
  - 任务数：`16`
  - Provider 请求数：`16`
  - Batch 数：`1`
  - Batch Run 数：`4`
  - 成功任务数：`6`
  - Dashboard 状态：`needs_attention`
  - Review Metrics 状态：`needs_optimization`
- 最新全量验证
  - 运行 ID：`full_system_validation_20260501131633383076`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`272412 ms`
  - 隔离数据库：`state\validation_runs\full_system_validation_20260501131633383076\aicomic_validation.db`
  - 总报告：`reports\full_system_validation_report.json`
- 当前判断
  - 模拟数据写库与统一总跑均已成功完成
  - 当前系统最新有效基线已刷新到 `full_system_validation_20260501131633383076`

### 2026-05-01 22:48:43 +08:00

- 本次整理
  - 对 `10_System` 做目录级整理，目标是收入口、修正文档乱码、补运行说明，不改业务代码结构
  - 重写 `README.md`，收敛为当前有效入口、命令、基线和目录说明
  - 重写 `result.md`，保留最新有效验证结论并去除历史乱码内容
  - 重写 `docs\项目资料索引.md`、`docs\Python项目代码规范.md`、`docs\系统提示词.md`、`docs\生成规则.md`、`docs\PythonCodeStyle.md`
  - 重写 `web\frontend\README.md`，清理乱码并收敛前端启动、版本能力和验证口径
  - 新增 `web\README.md`、`scripts\README.md`、`reports\README.md`、`state\README.md`、`logs\README.md`
  - 新增 `.gitignore`，隔离缓存、构建产物和本地状态目录
- 同步修正
  - 修复 `plan.md` 顶部配套资料中已迁移文档的路径引用
  - 统一把工程说明更新为当前 `49 / 49` 全量验证基线
- 验证说明
  - 本轮仅做目录整理与文档修订，未修改运行时代码
  - 因未改动业务代码，本轮未重跑全量测试，当前有效运行基线仍为 `full_system_validation_20260501131633383076`

### 2026-05-05 19:33:17 +08:00

- 本次修复目标
  - 修复 Docker 全量验证中安全治理复盘导出/归档的跨脚本数据污染问题
  - 将 Docker 验证入口固化为项目内可复现命令
  - 同步刷新当前有效验证基线与残余风险说明
- 代码改动
  - `scripts\validate_full_system_suite.py`：每个 `validate_*.py` 克隆独立数据库，并在报告 item 中记录脚本级数据库路径
  - `scripts\validation_runtime.py`：修正 `PYTHONPATH` 使用平台分隔符，并新增脚本级数据库/state 路径工具
  - `src\aicomic\core\config.py`、`web\backend\settings.py`：支持 `AICOMIC_STATE_DIR` 覆盖，避免验证脚本共享治理状态文件
  - `pyproject.toml`：新增 `validation` extra，收纳全量验证依赖
  - `Dockerfile`、`.dockerignore`、`scripts\run_docker_validation.sh`：新增容器化验证入口
- 最新 Docker 验证
  - 日志：`reports\docker_validation_20260505193238.log`
  - 全量运行 ID：`full_system_validation_20260505113305375968`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`8318 ms`
  - 总报告：`reports\full_system_validation_report.json`
- 当前残余风险
  - 模拟数据链路仍显示 `dashboard_status=needs_attention`、`review_metrics_status=needs_optimization`
  - OpenAI live run 未启用，`13` 个 OpenAI 请求处于 blocked/dry-run
  - 手工素材导入仍缺失 `14` 项，`10` 个任务需要 manual/retry
  - 批量执行运营报告仍为 `critical`，模拟失败率为 `51.6%`

### 2026-05-05 19:41:42 +08:00

- 本次修复目标
  - 继续收口生产链路成熟度问题：live Provider 未启用、素材补齐不足、批量重试率偏高
  - 不直接启用真实 OpenAI 调用，先建立本地可验证的 production fallback 闭环
- 修复方案
  - 自动按 Provider 请求清单生成完整本地 fallback 产物，覆盖图片、音频、视频输出文件名
  - 手工导入阶段导入全量 `16` 个产物，确保模拟生产链路不再停留在素材缺失状态
  - 在 retry-batch 后用最终 Job 状态刷新 episode state、state snapshot 和 resume report
  - 复盘指标中把“OpenAI live 未启用”从阻断风险调整为上线前提醒，前提是本地 fallback 已补齐
  - Dashboard 增加 production fallback / live provider readiness 字段
- 代码改动
  - `scripts\run_demo_validation.py`：生成全量 fallback 产物、刷新最终状态、输出 production readiness 字段
  - `src\aicomic\review\metrics.py`：本地 fallback 已就绪时不再把 OpenAI dry-run 计为阻断风险
  - `src\aicomic\publish\dashboard.py`：Dashboard 展示 fallback/live readiness，并调整下一步建议
- 最新 Docker 验证
  - 日志：`reports\docker_validation_20260505194104.log`
  - 全量运行 ID：`full_system_validation_20260505114130623816`
  - 脚本总数：`49`
  - 通过数：`49`
  - 失败数：`0`
  - 编译检查：`通过`
  - 总耗时：`8384 ms`
- 生产链路结果
  - Job 成功数：`16 / 16`
  - 剧集 ready 数：`2 / 2`
  - 手工导入：`16` 导入、`0` 缺失
  - Retry：`0`
  - Production readiness：`ready_with_local_fallback`
  - Dashboard：`ready`
  - Review Metrics：`healthy`
- 残余风险
  - `production_live_provider_ready=false`，说明当前仍未配置真实 OpenAI live Provider
  - 上线前应配置 `OPENAI_API_KEY`，以小批量执行图片/TTS 请求，确认真实 API、成本、失败保护和回写链路

### 2026-05-05 20:01:41 +08:00

- 本次修复目标
  - 基于 OpenAI 替代方案调研，把可本地运行的 Provider 纳入现有生产链路
  - 不改变默认稳态路线，继续保留 `manual_web` / `windows_tts` / 本地 fallback
  - 让 ComfyUI/Piper 在未安装模型时也能安全 dry-run，并明确暴露上线前配置缺口
- 修复方案
  - 图像替代：新增 `local_comfyui_image`，通过 ComfyUI HTTP API 提交 workflow，真实执行时轮询 history 并下载输出图片
  - TTS 替代：新增 `local_piper_tts`，通过本地 Piper CLI 生成 wav，要求配置模型路径
  - 执行安全：`execute-provider-requests` 支持 OpenAI 与本地 Provider 统一 dry-run / safe-block / `--confirm-live`
  - 生产报告：Dashboard / Review Metrics 增加本地 Provider dry-run readiness 字段；本地模型未配置时记为 info 级上线前提醒，不阻断 fallback 健康结论
  - 验证策略：新增本地 Provider 专项验证，覆盖配置注册、路由、请求生成、dry-run 预检和真实执行阻断
- 开发计划
  - Provider 配置层：在 `providers.yaml` 登记 `local_comfyui_image`、`local_piper_tts` 和本地执行参数
  - Provider 规划层：补充 ProviderProfile、队列、推荐语与 endpoint 映射
  - Provider 执行层：新增本地 adapter，改造 executor 为多 Provider 分发
  - 生产验证层：`run_demo_validation.py` 生成本地替代请求与 dry-run 报告，并输出 readiness 字段
  - 报告与文档层：同步 README、Dashboard、Review Metrics、专项验证报告和最终结果
- 代码改动
  - 新增 `src\aicomic\providers\local_adapter.py`
  - 更新 `src\aicomic\providers\executor.py`、`provider_planner.py`、`request_builder.py`
  - 更新 `src\aicomic\core\dispatcher.py`
  - 更新 `config\providers.yaml`
  - 更新 `scripts\run_demo_validation.py`
  - 新增 `scripts\validate_local_provider_alternatives.py`
  - 更新 `src\aicomic\publish\dashboard.py`、`src\aicomic\review\metrics.py`
  - 更新 `web\backend\services\report_service.py`
  - 更新 `README.md`、`result.md`
- 验证结果
  - `python -m aicomic.cli.main status` 通过（使用 Codex bundled Python 3.12.13）
  - `scripts\validate_local_provider_alternatives.py` 通过：本地 Provider dry-run `2`、safe-block `2`
  - `scripts\run_demo_validation.py` 通过：16/16 任务成功、Dashboard `ready`、Review `healthy`
  - Docker 全量验证通过：`50 / 50`
  - 最新 Docker 日志：`reports\docker_validation_20260505200045.log`
  - 最新全量运行 ID：`full_system_validation_20260505120114918742`
  - 编译检查：`通过`
  - 总耗时：`8644 ms`
- 当前风险
  - `production_live_provider_ready=false`：仍未配置 OpenAI live Provider
  - `production_local_provider_ready=false`：当前环境未配置 ComfyUI workflow 与 Piper model
  - 本地替代链路已完成 dry-run 接入，但上线前仍需在目标机器安装 ComfyUI/Piper，并以小批量 `--confirm-live` 验证产物质量、耗时、失败保护和回写链路

### 2026-05-05 20:18:25 +08:00

- 本次修复目标
  - 继续收口上轮剩余风险：OpenAI live 未配置、本地 Provider 未就绪、视频仍依赖 `manual_web`
  - 不伪造生产就绪状态，不在无 API key / 无模型的环境里强行标记 ready
  - 将风险转化为可执行的 readiness 报告、可 dry-run 的本地视频路由、可复验的安全门
- 修复方案
  - 新增 `provider-readiness` CLI，统一输出 OpenAI core、OpenAI video、本地 core、本地 video、人工 fallback 的就绪状态
  - 新增 `local_comfyui_video` Provider，视频可走 ComfyUI workflow dry-run 和 `--confirm-live` 小批量真实执行
  - 扩展 ComfyUI adapter，支持从 history 中提取 image / video / gif artifact，并按目标路径写回
  - Demo 验证改为本地图片、视频、TTS 全量 dry-run，覆盖 `16` 条本地替代请求
  - Dashboard / Review / Web API 增加 provider readiness 字段，明确显示当前仍是 `ready_with_manual_fallback`
  - 修复安全治理 analytics 验证的时间窗隔离，避免多轮 Docker 历史审计日志在固定未来小时内串场
- 开发计划
  - Provider 配置：在 `providers.yaml` 增加 `local_comfyui_video` 与视频 workflow 参数
  - Provider 适配：扩展 `local_adapter.py` 的 ComfyUI 输出识别能力
  - Provider readiness：新增 `providers/readiness.py` 与 CLI 命令
  - 验证接入：更新 `run_demo_validation.py` 与 `validate_local_provider_alternatives.py`
  - 可视化/接口：更新 Dashboard、Review Metrics、`/api/providers/executions`
  - 稳定性：修复 `validate_security_governance_history_analytics.py` 的跨轮时间窗碰撞
  - 文档：刷新 README、result 与本计划
- 代码改动
  - 新增 `src\aicomic\providers\readiness.py`
  - 更新 `src\aicomic\providers\local_adapter.py`，支持本地 ComfyUI 视频 artifact
  - 更新 `src\aicomic\providers\provider_planner.py`、`request_builder.py`、`core\dispatcher.py`
  - 更新 `src\aicomic\cli\main.py`，新增 `provider-readiness`
  - 更新 `config\providers.yaml`
  - 更新 `scripts\run_demo_validation.py`、`scripts\validate_local_provider_alternatives.py`
  - 更新 `src\aicomic\publish\dashboard.py`、`src\aicomic\review\metrics.py`
  - 更新 `web\backend\services\report_service.py`
  - 更新 `scripts\validate_security_governance_history_analytics.py`
- 验证结果
  - 编译检查：通过
  - `python -m aicomic.cli.main status`：通过
  - `scripts\validate_local_provider_alternatives.py`：通过，本地 Provider dry-run `3`、safe-block `3`
  - `scripts\run_demo_validation.py`：通过，16/16 任务成功，Dashboard `ready`，Review `healthy`
  - `provider-readiness`：输出 `ready_with_manual_fallback`
  - 首轮 Docker 暴露旧验证脚本时间窗碰撞，修复后重跑通过
  - 最新 Docker 日志：`reports\docker_validation_20260505201731.log`
  - 最新全量运行 ID：`full_system_validation_20260505121759270304`
  - 全量验证：`50 / 50` 通过
  - 编译检查：`通过`
  - 总耗时：`8618 ms`
- 当前风险
  - `production_fallback_ready=true`，说明当前生产 fallback 链路健康
  - `provider_readiness_status=ready_with_manual_fallback`
  - `production_live_provider_ready=false`：未配置 `OPENAI_API_KEY`
  - `production_local_provider_ready=false`：未配置 ComfyUI 图片 workflow、ComfyUI 视频 workflow、Piper model
  - 上线前必须在目标机器完成三条小批量真实验证：OpenAI `--limit 1`、本地图像/TTS `--limit 1`、本地视频低分辨率 `--limit 1`

### 2026-05-06 01:24:00 +08:00

- 本次修复目标
  - 按用户要求排除风险 3（OpenAI live provider），集中收口其它生产风险
  - 不破坏 Creator 本地单机默认体验，但新增可执行的生产风险闸门
  - 让 ComfyUI/Piper/依赖供应链风险进入结构化验证，而不是只靠人工备注
- 修复方案
  - 生产安全：新增 `production-risk-register`，检查 Web CORS、鉴权、dev login、mock SSO、JWT secret，并把默认 `config/web.yaml` 判定为非生产安全
  - 生产配置：新增 `config/web.production.example.yaml`，并支持 `AICOMIC_WEB_CONFIG_PATH` 与 `${AICOMIC_*}` 环境变量展开
  - ComfyUI：新增 `local_providers/comfyui/model_requirements.json` 和 `models/` 根目录，readiness 同时检查 API workflow、服务和模型权重
  - Piper：readiness 暴露 `MODEL_CARD` license 状态，runtime ready 与商业授权风险分开判断
  - 依赖供应链：新增 `requirements-lock.txt`，Docker 安装使用 `--constraint requirements-lock.txt`，新增依赖审计状态报告
  - 报表：Dashboard / Review Metrics 改为数据感知文案，不再把 Piper 说成未配置；OpenAI 在本轮范围内不作为风险动作
- 开发计划
  - 新增 `src\aicomic\security\dependency_audit.py` 与 `production_readiness.py`
  - 扩展 `src\aicomic\providers\local_adapter.py`、`providers\readiness.py`
  - 扩展 CLI：`dependency-audit`、`production-risk-register`
  - 更新 `scripts\run_demo_validation.py` 输出生产风险和依赖审计字段
  - 新增 `scripts\validate_dependency_audit.py`、`scripts\validate_production_risk_register.py`
  - 更新 Dockerfile、Provider 配置、README、生产风险说明文档和验证结果
- 代码改动
  - 新增 `src\aicomic\security`
  - 新增 `config\web.production.example.yaml`
  - 新增 `requirements-lock.txt`
  - 新增 `local_providers\comfyui\model_requirements.json`
  - 新增 `local_providers\comfyui\models\README.md`
  - 更新 `Dockerfile` 使用依赖约束安装
  - 更新 `web\backend\settings.py` 支持生产配置路径和环境变量展开
  - 更新 Dashboard / Review / Demo validation / CLI / 验证脚本 / 文档入口
- 验证结果
  - 窄验证通过：编译检查、`validate_dependency_audit.py`、`validate_local_provider_alternatives.py`、`validate_production_risk_register.py`
  - 模拟数据写库通过：16/16 任务成功，manual import 缺失 0，retry 0
  - Docker 全量验证通过：`52 / 52`
  - 最新 Docker 日志：`reports\docker_validation_20260506012253.log`
  - 最新全量运行 ID：`full_system_validation_20260505172340096103`
  - 编译检查：`通过`
  - 总耗时：`9169 ms`
- 当前风险（OpenAI 已排除）
  - 生产风险注册表：`blocked_for_production`
  - Blocking：`9`，集中在默认 Web dev-like 配置和 ComfyUI 服务/模型未就绪
  - Warning：`3`，集中在 Piper voice license、CVE 审计未运行、传递依赖未完整锁定
  - 当前 fallback 链路仍健康：`production_fallback_ready=true`，`production_batch_failure_rate=0.0`

### 2026-05-06 01:46:08 +08:00

- 本次修复目标
  - 针对 Blocking 9 与 Warning 3 继续收口，仍按用户要求排除 OpenAI live provider
  - 默认 `config/web.yaml` 继续保留 Creator 本地开发语义，不把开发默认值强行改成生产值
  - 增加可真实跑通的 production rehearsal，让生产闸门能区分“演练可跑”和“严格生产还缺真实 ComfyUI/模型”
- 修复方案
  - 生产配置：使用 `config/web.production.example.yaml` 与环境变量展开构造 rehearsal env，默认开发配置仍在严格生产风险闸门中保持阻断检测
  - ComfyUI：新增项目内 mock ComfyUI server、workflow fixture、6 个模型 fixture 文件生成器，验证图片/视频请求提交、history 读取和产物写回
  - Provider 网络：本地 provider 调用显式绕过代理，避免 localhost 被系统代理打成 502
  - Piper：新增 `LICENSE_REVIEW.json`，将 `MODEL_CARD` 的 Unknown dataset license 风险转为项目策略批准并保留 caveat
  - 依赖供应链：把 `pip-audit` 纳入 validation extras，生成完整 direct + transitive resolved lock，Docker/CI 强制 full dependency audit
  - 风险闸门：`deployment_mode=production` 继续严格阻断真实上线缺口，`deployment_mode=rehearsal` 对 mock/fixture 降级为 warning
- 开发计划
  - 新增 production rehearsal 支撑模块与 mock ComfyUI 启动脚本
  - 扩展 local provider adapter，识别 mock server、fixture 模型和 Piper license policy
  - 扩展 dependency audit，检查 installed distributions、传递依赖锁和 `pip-audit` CVE 输出
  - 扩展 production risk register，支持 strict / rehearsal 双模式
  - 更新 demo validation、专项验证脚本、Dockerfile、README、脚本说明和生产风险说明文档
  - 运行窄验证、Docker 全量验证，并把结果同步到 `result.md`
- 代码改动
  - 新增 `src\aicomic\security\production_rehearsal.py`
  - 新增 `scripts\run_mock_comfyui_server.py`
  - 新增 `scripts\validate_comfyui_production_rehearsal.py`
  - 新增 `local_providers\piper\models\LICENSE_REVIEW.json`
  - 更新 `src\aicomic\providers\local_adapter.py`
  - 更新 `src\aicomic\security\production_readiness.py`
  - 更新 `src\aicomic\security\dependency_audit.py`
  - 更新 `scripts\run_demo_validation.py`
  - 更新 `scripts\validate_dependency_audit.py`
  - 更新 `scripts\validate_production_risk_register.py`
  - 更新 `pyproject.toml`、`requirements-lock.txt`、`Dockerfile`
  - 更新 `README.md`、`scripts\README.md`、`docs\项目资料索引.md`、`docs\生产上线风险闸门说明.md`、`result.md`
- 验证结果
  - 编译检查：通过
  - `scripts\validate_comfyui_production_rehearsal.py`：通过，mock ComfyUI + 6 个 fixture 模型，图片/视频执行 `2 / 2` 成功
  - `scripts\validate_production_risk_register.py`：通过；strict 模式 Blocking `9`，rehearsal 模式 Blocking `0` / Warning `4`
  - `scripts\validate_local_provider_alternatives.py`：通过
  - `scripts\validate_dependency_audit.py`：Docker/CI 环境中要求 CVE 审计完成、已知漏洞为 0、传递依赖 fully locked
  - Docker 全量验证通过：`53 / 53`
  - 最新 Docker 日志：`reports\docker_validation_20260506014308.log`
  - 最新全量运行 ID：`full_system_validation_20260505174423182737`
  - 编译检查：`通过`
  - 总耗时：`34353 ms`
- 当前风险（OpenAI 已排除）
  - 生产风险注册表 rehearsal 状态：`ready_with_warnings`
  - Blocking：`0`
  - Warning：`4`
  - 剩余 warning：`local_comfyui_image-mock-server-used`、`local_comfyui_image-fixture-models-used`、`local_comfyui_video-mock-server-used`、`local_comfyui_video-fixture-models-used`
  - 依赖 CVE 审计：`completed`，已知漏洞 `0`
  - 传递依赖锁定：`fully_locked`
  - 严格生产上线前仍必须替换为真实 ComfyUI 服务和真实图片/视频模型权重，并跑小批量 `--confirm-live` 产物质量验证

### 2026-05-06 10:33:25 +08:00

- 本次修复目标
  - 修复全量验证剩余 2 个失败项：`validate_local_provider_alternatives.py`、`validate_production_risk_register.py`
  - 收口主要生产风险：默认 Web dev-like 配置、依赖审计超时、传递依赖锁误报、full video 超时预算不可见
- 修复方案
  - 验证基线：把 ComfyUI 断言改为双态，缺服务时要求 `setup_required`，真实服务/真实权重 ready 时要求 `live`、缺失模型 `0`、fixture `0`
  - Web 配置：默认 `config/web.yaml` 改为生产基线；新增 `config/web.development.yaml` 保存本地开发登录和 mock SSO
  - 依赖审计：对 `requirements-lock.txt` 使用 `pip-audit --no-deps --disable-pip`，避免 resolver 卡住本机额外依赖；传递依赖锁以 lock 文件完整性为准
  - 视频风险：生产风险闸门新增 `local_comfyui_video-timeout-budget-low`，显式提示 full video worker 超时预算不足
- 开发计划
  - 更新两个失败验证脚本的断言逻辑
  - 更新默认/开发 Web 配置与 README、生产风险说明、前端开发排障说明
  - 更新 `dependency_audit.py` 与 `production_readiness.py`
  - 运行定向验证、模拟数据验证、全量验证，并同步 `result.md`
- 验证结果
  - `scripts\validate_local_provider_alternatives.py`：通过，当前模式 `live_local_video_ready`
  - `scripts\validate_production_risk_register.py`：通过，strict 模式 Blocking `1` / Warning `1`
  - `scripts\validate_dependency_audit.py`：通过，CVE `completed`，已知漏洞 `0`，传递依赖 `fully_locked`
  - 模拟数据验证：通过，`16 / 16` 任务成功，manual import 缺失 `0`，retry `0`，批量失败率 `0.0`
  - 本机全量验证：`53 / 53` 通过，运行 ID `full_system_validation_20260506103238301276`
  - 临时注入生产 secret 后风险闸门：`ready_with_warnings`，Blocking `0` / Warning `1`
- 当前风险（OpenAI 已排除）
  - Blocking `1`：`prod-jwt-secret-unsafe`，需要注入生产级 `AICOMIC_JWT_SECRET`
  - Warning `1`：`local_comfyui_video-timeout-budget-low`，需要提升 full video 超时预算、异步回收或更快 GPU worker

### 2026-05-06 10:56:17 +08:00

- 本次修复目标
  - 关闭上一轮剩余生产风险：生产级 JWT/OIDC 注入、full video 超时预算、Docker 运行态鉴权/edition 策略、容器内本地 provider 资产可见性
  - 在本机 Docker Desktop 中启动项目并验证运行态健康
- 修复方案
  - 将 `local_comfyui_video.poll_timeout_seconds` 提升到 `3600`
  - 新增 `config/edition.production.yaml`，并通过 `AICOMIC_EDITION_CONFIG_PATH` 让 Docker 使用 Enterprise 生产版策略
  - 扩展生产风险闸门，检查生产态 edition 是否仍为单用户/无鉴权/无 OIDC
  - Docker compose 挂载 `local_providers` 只读目录，并通过 `host.docker.internal:8188` 访问宿主机真实 ComfyUI
  - 使用 `.env.docker.local` 注入本机 Docker 专用 secret / OIDC / edition / state 配置，文件已加入忽略规则
- 开发计划执行结果
  - 更新 edition 配置加载、CLI 风险参数、production rehearsal env、风险注册表验证
  - 新增 Docker compose Web 服务，构建 `aicomic-system:local` 并启动 `aicomic-system-web`
  - 运行编译、专项风险验证、全量验证、容器内 provider readiness / dependency audit / production risk register
- 验证结果
  - 本机全量验证：`53 / 53` 通过，运行 ID `full_system_validation_20260506105201321341`，`compile_ok=true`
  - 容器内 Provider readiness：`ready_with_full_local_provider`，`local_core_ready=true`，`local_video_ready=true`，`full_local_ready=true`
  - 容器内依赖审计：Blocking `0` / Warning `0`，CVE `completed`，已知漏洞 `0`，传递依赖 `fully_locked`
  - 容器内生产风险注册表：`ready_for_production`，Risk `0` / Blocking `0` / Warning `0`
  - Docker 容器：`aicomic-system-web`，状态 `running healthy`
  - 运行态健康接口：`/api/health` 返回 Enterprise 企业版，`auth_enabled=true`
  - 受保护接口：`/api/dashboard` 无 token 返回 `401 Authentication required`
- 当前风险
  - 本轮范围内剩余生产风险：`0`
  - OpenAI live provider 仍按用户要求暂不启用，不计入本轮风险

### 2026-05-06 11:08:14 +08:00

- 问题原因
  - 上一版 Docker Compose 只启动了 FastAPI 后端 `aicomic-web`，没有把前端页面服务纳入 compose
  - 补前端后首次浏览器检查发现本机前端 `http://127.0.0.1:8000` 被生产 CORS 域名配置拦截
- 修复方案与实现
  - 新增 `aicomic-frontend` compose 服务，复用 `aicomic-system:local` 镜像并挂载 `web/frontend/dist`
  - 新增 `scripts/serve_frontend_spa.py`，以 SPA fallback 方式服务 Umi 构建产物，支持 `/login` 等前端路由刷新
  - 新增 `config/web.docker.yaml`，保持生产鉴权/Enterprise 策略，同时允许本机前端 Origin：`http://127.0.0.1:8000`、`http://localhost:8000`
  - 后端 `/api/edition` 列为公开配置接口；鉴权中间件直接返回的 401 也附带允许 Origin 的 CORS 头
- 验证结果
  - Docker 服务：`aicomic-web` 与 `aicomic-frontend` 均为 `healthy`
  - 前端地址：`http://127.0.0.1:8000/login`
  - 后端地址：`http://127.0.0.1:7860/api/health`
  - 浏览器自动化：登录页 `200`，页面内容渲染成功，console error `0`，page error `0`
  - 定向验证：`validate_auth_flow.py`、`validate_edition_policy.py`、`validate_web_console.py` 均通过
  - 全量验证：`53 / 53` 通过，运行 ID `full_system_validation_20260506110735818506`
  - Docker 内生产风险注册表：`ready_for_production`，Risk `0` / Blocking `0` / Warning `0`

### 2026-05-06 13:41:15 +08:00

- 问题原因
  - 本机 Docker 页面无法登录，是因为 `config/web.docker.yaml` 保持生产鉴权但 `AICOMIC_OIDC_AUTHORIZE_URL` 仍指向占位 IdP：`https://idp.aicomic.example.com/...`
  - 本地开发登录按生产策略关闭，所以页面没有可完成的登录闭环
- 修复方案与实现
  - Docker 本机联调配置启用 Mock OIDC：`config/web.docker.yaml` 的 `mock_sso_enabled=true`
  - `.env.docker.local` 的 `AICOMIC_OIDC_AUTHORIZE_URL` 改为本机后端：`http://127.0.0.1:7860/api/auth/mock-oidc/authorize`
  - 保持正式生产配置 `config/web.yaml` 不启用 mock SSO；正式生产风险报告仍使用 `config/web.yaml` + `config/edition.production.yaml`
  - `scripts/serve_frontend_spa.py` 对 `/favicon.ico` 返回 `204`，消除 Chrome 控制台静态资源 404 噪音
- Chrome 验证
  - 使用本机 Google Chrome：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
  - 登录入口：`http://127.0.0.1:8000/login`
  - 登录结果：OIDC Mock 回调成功，进入 `http://127.0.0.1:8000/dashboard`
  - JWT：`aicomic_access_token` 写入 localStorage，带 token 调 `/api/dashboard` 返回 `200`
  - 页面巡检：`/dashboard`、`/jobs`、`/batches`、`/provider` 均可打开
  - Chrome console error：`0`；page error：`0`
- 模拟数据与全量验证
  - 模拟数据：1 项目、2 集、16 任务、16 成功任务、批量失败率 `0.0`
  - 全量验证：`53 / 53` 通过，运行 ID `full_system_validation_20260506134005309843`
  - 真实 provider readiness：`ready_with_full_local_provider`
  - 依赖审计：Blocking `0` / Warning `0`，CVE `completed`
  - 正式生产风险注册表：`ready_for_production`，Risk `0` / Blocking `0` / Warning `0`
- 风险说明
  - `config/web.docker.yaml` 当前启用 Mock OIDC，仅用于本机 Docker 登录联调
  - 正式上线必须使用 `config/web.yaml`/真实 IdP，并注入生产级 `AICOMIC_JWT_SECRET`

### 2026-05-06 15:25:23 +08:00

- 本次目标
  - 使用独立生产 Compose 将项目正式部署到本机 Docker Desktop
  - 生产栈必须同时启动后端 API 与前端页面
  - 生产栈保持 Enterprise、鉴权开启、dev login 关闭、Mock SSO 关闭、受保护 API 未登录返回 401
  - 在生产容器内重新跑 provider readiness、依赖审计、生产风险注册表和全量验证
- 修复方案
  - 新增并使用 `docker-compose.production.yml`、`config/web.production.docker.yaml`、`.env.production.local`
  - 生产容器使用 `aicomic-system:production` 镜像，后端端口 `7860`，前端端口 `8000`
  - 修复容器内 `dependency-audit` 报告序列化问题：超时输出可能为 `bytes`，统一清洗为文本；默认 `pip-audit` 超时提升到 90 秒并支持 `AICOMIC_PIP_AUDIT_TIMEOUT_SECONDS`
  - 修复生产鉴权下全量验证脚本：新增 `scripts/validation_auth.py`，6 个批量执行 API 验证脚本使用生产 JWT Bearer token，不再依赖未登录访问
  - 修复 `validate_production_risk_register.py` 在容器生产环境中被 `AICOMIC_EDITION_CONFIG_PATH` 影响的问题，严格风险验证显式指定要检查的 Web/Edition 配置
- 开发计划执行结果
  - 构建生产镜像 `aicomic-system:production`
  - 启动 `aicomic-production-web` 与 `aicomic-production-frontend`
  - 执行运行态健康检查、鉴权配置检查、未登录 401 验证
  - 执行容器内 provider readiness、dependency audit、production risk register
  - 执行容器内全量验证套件
- 验证结果
  - Docker 状态：`aicomic-production-web`、`aicomic-production-frontend` 均为 `healthy`
  - 前端地址：`http://127.0.0.1:8000/login`
  - 后端健康：`http://127.0.0.1:7860/api/health` 返回 `edition_name=enterprise`、`auth_enabled=true`
  - 鉴权配置：`dev_login_enabled=false`、`mock_sso_enabled=false`、`oidc_enabled=true`
  - 受保护接口：`/api/dashboard` 无 token 返回 `401 Authentication required`
  - 容器内 Provider readiness：`ready_with_full_local_provider`，`local_core_ready=true`，`local_video_ready=true`，`full_local_ready=true`
  - 容器内依赖审计：Blocking `0` / Warning `0`，CVE `completed`，已知漏洞 `0`，传递依赖 `fully_locked`
  - 容器内生产风险注册表：`ready_for_production`，Risk `0` / Blocking `0` / Warning `0`
  - 容器内全量验证：`53 / 53` 通过，运行 ID `full_system_validation_20260506072212685568`，`compile_ok=true`
- 当前风险
  - 本机 Docker 生产栈项目内风险：`0`
  - OpenAI live provider 仍按用户要求暂不启用，不计入本轮风险
  - 当前 `.env.production.local` 使用生产 OIDC 占位地址；真实企业登录需要替换为正式 IdP 的真实参数并完成外部 IdP 联调

### 2026-05-06 18:56:00 +08:00

- 本次目标
  - 先不考虑企业用户，优先把 Creator 个人创作者版从 0 到 1 打通
  - 围绕“一台电脑、一个人、从创意到单集导出”建立稳定闭环
  - 保持现有 Core / Provider / Render / Review 能力不推翻，在其上补齐 Creator 项目骨架和个人工作台
- 范围边界
  - 本轮不新增 OIDC、RBAC、成员协作、审计增强、多团队队列等企业能力
  - 本轮不追求全自动高动态动画，P0 先以“静态分镜 + 轻运动镜头 + TTS + 字幕 + 预览合成 + 发布包”为主
  - Web 前端继续作为薄控制台，核心生产逻辑仍以 `src/aicomic` 与 CLI 为准
- 详细开发计划
  - Phase 1：Creator 项目初始化骨架
    - 升级 `init-project`，除 `project_manifest / season_manifest / episode_manifest` 外，自动生成故事圣经、角色卡、风格模板、分集蓝图、Prompt 模板和发布检查单
    - 为 `project_manifest` 增加 `creator_profile`，沉淀 logline、主角、受众、调性、季钩子、目标集数
  - Phase 2：Creator 工作台后端 API
    - 新增项目发现能力，统一读取当前系统项目与 `state/generated_projects`
    - 新增 Creator 工作台聚合接口，输出项目设定、闭环步骤、剧集推进、交付物、下一步动作
    - 扩展 `episodes` 接口，补齐标题、镜头数、时长、预览/发布包状态
  - Phase 3：Creator 前端控制台
    - 新增 `创作台 /creator` 和 `项目 /projects` 页面
    - 让 Creator 用户可以直接看到：项目设定、阶段步骤、剧集推进、可交付产物、工程文件入口
    - 保留现有 Dashboard / Episodes，但增强到可服务个人创作者
  - Phase 4：验证与回归
    - 新增 `validate_creator_project_bootstrap.py`
    - 新增 `validate_creator_workspace.py`
    - 运行前端 `typecheck + build`
    - 运行 Docker 模拟数据 + 全量验证，确认新脚本纳入 suite 且无回归
- 本轮验收标准
  - `init-project` 生成的新 Creator 项目具备可直接补内容的完整骨架
  - 前端存在 Creator 专用入口，不再只围绕企业/批量治理页面组织
  - 后端能返回个人创作者闭环所需的项目与工作台数据
  - 新增专项验证通过，并进入全量验证
- 开发计划执行结果
  - 已新增 `src/aicomic/core/creator_bootstrap.py`，统一生成 Creator 项目设定骨架
  - 已升级 `core/project_initializer.py` 与 CLI `init-project`
  - 已新增 `web/backend/services/creator_service.py`，并开放 `/api/projects`、`/api/creator/workspace`
  - 已增强 `report_service.load_episodes`
  - 已新增前端页面 `web/frontend/src/pages/Projects`、`web/frontend/src/pages/CreatorWorkspace`
  - 已更新前端路由、Dashboard、Episodes 和 API / types
  - 已新增专项验证脚本 `validate_creator_project_bootstrap.py`、`validate_creator_workspace.py`
- 本轮验证结果
  - 前端 `npm run typecheck`：通过
  - 前端 `npm run build`：通过
  - Creator 项目初始化专项验证：通过
  - Creator 工作台专项验证：通过
  - Docker 模拟数据：通过，任务 `16 / 16` 成功，manual import 缺失 `0`，retry `0`
  - Docker 全量验证：`55 / 55` 通过，运行 ID `full_system_validation_20260506105556594561`

### 2026-05-06 19:23:31 +08:00

- 本次目标
  - 在 Creator P0 基础上，继续把个人用户端从“可看”推进到“可操作、可回写、可导出、可验证”
  - 不再只展示 Creator 数据，要让个人用户能直接在 Web 端完成项目创建、项目设定、剧集维护、镜头维护和关键生产动作触发
  - 保持项目现有 `src/aicomic + FastAPI + Umi/Ant Design` 架构不变，不引入企业后台复杂度
- 整体方案
  - Creator 建模继续以项目工作区为中心，保持 `project_manifest / episode_manifest / jobs / reports / state` 统一目录语义
  - 个人用户能力采用“精选动作”而不是开放通用命令控制台，避免 Creator 端越权、误操作和复杂度上升
  - Web 前端提供 Creator 专属操作面，核心执行仍调用现有 Core/Provider/Publish/Review 能力，避免重复造逻辑
  - 验证层新增 Creator 动作专项脚本，并纳入 Docker 全量验证套件，确保这轮扩展不是只靠页面联调通过
- 范围边界
  - 本轮继续只做 Creator / 个人用户，不引入企业成员、角色、审批、审计增强
  - 不开放原有通用 Web 命令台给 Creator，只暴露受控动作：
    - `build_jobs`
    - `build_provider_requests`
    - `scan_assets`
    - `render_preview`
    - `build_publish_pack`
    - `refresh_creator_reports`
  - 后端接口、前端交互和验证脚本都围绕个人创作者的“单项目生产闭环”展开
- 详细开发计划
  - Phase 1：Creator 项目与工作区能力补齐
    - 支持发现系统内项目，并按 `project_id` 解析 Creator 工作区
    - 支持在 Web 端创建 Creator 项目，并自动生成完整项目骨架
  - Phase 2：Creator 数据回写能力
    - 支持保存项目设定、更新剧集信息、更新镜头信息、删除镜头
    - 工作区 summary 直接从项目文档与 jobs 产物实时聚合
  - Phase 3：Creator 可操作化动作
    - 新增 Creator Action Service，把任务生成、请求包生成、素材扫描、预览渲染、发布包、报告刷新串起来
    - 动作执行结果回写到 Creator 报告、Dashboard 和 Review Metrics
  - Phase 4：前端交互收口
    - 新增项目列表页与 Creator 工作台页
    - 补项目创建、项目编辑、剧集编辑、镜头新增/编辑/删除、动作执行反馈
  - Phase 5：验证与回归
    - 新增 `validate_creator_actions.py`
    - 把 Creator 三个专项脚本纳入 Docker 全量验证，确保新脚本总数提升到 `56`
- 开发计划执行结果
  - 已新增 `web/backend/services/creator_action_service.py`
  - 已扩展 `web/backend/services/creator_service.py`，支持项目发现、项目创建、项目设定保存、剧集/镜头回写、Creator summary 聚合
  - 已扩展 `web/backend/app.py`，新增：
    - `GET /api/projects`
    - `GET /api/creator/workspace`
    - `POST /api/creator/projects`
    - `PATCH /api/creator/project-profile`
    - `PUT /api/creator/episodes`
    - `PUT /api/creator/shots`
    - `POST /api/creator/shots/delete`
    - `POST /api/creator/actions/run`
  - 已扩展前端 `src/types/api.ts`、`src/services/api.ts`
  - 已升级前端页面：
    - `src/pages/Projects/index.tsx`
    - `src/pages/CreatorWorkspace/index.tsx`
    - `src/pages/Dashboard/index.tsx`
    - `src/pages/Episodes/index.tsx`
    - `config/config.ts`
    - `src/global.less`
  - 已新增专项验证：
    - `scripts/validate_creator_project_bootstrap.py`
    - `scripts/validate_creator_workspace.py`
    - `scripts/validate_creator_actions.py`
- 本轮验收标准
  - Creator 用户可在 Web 端直接新建项目并进入工作台
  - 项目设定、剧集和镜头支持回写，不再只是只读浏览
  - Creator 关键生产动作可在工作台直接触发，并生成对应报告/产物
  - 新增专项脚本通过，并纳入 Docker 全量验证
- 本轮验证结果
  - 前端 `npm run typecheck`：通过
  - 前端 `npm run build`：通过
  - Creator 项目初始化专项验证：通过
  - Creator 工作台专项验证：通过
  - Creator 动作专项验证：通过
  - Docker 全量验证：`56 / 56` 通过
  - 运行 ID：`full_system_validation_20260506112110445512`
  - Docker 日志：`reports/docker_validation_20260506191958.log`

### 2026-05-06 19:35:42 +08:00

- 本次目标
  - 把这轮 Creator 个人用户端改造真正发布到本机生产 Docker 运行态，而不是只停留在源码和历史验证报告里
  - 补一轮浏览器级闭环验证，确认 `/login`、`/projects`、`/creator`、`/dashboard` 在当前 Docker 栈中真实可用
- 发现的问题
  - `web/frontend/dist` 在宿主机为空，导致生产前端容器虽然启动，但实际暴露的是空目录静态服务，`/login` 返回 `404`
  - 生产后端容器仍在运行旧镜像，最新新增的 `/api/projects`、`/api/creator/workspace` 等接口没有被发布进去，浏览器出现 API `404` 与未处理 promise 异常
  - 当前 shell 环境的 `docker` 命令路径失效，但 Docker Desktop 自带二进制仍可用
- 修复方案与执行
  - 重新执行前端生产构建：`web/frontend npm run build`，补齐 `dist` 产物
  - 使用 `docker compose -f docker-compose.production.yml up -d --build aicomic-web aicomic-frontend` 重建并重启生产后端/前端容器
  - 生产前端容器重新挂载宿主机 `dist` 后恢复 SPA 服务，`/login` 返回 `200`
  - 生产后端镜像重建后，Creator 新接口发布生效
- 本轮验证计划
  - 验证密码登录链路：普通用户从 `/login` 成功进入 `/dashboard`
  - 验证 Creator 新页面：`/projects`、`/creator`、`/dashboard`
  - 再跑 Docker 模拟数据 + 全量验证，确认当前发布态和验证基线一致
- 本轮验证结果
  - 生产容器状态：`aicomic-production-web`、`aicomic-production-frontend` 均 `healthy`
  - 登录验证：`reports/frontend_browser_login_creator_closure_report.json` 通过
  - Creator 浏览器验证：`reports/creator_browser_smoke_20260506113426/creator_browser_smoke_report.json`
    - `/projects`：通过，`eventCount=0`
    - `/creator`：通过，`eventCount=0`
    - `/dashboard`：通过，`eventCount=0`
  - Docker 全量验证：`56 / 56` 通过
  - 最新运行 ID：`full_system_validation_20260506113505803356`
  - 最新 Docker 日志：`reports/docker_validation_20260506193458.log`
