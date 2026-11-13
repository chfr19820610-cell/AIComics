# Phase F 实现计划：金样扩充 / 阈值配置化 / 成片有效率回归

日期：2026-10-18 · 来源：Phase C–E 收尾留白清单 + SOP §8.1 成片有效率回归字面项。

## 环境裁决（执行前探测）

- LM Studio 端点 `127.0.0.1:1234` Connection refused → 「expected=error 样本联跑转正」**不可执行**，保持结构化 skip（不假绿）。待端点上线后该路径自动可用，无需改码。
- 「成片级真数据回流」无生产数据 → 金样扩充按 SOP §8.4 变异思想落地为**指标级合成样本 20 好+20 坏**（与现库同 schema，真数据回流后可平替）。

## 范围

1. **F2 金样库扩充 40 条**：`evals/golden/workplace_E01.json` cases 4+4 → 20 pass + 20 revise（合成指标：黑帧梯度/时长梯度/分辨率梯度/无指标/混合集各向展开）；跑 `review_with_golden` 40/40 全绿。
2. **F3 阈值配置化**：金样 case 支持 `"threshold"` 字段覆盖默认（黑帧/时长/分辨率三线用 dict）；`judge_shots(shots, threshold_overrides=None)` 透传；入库样本默认不设 + 2 条 override 样本验证线可动。
3. **F4 成片有效率回归**（SOP §8.1 字面项）：`self_review.evaluate_episode_efficiency(shots, *, min_pass_rate=0.9) -> {pass_rate, passed, revise, error, ok}`——单集 pass-rate 统计；<阈值 → ok=False（回归测试红线）；runner `review_with_golden` 后接续出到 `efficiency` 字段展示全链。
4. **F4b CLI**：`efficiency-report` 命令输出 pass-rate 简表（stdout）；GC 测试 `AICOMIC_STATE_DIR` 隔离。
5. **F5 收尾**：变异×2（有效率统计恒 1.0 / 金样 threshold override 失效）红过即还原；全套 pytest（≥1458+新量）+ pyflakes 零告警；真机冒烟 CLI。

## 纪律（沿用 Phase B–E 七红线）

红→绿分记；无新依赖；CLI argparse 真机冒烟；不 push；docs/superpowers 计划仅 E 已入库份可更新、新 F 计划保持 untracked。

## 执行进度

✅ 全部完成（untracked 留库外）：金样 20/20（4 次生成踩踏 assert-in-write 顺序坑后先写后校）；override×2 全绿；pass-rate 线 3 臂真机冒烟（满分/亚线/未知集）；变异×2（恒1.0 1红、override 失效 3红）；全套 1464+1 / pyflakes 零告警。LM Studio 端点仍不可达——expected=error 样本行保持结构化 skip。
