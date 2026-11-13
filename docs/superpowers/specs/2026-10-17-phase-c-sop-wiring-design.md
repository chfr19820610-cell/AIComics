# Phase C 设计规格 — SOP 落地（预算哨兵 / ShowAgent 编排 / 交接包 / 合规 AI 标识）

- 日期：2026-10-17
- 依据：《docs/AI漫剧多Agent工业化SOP.md》§6（Agent 卡片）、§7（文件总线/交接契约）、§8（评估）、§9（失败模式）、§11（合规）、§12（本仓映射建议）
- 用户批准：2026-10-17 "批准，按计划执行"（范围为 B 档：编排+预算+合规）
- 惯例：TDD 红/绿两段式 commit（可单独 revert）；全套 pytest 不跌破 1384 passed + 1 skipped；pyflakes src/aicomic 零告警；不 push；docs/superpowers/ 保持 untracked
- 本规格不提交（遵循仓库已有约定）

## 0. 背景与非目标

代码盘查结论（2026-10-17）：
- 本仓已有两套编排：`core/pipeline_coordinator.py`（集级声明式阶段机：checkpoint/审批门/推进）与 `batch/coordinator.py`（季/批步行器）；
- 六个可复用 gate 已在位（approval_gate / preflight_gate / ffprobe quality_gate / drift_gate / silent_failure / playback_review）；
- `core/cost_dashboard.py` 为生产级账本（`atomic_write_json`、`check_budget`、`get_budget_status`），但**管道零调用点**；
- SOP §12 点名的孤儿模块：`core/director_agent.py`（通用执行原语，7 工位空壳）、`providers/smart_router.py`、`intelligence/{best_of_n,speculative_fanout,patch_verifier}.py`、`characters/autocameo.py`、`video_synthesis/audio_avatar.py`、`publish/orchestrator.py`。

**本阶段做**（SOP → 仓库翻译）：
1. C1 预算哨兵：账本+kill 开关切进 provider live 执行链（SOP §9 #9 成本爆炸对策）；
2. C2 ShowAgent：SOP"编排器+审批卡点"用现有级机落地（SOP §6.2 ①制片工位 + IT 五卡点）；
3. C3 交接包：SOP §7 handoff.md（跨会话断点续跑的 SSOT 面向人的一份）；
4. C4 AI 标识：SOP §11 双标识——release 导出自动烧 AI 元数据（显式水印 opt-in）。

**非目标（YAGNI，明确不做）**：
- 不接 `providers/smart_router.py`（与 `video_router`+`model_cascade` 职责重叠，判定搁置，写进孤儿 memo）；
- 不动 `director_agent.py` 通用引擎（继续服务 `tests/test_p4_agent.py`）；
- 不接 autocameo / audio_avatar / publish orchestrator；
- 不做 LLM-as-judge / evals-golden（无 OPENAI_API_KEY，留 Phase D；
- 不启用 publish 平台（凭据缺，`config/publish.yaml` 维持全 false）；
- 不重造 runs/ 目录树（复用 state/checkpoints + reports 约定）。

## 1. C1 预算哨兵

**新模块** `src/aicomic/core/budget_sentinel.py`：

```python
DEFAULT_COST_CENTS: dict[str, int] = {   # 估价表（ cents/次 live 尝试 ）
    "kling": 45, "seedance": 15, "wan": 5, "dall_e": 8,
    "openai_image": 8, "openai_tts": 2, "comfyui": 0,
}
# 未知 provider → 0（不拦截）；同一 provider 每请求按表估一次。

class BudgetSentinel:
    def __init__(self, dashboard: CostDashboard, pricing: dict[str, int] | None = None) -> None: ...
    def estimate_cents(self, request_item: dict[str, Any]) -> int: ...
    def guard(self, request_item: dict[str, Any], *, episode_code: str = "", job_id: str = "") -> bool:
        """语义（SOP §9 #9）：API 提交即扣费 → 尝试前记账并判断。
        - 预算未超：把预估 cents 记入账本（notes="budget_sentinel:attempt"），返回 True；
        - 预算超（dashboard.check_budget() False）：不记账、返回 False（由调用方 kill）。
        """
```

- 估价规则：`cents = pricing.get(provider, 0)`；`job_type` 不在 `{"image","video","tts"}` → 0；
- `estimate_cents` 对坏形状（非 dict/缺 payload）安全返回 0。

