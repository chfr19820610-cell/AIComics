# AIComics v4.0 升级计划

> 版本: v4.0-plan  
> 日期: 2026-09-06  
> 状态: 待执行  
> 前置: v3.0 已完成 (992 tests, 22,585 行代码, 8阶段SOP管线)  
> 执行方式: superpowers + gstack  
> 验收: 全局 QA 认证  

---

## 一、调研结论

GitHub 竞品调研覆盖 15 个项目（详见 `docs/v4-competitive-research.md`），核心发现：

**已有但未完全接入的能力（v4.0 = 打通断链）：**
- ✅ 角色四视图系统 `character_views.py` (622行) — 已写但未接入 SOP 阶段⑤
- ✅ 多语言 i18n `i18n.py` (272行) — 4语言翻译+TTS voice map 但仅 CLI 手动调用
- ✅ 多模型视频路由 `video_router.py` (241行) — 5种 shot type 路由但 JieYou 401 卡住
- ✅ 一致性检查 `consistency_service.py` (372行) + `triple_lock.py` (166行) — 存在但 plan_only
- ✅ 发布平台 `publish/` (1003行) — YouTube/国内平台都在但未接入 SOP 阶段⑧

**完全缺失的能力（v4.0 = 新建）：**
- ❌ 跨集一致性校验 — 季内角色/场景/风格漂移检测
- ❌ 防偏移质量门 — 自动对比参考图 vs 生成图
- ❌ Docker 一键部署 — 竞品 kingdoja 已有
- ❌ 小说→漫剧管道深度集成 — `novel_pipeline.py` 存在但未接入主流程

**独家优势（保持领先）：**
- ✅ 三线渲染架构 2D/2.5D/3D — 全部竞品都没有
- ✅ 992 测试覆盖 — 领先所有竞品
- ✅ 8阶段 SOP 管线 — 最完整

---

## 二、v4.0 升级项 (12项，4个优先级)

### P0 — 打通断链（必须完成，1周）

#### P0-1: 角色四视图接入 SOP 阶段⑤
- **现状**: `character_views.py` 622行已写，`ViewAngle.FRONT/THREE_QUARTER/SIDE/BACK` 已定义，但 SOP 阶段⑤ `asset_generation` 不调用它
- **目标**: 阶段⑤自动生成角色四视图参考图，后续所有角色镜头引用四视图锁定一致性
- **改动**:
  1. `pipeline_coordinator.py` 阶段⑤执行器增加 `generate_four_view_prompts()` 调用
  2. 角色数据库 schema 增加 `view_references` 字段
  3. 生成流程: 先出正面 → 3/4 → 侧面 → 背面 → 存入参考库
- **测试**: 8-12 个新测试（四视图生成、引用、CRUD）
- **行数**: ~150 行新代码
- **文件**: `pipeline_coordinator.py`, `characters/character_views.py`, 新增 `tests/test_four_view_integration.py`

#### P0-2: 多模型视频路由全面接入
- **现状**: `video_router.py` 已支持 5种 shot type → Kling/Seedance/Wan 路由，但 `request_builder.py` 只在特定条件下调用
- **目标**: 所有视频生成请求自动走 `VideoRouter.route_shot()`，不再硬编码单一 provider
- **改动**:
  1. `request_builder.py` 的 `_build_video_request()` 强制走 VideoRouter
  2. `provider_registry.py` 增加 Wan provider 注册
  3. `providers.yaml` 配置化路由表
  4. 增加 fallback 链: Kling 401 → Seedance → Edge TTS 静态帧
- **测试**: 10-15 个新测试（路由决策、fallback、多 shot type）
- **行数**: ~200 行新代码
- **文件**: `request_builder.py`, `video_router.py`, `provider_registry.py`, 新增 `tests/test_video_router_integration.py`

#### P0-3: 防偏移一致性门禁
- **现状**: `consistency_service.py` 372行 + `triple_lock.py` 166行存在但 plan_only
- **目标**: SOP 阶段⑤ 生成图片后自动跑一致性检查，低于阈值自动返工
- **改动**:
  1. 新建 `image_consistency/drift_gate.py` (~200行) — 偏移检测门禁
  2. 阶段⑤执行器增加 drift gate 调用
  3. 检查维度: 角色面部特征、服装颜色、场景色调、画风一致性
  4. 输出: PASS/WARN/FAIL + 偏移分数 (0-100)
  5. FAIL 自动触发返工 (max 3次)
