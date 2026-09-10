# AIComics CHANGELOG

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
