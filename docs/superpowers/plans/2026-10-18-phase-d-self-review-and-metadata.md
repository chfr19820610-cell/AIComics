# Phase D 实现计划：LLM 自审 / 素材质检 / 发布联检

日期：2026-10-18（Phase C 收尾次日）
规格来源：《docs/AI漫剧多Agent工业化SOP.md》§8.1 三层质检、§10 #7 合规四向联测；Phase C 遗留清单。

## 范围（承接 Phase C 遗留，窄改再出手）

1. **D1 规则层质检** `video_synthesis/quality_check.py`
   - `check_asset(path, *, min_duration=0.0, min_width=0, min_height=0) -> dict`（`ok + issues[]`）
   - 探针复用 stdout json 形态（ffprobe -show_streams），黑帧用 ffmpeg blackdetect 兜底（无 ffprobe 同理放行 issue="probe_unavailable"）——不静默假绿
   - 与 ai_label 同签名 sibling：`_run_probe`/`_run_ffmpeg` 可 monkeypatch
2. **D2 LLM 自审薄壳** `core/self_review.py`
   - OpenAI 兼容 `POST {base}/chat/completions`（stdlib urllib）；env：`AICOMIC_OPENAI_API_KEY`、`AICOMIC_OPENAI_BASE_URL`（默认 LM Studio `http://127.0.0.1:1234/v1`）、`AICOMIC_SELF_REVIEW_MODEL`（默认 `aicomic-self-review`）
   - `review_assets(shots: list[dict], *, episode_code="") -> dict`：`{verdict: pass|revise|error, issues: [...], model, latency_ms?}`；输出 JSON 解析失败 → verdict=error（fail-soft 结构化，不 raise）
3. **D3 ShowAgent 接入**（窄 DI，不破坏 10 测试）
   - `ShowAgent(..., self_reviewer=None)`：publish_pack 前 `_dispatch` 追加 optional `self_reviewer(shots) -> dict`，结果塞 `coordinator.begin 的 checkpoint metadata self_review`（复核路径：直接 write_checkpoint 各 stage 已有通道——最窄实现：handoff/报告里带上，不重写 checkpoint store）
4. **D4 发布 metadata 联检** `publish/domestic_publisher.py`
   - `publish_to_platforms` 每平台前置 `ai_label_present(video)`；缺标签 → `{success: False, error: "ai_label missing: run ai-label-embed first"}`（SOP §10 #7 |
   - cfg `require_ai_label`（默认 True）
   - `precheck_publish_ready(payload, platform, cfg) -> {ready, reason}` 抽函数（单元测点）
5. **D5 收尾自检**
   - 全套 pytest（>=1429+1 baseline 增量）+ pyflakes 零告警
   - 变异自检×3：①self_review verdict 恒 pass → 测试红；②发布联检拆除 → 红；③质检黑帧规则拆除 → 红
   - 真机冒烟：LM Studio 端点不可达 → verdict=error fail-soft；`publish --require` 对照臂 rc 语义

## 执行纪律（同 Phase C 7 红线）

红→绿→commit 分记；CLI 测试 AICOMIC_STATE_DIR 隔离；不 push；不动 Phase C 交付面签名；ENV key 缺失走结构化 error 不假绿。

## 执行前自检

接缝已核：`show_agent._dispatch`（publish_pack 分支）、`publish_to_platforms` per-platform 循环、`ai_label_present/_run_probe`、`checkpoint.metadata` 无需新参数全部可测。

## 执行进度

✅ 全部完成：全套 1445+1 / pyflakes 零 / 变异×3 红过（D5 publish 双臂真机冒烟 2026-10-18 补录：未打标拦截 / 打标放行至 sau）。
