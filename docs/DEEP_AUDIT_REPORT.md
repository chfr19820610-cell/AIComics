# AIComics v3.0 深度审计报告

**审计日期**: 2026-09-10  
**审计范围**: 全代码库 + 测试 + 配置 + CLI + 模块依赖  
**审计目标**: 发现 v3.0 架构中的断链、孤儿代码、测试盲区、配置风险

---

## 执行摘要

| 维度 | 状态 | 发现数 | 严重度 |
|------|------|--------|--------|
| 模块导入 | ✅ 通过 | 0 错误 | - |
| 类型注解 | ✅ 98% 覆盖率 | 18 函数无返回注解 | 🟢 低 |
| TODO/FIXME 残留 | ✅ 0 个 | 0 | - |
| API Key 泄露 | ✅ 无硬编码 | 0 | - |
| **孤儿函数** | 🔴 **167 个** | 167 定义但从未调用 | 🟡 中 |
| **测试盲区** | 🔴 **109/125 模块** | 87% 模块无直接测试导入 | 🟡 中 |
| CLI 命令注册 | ✅ 60 个命令 | 全部有 handler | - |
| 三线渲染架构 | ✅ 正确集成 | season_renderer 调用三条 pipeline | - |
| Video Router | ✅ 正确集成 | request_builder 调用 | - |
| Publish Pack | ✅ 正确集成 | pipeline_coordinator 调用 | - |

---

## 🔴 关键发现

### 1. 孤儿函数 167 个 (按模块分组)

**定义**: 在代码中定义但从未被任何其他模块调用的 public 函数

| 模块 | 孤儿数 | 主要函数 | 建议 |
|------|--------|----------|------|
| `core/` | 61 | `advance`, `begin_stage`, `build_romance_*`, `build_season_*`, `checkpoint_summary`, `connect_database`, `initialize_schema`, `insert_batch*`, `resume_*`, `tag_shot_version`, `rollback_to_version` 等 | 大部分是 database/shot_versioning/romance_pipeline/novel_pipeline 的遗留代码，建议删除或接入 CLI |
| `characters/` | 40 | `analyze_episode_manifest`, `analyze_shot`, `auto_create_characters`, `auto_register`, `batch_update_tags` 等 | character_sheet_builder/character_workshop 未接入主线，需确认是否保留 |
| `providers/` | 25 | `apply_cloud_mode`, `base_url`, `command`, `create_key`, `download` 等 | 部分来自 _vidgen_mixin，需确认是否废弃 |
| `video_synthesis/` | 12 | `add_term`, `apply_transitions`, `batch_synthesize`, `build_multilang_episode`, `burn_subtitles` 等 | video_synthesis 模块未接入 v3.0 管线 |
| `security/` | 8 | `build_rehearsal_environment`, `collect_installed_distribution_versions`, `do_GET`, `do_POST`, `log_message` 等 | production_rehearsal 未接入 CLI |
| `publish/` | 8 | `create_analytics_record`, `get_expired_platforms`, `list_pending_tasks`, `mark_task_done`, `publish` 等 | publish dashboard 功能未接入 |
| `image_pipeline/` | 4 | `build_full_pipeline_workflow`, `build_readiness`, `check_available`, `get_download_instructions` | image_consistency_cmd 未调用 |
| `image_consistency/` | 4 | `check_episode_frames`, `get_master_by_character`, `update_master_dna`, `validate_locked_workflow` | triple_lock 未完整接入 |
| `qc/` | 2 | `build_horror_regeneration_queue`, `write_horror_regeneration_queue` | horror pipeline 遗留 |
| `render/` | 2 | `get_capabilities`, `route_batch` | mode_router 内部函数，非真孤儿 |
| `cli/` | 1 | `handle_render` | 别名导入，非真孤儿 |

**建议行动**:
1. **高优先级**: 删除 `core/database.py` 中 16 个未使用函数 (整个模块未被 import)
2. **高优先级**: 删除 `core/shot_versioning.py` 中 11 个未使用函数 (整个模块未被 import)
3. **中优先级**: 删除 `core/romance_pipeline.py` (仅 CLI 调用 `import_novel_file`)
4. **中优先级**: 清理 `core/novel_pipeline.py` 中 7 个未使用函数
5. **低优先级**: 清理 `video_synthesis/` 中 12 个函数 (整个模块未被 v3.0 使用)

---

### 2. 测试覆盖盲区

**109/125 源模块 (87%) 无直接测试导入**

这意味着这些模块没有对应的 `test_*.py` 文件直接 import 并测试它们的函数。