- **测试**: 12-15 个新测试
- **行数**: ~200 行新代码
- **文件**: 新增 `image_consistency/drift_gate.py`, `pipeline_coordinator.py`, 新增 `tests/test_drift_gate.py`

#### P0-4: 多语言管线接入
- **现状**: `i18n.py` 272行已支持 中/英/日/韩 4语言翻译+TTS，但仅 CLI 手动调用
- **目标**: SOP 阶段⑥ `tts_subtitle` 自动生成多语言字幕和 TTS
- **改动**:
  1. 阶段⑥执行器增加 `build_multilang_subtitle_set()` 调用
  2. `config.yaml` 增加 `output_languages: [zh, en]` 配置
  3. 输出: 每集生成 `_zh.srt` + `_en.srt` + 对应 TTS 音频
- **测试**: 8-10 个新测试
- **行数**: ~120 行新代码
- **文件**: `pipeline_coordinator.py`, `video_synthesis/i18n.py`, 新增 `tests/test_i18n_pipeline.py`

### P1 — 差异化深化（2周）

#### P1-1: 跨集一致性校验
- **现状**: 无跨集检查，季内角色可能逐集漂移
- **目标**: 季级一致性守护，每集生成后对比首集角色参考
- **改动**:
  1. 新建 `image_consistency/cross_episode.py` (~250行)
  2. `season_renderer.py` 增加跨集校验 hook
  3. 检查: 角色面部 embedding 距离、服装色板偏移、场景连续性
  4. 输出: 季级一致性报告 `season_consistency_report.json`
- **测试**: 10-12 个新测试
- **行数**: ~250 行新代码

#### P1-2: 发布平台集成接入 SOP 阶段⑧
- **现状**: `publish/` 1003行已写 (YouTube/国内平台)，但 SOP 阶段⑧ `publish_pack` 只打包不上传
- **目标**: 阶段⑧自动上传到配置的平台
- **改动**:
  1. `publish_pack.py` 增加上传调度
  2. `publish_scheduler.py` 接入阶段⑧执行器
  3. 配置化: `publish_platforms: [youtube, douyin, bilibili]`
  4. 发布前预检: 视频时长/分辨率/字幕格式
- **测试**: 10-12 个新测试
- **行数**: ~200 行新代码

#### P1-3: 小说→漫剧管道深度集成
- **现状**: `novel_pipeline.py` 存在但与主 SOP 管线割裂
- **目标**: 输入小说文本 → 自动走完整 8 阶段 SOP
- **改动**:
  1. `novel_pipeline.py` 接入 `PipelineCoordinator`
  2. 小说拆分 → 剧本生成 → 分镜 → 全管线自动
  3. CLI 新增 `aicomic novel-to-drama <file>` 命令
- **测试**: 8-10 个新测试
- **行数**: ~200 行新代码

#### P1-4: 模板系统增强
- **现状**: `template_engine.py` + `template_market.py` 已存在
- **目标**: 预置 5 种风格模板 (悬疑/爱情/热血/日常/恐怖)
- **改动**:
  1. 新增 `templates/` 目录含 5 个 JSON 模板
  2. 模板包含: 画风 prompt、角色模板、分镜模板、TTS 风格
  3. CLI `aicomic template apply <name>` 一键应用
- **测试**: 6-8 个新测试
- **行数**: ~150 行新代码

### P2 — 创新能力（3周）

#### P2-1: Docker 一键部署
- **目标**: `docker-compose up` 一键启动完整管线
- **改动**:
  1. 新建 `Dockerfile` (~50行)
  2. 新建 `docker-compose.yml` (~80行) — 含 ComfyUI + AIComics + Redis
  3. 新建 `.dockerignore`
- **测试**: Docker 构建冒烟测试
- **行数**: ~150 行

#### P2-2: LoRA 训练 GUI (Web UI)
- **目标**: Web UI 上传角色图 → 自动训练 LoRA → 接入管线
- **改动**:
  1. `web/backend/` 增加 LoRA 训练 API
  2. `web/frontend/` 增加训练页面
- **测试**: 6-8 个新测试
- **行数**: ~300 行

#### P2-3: 季级仪表板
- **目标**: Web UI 显示季级进度、一致性报告、发布状态
- **改动**:
  1. `web/backend/` 增加仪表板 API
  2. `web/frontend/` 增加仪表板页面
