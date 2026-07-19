# GitHub 生态深度扫描：AI 视频生成 + 漫画生成赛道

> **扫描日期**: 2026-07-19  
> **扫描目的**: 识别 AIComics 可集成的开源项目和生态机会  
> **方法论**: 5 个赛道 × 各 Top 5 项目，记录 star 数、最近更新、核心能力、集成点  
> **工具**: GitHub API + 网页爬取 + 交叉验证  

---

## 赛道 1：ComfyUI 工作流 + 漫画/漫剧 (Comic/Manhwa Workflow)

| # | 项目 | Stars | 最近更新 | 核心能力 | 与 AIComics 集成点 |
|---|------|-------|---------|---------|-------------------|
| 1 | **[manga-image-translator](https://github.com/zyddnys/manga-image-translator)** (zyddnys) | ★10.2k | 活跃 (2018 commits) | 漫画图片翻译、文字检测和擦除、文本渲染 | 可直接复用其文字检测/OCR/Optical Character Recognition管线处理漫画帧；其文本渲染引擎可用于 AIComics 的对话气泡处理 |
| 2 | **[ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)** (kijai) | ★6.6k | 极活跃 (1,439 commits) | Wan2.1/2.2 视频生成 ComfyUI 集成；含 ATI 轨迹控制、FlashVSR 超分 | AIComics 可直接用其作为视频生成后端，完成剧本→视频帧的转换管线 |
| 3 | **[ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo)** (Lightricks) | ★4.0k | 活跃 (90 commits) | LTX-2 模型的 ComfyUI 节点支持；视频+音频同步生成 | 为 AIComics 提供音频+视频同步生成能力，适合漫剧/动态漫画 |
| 4 | **[ComfyUI_Isulion](https://github.com/Isulion/ComfyUI_Isulion)** (Isulion) | ★~400 | 中等活跃 | Mega Prompt Generator；含 Manga Panel 分镜节点 | 其中的 Manga Panel 节点可直接用于 AIComics 的自动分镜工作流 |
| 5 | **[comfyui_panels](https://github.com/bmad4ever/comfyui_panels)** (bmad4ever) | ★35 | 中等活跃 | 漫画/漫画面板布局生成的 ComfyUI 节点 | 较小但专注：漫画面板布局生成，可用于 AIComics 的页面自动排版 |

### 生态发现
- **ComfyUI 漫画生态仍然碎片化**，缺乏端到端的"文本→漫画页"一站式工作流
- manga-image-translator 是唯一超过 10k star 的项目，说明漫画文本处理需求强
- kijai 的 Wrapper 系列是 ComfyUI 视频生态的核心枢纽（6.6k star，1400+ commits）
- **机会：AIComics 可以成为 ComfyUI 上第一个端到端漫画生成工作流的整合者**

---

## 赛道 2：Wan2.2 / LTX 等新模型的开源生态项目

| # | 项目 | Stars | 最近更新 | 核心能力 | 与 AIComics 集成点 |
|---|------|-------|---------|---------|-------------------|
| 1 | **[Wan2.2](https://github.com/Wan-Video/Wan2.2)** (Wan-Video) | ★16.7k | 2026-07 (51 commits) | MoE (Mixture of Experts) 架构视频模型；T2V (Text-to-Video) + I2V (Image-to-Video) + A2V (Audio-to-Video)；Apache 2.0 | **核心视频生成引擎候选**。MoE 架构的漫画风格生成潜力大；Apache 2.0 许可无商业风险 |
| 2 | **[Wan2.1](https://github.com/Wan-Video/Wan2.1)** (Wan-Video) | ★16.6k | 2026-07 (53 commits) | Wan2.2 的前一代；视频基础模型套件含 T2V + I2V | 作为 Wan2.2 的备用/兼容版本，用于低配推理场景 |
| 3 | **[Wan2GP](https://github.com/deepbeepmeep/Wan2GP)** (deepbeepmeep) | ★6.6k | 极活跃 (1,603 commits) | GPU Poor 友好的视频生成应用；支持 Wan 2.1/2.2 + LTX-2 + Hunyuan + Flux | **低配 GPU 用户入口**。AIComics 可打包 Wan2GP 作为轻量级本地推理方案 |
| 4 | **[LTX-Video](https://github.com/Lightricks/LTX-Video)** (Lightricks) | ★10.7k | 2026-07 (89 commits) | 首个 DiT (Diffusion Transformer) 视频模型；50 FPS 4K 视频；同步音频+视频 | 高质量视频生成备选；其音频同步特性适合有声漫剧 |
| 5 | **[LTX-2](https://github.com/Lightricks/LTX-2)** (Lightricks) | ★8.3k | 2026-07 (41 commits) | LTX-Video 的升级，音频+视频融合模型；LoRA 训练支持 | 支持 LoRA 微调，适合针对漫画风格做模型定制 |
| — | **[LTX-Desktop](https://github.com/Lightricks/LTX-Desktop)** (Lightricks) | ★1.8k | 2026-07-19 | 本地 LTX 视频编辑器桌面应用；开源 | 可作为 AIComics 的视频后期编辑模块参考 |

### 生态发现
- **Wan2.2 (16.7k) 是目前 GitHub 上最受欢迎的开源视频模型**，增长极快
- LTX 系列（LTX-Video 10.7k + LTX-2 8.3k）是第二极
- Wan2GP 的出现（6.6k star，1600+ commits）说明"低配友好"是刚需
- **两者都强在通用视频生成，但都缺乏漫画/漫剧特定优化**
- **AIComics 的机会：做 Wan/LTX 模型上的漫画风格 LoRA 和专用推理管线**

---

## 赛道 3：AI 视频质量优化工具

| # | 项目 | Stars | 最近更新 | 核心能力 | 与 AIComics 集成点 |
|---|------|-------|---------|---------|-------------------|
| 1 | **[Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)** (xinntao) | ★36.2k | 2022-09 (10 releases) | 通用图像/视频超分辨率放大；动漫/真实场景双模型 | **漫画帧超分首选**。在漫画/动漫场景表现出色，可集成在 AIComics 后处理管线 |
| 2 | **[HunyuanVideo](https://github.com/Tencent-Hunyuan/HunyuanVideo)** (Tencent) | ★12.3k | 2026-07 (240 commits) | 13B 参数视频生成模型；FP8 量化推理 | 其视频质量框架可做 AIComics 的对比基准；13B 模型画面细节丰富 |
| 3 | **[StreamingT2V](https://github.com/Picsart-AI-Research/StreamingT2V)** (Picsart) | ★1.6k | 2025 (CVPR 2025) | 长视频一致性生成 (CVPR 2025)；自回归扩展生成 | 用于 AIComics 生成长序列漫画帧时保持角色一致性 |
| 4 | **[Enhance-A-Video](https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video)** (NUS-HPC-AI-Lab) | ★~200 | 2024 | 免费视频增强；对生成视频进行后处理质量提升 | 轻量级视频后处理，适合 AIComics 管线中的画质提升步骤 |
| 5 | **[KLing-Video-WatermarkRemover-Enhancer](https://github.com/chenwr727/KLing-Video-WatermarkRemover-Enhancer)** (chenwr727) | ★~150 | 2025 | 去水印 + 视频增强；针对 AI 生成视频 | 水印去除+增强组合，可集成到 AIComics 后期处理管线 |

### 生态发现
- **Real-ESRGAN (36.2k) 是绝对王者**，其动漫优化模型是漫画场景必备
- 视频质量优化赛道相对细分，独立工具不多——大部分功能被整合进生成模型本身
- **AIComics 的最佳质量管线**：Wan2.2/LTX 生成 → Real-ESRGAN 超分 → 可选择 Enhance-A-Video 再增强
- StreamingT2V 的长视频一致性方案是 AIComics 规划长剧情时的重要参考

---

## 赛道 4：AI 叙事/剧本生成工具 (LLM-based Story Generator)

| # | 项目 | Stars | 最近更新 | 核心能力 | 与 AIComics 集成点 |
|---|------|-------|---------|---------|-------------------|
| 1 | **[VGen](https://github.com/ali-vilab/VGen)** (Alibaba) | ★3.2k | 2025-01 (88 commits) | 阿里通义视频生成生态；I2VGen-XL 等模型整合 | 其图像到视频的管线可复用；VGen 生态与 AIComics 的视觉生成方向互补 |
| 2 | **[AIStoryWriter](https://github.com/datacrystals/AIStoryWriter)** (datacrystals) | ★255 | 2025-06 (284 commits) | LLM 长篇故事生成；多步提示链保证叙事连贯性 | **直接可集成的故事引擎**。Python 实现，支持任意 LLM，可输出结构化叙事 |
| 3 | **[NovelGenerator](https://github.com/KazKozDev/NovelGenerator)** (KazKozDev) | ★138 | 2025-10 (v4.1) | 多 Agent 小说生成系统；角色开发 + 情节连贯 | 多 Agent 架构思路可借鉴——为 AIComics 的"编辑→作者→审查"流程 |
| 4 | **[llm-storyteller](https://github.com/warc0s/llm-storyteller)** (warc0s) | ★~50 | 2025 | Streamlit AI 故事生成器；支持 OpenRouter/本地模型 | 轻量级故事原型，可作为 AIComics 故事的快速原型验证 |
| 5 | **[Awesome-Story-Generation](https://github.com/yingpengma/Awesome-Story-Generation)** (论文列表) | ★~500 | 持续更新 | LLM 时代故事生成论文索引 | 学术参考：跟踪前沿叙事生成技术（长剧情、角色一致性等） |

### 生态发现
- **叙事/剧本生成是一个相对早期且分散的赛道**——最高仅 3.2k star (VGen 偏视频)
- 相比视觉生成，纯文本故事生成工具规模小很多（最高 255 star）
- **AIComics 的自研叙事引擎有先发优势**——目前没有产品把故事生成+漫剧生成端到端打通
- 多 Agent 架构的故事生成（NovelGenerator 的 v4.1 方向）是值得跟踪的趋势

---

## 赛道 5：开源视频管线框架（非 ComfyUI）

| # | 项目 | Stars | 最近更新 | 核心能力 | 与 AIComics 集成点 |
|---|------|-------|---------|---------|-------------------|
| 1 | **[Open-Sora](https://github.com/hpcaitech/Open-Sora)** (HPC-AI) | ★29.2k | 2025-02 (v1.3, 1,333 commits) | Sora 开源复现；文本→视频；1.3 版本支持更长视频 | **非 ComfyUI 的主要视频生成框架选择**。成熟的视频生成管线，1.3k+ commits |
| 2 | **[DiffSynth-Studio](https://github.com/modelscope/DiffSynth-Studio)** (ModelScope) | ★12.7k | 2025-11 (v1.1.9, 1,185 commits) | 扩散模型引擎；文本编码器/UNet/VAE 重构；社区插件框架 | **可直接作为 AIComics 的核心渲染引擎**。支持 Wan、SD、FLUX 等模型，插件架构灵活 |
| 3 | **[CogVideo](https://github.com/THUDM/CogVideo)** (THUDM → zai-org) | ★12.9k | 2024-11 (454 commits) | CogVideoX (2024) 文本→视频；多分辨率支持 | 视频生成候选引擎；CogVideoX 的微调能力可用于漫画风格定制 |
| 4 | **[VideoCrafter](https://github.com/AILab-CVC/VideoCrafter)** (AILab-CVC) | ★5.1k | 2024-01 (120 commits) | T2V + I2V 视频生成工具包；VideoCrafter2 质量提升 | 参考其工具包设计理念，AIComics 可构建类似的模块化视频管线 |
| 5 | **[Vibe-Workflow](https://github.com/SamurAIGPT/Vibe-Workflow)** (SamurAIGPT) | ★504 | 2025-11 (27 commits) | 节点式 AI 工作流构建器；Freepik/Krea Nodes 的开源替代 | 轻量级 ComfyUI 替代，适合 AIComics 的云服务/Web 端工作流 |

### 生态发现
- **Open-Sora (29.2k) 是非 ComfyUI 管线的第一选择**，但最近更新在 2025-02，活跃度下降
- **DiffSynth-Studio (12.7k) 是最活跃的通用扩散引擎**（v1.1.9 发布，1,185 commits），且原生支持 Wan/FLUX/SD
- CogVideo 12.9k 但最后 release 在 2024-11，更新放缓
- **趋势：从 ComfyUI 向 API-first 框架迁移**——DiffSynth-Studio 的服务化架构值得关注
- **AIComics 的机会**：DiffSynth-Studio 的插件架构可以扩展漫画生成插件，从而让 AIComics 作为 ModelScope 生态的漫画创作工具

---

## 跨赛道集成机会分析

### 🔥 高优先级集成机会

| 优先级 | 机会 | 涉及赛道 | 说明 |
|--------|------|---------|------|
| P0 | **Wan2.2 + ComfyUI-WanVideoWrapper 作为主力视频生成引擎** | 1, 2 | Wan2.2 16.7k star，Apache 2.0 许可，MoE 架构；kijai 的 Wrapper 6.6k star，社区支持强。AIComics 可直接调用 |
| P0 | **DiffSynth-Studio 作为核心渲染引擎** | 5 | 12.7k star，1,185 commits，支持多模型、插件化架构。AIComics 可以作为插件生态的一部分 |
| P1 | **Real-ESRGAN 动漫模型用于漫画帧超分** | 3 | 36.2k star 绝对王者，直接用于后处理放大管线 |
| P1 | **manga-image-translator 的 OCR/文字处理管线** | 1 | 10.2k star，成熟漫画文字处理方案，用于 AIComics 的文字气泡自动处理 |
| P2 | **AIStoryWriter/NovelGenerator 的故事生成** | 4 | 整合 LLM 叙事引擎，实现完整的 故事→剧本→分镜→视频 管线 |
| P2 | **Wan2GP 作为低配 GPU 用户入口** | 2 | 降低硬件门槛，扩大 AIComics 用户基数 |

### 📊 市场格局总结

```
                    ★ 规模（stars）
                    ↑
        40k        Real-ESRGAN(36.2k)
                    │
        30k        Open-Sora(29.2k)
                    │
        20k        Wan2.2(16.7k)  Wan2.1(16.6k)
                    │
        15k        CogVideo(12.9k)  DiffSynth(12.7k)  HunyuanVideo(12.3k)
                    │
        10k        LTX-Video(10.7k)  manga-translator(10.2k)
                    │
         5k        LTX-2(8.3k)  Wan2GP(6.6k)  VideoCrafter(5.1k)  ComfyUI-WanWrapper(6.6k)
                    │
         1k        VGen(3.2k)  StreamingT2V(1.6k)  LTX-Desktop(1.8k)
                    │
         <1k       ════════════════════════════════════════════════
                    │   叙事/剧本生成 (138-500)  ComfyUI漫画节点 (35-400)
                    │
                    └──────────────────────────────────────────→ 与漫画的关联度
                    低                                      高
```

### 🚀 行动建议

1. **立即启动**：搭建 Wan2.2 + ComfyUI 的漫画风格视频生成 PoC
2. **1-2 个月**：完成 AIStoryWriter 整合，实现端到端文字→剧本文案
3. **3-4 个月**：基于 DiffSynth-Studio 构建 AIComics 专属渲染管线
4. **5-6 个月**：发布 ComfyUI 漫画生成工作流模板，建立社区
5. **长期**：建立漫画风格 LoRA 模型体系，形成差异化护城河

### ⚠️ 风险提示

- Wan2.2/LTX 等新模型迭代快，需保持关注版本兼容
- ComfyUI 生态碎片化，需做好多版本适配
- 叙事/剧本生成赛道尚未成熟，自研投入需控制节奏
- Real-ESRGAN 更新停滞（2022年最后 release），需关注替代方案

---

*报告生成：Hermes Agent · Product Manager + Trend Researcher 模式*
*数据来源：GitHub API + 网页抓取，截至 2026-07-19*
