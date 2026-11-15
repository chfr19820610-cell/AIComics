# SOP 符合性验收报告

> 生成时间: 2026-11-15
> 依据: `docs/AI漫剧多Agent工业化SOP.md`
> 项目: xianxia-12（12 集 × 6 镜 = 72 镜）

---

## 一、SOP 要求 vs 实际交付

| SOP 要求 | 状态 | 产物 |
|---|---|---|
| specs/what-vision.md | ✅ 已建 | 创作愿景/幕结构/范围边界 |
| specs/how-pipeline.md | ✅ 已建 | 九阶段/文件总线/三层质检/CCV/Debate |
| specs/style-bible.md | ✅ 已建 | 风格/角色/场景/特效/运镜/禁止项 |
| specs/compliance.md | ✅ 已建 | 7 条硬红线/AIGC 标识/平台差异 |
| assets/bible.json | ✅ 已建 | 8 角色 + 10 场景 + 5 道具 + 5 特效 |
| scripts/E*.json（四表一纲） | ✅ 12 个 | 集纲/幕表/场表/角色表/钩子表/台词表 |
| shots/E*.json（12 字段） | ✅ 12 个 | 72 镜全字段齐全（emotion/sound_cue 由 LLM 补） |
| routes/E*.json（路由+预算） | ✅ 12 个 | 模型矩阵/预算/熔断/单镜路由 |
| runs/E*/ 包 | ✅ 12 个 | shots/images/audio/cut + compliance/metrics/handoff |
| evals/rubrics/*.md | ✅ 3 个 | 单镜/单集/全季三层 rubric |
| evals/golden/*.json | ✅ 1 个 | 5 金样 + 3 反例 |
| gates/*.sh（可执行） | ✅ 7 个 + run_all | G1–G7 + 一键 |
| CCV 环 | ✅ 已跑 | 12 集评审 + 56 条问题 + SUMMARY.md |
| Debate-Judge | ✅ 已跑 | E01–E03 示范（18 镜裁决） |

---

## 二、Gate 验收结果

| Gate | 结果 | 说明 |
|---|---|---|
| G1 剧本 | ✅ PASS | 12 集四表一纲齐全、钩子存在 |
| G2 资产 | ✅ PASS | 8 角色/10 场景/5 道具/5 特效 |
| G3 分镜 | ✅ PASS | 72 镜 × 12 字段齐全 |
| G4 生成 | ✅ PASS | 12 集各 6 镜，512×384，3.04 秒 |
| G5 音频 | ✅ PASS | 配音 + 字幕齐全 |
| G6 导出 | ✅ PASS | 12 集成片 18 秒，v+a 齐全 |
| G7 合规 | ⚠️ CONDITIONAL | 6 条硬红线通过，R7 备案号待填 |

**7/7 gate 通过**（G7 为软警告）。

---

## 三、CCV 环结果（三轮，已改进）

| 项 | 值 |
|---|---|
| 评审集数 | 12 |
| 判决分布 | R1: CONCERNS×12 → R2: CONCERNS×12 → **R3: E12 达成 PASS** |
| 问题总数 | 56 条 |
| 高频问题 | 信息密度过高 / 情绪曲线缺爆点 / 功能重复镜 / 悬念指向不明 / 台词语义错位 |

**必须说清**：按 SOP，CONCERNS 应进入第 2 轮修改。但**修改剧本 = 重拍视频**（72 镜 × 12 分钟 = 14 小时）。
当前选择：**如实记录 CONCERNS，不重拍**，等峰哥决策。

详见 `reviews/ccv/SUMMARY.md`。

---

## 四、Debate-Judge 结果

| 项 | 值 |
|---|---|
| 覆盖 | E01–E03（示范，18 镜） |
| 争议 | 保守派 A（稳）vs 激进派 B（动） |
| 裁决结果 | 混合（A/折中/B 各有） |
| 输出 | 每镜运镜方案 + 一句理由 |

详见 `reviews/debate/E0*_debate.json`。

---

## 五、与旧结构的差异

| 旧结构 | 新结构（SOP） |
|---|---|
| manifests/xianxia_12.json（剧本+分镜混在一起） | scripts/ + shots/ 分层 |
| docs/shot_prompts_en.json（只有 prompt） | shots/*.json 的 prompt_en 字段 |
| docs/character_bible.json（3 个通用角色） | assets/bible.json（8 角色 + 详细锚点） |
| 无预算/路由 | routes/*.json（模型矩阵+预算+熔断） |
| 无验收 | gates/*.sh（7 个可执行） |
| 无质检标准 | evals/（3 rubric + golden） |
| 无交接 | runs/*/handoff.md（12 个） |
| 无评审 | reviews/ccv + reviews/debate |

---

## 六、遗留项（如实）

| # | 项 | 状态 |
|---|---|---|
| 1 | CCV 第 2 轮修改（56 条问题） | ⏸ 未做（需重拍，14 小时） |
| 2 | Debate-Judge 全 72 镜 | ⏸ 只做 E01–E03 示范 |
| 3 | R7 备案号 | ⏸ 待峰哥填 |
| 4 | 风格漂移（Q 版） | ⏸ 模型能力边界 |
| 5 | AI 标识水印烧录 | ⏸ 需 ffmpeg overlay（未做） |


---

## 七、CCV 第 2/3 轮改进（2026-11-15 晚）

### 实际改动（A 类台词层）
- 改 **19 镜台词**（DeepSeek 按 22 条建议重写）
- 12 集全部重做 TTS + SRT + 合成
- **修正时间轴**：从错误的 7 秒/镜（42 秒）改为正确的 3 秒/镜（18 秒）

### 真实效果
| 指标 | R1 | R2 | 变化 |
|---|---|---|---|
| 钩子 | 4.00 | 4.50 | **+0.50** |
| 曲线 | 3.33 | 3.50 | +0.17 |
| 悬念 | 4.42 | 4.33 | -0.09 |

### 第 3 轮（结尾重写）
- **E12: CONCERNS → PASS**（悬念 4→9，钩子 4→8）
- E08: 悬念 2→4→6，仍 CONCERNS（画面缺反常信号）

### 遗留（如实）
- B 类（剪辑层 38 条）：会破坏 18 秒结构，未做
- C 类（画面层 55 条）：需重拍 55 镜 × 12 分钟 = 11 小时，未做
- 旧版成片备份在 `assets/_backup_r1/`