**高风险未测试模块**:
- `core/pipeline_coordinator.py` - SOP 管线核心
- `core/project_initializer.py` - 项目初始化
- `core/template_engine.py` - 模板引擎
- `core/creator_bootstrap.py` - 创作者引导
- `core/dispatcher.py` - 任务分发
- `core/episode_lifecycle.py` - 状态机
- `core/keyframe_engine.py` - 关键帧生成
- `core/storyboard_grid.py` - 分镜网格
- `core/state_store.py` - 状态存储
- `core/resume.py` - 断点续跑
- `core/romance_pipeline.py` - 言情管线
- `core/novel_pipeline.py` - 小说管线
- `render/mode_router.py` - 三线渲染路由
- `render/preview_renderer.py` - 预览渲染
- `render/release_renderer.py` - 正式渲染
- `render/season_renderer.py` - 季渲染
- `providers/video_router.py` - 视频路由
- `providers/request_builder.py` - 请求构建
- `publish/publish_pack.py` - 发布包
- `publish/publish_scheduler.py` - 发布调度
- `qc/asset_scanner.py` - 资产扫描
- `qc/repair_advisor.py` - 修复建议
- `qc/season_scanner.py` - 季扫描
- `security/dependency_audit.py` - 依赖审计
- `security/production_readiness.py` - 生产就绪
- `batch/coordinator.py` - 批次协调
- `batch/preflight_gate.py` - 起飞检查
- `batch/retry_manager.py` - 重试管理
- `batch/reporter.py` - 批次报告
- `characters/*` - 角色系统全模块
- `image_consistency/*` - 角色一致性全模块
- `image_pipeline/*` - 图像管线全模块
- `video_synthesis/*` - 视频合成全模块

**建议行动**:
1. 为 `core/pipeline_coordinator.py` 编写集成测试 (已有部分测试，需补充)
2. 为 `render/` 模块编写渲染测试 (需 mock Blender/FFmpeg)
3. 为 `providers/` 模块编写 provider 测试 (需 mock API)
4. 为 `publish/` 模块编写发布测试 (需 mock 平台 API)
5. 为 `qc/` 模块编写质量检查测试

---

### 3. 架构断链检查

#### ✅ 已正确集成的模块

| 模块 | 调用方 | 状态 |
|------|--------|------|
| `render/mode_router.py` | `season_renderer.py` (line 9) | ✅ 正确 import 并使用 |
| `render/two_d/pipeline.py` | `season_renderer.py` (line 10) | ✅ 正确 import 并调用 |
| `render/two_half_d/pipeline.py` | `season_renderer.py` (line 11) | ✅ 正确 import 并调用 |
| `render/three_d/pipeline.py` | `season_renderer.py` (line 12) | ✅ 正确 import 并调用 |
| `providers/video_router.py` | `providers/request_builder.py` (line 16) | ✅ 正确 import 并调用 |
| `publish/publish_pack.py` | `pipeline_coordinator.py` (line 246) | ✅ 正确 import 并调用 |
| `security/dependency_audit.py` | `cli/main.py` (line 81), `production_readiness.py` | ✅ 正确 import 并调用 |
| `security/production_readiness.py` | `cli/main.py` (line 82) | ✅ 正确 import 并调用 |
| `qc/asset_scanner.py` | `cli/main.py` (line 68), `batch/coordinator.py` | ✅ 正确 import 并调用 |
| `utils/atomic_io.py` | 9 个核心模块 | ✅ 正确 import 并调用 |

#### 🔴 存在断链的模块

| 模块 | 问题 | 影响 |
|------|------|------|
| `core/database.py` | 16 个函数定义但全模块未被 import | 数据库初始化/批量插入功能未接入 |
| `core/shot_versioning.py` | 11 个函数定义但全模块未被 import | 分镜版本管理功能未接入 |
| `core/romance_pipeline.py` | 4 个函数定义但仅 CLI 调用 1 个 | 言情管线 90% 代码未使用 |
| `core/novel_pipeline.py` | 8 个函数定义但仅 CLI 调用 1 个 | 小说管线 87% 代码未使用 |
| `video_synthesis/*` | 12 个函数定义但全模块未被 import | 视频合成功能未接入 v3.0 |
| `characters/*` | 40 个孤儿函数 | 角色系统大部分功能未接入主线 |

---

### 4. CLI 命令完整性

**60 个 CLI 命令全部注册并有 handler** ✅

```
image-consistency, status, build-jobs, sync-states, dispatch-jobs,
advance-episode, scan-assets, render-preview, prepare-subtitles-audio,
horror-blueprint, build-horror-episode, list-templates, template-blueprint,
template-manifest, publish, check-publish, novel-import, install-template,
uninstall-template, share-template, translate-subtitles, browse-templates,
preview-template, schedule-publish, analytics, filter-jobs, retry-jobs,
retry-batch, resume-report, init-project, generate-keyframes,
generate-storyboard, split-novel, render-remotion, render-release,
build-publish-pack, enhance-publish-pack, suggest-asset-repairs,
plan-providers, build-provider-requests, apply-provider-results,
manual-import-batch, execute-provider-requests, provider-readiness,
comfyui-service, local-provider-live-smoke, dependency-audit,
production-risk-register, build-batch, run-batch, dashboard-export,
review-metrics, plan-rework, build-navigator, build-season-jobs,
scan-season-assets, render-season, render, build-season-summary,
init-demo-db
```

