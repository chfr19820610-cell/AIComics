# AIComics CHANGELOG

## v4.0.0 — 2026-09-06

### v4.0 升级 — 12项功能 · 4优先级 · TDD全程

基于 GitHub 竞品调研（4个项目对比）+ v3.0 深度审计（20+维度），补齐断链、防偏移、跨集一致性、发布集成。

#### P0 — 核心体验（1-2周）
- **P0-1 角色四视图接入**: `execute_asset_generation` 调用 `generate_view_prompt()` 生成正面/侧面/背面/45° 四视图
- **P0-2 多模型视频路由**: `VideoRouter.route(shot_type)` → `RoutingDecision`（provider/model/flf_enabled）
- **P0-3 防偏移Drift Gate**: `drift_gate.py` (146行) — `DriftGate.check(shots, refs)` → PASS/WARN/FAIL + drift_score 0-100
- **P0-4 多语言TTS+字幕**: `get_voice_for_language(lang, gender)` + `translate_subtitles(list)` + `build_subtitle_entries`

#### P1 — 生产力（2-3周）
- **P1-5 Workflow-First**: `execute_publish_pack` 已接入 `pipeline_coordinator.py`
- **P1-6 跨集一致性**: 新增 `check_cross_episode_consistency(ep_a, ep_b)` → `list[ConsistencyIssue]`
- **P1-7 发布平台集成**: `international.py` — `publish()` + `YouTubeUploader`（YouTube/TikTok/IG selenium）
- **P1-8 模板系统**: `template_loader.py` (53行) — `load_genre_template(name)` + 6个题材YAML模板

#### P2/P3 — 扩展能力（3-4周）
- **P2-9 LoRA训练配置**: `lora_config.py` (73行) — `build_lora_training_config()` 生成SDXL角色LoRA训练配置
- **P2-10 Docker一键部署**: Dockerfile + 7个compose文件（dev/prod/gpu/cpu/comfyui/all-in-one）
- **P3-11 小说→漫剧管道**: `import_novel()` → `split_novel_to_episodes()` → `generate_episode_plan()` → `build_season_production_plan()`
- **P3-12 Electron桌面端**: `desktop/` 脚手架 — Electron main + preload + package.json

### 测试
- v3.0 基线: 992 passed
- P0: +13 → 1005 passed
- P1: +13 → 1018 passed
- P2/P3: +18 → **1036 passed, 1 skipped, 0 failed**
- 零回归（992 v3.0 测试全部仍通过）

### QA 认证
- ✅ 1036/1037 测试通过 (99.9%)
- ✅ 12/12 v4.0 功能项逐条验证
- ✅ 10个核心模块导入冒烟
- ✅ CLI 60+ 命令可用
- ✅ Git 4 commits, all pushed

---

## v3.0.0 — 2026-09-06

### 破坏性变更
- 版本从 2.0 → 3.0.0
- `config/providers.yaml` 新增 `video_router` section（视频多模型路由）
- `config/pipelines/manhua_episode.yaml` SOP 8阶段管线定义

### 新功能

#### P0 — 基础修复
- `image_pipeline/pipeline.py` — 图像管线诊断 + workflow guards
- Pillow 14 兼容修复（`getdata()` → `get_flattened_data()`）

#### P1 — Triple-Lock 角色一致性
- `triple_lock.py` — 三重锁定角色一致性系统
  - Lock 1: seed 锁定（角色唯一 seed）
  - Lock 2: LoRA 风格锁定
  - Lock 3: 参考图 IP-Adapter
- `plan_only` 模式（ComfyUI 离线时产出 plan.json）

#### P2 — 视频生成升级
- `video_router.py` — 多模型路由（Kling/Seedance/JieYou 按成本/质量路由）
- `flf_interpolator.py` — FLF 帧插值（关键帧→平滑视频）

#### 三线渲染架构
- `render/season_renderer.py` — 统一渲染入口
  - 2D 线：image_pipeline + FLF 插值 + video_router
  - 2.5D 线：depth + parallax + motion
  - 3D 线：Tripo API → Blender → 3D render
- CLI `aicomic render --mode 2d|2.5d|3d`
- `tests/test_render_modes.py` — 14 测试

#### 提示词/意图识别系统
- `prompt_enhancer.py` — `classify_shot_intent()` 6类意图分类
  - exposition / confrontation / revelation / transition / emotional / climax
- `enhance_by_intent()` — 意图感知提示词增强
- 5 项修复（静默异常/双重增强/horror 绕过/质量门/video mode）
- 28 测试覆盖

#### SOP v3.0 管线接入
- 4 个 v3.0 模块断链接入 SOP 管线（Round 1-4）
- 6 防回归集成测试

### SOP 修复（5额外问题）

#### 问题A — 状态机映射
- `episode_lifecycle.py` 新增 `STAGE_TO_STATUS` 映射表
- `StageAdvanceResult.episode_status` — `complete_stage()`/`approve_stage()` 同步返回 episode 状态

#### 问题B — story_bible 读 template YAML
- `creator_bootstrap.py` `build_story_bible()` 新增 `template_name` 参数
- 有 template 时从 YAML 读 `world_rules`/`narrative_beats`/`taboos`/`twist`

#### 问题C — horror_beat 通过 template_engine
- `template_engine.py` shot dict 新增 `horror_beat` 字段
- 不再只有 `horror_pipeline.py` 独立路径

#### 问题D — publish_pack 空壳修复
- `pipeline_coordinator.py` 新增 `execute_publish_pack()` 方法
- 桥接 SOP 单集管线与 `build_enhanced_publish_pack`

#### 问题E — JieYou API 401
- API key 过期，代码层面 skip，待配 key

### 文档
- `docs/sop-v3-architecture.md` — SOP v3.0 完整架构图
- README 更新至 v3.0 + 三线渲染 CLI 用法

### 测试演进
```
v2.0 基线:  939 → P0: 965 → P1+P2: 997 → 三线: 1011
→ 提示词: 1039 → v3.0接入: 1045 → SOP修复: 1045 (0 回归)
```

### 提交链
```
a816c6b  feat: v3.0 P0 — image_pipeline
15ebbf5  feat: v3.0 P1+P2 — Triple-Lock + video router + FLF
4f8a4f3  feat: v3.0 three-line render architecture
32e8549  feat: v3.0 CLI render command
21dd196  test: 28 tests for prompt system
69f37d5  fix: 5 prompt system issues
c9f86f0  feat(v3.0): wire 4 disconnected modules into SOP
98cfe70  test(v3.0): 6 integration tests
ca85cf2  fix(sop): problem B+C
de02b8f  fix(sop): problem A — stage→state mapping
756d954  fix(sop): problem D — execute_publish_pack
6dc31b8  docs: SOP v3.0 architecture diagram
```