**executor 接线**（`src/aicomic/providers/executor.py :: execute_provider_requests`）：
- 新增可选参数 `budget_sentinel: BudgetSentinel | None = None`（DI；为 None 时行为与现状逐字节一致）；
- 在 live 分支（`confirm_live=True` 通过后、`perform_provider_request` 之前）：
  - `sentinel.guard(...)` False → `result["status"]="stopped_by_budget"`，置 `stopped_by_budget_guard=True`，其后未处理请求全部标 `stopped_by_budget`（语义仿 failure guard）；
  - True → 继续执行；
- 返回报告新增字段：`budget_guard_enabled: bool`、`stopped_by_budget_guard: bool`、`budget_status: str`（sentinel 存在时取 `dashboard.get_budget_status().status`，否则 `"unlimited"`）；
- dry_run / blocked / cached / unsupported / failure-guard 各分支**不记账**。

**CLI**（`src/aicomic/cli/main.py :: handle_execute_provider_requests`）：
- 新增可选 flag `--budget-cents INT`（默认 0=关闭；env `AICOMIC_BUDGET_CENTS` 作为缺省来源，解析失败按 0）；
- `>0` 时构建 `CostDashboard(storage_dir=<state>/costs, budget_cents=n)` + `BudgetSentinel` 传入执行函数；
- `<0` 或非整数：按 0 处理（容错，不炸 CLI）。

## 2. C2 ShowAgent 编排

**新模块** `src/aicomic/core/show_agent.py`：

```python
@dataclass
class ShowRunResult:
    episode_code: str
    stages_run: list[str]          # 本轮执行过的 stage id
    stop_reason: str               # all_completed / awaiting_human / failed / needs_input / budget_stopped
    current_stage: str             # 停在哪（全完成时为 ""）
    details: dict[str, Any]        # 各阶段执行结果摘要 / handoff_path / 报警

class ShowAgent:
    def __init__(self, state_dir: Path, *, coordinator: PipelineCoordinator | None = None,
                 budget_sentinel: BudgetSentinel | None = None,
                 providers_config_path: Path | None = None,
                 output_root: Path | None = None) -> None: ...
    def run_until_human(self, episode_code: str, inputs: dict[str, Any]) -> ShowRunResult: ...
```

**驱动循环**（复用级机全部信控，零平行状态）：
1. `stage = coordinator.current_stage(episode_code)`；None → `all_completed` 收尾；
   1b. **门禁防护**：若该 stage 的 checkpoint `status == awaiting_human`（或为门禁阶段且未 `human_approved`）→ **不得 `begin_stage` 重放该阶段**，立即返回 `stop_reason="awaiting_human"`（防止重复调用死循环重执行门禁阶段）；
2. `begin_stage`；
3. 分发器 `_STAGE_DISPATCH[stage_id]` 执行（全部桥接 coordinator 现有方法）：
   - `project_setup / story_bible / episode_outline`：声明式 pass-through（产物=inputs 交付的蓝图/清单本身），checkpoint completed，metadata 标 `{"show_agent": "passthrough"}`；
   - `shot_breakdown`：需 `inputs["blueprint"]`（缺 → `needs_input`，详情列出 `required_input: blueprint`）；
   - `asset_generation`：需 `inputs["episode_manifest"]`；调 `coordinator.execute_asset_generation`；若 `inputs.get("execute_live")` → 链 `execute_provider_requests(provider_requests=…, providers_config_path=…, confirm_live=True, budget_sentinel=self.budget_sentinel)` 并把执行报告并入结果（报告 key `provider_execution`）；
   - `tts_subtitle`：需 `inputs["episode_manifest"]`；
   - `preview_render`：优先用 `inputs["render_plan"]`；缺失时若 `inputs["episode_manifest"]` 在 → 分发器内经 `render/preview_renderer.build_render_plan` 现算；两者皆缺 → `needs_input`；
   - `publish_pack`：需 `inputs["episode_manifest"]`；
4. 执行异常 → 写 checkpoint `failed`（`metadata.error`），`stop_reason="failed"`；
5. `complete_stage`：门禁阶段 → awaiting_human → `stop_reason="awaiting_human"` 停；
6. 每次阶段迁移后调用 `handoff.refresh`（C3，可注入替身）；收敛收尾再刷一次；
7. `asset_generation` live 执行若被哨兵 kill（报告 `stopped_by_budget_guard=True`）→ `stop_reason="budget_stopped"`，checkpoint metadata 记录预算状态。