**注意**: `render` 命令的 handler `handle_render` 是别名导入，非真孤儿 ✅

---

### 5. 配置一致性

#### ✅ 通过检查

- **providers.yaml**: 包含 `video_router` 配置 (v3.0 新增)
- **pipelines**: `manhua_episode.yaml` 定义 SOP 8 阶段
- **templates**: 存在模板目录
- **.env 文件**: `.env.local` 被 .gitignore 保护 ✅
- **API Key**: 无硬编码泄露 ✅

#### 🟡 待确认

- **Tripo API Key**: 401 错误 (需峰哥配 key)
- **JieYou API Key**: 401 错误 (需峰哥配 key)
- **ComfyUI**: 离线状态 (需本地部署)

---

### 6. 类型注解覆盖率

**98% 函数有返回类型注解** ✅

仅 18 个函数缺少返回注解，建议补充:
- `core/database.py` 中的辅助函数
- `core/novel_pipeline.py` 中的遗留函数
- `video_synthesis/` 中的辅助函数

---

## 🎯 优先级建议

### P0 - 立即删除 (阻断 v3.0 发布)
1. **删除 `core/database.py` 全模块** - 16 个孤儿函数，未被任何地方 import
2. **删除 `core/shot_versioning.py` 全模块** - 11 个孤儿函数，未被任何地方 import
3. **删除 `video_synthesis/` 全目录** - 12 个孤儿函数，未接入 v3.0

### P1 - 高优先级 (v3.0 发布前)
1. **清理 `core/novel_pipeline.py`** - 保留 `import_novel_file`，删除其他 7 个函数
2. **清理 `core/romance_pipeline.py`** - 整个模块仅 1 个函数被调用
3. **为 `pipeline_coordinator.py` 编写集成测试** - SOP 核心模块
4. **为 `mode_router.py` 编写单元测试** - 三线渲染路由核心

### P2 - 中优先级 (v3.0 发布后)
1. **清理 `characters/` 模块** - 40 个孤儿函数，需确认是否保留角色系统
2. **清理 `image_consistency/` 模块** - 4 个孤儿函数，需确认 triple_lock 是否完整
3. **为 `providers/` 模块编写测试** - 25 个孤儿函数
4. **为 `publish/` 模块编写测试** - 8 个孤儿函数

### P3 - 低优先级 (技术债务)
1. **补充类型注解** - 18 个函数缺少返回注解
2. **清理 `qc/` 模块** - 2 个 horror 遗留函数
3. **清理 `cli/` 中的废弃命令** - 检查是否有命令不再使用

---

## 📊 代码健康度评分

| 维度 | 得分 | 说明 |
|------|------|------|
| 模块导入 | 100% | 所有模块可正常 import |
| 类型注解 | 98% | 仅 18 函数缺少返回注解 |
| TODO 残留 | 100% | 0 个 TODO/FIXME/HACK |
| API Key 安全 | 100% | 无硬编码泄露 |
| **代码复用** | **73%** | 167 孤儿函数/844 总函数 |
| **测试覆盖** | **13%** | 16/125 模块有直接测试 |
| CLI 完整性 | 100% | 60 命令全部有 handler |
| 架构一致性 | 85% | 三线渲染正确集成，部分模块断链 |

**综合健康度**: **83/100** 🟡

---

## 🔧 立即行动清单

```bash
# 1. 删除 P0 孤儿模块
rm src/aicomic/core/database.py
rm src/aicomic/core/shot_versioning.py
rm -rf src/aicomic/video_synthesis/

# 2. 清理 P1 孤儿函数
# (手动编辑 novel_pipeline.py, romance_pipeline.py)

# 3. 运行测试确认无回归
.venv/bin/python -m pytest --tb=short -q

# 4. 提交清理
git add -A
git commit -m "refactor: remove orphan modules (database, shot_versioning, video_synthesis)"
git push
```

---

## 📝 备注

1. **孤儿函数不一定是坏事** - 部分是为未来功能预留的扩展点
2. **但 v3.0 发布前应明确标记** - 要么接入，要么删除，要么标记为 `@deprecated`
3. **测试覆盖率不是越高越好** - 核心模块必须测试，工具函数可以延迟
4. **建议引入 `@unused` 装饰器** - 明确标记"故意保留但未使用"的函数

---

**审计结论**: AIComics v3.0 架构整体健康，核心管线 (SOP 8 阶段 + 三线渲染 + Video Router) 全部正确集成。主要问题是历史遗留代码未清理 (167 个孤儿函数) 和测试覆盖不足 (87% 模块无直接测试)。建议先删除 P0 孤儿模块，再发布 v3.0。
