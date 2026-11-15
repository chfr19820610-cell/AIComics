# HOW — 生产流程规范

> SOP §1.2 的「how」侧：本文件只回答**怎么做**，不含创作意图。

---

## 1. 九阶段产线

| 阶段 | Agent | 输入 | 输出 | 人审卡点 |
|---|---|---|---|---|
| 1. 剧本 | 编剧 Agent + 剧本医生（CCV） | what-vision | `scripts/E*.json` | 卡点1 剧本会 |
| 2. 资产 | 资产馆 Agent + 审计 Agent | scripts | `assets/bible.json` + 角色图 | 卡点2 资产会 |
| 3. 分镜 | 分镜师 + 双估算（Debate-Judge） | scripts | `shots/E*.json` | 卡点3 分镜会 |
| 4. 路由 | 编排器 | shots | `routes/E*.json` | — |
| 5. 生图 | 抽卡 Agent | routes.image | `runs/E*/images/` | 卡点4 精修 |
| 6. 生视频 | 抽卡 + 质检 + 审片 | routes.video | `runs/E*/shots/` | 卡点4 精修 |
| 7. 配音 | 配音 + 对位 Agent | scripts.dialogue | `runs/E*/audio/` | — |
| 8. 剪辑 | 剪辑 + 字幕 + 混音 | shots/audio | `runs/E*/cut/` | — |
| 9. 合规 | 合规 Agent | 全部 | `runs/E*/compliance.json` | 卡点5 发布审 |

## 2. 文件总线（SSOT）

```
specs/              # 只读规格，人审后锁定
  what-vision.md
  how-pipeline.md
  style-bible.md
  compliance.md
scripts/E*.json     # 剧本层：四表一纲
shots/E*.json       # 分镜层：12 字段
routes/E*.json      # 路由层：模型+预算
assets/bible.json   # 资产层：角色/场景/道具 SSOT
runs/E*/            # 运行层：本集全部产物+交接
  shots/            # 镜视频
  images/           # 关键帧
  audio/            # 配音+对位
  cut/              # 剪辑中间件
  compliance.json   # 合规自检
  metrics.json      # 成本/耗时指标
  handoff.md        # 交接卡
evals/
  rubrics/*.md      # 质检 rubric
  golden/*.json     # 金样标注
```

## 3. 三层质检

| 层 | 时机 | 判定 |
|---|---|---|
| L1 单镜 | 每镜生成后 | 构图/角色/动作是否达标 |
| L2 单集 | 六镜齐全后 | 叙事连贯/情绪曲线 |
| L3 全季 | 12 集完成后 | 风格统一/角色一致 |

## 4. Gate 验收（可执行）

7 个 gate，每个是**可执行命令**，退出码 0 通过：

| Gate | 命令 | 检查项 |
|---|---|---|
| G1 script | `bash gates/g1_script.sh` | 四表一纲齐全、钩子存在 |
| G2 asset | `bash gates/g2_asset.sh` | bible 完整、角色图存在 |
| G3 storyboard | `bash gates/g3_storyboard.sh` | 12 字段齐全、时长合法 |
| G4 generation | `bash gates/g4_generation.sh` | 每集 6 镜、分辨率正确 |
| G5 audio | `bash gates/g5_audio.sh` | 配音存在、字幕时间轴合法 |
| G6 export | `bash gates/g6_export.sh` | 成片可播、音频轨存在 |
| G7 compliance | `bash gates/g7_compliance.sh` | AI 标识、备案号、无违规 |

## 5. CCV 环（剧本层）

```
编剧 Agent 出稿 → 剧本医生 Agent 评审（PASS/CONCERNS/FAIL）→
  FAIL/CONCERNS → 编剧改 → 再审（最多 2 轮）→ 人工终审
```

## 6. Debate-Judge（分镜层）

```
运镜估算 Agent A（保守：稳镜为主）
  vs
运镜估算 Agent B（激进：动感为主）
  ↓
Judge Agent 裁决 → 每镜一个运镜决策 + 理由
```

## 7. 预算与熔断

| 项 | 上限 |
|---|---|
| 单集视频生成 | 8 次抽卡 |
| 单集图像生成 | 12 次抽卡 |
| 单集总成本 | 由 routes/E*.json 的 budget 字段锁定 |
| 熔断 | 超预算 150% 自动停 + 告警 |