**不变量**：
- 门禁未批准永远无法推进（完全继承 `current_stage` 的防绕过逻辑）；
- `run_until_human` 是幂等续跑友好的：已完成阶段自动跳过；
- 不修改 `PipelineCoordinator` 与 `approval_gate` 现有行为。

**CLI**：新命令 `show-run`（`--episode` 必填，`--inputs <json 路径>` 可选=阶段 payload 集，`--execute-live` 开关），报告写 `reports/show_run_<ep>.json`（原子写）。

## 3. C3 交接包 handoff

**新模块** `src/aicomic/core/handoff.py`：

```python
def build_handoff_record(state_dir: Path, episode_code: str, *, coordinator: PipelineCoordinator,
                         cost_dashboard: CostDashboard | None = None) -> dict[str, Any]:
    """数据层（SSOT）：pipeline_id、current_stage、每阶段一行
    {stage_id, status, updated_at, human_approved, review_focus}、
    next_action 提示（awaiting_human → "approve_stage <sid>"；needs budgets → ...）、
    budget 段（sentinel 未接时 {"status": "unlimited"}）。"""

def render_handoff_markdown(record: dict[str, Any]) -> str: ...

def write_handoff(state_dir, episode_code, *, coordinator, cost_dashboard=None) -> Path:
    """原子写 markdown 至 <state>/handoff/<episode>_handoff.md，返回 Path。"""
```

**工具**：`utils/atomic_io.py` 新增 `atomic_write_text(path, text)`——与 `atomic_write_json` 同语义（tmp+replace，BaseException 清 tmp，missing_ok）。

**接入点**：ShowAgent 每次阶段迁移/停止后 `write_handoff`（构造函数可注入 `handoff_writer` 替身，默认真写）；CLI 新命令 `show-handoff --episode E01` 单独生成（stdout 摘要 + 文件路径）。

**门禁高亮**：markdown 中 awaiting_human / failed 行加 `⚠` 标记（SOP 五卡点对人审的可见性）。

## 4. C4 合规 AI 标识

**新模块** `src/aicomic/video_synthesis/ai_label.py`：

```python
AI_METADATA_TAGS: dict[str, str] = {
    "ai_generated": "true",
    "comment": "本内容由AI生成（AIComics）",
    "ai_generator": "AIComics",
}

def embed_ai_label(video_path: Path, output_path: Path | None = None, *,
                   watermark: bool = False, watermark_text: str = "",
                   ffmpeg_bin: Path | str | None = None) -> dict[str, Any]:
    """remux 烧元数据（默认）：ffmpeg -i in -map 0 -c copy -metadata k=v …
    -movflags +faststart，输出目录 tmp + replace（原子）；
    watermark=True 时走 -vf drawtext 重编码分支（慢路径，opt-in）。
    返回 report：{output_path, size_bytes, tags_applied, watermark, ffmpeg_ok}。
    ffmpeg_bin=None → 复用 video_synthesis.config.FFMPEG 解析链。"""

def ai_label_present(video_path: Path, ffmpeg_bin=None) -> bool:
    """ffprobe -show_format -print_format json=pickle? 解析 format.tags 含
    ai_generated=true → True；ffprobe 不可用 → False。"""
```

- 失败语义：ffmpeg 调用失败 → 抛 `RuntimeError`（与仓内 other ffmpeg helper 一致：`raise RuntimeError(f"ffmpeg 失败: …")`）；
- 原子性：成功路径 tmp+replace；失败清理 tmp 不动原文件。

**接入点**：
1. `render/release_renderer.py :: render_release_video` 成功产出后自动 `embed_ai_label`（env `AICOMIC_AI_LABEL=0` 可关；默认开=微短剧 AI 双标识基线）；
2. CLI 新命令：`ai-label-embed <video> [--watermark] [--output <path>]`、`ai-label-check <video>`（exit 0/1）。

## 5. CLI 面新增总览