- **测试**: 6-8 个新测试
- **行数**: ~250 行

### P3 — 未来探索（待定）

#### P3-1: Electron 桌面端
#### P3-2: 实时预览（WebSocket 流式渲染）
#### P3-3: AI 导演助手（LLM 驱动的镜头建议）

---

## 三、执行计划

### Phase 1: P0 打通断链 (Day 1-7)

使用 superpowers subagent-driven-development 模式：

```
Day 1-2: P0-1 角色四视图接入
Day 2-3: P0-2 多模型视频路由接入
Day 3-5: P0-3 防偏移一致性门禁
Day 5-6: P0-4 多语言管线接入
Day 7:   P0 集成测试 + 验证
```

每个 P0 项的工作流：
1. `superpowers:writing-plans` → 写子计划
2. `superpowers:subagent-driven-development` → 派子代理执行
3. `superpowers:verification-before-completion` → 验证
4. 每项完成后全量 pytest 确认零回归

### Phase 2: P1 差异化深化 (Day 8-21)

```
Day 8-10:  P1-1 跨集一致性校验
Day 10-12: P1-2 发布平台集成
Day 12-15: P1-3 小说→漫剧管道
Day 15-18: P1-4 模板系统增强
Day 18-21: P1 集成测试 + 验证
```

### Phase 3: P2 创新能力 (Day 22-42)

```
Day 22-25: P2-1 Docker 一键部署
Day 25-32: P2-2 LoRA 训练 GUI
Day 32-42: P2-3 季级仪表板
```

### Phase 4: 全局 QA 认证 (Day 43-45)

使用 gstack QA 工具链：
1. `gstack health` — 代码质量仪表板
2. `gstack review` — 全量 PR 审查
3. `gstack qa` — 系统化 QA 测试
4. `superpowers:verification-before-completion` — 最终验证
5. 全量 pytest (目标: ≥1100 tests, 0 失败)
6. CLI 60+ 命令冒烟
7. 核心模块冒烟
8. 输出 `docs/v4-qA-certification.md`

---

## 四、验收标准

| 维度 | 标准 |
|------|------|
| 测试 | ≥1100 passed, 0 失败, 0 回归 |
| 代码量 | v3.0 22,585行 → v4.0 ≤26,000行 (增量 ≤3,400行) |
| 极简铁律 | 每个新模块 <400行 |
| P0 完成 | 4项全部接入 SOP 管线 |
| 角色一致性 | 四视图生成 → drift gate 门禁 → 跨集校验 |
| 视频路由 | 5种 shot type 自动路由 + fallback 链 |
| 多语言 | 中/英字幕+TTS 自动生成 |
| 发布 | SOP 阶段⑧ 可自动上传 |
| Docker | `docker-compose up` 可启动 |
| 文档 | CHANGELOG + ROADMAP + QA 报告 |

---

## 五、风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| ComfyUI 离线 → 三线渲染 plan_only | 高 | 沿用 v3.0 plan_only 模式，不阻塞 |
| JieYou API 401 → 视频生成不可用 | 高 | P0-2 fallback 链解决，不依赖单一 provider |
| Tripo API 401 → 3D 线不可用 | 中 | 用户已说跳过，3D 线 plan_only |
| 子代理执行质量不稳定 | 中 | superpowers TDD + 每步验证 |
| 新模块超 400 行 | 低 | 拆分子模块，强制 <400 行 |

---

## 六、版本号

- v3.0.0 → v4.0.0
- `pyproject.toml` version 更新
- `CHANGELOG.md` 新增 v4.0 条目
- Git tag `v4.0.0`

---

## 七、执行检查清单

- [ ] P0-1 角色四视图接入
- [ ] P0-2 多模型视频路由接入
- [ ] P0-3 防偏移一致性门禁
- [ ] P0-4 多语言管线接入
- [ ] P1-1 跨集一致性校验
- [ ] P1-2 发布平台集成
- [ ] P1-3 小说→漫剧管道
- [ ] P1-4 模板系统增强
- [ ] P2-1 Docker 一键部署
- [ ] P2-2 LoRA 训练 GUI
- [ ] P2-3 季级仪表板
- [ ] 全局 QA 认证
- [ ] 版本号 + CHANGELOG + tag
