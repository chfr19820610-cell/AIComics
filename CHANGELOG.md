# Changelog

All notable changes to AIComics are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] — 2026-08-19

### Roadmap v2.0 — 全部 6 项完成

#### ① 漫剧模板系统
- YAML 驱动模板注册器（6 题材：恐怖/爱情/职场/修仙/悬疑/甜宠）
- `template_engine.py` — 幕结构 + 场景 + 角色 + 钩子 + pipeline_override
- `template_market.py` — 安装/卸载/分享/在线浏览
- CLI: `list-templates` / `browse-templates` / `preview-template` / `install-template` / `share-template` / `template-blueprint` / `template-manifest`

#### ② 小说→漫剧管道
- `novel_pipeline.py` — 小说文本→章节拆分→整季蓝图→分镜计划→全管线
- 支持 .txt / .md / .epub 格式
- `narrate_rewrite()` — 小说原文→漫剧旁白体（去对话标签+压缩+LLM hook）
- `character_auto_register()` — 自动提取角色名→映射模板角色
- `run_full_pipeline()` — blueprint→shot_plan→asset_plan→render_plan
- CLI: `novel-import` / Web API: `POST /api/novel/import`

#### ③ 多语言配音&字幕
- `i18n.py` — 中→英/日/韩字幕翻译 + 多语言 TTS 路由
- `translation_memory.py` — 翻译记忆库（避免重复翻译）
- `build_multilang_episode()` — 一集→多语言完整版本（字幕+TTS+标签）
- `get_lang_to_platform_map()` + `publish_multilang_routing()` — 语言→平台地区路由
- CLI: `translate-subtitles` / Web API: `POST /api/translate`

#### ④ 发布平台集成
- 国内 3 平台: 抖音/小红书/B站（social-auto-upload subprocess）
- 国际 3 平台: YouTube（Data API v3）/ TikTok（sau tk_uploader）/ Instagram（Graph API）
- `cookie_manager.py` — Cookie 持久化 + 有效性检查 + 过期检测 + 批量检查
- `publish_scheduler.py` — 定时发布
- `publish_analytics.py` — 数据回收
- `publish_batch()` — 整季N集→多平台批量发布
- CLI: `publish` / `check-publish` / `schedule-publish` / `analytics`
- Web API: `GET /api/publish/status` / `POST /api/publish/schedule` / `GET /api/publish/analytics/summary`

#### ⑤ 云端轻量模式
- `cloud_mode.py` — `AICOMIC_CLOUD=1` 跳过 local_providers 全走 API
- `remote_gpu_dispatch()` — 多 GPU round-robin 负载均衡
- `saas_api_key.py` — API Key 管理 + 验证（SaaS 多租户）
- `Dockerfile.cloud` + `docker-compose.cloud.yml` — 轻量 Docker 镜像（842MB vs 全栈 105GB）
- `pyproject.toml` `[cloud]` extras

#### ⑥ 社区模板市场
- `install-template --url <url>` — 从 URL 安装模板
- `share-template --name horror` — 分享模板（base64 URL）
- `browse-templates [--genre 恐怖]` — 浏览所有模板含摘要
- `preview-template --template horror` — 预览模板详情

### Web UI 新增
- 前端路由: `/templates` / `/publish` / `/novel-import`
- 3 个新页面: Templates（模板浏览+预览）/ Publish（平台状态+数据统计）/ NovelImport（小说导入）
- `api.ts` +100 行: 8 个新 API 函数 + 6 个 TypeScript 接口

### 工程改进
- ASGI 入口统一: `main.py` → `web.backend.app`
- `__init__.py` 完整导出: providers(8) + publish(19) + video_synthesis(8)
- `.env.production.example` 更新: 15 个环境变量（核心 7 + v2.0 新增 8）
- `requirements-lock.txt` 更新: 可选依赖注释
- `config/publish.yaml` 加国际平台配置
- `config/providers.yaml` 加远程 ComfyUI 文档
- `scripts/yt_upload.py` — YouTube Data API v3 上传脚本

### 测试
- 711 → 939 tests (+228, +32%)
- 所有新模块公共函数 100% 测试覆盖
- 所有新 API 端点 TestClient 全覆盖
- Docker build + runtime 验证通过
- hermes verify: ok=true

---

## [1.0.0] — 2026-08-18

- 初始发布
- 核心引擎: CLI + Web SPA + REST API
- 15 个子模块: cli / core / providers / characters / video_synthesis / batch / render / publish / qc / review / security
- 711 tests
- ComfyUI 集成 + SDXL/DALL·E/Seedance/Kling 图像生成
- Piper TTS + Edge TTS 配音
- Ken Burns 视频合成 + 字幕烧录
- 688 测试全通过