| 命令 | 参数 | 行为 |
|---|---|---|
| `show-run` | `--episode`（必）、`--inputs`（opt json）、`--execute-live` | ShowAgent 全自动推进至人工卡点，报告落 reports/ |
| `show-handoff` | `--episode`（必） | 生成/刷新 handoff md，输出路径 |
| `ai-label-embed` | `<video>` `--watermark --output` | 元数据烧录（+可选水印） |
| `ai-label-check` | `<video>` | 验证 ai_generated 标（rc 0/1） |
| `execute-provider-requests`（扩展） | `--budget-cents INT` | 预算哨兵开关 |

## 6. 测试矩阵（红→绿，先测后码）

| # | 测试 | 目标 | 文件 |
|---|---|---|---|
| T1 | 无 sentinel：现有 9 个 executor 用例全部保持绿 | 回归不变 | tests/test_executor.py（已存在） |
| T2 | sentinel 预算 100、首请求估 120 → live 即 `stopped_by_budget`、perform 零调用（mock 断言）、账本 0 笔新 attempt | kill 生效 | tests/test_budget_sentinel.py |
| T3 | 预算充足：成功执行后账本有 attempt 记录、`budget_status="ok"` | 记账语义 | 同上 |
| T4 | dry_run/blocked/cached 分支不记账 | 记账边界 | 同上 |
| T5 | job_type 非媒体（如 edit）/未知 provider → 估价 0 不拦截 | 估 价表边界 | 同上 |
| T6 | CLI `--budget-cents 100` 贯通（mock execute 断言 sentinel 传入） | CLI 面 | tests/test_cli_main.py 追加 |
| T7 | ShowAgent：蓝本缺 → needs_input（不写 completed） | 输入契约 | tests/test_show_agent.py |
| T8 | ShowAgent：真实小样例 → 三前置 pass-through completed → 停 shot_breakdown awaiting_human | 级机协同 | 同上 |
| T9 | approve 后续跑推进到 asset_generation；执行器抛错 → checkpoint failed + stop failed | 门禁/失败 | 同上 |
| T10 | execute_live + sentinel kill → budget_stopped；live 关闭时不建 sentinel 调用 | 与 C1 缝合 | 同上 |
| T11 | run_until_human 幂等：重复调用从断点续跑；对 awaiting_human 门禁阶段不重放（checkpoint updated_at 不变） | 续跑/门禁不重放 | 同上 |
| T12 | atomic_write_text 崩溃注入（写一半 boom / rename 失败）→ 旧内容保留 + 无 tmp 残留（沿用 Phase A 加固写法） | 原子语义 | tests/test_phase_c_wiring.py（新） |
| T13 | handoff 内容：全 stage 行、awaiting_human ⚠ 高亮、预算段、next_action | 内容契约 | 同上 |
| T14 | ShowAgent 迁移后 handoff 文件刷新（mock writer 调用计数） | 接线 | 同上 |
| T15 | embed_ai_label remux：真 ffmpeg 小视频 → tags 在 + faststart + 原文件不动 | C4 核心 | tests/test_ai_label.py |
| T16 | ai_label_present 真假两态；未标注视频 False | 校验 | 同上 |
| T17 | release renderer 自动嵌入（AICOMIC_AI_LABEL 未设 → 嵌入；=0 → 不嵌） | 默认合规 | tests/test_phase_c_wiring.py |
| T18 | CLI ai-label-embed / ai-label-check rc 语义 | CLI 面 | tests/test_cli_main.py 追加 |

**变异自检**（收尾抽 3）：预算 kill 变异（guard 恒 True）须让 T2 变红；atomic_write_text 去掉 tmp 清理须让 T12 变红；ai-label remux 去掉 `-metadata` 须让 T15/T16 变红。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| executor 签名变化影响既有调用方（CLI/batch）| 可选参数置尾，None 默认零行为变化；T1 回归 |
| ShowAgent 分发器与执行器参数形状不匹配 | 全部桥接现有方法签名，inputs 缺失走 needs_input 而非 crash；T7 |
| ai_label remux 改写 release 输出影响既有 renderer 测试 | remux 幂等 + 环境开关；T17 显式双态；其余 render 相关既有测试保持原断言（输出文件存在等），tags 断言只在新增用例里做 |
| 成本估价数值拍脑袋 | 注释注明"估价上限哨兵，非计费"；数值集中 DEFAULT_COST_CENTS 一处可调 |
| state 目录并发 | 沿用 atomic_io 既有语义（tmp+replace） |
