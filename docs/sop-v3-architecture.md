# AIComics SOP v3.0 架构图（修复后完整版）

> 生成时间: 2026-09-06  |  测试: 1045 passed  |  提交: 756d954

---

## 一、SOP 8阶段管线 + 状态机映射（问题A已修复）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SOP Pipeline (config/pipelines/manhua_episode)    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ①project_setup ──→ ②story_bible ──→ ③episode_outline             │
│       │                  │                   │                      │
│       ▼                  ▼                   ▼                      │
│    [idea]          [script_ready]     [script_ready]                │
│                                                                     │
│  ④shot_breakdown ──→ ⑤asset_generation ──→ ⑥tts_subtitle          │
│       │                     │                      │                │
│       ▼                     ▼                      ▼                │
│  [shotlist_ready]    [assets_ready]          [assets_ready]         │
│                      [assets_partial]                               │
│                                                                     │
│  ⑦preview_render ──→ ⑧publish_pack                                 │
│       │                    │                                        │
│       ▼                    ▼                                        │
│  [preview_rendered]   [publish_pack_ready]                         │
│                             │                                       │
│                             ▼                                       │
│                        [archived]                                   │
└─────────────────────────────────────────────────────────────────────┘

  STAGE_TO_STATUS 映射表 (episode_lifecycle.py):
  ┌────────────────────┬──────────────────────┐
  │ SOP Stage          │ EpisodeState         │
  ├────────────────────┼──────────────────────┤
  │ project_setup      │ idea                 │
  │ story_bible        │ script_ready         │
  │ episode_outline    │ script_ready         │
  │ shot_breakdown     │ shotlist_ready       │
  │ asset_generation   │ assets_ready/partial │
  │ tts_subtitle       │ assets_ready         │
  │ preview_render     │ preview_rendered     │
  │ publish_pack       │ publish_pack_ready   │
  └────────────────────┴──────────────────────┘

  StageAdvanceResult.episode_status → complete_stage()/approve_stage() 同步返回
```

---

## 二、模块接入全景（4断链已修复 + 2额外修复）

```
                        ┌──────────────────┐
                        │  Template YAML   │
                        │  (horror.yaml等) │
                        └────────┬─────────┘
                                 │
                    ┌────────────┼─────────────┐
                    ▼            ▼             ▼
           ┌──────────────┐ ┌──────────┐ ┌──────────────┐
           │story_bible   │ │template_ │ │horror_       │
           │.py ✅问题B   │ │engine.py │ │pipeline.py   │
           │读template    │ │✅问题C   │ │(legacy路径)  │
           │world_rules   │ │horror_   │ │              │
           │taboos/twist  │ │beat字段  │ │              │
           └──────┬───────┘ └────┬─────┘ └──────┬───────┘
                  │              │              │
                  ▼              ▼              │
           ┌──────────────┐ ┌──────────┐       │
           │project_      │ │shot      │       │
           │initializer   │ │breakdown │       │
           │.py           │ │manifest  │       │
           └──────┬───────┘ └────┬─────┘       │
                  │              │             │
                  ▼              ▼             │
    ┌─────────────────────────────────────────────┐
    │         PipelineCoordinator                 │
    │  complete_stage() ──→ checkpoint + status   │
    │  execute_publish_pack() ✅问题D             │
    │  approve_stage()                           │
    │  advance()                                 │
    └─────────────────┬───────────────────────────┘
                      │
         ┌────────────┼─────────────┐
         ▼            ▼             ▼
  ┌────────────┐ ┌──────────┐ ┌──────────────┐
  │build_      │ │triple_   │ │publish_pack  │
  │provider_   │ │lock.py   │ │.py           │
  │requests()  │ │P1角色一致│ │✅问题D       │
  │             │ │          │ │桥接SOP→publish│
  │ enhance_   │ └──────────┘ └──────┬───────┘
  │ by_intent  │                     │
  │ ✅已接入    │                     ▼
  └──────┬─────┘            ┌──────────────┐
         │                  │ 发布材料输出  │
         ▼                  │ title_candidates│
  ┌────────────┐            │ hashtags     │
  │ image/     │            │ cover_text   │
  │ video      │            │ comment_seed │
  │ prompt     │            └──────────────┘
  │ enhanced   │
  └──────┬─────┘
         │
         ▼
  ┌────────────┐
  │ Provider   │
  │ Request    │
  │ Payload    │
  └────────────┘
