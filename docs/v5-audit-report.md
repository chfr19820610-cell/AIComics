# AIComics v4.0 深度代码审计报告
> 审计时间: 2026-09-23
> 审计人: SH (小h)

## 1. 代码规模

| 指标 | 数值 |
|------|------|
| Python源文件 | 142个 |
| 源代码总行数 | 23,425行 |
| CLI命令 | 60个 |
| API端点 | 48个 |
| 测试文件 | 60个 |
| 测试用例 | 966个 (60文件中) |
| Docker配置 | 3个 (Dockerfile/Dockerfile.cloud/Dockerfile.comfyui-sidecar) |
| 模板文件 | 6个YAML (修仙/恐怖/悬疑/爱情/甜宠/职场) |

## 2. 实际产出

| 内容 | 状态 |
|------|------|
| 九转丹霄 E01-E12 | ✅ 12集全有MP4 (3.1-44.1MB不等) |
| 完整季Bundle | ✅ 120.5MB zip |
| 星痕纪元EP2 | ✅ 30.3MB |
| 30s样品 | ✅ |
| E13-E15分镜 | ⚠️ 只有storyboard JSON，无视频 |

## 3. 关键缺陷清单

### A. 未接线功能 (代码存在但没接入主管线)

| 模块 | 行数 | 问题 | 影响 |
|------|------|------|------|
| `template_loader.py` | 60 | **0个importer** — 没有任何模块导入它 | 模板系统只有CLI能用，管线内部不自动加载模板 |
| `lora_config.py` | 73 | **0个importer** — 生成的LoRA配置无人消费 | LoRA训练配置是死代码 |

### B. Web API 未暴露的v4.0功能

| 功能 | CLI | Web API | 前端页面 |
|------|-----|---------|----------|
| Drift Gate | ❌ | ❌ | ❌ |
| 跨集一致性 | ❌ | ❌ | ❌ |
| LoRA配置 | ❌ | ❌ | ❌ |
| 云端模式 | ❌ | ❌ | ❌ |
| 模板市场 | ✅ | ✅ | ✅ Templates |
| 小说导入 | ✅ | ✅ | ✅ NovelImport |

### C. Stub/Placeholder 代码

| 位置 | 问题 |
|------|------|
| `video_router.py:49-50` | Wan provider是 `_StubLoader`，不是真实Provider |
| `video_router.py:100-101` | stub._load_settings — 临时实现 |
| `i18n.py:60` | 翻译标记为"placeholder"，不是真实LLM翻译 |
| `render/preview_renderer.py:47` | 预览是文字placeholder |
| `render/three_d/pipeline.py:10` | 3D管线无API key时fallback到placeholder |
| `providers/manual_provider.py:12` | windows_tts标记为placeholder |

### D. 测试盲区

- 75个模块 >50行代码没有对应测试文件
- 最大的未测试模块: `cli/main.py` (1097行), `prompt_enhancer.py` (724行), `character_views.py` (622行)
- README声称1036测试，实际审计找到966个 `def test_` — 差异可能是parametrize或间接测试

### E. 架构问题

1. **无API Key管理** — 外部provider (Kling/Seedance/OpenAI) 无统一的key轮转/限流/失败重试
2. **无视频缩略图** — 产出的MP4没有自动生成预览图
3. **i18n是假翻译** — `translate_subtitles` 标记为placeholder，没有接入LLM
4. **3D渲染线依赖Tripo API** — 无key时降级到placeholder
5. **发布集成依赖selenium** — 浏览器自动化方案，非API方式，易碎
6. **Wan provider是空壳** — 只有路由逻辑，没有真实Provider适配器

## 4. 依赖分析

59个锁定依赖，全部pinned。但注意:
- `google-api-python-client` 和 `edge-tts` 被注释掉了（YouTube上传和多语言TTS实际无法用）
- `selenium` 不在依赖列表里 — international.py导入了但无法安装
- 无 `openai` 包 — cloud_mode默认openai_image/openai_tts但没装SDK

## 5. 竞争力评估

### 优势
- 全管线自动化（故事→视频→发布）
- 60个CLI命令覆盖面广
- 6个题材模板
- Docker全栈部署
- 实际产出12集完整季
- Apache 2.0 开源

### 弱势
- 无真实视频生成模型集成（只有路由框架）
- 无LLM驱动的故事/分镜生成（只有模板填空）
- 无角色一致性实际验证（Triple-Lock代码在但没跑过真实ComfyUI）
- 无发布平台API集成（selenium方案易碎）
- 无用户系统/多租户
- 无监控/可观测性
