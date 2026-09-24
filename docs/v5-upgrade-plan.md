# AIComics v5.0 升级规划（最终版）

> 基于：v4.0深度代码审计(15个缺陷) + GitHub竞品调研(12个项目) + 2025-2026技术趋势调研(6大趋势)
> 日期：2026-09-23
> 状态：调研完成，待审批

---

## 一、竞品全景

### 12个GitHub高星竞品

| 竞品 | Stars | 核心定位 | AIComics最大差距 |
|------|-------|---------|-----------------|
| ComfyUI | 130.8K | 可视化节点图AI创作引擎 | AIComics用固定管线，无节点图编辑器，无12K+社区组件 |
| MoneyPrinterTurbo | 99.5K | 一键AI短视频生成 | 无TikTok/IG/YouTube一键发布，无Agent模式，无真实素材库 |
| Open-Sora | 29.4K | 开源T2V模型训练 | 无自研视频模型，无训练框架，无V2V |
| Remotion | 58.2K | React编程式视频 | AIComics用了Remotion但没深入——无Lambda云渲染、无agentic模式 |
| OpenMontage | 55.9K | Agent-first视频生产 | 无agent-first架构，无700+技能文件，无7维provider评分 |
| Toonflow-app | 14.4K | **AI短剧创作（直接竞品）** | **同功能但720倍stars。无限画布、ScriptAgent+ProductionAgent双Agent** |
| Wan2.2 | 17.4K | 开源视频基础模型 | Wan-Animate角色替换、S2V语音驱动视频——AIComics只路由Wan API没利用本地能力 |
| HunyuanVideo | 12.5K | 13B视频模型+Avatar | 音频驱动avatar动画、多人对话视频生成、情绪可控avatar |
| ViMax | 12.1K | Agent视频生成全角色 | **AutoCameo（用户自拍入剧）——AIComics完全没有的病毒级功能** |
| CogVideo | 13.0K | 开源T2V/I2V/V2V | 自研模型、fine-tuning框架、学术背书 |
| StoryDiffusion | 6.4K | 角色一致性学术方法 | Consistent Self-Attention训练-free方案，NeurIPS 2024 |
| AIComicBuilder | 1.6K | **AI漫剧生成（直接竞品）** | **同功能但78倍stars。四视图角色参考实际集成、首尾帧关键帧、Next.js 16** |

### 最直接威胁

**Toonflow-app (14.4K星)** 和 **AIComicBuilder (1.6K星)** 跟AIComics功能几乎一样——小说/剧本→动画视频全管线，但stars分别是720倍和78倍。

---

## 二、代码审计核心缺陷

| # | 缺陷 | 严重度 |
|---|------|--------|
| 1 | `template_loader.py` 0个importer — 死代码 | 🔴 |
| 2 | `lora_config.py` 0个importer — 死代码 | 🔴 |
| 3 | i18n翻译是placeholder，没接LLM | 🔴 |
| 4 | selenium/openai/edge-tts不在requirements — 功能无法运行 | 🔴 |
| 5 | Wan provider是`_StubLoader`空壳 | 🟡 |
| 6 | drift_gate/consistency/lora/cloud_mode 4个功能无Web API | 🟡 |
| 7 | 75个模块>50行无测试覆盖 | 🟡 |
| 8 | 无ffprobe质量门 | 🟡 |
| 9 | 发布模块依赖selenium(易碎)而非API | 🟡 |
| 10 | 无API Key管理/限流 | 🟡 |

---

## 三、v5.0升级规划（5大方向 · 20项）

### 方向一：修复v4.0死代码（P0 — 2周）

> 先让已有的东西能跑

| # | 任务 | 具体内容 |
|---|------|---------|
| 1 | 接线template_loader | pipeline_coordinator创建项目时自动调用load_genre_template() |
| 2 | 接线lora_config | character_workshop创建角色时生成LoRA训练配置 |
| 3 | 修复i18n翻译 | 接入OpenAI/Gemini API做真实中→英/日/韩翻译 |
| 4 | 修复依赖 | 加入selenium/openai/edge-tts/google-api-python-client |
| 5 | 修复Wan provider | 替换_StubLoader为真实Wan API适配器或移除 |

### 方向二：质量控制体系（P1 — 2周）

> 对标MoneyPrinterTurbo的ffprobe + 学术界伪影检测

