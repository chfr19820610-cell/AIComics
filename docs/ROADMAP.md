# AIComics 路线图 v2.0

更新时间：2026-08-19

## 已完成 ✅

- [x] 基础漫剧管线 (故事→分镜→图片→配音)
- [x] CLI + Web API + SPA 三端入口
- [x] 711 测试全通过
- [x] 供应商抽象层 (ComfyUI/Piper/OpenAI/Seedance/Kling/Edge TTS)
- [x] 角色系统 (定义/一致性/提示词注入/参考图)
- [x] 分镜版本管理
- [x] 自动风格轮换引擎 + 无限自循环
- [x] Docker 化全栈部署 + ComfyUI v0.33 升级
- [x] ASGI 入口统一 (main:app)
- [x] prompt 英文化 + 镜头意图分类 + 角色表构建器

---

## 未完成路线图 (6 项)

### ④ 发布平台深度集成 — P0（直接赚钱，先做）

**现状**：`international.py` 有 YouTube/TikTok/Instagram 三个 Uploader 类（selenium 骨架，未实战）。国内平台（抖音/小红书/B站）完全没有。`auto-publisher` skill 指向 social-auto-upload (13k⭐) 但未集成进 AIComics 代码。

**Phase 1: 国内3平台自动发布**（3-5天）
- 集成 social-auto-upload 到 publish/ 模块
- 抖音/小红书/B站 3个 Uploader（浏览器自动化）
- Cookie 持久化 + 自动登录态恢复
- `config/publish.yaml` 声明式平台配置
- CLI: `aicomic publish --platform douyin,xhs,bili --code MYCOMIC --ep E01`

**Phase 2: 国际3平台**（2天）
- YouTube Data API v3（非 selenium，用官方 API）
- TikTok / Instagram 复用 selenium

**Phase 3: 发布编排**（2天）
- 一键多平台分发（标题/标签/封面各平台适配）
- 定时发布
- 发布后数据回收（播放量/点赞）

---

### ① 漫剧专用模板系统 — P1（标准化生产）

**现状**：`horror_pipeline.py` 和 `romance_pipeline.py` 是硬编码的两个题材蓝图（五幕法 A1-A5）。`manhua_episode.yaml` 是管线阶段清单。缺模板注册/选择/参数化。

**Phase 1: 模板注册器**（2天）
- `config/templates/` 目录，每个模板一个 YAML
- 模板 schema: 题材/五幕结构/角色原型/场景库/情绪图/镜头语言/音效提示/避坑清单
- 模板引擎读 YAML 替代硬编码

**Phase 2: 内置6题材模板**（3天）
- 恐怖(已有) / 爱情(已有) / 职场逆袭 / 修仙 / 悬疑推理 / 甜宠

**Phase 3: 模板→管线绑定**（1天）
- `init-project --template horror` → 自动套用模板
- 模板可覆盖管线阶段/审核门/风格轮换

---

### ② 小说→漫剧一站式管道 — P1（内容供给）

**现状**：`novel_splitter.py` 做章节拆分（正则匹配"第X章"→6-10 shot/集），`horror_pipeline.py` 做5幕蓝图生成，两者没衔接。

**Phase 1: 小说导入→分集→蓝图**（3天）
- `novel_import` CLI: 读 txt/epub → novel_splitter 拆分 → 每集接 pipeline 生成蓝图
- LLM 改写层：小说原文 → 漫剧旁白体（压缩/改编/加钩子）

**Phase 2: 蓝图→分镜→全管线**（2天）
- 蓝图自动接 shot_breakdown → asset_generation → 合成
- 小说角色名→角色系统自动建档

**Phase 3: 批量编排**（1天）
- 一本小说→整季N集→批量生产→批量发布

---

### ③ 多语言配音 & 字幕 — P2（出海）

**现状**：TTS 有 Piper/Edge TTS/OpenAI TTS，字幕 `subtitles.py` 生成 SRT/ASS（中文）。无翻译层。

**Phase 1: 字幕翻译**（1天）
- LLM 翻译层：中文字幕→英/日/韩 字幕

**Phase 2: 多语言 TTS**（2天）
- Edge TTS 多语言路由（zh-CN/en-US/ja-JP/ko-KR）
- 一集→多语言版本

**Phase 3: 语言包管理**（2天）
- 一集视频→N个语言版本→各平台对应地区发布

---

### ⑤ 云端轻量模式 — P2（降低部署门槛）

**现状**：Docker 全栈 105G（ComfyUI+模型）。已有 `openai_image`/`openai_tts`/`seedance` 云端 provider。

**Phase 1: 纯云端 Provider 模式**（1天）
- `--cloud` 标志：跳过 local_providers，全走 API
- Docker 镜像不含 ComfyUI（< 500MB）

**Phase 2: 远程 ComfyUI**（1天）
- 支持远程 ComfyUI URL
- 多机推理：本地编排 + 远程 GPU 出图

**Phase 3: SaaS 化**（5天+）
- API key 体系 + 多租户

---

### ⑥ 社区模板市场 — P3（生态）

**现状**：完全空白。

**Phase 1: 模板分享**（2天）
- GitHub repo 做模板仓库
- CLI: `aicomic install-template <url/name>`

**Phase 2-3: 在线市场 + 变现**（看用户量再定）

---

## 执行优先级（赚钱驱动）

```
第一批（直接赚钱）:
  ④发布平台 Phase 1  ← 先做，能发布才能赚钱
  ①模板系统 Phase 1  ← 标准化才能批量产

第二批（扩大产能）:
  ②小说→漫剧 Phase 1-2
  ①模板系统 Phase 2-3
  ④发布 Phase 2-3

第三批（出海+降门槛）:
  ③多语言 Phase 1-2
  ⑤云端轻量 Phase 1-2

第四批（生态）:
  ⑥社区模板市场
```