```

---

## 三、提示词增强链路（已验证端到端通）

```
Shot dict
  │
  ▼
classify_shot_intent(shot, idx, total, prev, next)
  │ → intent: exposition/confrontation/revelation/transition/emotional/climax
  │ → confidence: 0.0-1.0
  │ → narrative_position: 开头/发展/高潮/结尾
  ▼
enhance_by_intent(base_prompt, shot, ...)
  │ → 根据 intent 选择增强策略
  │ → 输出: { prompt, intent, confidence, ... }
  ▼
build_image_prompt_enhanced() / build_video_prompt_enhanced()
  │ → 注入角色一致性描述 (triple_lock)
  │ → 意图感知镜头语言
  ▼
build_request_payload(job, provider, ...)
  │ → 组装 provider API payload
  ▼
build_provider_requests(manifest, jobs, config, output)
  │ → 批量生成所有 shot 的 request
  ▼
ProviderRequestRecord → 输出到 output_root/
```

---

## 四、三线渲染架构

```
                    ┌──────────────────┐
                    │   Episode        │
                    │   Manifest       │
                    └────────┬─────────┘
                             │
                    ┌────────┼────────┐
                    │ mode = "2d" │ "2.5d" │ "3d" │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌────────────┐ ┌──────────────┐
     │ 2D 线        │ │ 2.5D 线    │ │ 3D 线        │
     │ image_pipeline│ │ depth+     │ │ Tripo API    │
     │ + FLF 插值   │ │ parallax   │ │ → Blender    │
     │ + video_router│ │ + motion   │ │ → 3D render  │
     └──────┬───────┘ └─────┬──────┘ └──────┬───────┘
            │               │               │
            └───────────────┼───────────────┘
                            ▼
                   ┌────────────────┐
                   │ Season Renderer│
                   │ season_renderer│
                   │ .py            │
                   │ mode_router()  │
                   └────────────────┘
```

---

## 五、修复清单

| # | 问题 | 根因 | 修复 | 提交 |
|---|------|------|------|------|
| R1 | round 1 | request_builder L140 shot['scene'] 硬访问 | 加 .get() 防御 | c9f86f0 |
| R2 | round 2 | season_renderer 无三线 mode router | 新增 mode_router() | c9f86f0 |
| R3 | round 3 | triple_lock 不接入 image_pipeline | pipeline.py 调 triple_lock | c9f86f0 |
| R4 | round 4 | request_builder parse_shot_id 硬编码 | 改为通用解析 | c9f86f0 |
| A | 状态机映射 | complete_stage 不更新 EpisodeState | STAGE_TO_STATUS + episode_status 同步 | de02b8f |
| B | story_bible 硬编码 | build_story_bible 不读 template YAML | 新增 template_name 参数 | ca85cf2 |
| C | horror_beat 断链 | template_engine 不写 horror_beat | shot dict 新增字段 | ca85cf2 |
| D | publish_pack 空壳 | 无 stage executor | execute_publish_pack() 桥接 | 756d954 |
| E | JieYou API 401 | API key 过期 | 🔒 需峰哥配 key | — |

---

## 六、测试覆盖

```
v2.0 基线:  939 passed
P0 修复:    965 passed (+26)
P1+P2:      997 passed (+32)
三线架构:   1011 passed (+14)
提示词系统: 1039 passed (+28)
v3.0接入:   1045 passed (+6  ← 防回归集成测试)
问题A-D:    1045 passed (0 回归)
```

6个防回归集成测试 (`tests/test_request_builder.py::TestV3ModuleIntegration`):
1. test_triple_lock_plan_only_mode
2. test_video_router_config_loading
3. test_flf_interpolator_pipeline
4. test_render_mode_2d_default
5. test_render_mode_25d_depth
6. test_render_mode_3d_tripo