| # | 任务 | 具体内容 |
|---|------|---------|
| 6 | ffprobe视频质量门 | 每个MP4自动检查分辨率/帧率/比特率/时长/音视频同步 |
| 7 | AI伪影检测器 | 基于Artifact-Bench三级分类：角色变形(手指/面部)/文字乱码/色彩异常/时序不连续 |
| 8 | 自动重试循环 | 检测到伪影→prompt精炼→模型切换→重生成→再检测，最多3轮 |
| 9 | Drift Gate + Consistency Web API | 暴露/api/drift/check和/api/consistency/cross-episode |
| 10 | 视频缩略图预览 | MP4自动提取关键帧，Web前端展示视频预览 |

### 方向三：MLLM智能创作层（P2 — 3周）

> 从模板填空升级到多模态大模型编排

| # | 任务 | 具体内容 |
|---|------|---------|
| 11 | MLLM故事理解引擎 | GPT-5/Gemini做故事→结构化分镜JSON(场景/角色/情绪/运镜/时长)，替代YAML模板填空 |
| 12 | 角色Content Anchor | 基于Gloria/SlotMem论文：结构化锚帧集(正面/侧面/背面/45°/表情集)，跨集角色记忆 |
| 13 | Provider 7维智能路由 | 评分维度：质量/速度/成本/可用性/限额/延迟/成功率。自动降级 |
| 14 | Sora 2迁移计划 | Sora 2 API于2026年9月24日停服，迁移到Kling 3.0/Veo 3.1/Wan 2.5 |

### 方向四：差异化杀手功能（P3 — 3周）

> 对标ViMax AutoCameo + HunyuanVideo Avatar — 竞品没有同时做漫剧+自拍入剧的

| # | 任务 | 具体内容 |
|---|------|---------|
| 15 | **AutoCameo自拍入剧** | 用户上传自拍→面部特征提取→角色面部替换→生成"你主演的漫剧"。ViMax的病毒级功能 |
| 16 | **音频驱动Avatar** | 对标HunyuanVideo-Avatar：TTS音频→角色唇形同步+表情动画。对话场景不再靠静态帧+旁白 |
| 17 | **多平台API发布** | YouTube Data API(替代selenium) + 抖音/小红书/B站API接入。对标MoneyPrinterTurbo一键发布 |

### 方向五：多Agent架构重构（P4 — 3周+）

> 对标OpenMontage(55.9K星)的agent-first + Toonflow(14.4K星)的双Agent

| # | 任务 | 具体内容 |
|---|------|---------|
| 18 | Director Agent编排 | 重构为Director Agent中央调度：Script Agent→Storyboard Agent→Character Agent→Video Agent→Quality Agent→Editor Agent |
| 19 | API Key管理面板 | 统一加密存储所有provider key，支持轮转/限额监控/失败告警 |
| 20 | 测试补全 | 优先补cli/main.py(1097行)/prompt_enhancer.py(724行)/character_views.py(622行)。目标90%核心模块有测试 |

---

## 四、优先级排期

```
P0 (Week 1-2):   #1-5   修复死代码和断裂管线
P1 (Week 3-4):   #6-10  质量控制 + Web API暴露
P2 (Week 5-7):   #11-14 MLLM智能创作层
P3 (Week 8-10):  #15-17 杀手功能（AutoCameo/Avatar/多平台发布）
P4 (Week 11+):   #18-20 多Agent重构 + 测试补全
```

## 五、技术选型

| 组件 | v4.0 | v5.0 |
|------|------|------|
| 故事→分镜 | YAML模板填空 | MLLM编排(GPT-5/Gemini) |
| 角色一致性 | Triple-Lock(IPAdapter) | + Content Anchor锚帧记忆 + Consistent Self-Attention |
| 质量控制 | 无 | ffprobe门 + AI伪影检测 + 自动重试 |
| Provider路由 | 静态配置 | 7维动态评分 + 自动降级 |
| 视频模型 | Kling/Seedance/Wan(stub) | + Kling 3.0/Veo 3.1/Wan 2.5(真实API) |
| 角色表演 | 静态帧+旁白 | 音频驱动Avatar(唇形同步+表情) |
| 自拍入剧 | 无 | AutoCameo面部替换 |
| 翻译 | placeholder | LLM翻译(OpenAI/Gemini) |
| 发布 | selenium(易碎) | YouTube Data API + 平台API |
| 架构 | 固定管线 | Director Agent + 专业Agent编排 |

## 六、验收标准

- [ ] P0: 5个死代码全部修复，i18n/发布/云端模式全部可运行
- [ ] P1: 产出视频通过ffprobe质量门，伪影检测准确率>80%
- [ ] P2: MLLM分镜质量≥模板填空(人工AB测试)
- [ ] P3: AutoCameo可生成用户自拍入剧视频，Avatar唇形同步可观赏
- [ ] P4: Director Agent可端到端自动产出完整剧集
- [ ] 全程: 1036个现有测试零回归
