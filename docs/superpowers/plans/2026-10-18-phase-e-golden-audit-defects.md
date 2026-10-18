# Phase E 实现计划：金样评估 / 审计 Agent / 缺陷看板

日期：2026-10-18 · 规格来源：SOP §8.1 三层质检、§8.4 金样回归、§4③ 资产馆审计、§12 看板。

## 范围

1. **E1 金样回归库**（eval-drivenTDD）
   - `core/self_review.judge_shots(shots, quality_reports=None) -> dict`：规则层融合 verdict——任一规则 issue ⇒ revise（无 LLM 也具备判别力，LLM 仅增强）
   - `core/self_review.review_with_golden(golden_path) -> {passed, failed, skipped}` runner：`evals/golden/*.json` 样本 `{name, expected, shots, quality_reports}`；运行时注入变异（bad case 改动 shots）⇒ verdict 必须变红
   - fixture：`evals/golden/workplace_E01.json`（4 pass + 4 revise 合成样本，指标式非图片）
2. **E2 审计 Agent 输出**（复用 image_consistency.image_dhash/similarity，不重造）
   - `core/consistency_audit.audit_character_assets(refs, assets, *, threshold) -> {verdict, pairs[]}`
   - pair=(ref, asset) 两两 similarity：<threshold → below=True；verdict accept 仅当全过
3. **E3 缺陷看板**（§12）
   - `core/defect_board.build_defect_board(state_dir, *, provider_manifest=None) -> {checkedpoints, by_stage, entries[]}`
   - `write_defect_board(state_dir, out_path) -> Path`（atomic_write_json + markdown 简版）
   - CLI `defect-board`（state_dir 来自 ProjectPaths.state_dir()，AICOMIC_STATE_DIR 兼容）
4. **E4 收尾**：变异×3（judge_shots 恒 pass / audit threshold 永过 / 看板 ignore failed）红过即还原；全套 pytest ≥1445 新增量；pyflakes 零告警。

## 纪律（沿用）

红→绿分记；无外部新依赖（PIL/dHash 已在库内）；CLI 注册面 argparse 真机冒烟；不 push。

## 执行进度

✅ 全部完成：全套 1458+1 / pyflakes 零 / 变异×3 红过（judge恒pass 5红、阈值永过1红、看板忽略failed 2红）。
