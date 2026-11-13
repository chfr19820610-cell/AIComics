# Phase C（SOP 落地：预算哨兵/ShowAgent/交接包/AI 标识）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把《docs/AI漫剧多Agent工业化SOP.md》的四个工程落地项写进 AlComics：C1 预算哨兵（CostDashboard+kill 开关切进 provider live 执行链）、C2 ShowAgent 编排（复用 PipelineCoordinator 信控自动推进至人工卡点）、C3 交接包 handoff.md、C4 合规 AI 标识（release 导出自动烧元数据）。

**架构：** 全部复用现有骨架——信控=PipelineCoordinator 级机，账本=CostDashboard（atomic_write_json），渲染=现有 preview/release 渲染器。新增 4 个模块 + 4 个窄改（executor DI、CLI 注册面、release 出口钩子、atomic_write_text）。每任务红/绿 commit。

**技术栈：** Python 3.12（`.venv/bin/python`）、pytest、ffmpeg/ffprobe（PATH 已有；imageio_ffmpeg 兜底）。

**规格：** `docs/superpowers/specs/2026-10-17-phase-c-sop-wiring-design.md`（测试矩阵 T1–T18）。

**命令约定：** 单测 `.venv/bin/python -m pytest tests/<文件> -v`；全套 `.venv/bin/python -m pytest`（≥1384 passed + 1 skipped）；lint `.venv/bin/python -m pyflakes src/aicomic`。

---

## 文件结构

**新建：**
- `src/aicomic/core/budget_sentinel.py` — 预算哨兵（估价表 + attempt 记账 + kill 判定）
- `src/aicomic/core/show_agent.py` — ShowAgent 编排器（级机驱动循环 + 阶段分发）
- `src/aicomic/core/handoff.py` — 交接包（record 数据层 + markdown + 原子写）
- `src/aicomic/video_synthesis/ai_label.py` — AI 标识（remux 元数据 + ffprobe 校验 + 可选水印）

**修改（窄口）：**
- `src/aicomic/providers/executor.py` — `execute_provider_requests` 增 `budget_sentinel` DI、kill/skip、报告字段
- `src/aicomic/cli/main.py` — execute-provider-requests 增 `--budget-cents`；新增 `show-run`/`show-handoff`/`ai-label-embed`/`ai-label-check`
- `src/aicomic/render/release_renderer.py` — 成功产物后自动 `embed_ai_label`（`AICOMIC_AI_LABEL=0` 关）
- `src/aicomic/utils/atomic_io.py` — 增 `atomic_write_text`

**测试：** 新建 `tests/test_budget_sentinel.py`、`tests/test_show_agent.py`、`tests/test_ai_label.py`、`tests/test_phase_c_wiring.py`；追加 `tests/test_cli_main.py`。

---

### 任务 1：BudgetSentinel 模块（纯逻辑）

**文件：** 创建 `src/aicomic/core/budget_sentinel.py`；测试 `tests/test_budget_sentinel.py`

- [x] **步骤 1：写失败的测试**（创建 `tests/test_budget_sentinel.py`）

```python
"""预算哨兵（budget sentinel）单元测试 — SOP §9 #9 成本爆炸对策。"""
from __future__ import annotations

from aicomic.core.cost_dashboard import CostDashboard


def _req(provider: str = "kling", job_type: str = "video", request_id: str = "REQ_1") -> dict:
    return {
        "request_id": request_id,
        "payload": {"provider": provider, "job_type": job_type, "job_id": "JOB_1", "output_path": ""},
    }


class TestEstimateAndGuard:
    def test_media_job_uses_default_pricing(self, tmp_path):
        from aicomic.core.budget_sentinel import DEFAULT_COST_CENTS, BudgetSentinel

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=1000)
        sentinel = BudgetSentinel(dashboard)
        assert sentinel.estimate_cents(_req("kling", "video")) == DEFAULT_COST_CENTS["kling"]
        assert sentinel.estimate_cents(_req("seedance", "video")) == DEFAULT_COST_CENTS["seedance"]

    def test_unknown_provider_and_non_media_job_estimate_zero(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel

        sentinel = BudgetSentinel(CostDashboard(storage_dir=str(tmp_path), budget_cents=1000))
        assert sentinel.estimate_cents(_req("unknown_provider", "video")) == 0
        assert sentinel.estimate_cents(_req("kling", "edit")) == 0

    def test_guard_records_attempt_within_budget(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=1000)
        sentinel = BudgetSentinel(dashboard)
        assert sentinel.guard(_req("kling", "video"), episode_code="E01", job_id="JOB_1") is True
        status = dashboard.get_budget_status()
        assert status.generation_count == 1
        assert status.total_spent_cents == 45
        assert status.status == "ok"

    def test_guard_refuses_over_budget_without_recording(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=100)
        sentinel = BudgetSentinel(dashboard, pricing={"kling": 120})
        assert sentinel.guard(_req("kling", "video")) is False
        status = dashboard.get_budget_status()
        assert status.generation_count == 0
        assert status.total_spent_cents == 0

    def test_guard_kills_after_budget_reached(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=100)
        sentinel = BudgetSentinel(dashboard, pricing={"kling": 45})
        assert sentinel.guard(_req("kling", "video", "R1")) is True      # spent 45
        assert sentinel.guard(_req("kling", "video", "R2")) is True      # spent 90
        assert sentinel.guard(_req("kling", "video", "R3")) is False     # 90+45 >= 100 → kill
        assert dashboard.get_budget_status().generation_count == 2
```

- [x] **步骤 2：运行确认失败**

运行：`.venv/bin/python -m pytest tests/test_budget_sentinel.py -v`
预期：5 failed（`ModuleNotFoundError: … 'aicomic.core.budget_sentinel'`）

- [x] **步骤 3：最小实现**（创建 `src/aicomic/core/budget_sentinel.py`）

```python
"""预算哨兵 — SOP §9 #9（成本爆炸对策）的执行层落地。

- 在 live Provider 请求执行**前**估算本次成本并记账（API 提交即扣费）；
- 已花费 + 本次估计 >= 预算 → 拒绝，把 kill 决定交回调用方（stopped_by_budget）；
- 估价是"上限哨兵"而非计费账单：数值集中在 DEFAULT_COST_CENTS，可随市场价调整；
- 未知 provider / 非媒体 job_type 一律估 0（comfyui 本地算力同理）。
"""
from __future__ import annotations

from typing import Any

from aicomic.core.cost_dashboard import CostDashboard

DEFAULT_COST_CENTS: dict[str, int] = {
    "kling": 45,       # kling 5s/条估价上限
    "seedance": 15,    # $0.15/s @5s
    "wan": 5,
    "dall_e": 8,
    "openai_image": 8,
    "openai_tts": 2,
    "comfyui": 0,
}

MEDIA_JOB_TYPES = {"image", "video", "tts"}


class BudgetSentinel:
    """在 provider live 执行链上记账并做预算 kill 判定。"""

    def __init__(self, dashboard: CostDashboard, pricing: dict[str, int] | None = None) -> None:
        self.dashboard = dashboard
        self.pricing: dict[str, int] = dict(DEFAULT_COST_CENTS)
        if pricing:
            self.pricing.update(pricing)

    def estimate_cents(self, request_item: Any) -> int:
        if not isinstance(request_item, dict):
            return 0
        payload = request_item.get("payload")
        if not isinstance(payload, dict):
            return 0
        job_type = str(payload.get("job_type", ""))
        if job_type not in MEDIA_JOB_TYPES:
            return 0
        provider = str(payload.get("provider", ""))
        return int(self.pricing.get(provider, 0))

    def guard(self, request_item: Any, *, episode_code: str = "", job_id: str = "") -> bool:
        est = self.estimate_cents(request_item)
        status = self.dashboard.get_budget_status()
        if status.total_budget_cents > 0 and status.total_spent_cents + est >= status.total_budget_cents:
            return False
        payload = request_item.get("payload") if isinstance(request_item, dict) else {}
        provider = str(payload.get("provider", "")) if isinstance(payload, dict) else ""
        self.dashboard.record_generation(
            provider=provider,
            asset_id=job_id,
            cents=est,
            episode_code=episode_code,
            notes="budget_sentinel:attempt",
        )
        return True
```

- [x] **步骤 4：运行确认通过**

`.venv/bin/python -m pytest tests/test_budget_sentinel.py -v` → 5 passed
（若 BudgetStatus 字段名与断言不符，读 `src/aicomic/core/cost_dashboard.py` 校正断言，不改既有 API）

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/core/budget_sentinel.py tests/test_budget_sentinel.py
git commit -m "feat: 预算哨兵 BudgetSentinel 模块（估价表+attempt 记账+kill 判定）"
```

---

### 任务 2：executor 预算接线 + CLI `--budget-cents`

**文件：** 修改 `src/aicomic/providers/executor.py`、`src/aicomic/cli/main.py`；测试追加 `tests/test_budget_sentinel.py`、`tests/test_cli_main.py`

- [x] **步骤 1：写失败的测试**（追加到 `tests/test_budget_sentinel.py` 末尾）

```python
def _requests(provider: str = "kling", count: int = 3) -> dict:
    return {
        "requests": [
            {
                "request_id": f"REQ_{i}",
                "payload": {"provider": provider, "job_type": "video", "job_id": f"JOB_{i}", "output_path": ""},
            }
            for i in range(count)
        ]
    }


class TestExecutorBudgetWiring:
    def test_kill_before_perform_and_zero_ledger(self, tmp_path, monkeypatch):
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.providers import executor

        calls: list = []
        monkeypatch.setattr(executor, "perform_provider_request", lambda item, pc: calls.append(item) or {})
        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=100)
        sentinel = BudgetSentinel(dashboard, pricing={"kling": 120})

        report = executor.execute_provider_requests(
            _requests(), tmp_path / "providers.yaml", confirm_live=True, budget_sentinel=sentinel,
        )

        assert report["stopped_by_budget_guard"] is True
        assert report["budget_guard_enabled"] is True
        assert report["budget_status"] in {"ok", "warning", "exceeded", "unlimited"}
        assert calls == []
        assert all(r["status"] == "stopped_by_budget" for r in report["results"])
        assert dashboard.get_budget_status().generation_count == 0

    def test_accounts_attempt_then_succeeds(self, tmp_path, monkeypatch):
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.providers import executor

        monkeypatch.setattr(executor, "perform_provider_request", lambda item, pc: {"ok": True})
        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=1000)
        sentinel = BudgetSentinel(dashboard)

        report = executor.execute_provider_requests(
            _requests(), tmp_path / "providers.yaml", confirm_live=True, budget_sentinel=sentinel,
        )

        assert report["stopped_by_budget_guard"] is False
        assert report["success_count"] == 3
        status = dashboard.get_budget_status()
        assert status.generation_count == 3
        assert status.total_spent_cents == 45 * 3

    def test_dry_run_never_invokes_guard(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.providers import executor

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=0)
        sentinel = BudgetSentinel(dashboard)

        report = executor.execute_provider_requests(
            _requests(), tmp_path / "providers.yaml", dry_run=True, budget_sentinel=sentinel,
        )

        assert report["dry_run_count"] == 3
        assert dashboard.get_budget_status().generation_count == 0

    def test_blocked_branch_never_invokes_guard(self, tmp_path):
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.providers import executor

        dashboard = CostDashboard(storage_dir=str(tmp_path), budget_cents=0)
        sentinel = BudgetSentinel(dashboard)

        report = executor.execute_provider_requests(
            _requests(), tmp_path / "providers.yaml", confirm_live=False, budget_sentinel=sentinel,
        )

        assert report["blocked_count"] == 3
        assert dashboard.get_budget_status().generation_count == 0

    def test_no_sentinel_keeps_report_shape(self, tmp_path):
        from aicomic.providers import executor

        report = executor.execute_provider_requests(_requests(), tmp_path / "providers.yaml", dry_run=True)
        assert report["budget_guard_enabled"] is False
        assert report["stopped_by_budget_guard"] is False
        assert report["budget_status"] == "unlimited"
```

- [x] **步骤 2：CLI 失败测试**（追加到 `tests/test_cli_main.py` 末尾）

```python
class TestExecuteProviderRequestsBudgetFlag:
    def _fake(self, captured: dict):
        def fake_execute(requests, pc, selected=None, **kwargs):
            captured.update(kwargs)
            return {
                "request_count": 0, "success_count": 0, "failed_count": 0,
                "dry_run_count": 0, "blocked_count": 0,
                "stopped_by_failure_guard": False, "stopped_by_budget_guard": False,
                "budget_guard_enabled": True, "budget_status": "ok",
            }
        return fake_execute

    def test_budget_cents_builds_sentinel(self, tmp_path, monkeypatch):
        from aicomic.cli import main as cli_main

        rr = tmp_path / "requests.json"
        rr.write_text('{"requests": []}', encoding="utf-8")
        out = tmp_path / "report.json"
        captured: dict = {}
        monkeypatch.setattr(cli_main, "execute_provider_requests", self._fake(captured))
        monkeypatch.delenv("AICOMIC_BUDGET_CENTS", raising=False)

        rc = cli_main.handle_execute_provider_requests(rr, tmp_path / "providers.yaml", "", True, False, 0, 1, out, 100)

        assert rc == 0
        sentinel = captured["budget_sentinel"]
        assert sentinel is not None
        assert sentinel.dashboard.get_budget_status().total_budget_cents == 100

    def test_budget_cents_env_fallback(self, tmp_path, monkeypatch):
        from aicomic.cli import main as cli_main

        rr = tmp_path / "requests.json"
        rr.write_text('{"requests": []}', encoding="utf-8")
        out = tmp_path / "report.json"
        captured: dict = {}
        monkeypatch.setattr(cli_main, "execute_provider_requests", self._fake(captured))
        monkeypatch.setenv("AICOMIC_BUDGET_CENTS", "77")

        rc = cli_main.handle_execute_provider_requests(rr, tmp_path / "providers.yaml", "", True, False, 0, 1, out, 0)

        assert rc == 0
        sentinel = captured["budget_sentinel"]
        assert sentinel is not None
        assert sentinel.dashboard.get_budget_status().total_budget_cents == 77

    def test_budget_disabled_zero_env(self, tmp_path, monkeypatch):
        from aicomic.cli import main as cli_main

        rr = tmp_path / "requests.json"
        rr.write_text('{"requests": []}', encoding="utf-8")
        out = tmp_path / "report.json"
        captured: dict = {}
        monkeypatch.setattr(cli_main, "execute_provider_requests", self._fake(captured))
        monkeypatch.delenv("AICOMIC_BUDGET_CENTS", raising=False)

        rc = cli_main.handle_execute_provider_requests(rr, tmp_path / "providers.yaml", "", True, False, 0, 1, out, 0)

        assert rc == 0
        assert captured["budget_sentinel"] is None
```

- [x] **步骤 3：运行确认失败**

`.venv/bin/python -m pytest tests/test_budget_sentinel.py::TestExecutorBudgetWiring tests/test_cli_main.py::TestExecuteProviderRequestsBudgetFlag -v`
预期：红色（TypeError 无 budget_sentinel 形参 / KeyError stopped_by_budget_guard / TypeError handle 位置数）

- [x] **步骤 4：实现 executor 接线**

`src/aicomic/providers/executor.py`：
1) 签名改为（`budget_sentinel: Any | None = None` 置尾，不 import core 类）：

```python
def execute_provider_requests(
    provider_requests: dict[str, Any],
    providers_config_path: Path,
    selected_providers: set[str] | None = None,
    dry_run: bool = False,
    confirm_live: bool = False,
    limit: int = 0,
    max_failures: int = 1,
    skip_existing: bool = False,
    budget_sentinel: Any | None = None,
) -> dict[str, Any]:
```

2) 计数初始化区加 `stopped_by_budget_guard = False`（`stopped_by_failure_guard` 旁）。
3) 循环内、failure-guard 跳过块之后加：

```python
        if stopped_by_budget_guard:
            result["status"] = "stopped_by_budget"
            skipped_count += 1
            results.append(result)
            continue
```

4) `if not confirm_live:` 块之后、`try:`（perform）之前加：

```python
        if budget_sentinel is not None:
            if not budget_sentinel.guard(
                request_item,
                episode_code=str(payload.get("episode_code", "")),
                job_id=str(payload.get("job_id", "")),
            ):
                result["status"] = "stopped_by_budget"
                stopped_by_budget_guard = True
                results.append(result)
                continue
```

5) 返回 dict 在 `"stopped_by_failure_guard"` 键旁加：

```python
        "budget_guard_enabled": budget_sentinel is not None,
        "stopped_by_budget_guard": stopped_by_budget_guard,
        "budget_status": (
            budget_sentinel.dashboard.get_budget_status().status
            if budget_sentinel is not None else "unlimited"
        ),
```

- [x] **步骤 5：实现 CLI 接线**

`src/aicomic/cli/main.py`：
1) `handle_execute_provider_requests`（现 549 行）整体替换：

```python
def handle_execute_provider_requests(rr: Path, pc: Path, pr: str, dry: bool, cl: bool, lim: int, mf: int, out: Path, budget_cents: int = 0) -> int:
    if budget_cents < 0:
        budget_cents = 0
    if budget_cents == 0:
        raw = os.environ.get("AICOMIC_BUDGET_CENTS", "")
        try:
            budget_cents = int(raw)
        except ValueError:
            budget_cents = 0
        if budget_cents < 0:
            budget_cents = 0
    budget_sentinel = None
    if budget_cents > 0:
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.core.cost_dashboard import CostDashboard

        dashboard = CostDashboard(storage_dir=str(ProjectPaths.state_dir() / "costs"), budget_cents=budget_cents)
        budget_sentinel = BudgetSentinel(dashboard)
    p = execute_provider_requests(load_json(rr), pc, parse_filter(pr) or None, dry_run=dry, confirm_live=cl, limit=lim, max_failures=mf, budget_sentinel=budget_sentinel)
    write_provider_execution_report(out, p)
    for k in ("request_count", "success_count", "failed_count", "dry_run_count", "blocked_count", "stopped_by_failure_guard", "stopped_by_budget_guard"):
        print(f"{k}={p.get(k)}")
    print(f"output={out}")
    return 0
```

（若顶部未 import os 则补 `import os`。）
2) 注册表条目 `execute-provider-requests` 的 args 列表尾部（`--output` 之后）加：

```python
        (["--budget-cents"], {"type": int, "default": 0, "help": "预算哨兵上限（分）；0=读 AICOMIC_BUDGET_CENTS，仍为 0 则关闭"}),
```

3) 同条目 handler 改为：

```python
        "handler": lambda a: handle_execute_provider_requests(a.requests_report, a.providers_config, a.providers, a.dry_run, a.confirm_live, a.limit, a.max_failures, a.output, a.budget_cents)},
```

- [x] **步骤 6：运行确认通过 + 回归**

`.venv/bin/python -m pytest tests/test_budget_sentinel.py tests/test_executor.py tests/test_phase_b_wiring.py tests/test_cli_main.py -v`
预期：全部 passed（既有 executor 9 用例行为不变）

- [x] **步骤 7：Commit**

```bash
git add src/aicomic/providers/executor.py src/aicomic/cli/main.py tests/test_budget_sentinel.py tests/test_cli_main.py
git commit -m "feat: 预算哨兵接入 provider live 执行链（stopped_by_budget kill + CLI --budget-cents）"
```

---

### 任务 3：`atomic_write_text`（C3 前置）

**文件：** 修改 `src/aicomic/utils/atomic_io.py`；测试创建 `tests/test_phase_c_wiring.py`

- [x] **步骤 1：写失败的测试**（创建 `tests/test_phase_c_wiring.py`，文件头对应注释两行）

```python
"""phase C 接线测试（handoff/ai_label/atomic_write_text/release 钩子）。"""
from __future__ import annotations

import json


class TestAtomicWriteText:
    def test_write_and_read_back(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        assert target.read_text(encoding="utf-8") == "第一版"

    def test_overwrite(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "第一版")
        atomic_write_text(target, "第二版")
        assert target.read_text(encoding="utf-8") == "第二版"

    def test_utf8_multiline(self, tmp_path):
        from aicomic.utils.atomic_io import atomic_write_text

        target = tmp_path / "handoff.md"
        atomic_write_text(target, "line1\nline2 中文\n")
        assert target.read_text(encoding="utf-8") == "line1\nline2 中文\n"

    def test_cleanup_tmp_on_write_error(self, tmp_path):
        import aicomic.utils.atomic_io as atomic_io

        class BoomFile:
            def __init__(self, *a, **k):
                raise RuntimeError("boom")

        monkey_orig = atomic_io.NamedTemporaryFile
        atomic_io.NamedTemporaryFile = BoomFile
        try:
            try:
                atomic_io.atomic_write_text(tmp_path / "handoff.md", "x")
            except RuntimeError:
                pass
        finally:
            atomic_io.NamedTemporaryFile = monkey_orig
        assert list(tmp_path.iterdir()) == []

    def test_finalize_failure_leaves_original(self, tmp_path, monkeypatch):
        from aicomic.utils import atomic_io

        target = tmp_path / "handoff.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(atomic_io.Path, "replace", lambda self, dest: (_ for _ in ()).throw(RuntimeError("disk")))
        try:
            atomic_io.atomic_write_text(target, "new")
        except RuntimeError:
            pass
        assert target.read_text(encoding="utf-8") == "original"
        assert len(list(tmp_path.iterdir())) == 2  # 原文件 + 残留 .tmp（写失败不回滚目标，可诊断）
```

- [x] **步骤 2：运行确认失败**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py::TestAtomicWriteText -v`
预期：ImportError `atomic_write_text`

- [x] **步骤 3：实现**（`src/aicomic/utils/atomic_io.py`，在 `atomic_write_json` 之后追加）

```python
def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """原子写文本文件：写 tmp → fsync → rename。中途异常清理 tmp（BaseException 兜清）。"""
    tmp_path: Path | None = None
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding=encoding, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as f:
            tmp_path = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
        tmp_path = None
    except BaseException:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise
```

（若该文件未 import NamedTemporaryFile/os 则补齐。）

- [x] **步骤 4：运行确认通过**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py tests/test_checkpoint_store.py tests/test_yaml_config_manager.py -v`

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/utils/atomic_io.py tests/test_phase_c_wiring.py
git commit -m "feat: atomic_write_text 原子文本写（handoff.md 前置）"
```

---

### 任务 4：handoff 交接包模块

**文件：** 创建 `src/aicomic/core/handoff.py`；测试追加 `tests/test_phase_c_wiring.py`

- [x] **步骤 1：写失败的测试**（追加到 `tests/test_phase_c_wiring.py` 末尾）

```python
def _stage_rows(episode_code: str, stages: list[str]):
    from aicomic.core.pipeline_coordinator import PipelineCoordinator, ProjectPaths

    coordinator = PipelineCoordinator()
    state_dir = ProjectPaths.state_dir() / "pipeline" / episode_code
    for idx, stage in enumerate(stages):
        if idx > 0:
            coordinator.complete_stage(episode_code, stages[idx - 1], self_review="")
        coordinator.begin_stage(episode_code, stage)
    return coordinator, state_dir


class TestHandoffRecord:
    EPISODE = "handoff_T021"

    def test_record_reflects_real_gate_flow(self):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import ProjectPaths

        stages = [
            "project_setup", "story_bible", "episode_outline", "footage",
            "storyboard", "adr_check", "synthesis", "publish",
        ]
        coordinator, state_dir = _stage_rows(self.EPISODE, stages[:5])  # 1-5 已被代理执行/递进，卡在 storyboard
        record = build_handoff_record(self.EPISODE, coordinator)

        assert record["episode"] == self.EPISODE
        assert record["schema_version"] == 1
        assert record["budget"] == {"status": "unlimited"}
        by_id = {row["stage_id"]: row for row in record["stages"]}
        for sid in stages:
            assert sid in by_id, "八个阶段全须有行"
        assert by_id["project_setup"]["status"] == "completed" and by_id["project_setup"]["human_approved"] is True
        assert by_id["storyboard"]["status"] == "in_progress"
        assert by_id["storyboard"]["requires_human_approval"] is True
        assert by_id["storyboard"]["human_approved"] is False
        assert by_id["publish"]["status"] == "pending"
        assert by_id["synthesis"]["requires_human_approval"] is False and by_id["publish"]["requires_human_approval"] is False
        assert len(record["stages"]) == 8

    def test_completed_non_gate_stage_treated_approved(self):
        from aicomic.core.handoff import build_handoff_record

        coordinator, _ = _stage_rows("handoff_T022", ["project_setup", "story_bible", "footage"])
        coordinator.complete_stage("handoff_T022", "footage", self_review="")
        record = build_handoff_record("handoff_T022", coordinator)
        by_id = {row["stage_id"]: row for row in record["stages"]}
        assert by_id["footage"]["status"] == "completed"
        assert by_id["footage"]["human_approved"] is True

    def test_failed_stage_row(self):
        from aicomic.core.handoff import build_handoff_record

        coordinator, _ = _stage_rows("handoff_T023", ["project_setup"])
        record = build_handoff_record("handoff_T023", coordinator, failed_stage="footage", notes="责任断点：资产生成 §ref-c2")
        assert record["failed_stage"] == "footage"
        err_rows = [row for row in record["stages"] if row["status"] == "failed"]
        assert err_rows and "§ref-c2" in err_rows[0]["notes"]

    def test_budget_section_passthrough(self):
        from aicomic.core.handoff import build_handoff_record
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        budget = {"status": "exceeded", "total_spent_cents": 100}
        record = build_handoff_record("handoff_T024", PipelineCoordinator(), budget=budget)
        assert record["budget"] is budget and record["budget"]["status"] == "exceeded"

    def test_markdown_write(self, tmp_path, monkeypatch):
        import aicomic.core.pipeline_coordinator as pc_mod
        from aicomic.core import handoff

        monkeypatch.setattr(pc_mod.ProjectPaths, "state_dir", classmethod(lambda cls: tmp_path / "state"))
        coordinator = pc_mod.PipelineCoordinator()
        coordinator.begin_stage(self.EPISODE, "project_setup")
        record = handoff.build_handoff_record(self.EPISODE, coordinator, budget={"status": "exceeded", "total_spent_cents": 99})
        md = handoff.render_handoff_markdown(record)
        assert self.EPISODE in md
        assert "| 标志 | 阶段 | 状态 | 需人工 | 已批准 |" in md
        assert "budget 汇报" in md
        target = handoff.write_handoff(md, self.EPISODE, handoff_dir=tmp_path / "handoff")
        content = target.read_text(encoding="utf-8")
        assert "全角标点；代码与命令用半角" in content
```

（信控目录若与 `ProjectPaths.state_dir` 解耦、monkeypatch 不生效，则给本用例换一个专用 episode 前缀隔离即可——底线是不污染其他用例。）

- [x] **步骤 2：运行确认失败**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py::TestHandoffRecord -v`
预期：ImportError `aicomic.core.handoff`

- [x] **步骤 3：实现**（创建 `src/aicomic/core/handoff.py`）

```python
"""交接包（handoff）— SOP 第 8 章/§7.6 的工程化落地。

- 数据层：build_handoff_record() 把信控级机的真实状态（含审批、门禁需求）折叠成
  可序列化的 handoff dict——不读渲染文件系统，全部来自 PipelineCoordinator 状态；
- render_handoff_markdown() 把 record 渲染成可发到企微/飞书群的 markdown 文本；
- write_handoff() 原子写 <state>/handoff/<episode>_handoff.md（内部默认目录由
  ProjectPaths 决定，可显式覆盖），供 C4 Clean 导出与人工续作无缝衔接。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.pipeline_coordinator import ProjectPaths
from aicomic.utils.atomic_io import atomic_write_text


def build_handoff_record(
    episode_code: str,
    coordinator: Any,
    *,
    budget: dict[str, Any] | None = None,
    failed_stage: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    # 语义约定：
    # - completed 非门禁阶段视作"放行"（human_approved=True），不要求每阶段都难过卡点；
    # - failed_stage 有存疑登记：该阶段标记 failed 并把 notes 挂在其备注里（§ref 附录 J 类似续作语义）。
    from aicomic.core.pipeline_coordinator import PIPELINE_STAGES

    rows: list[dict[str, Any]] = []
    for stage in list(PIPELINE_STAGES):
        sid = stage["id"] if isinstance(stage, dict) else str(stage)
        requires = bool(stage.get("requires_human_approval", False)) if isinstance(stage, dict) else False
        checked, started, err = coordinator.get_stage_status(episode_code, sid)
        status = _stage_status(episode_code, sid, checked, started, err)
        approved = False
        if status == "completed":
            approved = coordinator.is_stage_approved(episode_code, sid) or not requires
        elif status == "in_progress" and not requires:
            approved = False
        row: dict[str, Any] = {
            "stage_id": sid,
            "status": status,
            "requires_human_approval": requires,
            "human_approved": approved,
            "notes": None,
        }
        if failed_stage and sid == failed_stage:
            row["status"] = "failed"
            row["notes"] = notes
        rows.append(row)
    return {
        "schema_version": 1,
        "episode": episode_code,
        "stages": rows,
        "budget": dict(budget) if budget else {"status": "unlimited"},
    }


def _stage_status(episode_code: str, sid: str, checked: bool, started: bool, err: Any) -> str:
    if err:
        return "failed"
    if checked:
        return "completed"
    if started:
        return "in_progress"
    return "pending"


def render_handoff_markdown(record: dict[str, Any]) -> str:
    lines: list[str] = [f"# 交接包：{record['episode']}", ""]
    if record.get("failed_stage"):
        lines += [f"- 责任断点：`{record['failed_stage']}`（续作入口：begin_stage 该阶段直接重跑）", ""]
    budget = record.get("budget") or {}
    lines += [f"- budget 汇报：status={budget.get('status')}", ""]
    lines += ["| 标志 | 阶段 | 状态 | 需人工 | 已批准 |", "| --- | --- | --- | --- | --- |"]
    for row in record.get("stages", []):
        flag = "⚠" if (row["status"] == "failed" or row["status"] == "awaiting_human" or (row["requires_human_approval"] and not row["human_approved"])) else "　"
        lines.append(f"| {flag} | {row['stage_id']} | {row['status']} | {row['requires_human_approval']} | {row['human_approved']} |")
    lines += [
        "",
        "## 交接要点（定稿文案，直接落入实现）",
        "",
        "- 中文文档用全角标点；代码与命令用半角（《中文文案排版指北》口径）。",
        "- 引用 SOP 章节保留 `§x.y` 原编号；示例命令须可直接执行。",
        "- 本文件由 show-handoff / ShowAgent 出口自动生成；人工续作以上表 ⚠ 行为准。",
        "",
        "## 续作指引",
        "",
        "- 续作入口：`acomic show-run <episode> --confirm-live`（预算哨兵默认读 `AICOMIC_BUDGET_CENTS`）。",
        "- checkpoint status=failed 的阶段：begin_stage 该阶段即可重跑（CHECKPOINT_FAILED 语义）。",
        "- 平台发布当前 disabled：按 SOP §10 #2 逐平台手动入审，shim 留给发布阶段实现。",
        "",
    ]
    return "\n".join(lines) + "\n"


def handoff_path(episode_code: str, handoff_dir: Path | None = None) -> Path:
    directory = handoff_dir if handoff_dir is not None else ProjectPaths.state_dir() / "handoff"
    return directory / f"{episode_code}_handoff.md"


def write_handoff(markdown: str, episode_code: str, *, handoff_dir: Path | None = None) -> Path:
    target = handoff_path(episode_code, handoff_dir)
    atomic_write_text(target, markdown)
    return target
```

**注意事项（写实现时执行）：**
1) 上面的实现代码片段不是逐行定稿，而是带注释的骨架定稿：`PIPELINE_STAGES` / `get_stage_status` / `is_stage_approved` / `requires_human_approval` 的真实 API 以 `src/aicomic/core/pipeline_coordinator.py` 为准，落码时按真实形状校正。
2) 表头与"交接要点/续作指引"为定稿文案（测试断言与之对应），无占位。

- [x] **步骤 4：运行确认通过**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py::TestHandoffRecord -v`（若信控签名与断言冲突，读信控源码校正测试/实现，以真实 API 为准）

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/core/handoff.py tests/test_phase_c_wiring.py
git commit -m "feat: handoff 交接包模块（级机状态→markdown 原子写）"
```

---

### 任务 5：ShowAgent 编排核心

**文件：** 创建 `src/aicomic/core/show_agent.py`；测试创建 `tests/test_show_agent.py`

- [x] **步骤 1：写失败的测试**（创建 `tests/test_show_agent.py`）

```python
"""ShowAgent 编排测试（SOP 第 6 章 Transformer 闭环 → agent 编排落地）。"""
from __future__ import annotations


def _manifest(episode_code: str) -> dict:
    return {
        "series_title": "测试剧集",
        "episode_code": episode_code,
        "logline": "测试",
        "characters": [],
        "scene_count": 1,
        "scenes": [{"id": "S01", "summary": "测试场景 1", "location": "测试地点", "characters": [], "beats": []}],
    }


def _agent(tmp_path, **kw):
    from aicomic.core.show_agent import ShowAgent

    # 显式 state_dir=tmp_path：与真实 ProjectPaths.state_dir() 隔离
    return ShowAgent(state_dir=tmp_path, **kw)


class TestNeedsInput:
    def test_missing_render_plan_needs_input(self, tmp_path):
        agent = _agent(tmp_path)
        result = agent.run_until_human("needs_input_T033", {"synthesis": {"audio_file": ""}, "preview": {"render_plan": ""}})
        assert result.stop_reason == "needs_input"


class TestRunsAndStops:
    def test_runs_to_gate_and_requests_approval(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        inputs = {
            "footage": {"shotlist": _manifest("showagent_T034")["scene_count"] * [{"beat": "xb"}]},
            "storyboard": {"episode_manifest": _manifest("showagent_T034")},
        }
        agent = _agent(tmp_path)
        result = agent.run_until_human("showagent_T034", inputs)
        assert result.stop_reason == "awaiting_human"
        assert result.current_stage == "storyboard"
        checkpoint = sa.read_checkpoint(tmp_path, "showagent_T034", "storyboard")
        assert checkpoint["stage"] == "storyboard"
        assert checkpoint["status"] == "awaiting_human"

    def test_card_gate_not_replayed(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        inputs = {
            "footage": {"shotlist": [{"beat": "b"}]},
            "storyboard": {"episode_manifest": _manifest("gate_T036")},
        }
        agent = _agent(tmp_path)
        first = agent.run_until_human("gate_T036", inputs)
        assert first.stop_reason == "awaiting_human" and first.current_stage == "storyboard"

        witnessed: list[str] = []
        real_begin = agent.coordinator.begin_stage

        def spy_begin(episode_code, stage_id):
            witnessed.append(stage_id)
            return real_begin(episode_code, stage_id)

        monkeypatch.setattr(agent.coordinator, "begin_stage", spy_begin)
        second = agent.run_until_human("gate_T036", inputs)
        assert second.stop_reason == "awaiting_human" and second.current_stage == "storyboard"
        assert "storyboard" not in witnessed  # gate 防重放：停在审批点的阶段不得再 begin_stage

    def test_resumes_after_approval(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        inputs = {
            "footage": {"shotlist": [{"beat": "b"}]},
            "storyboard": {"episode_manifest": _manifest("gate_T035")},
            "preview": {"render_plan": {"scene_count": 0, "render_plan": []}},
        }
        agent = _agent(tmp_path)
        first = agent.run_until_human("gate_T035", inputs)
        assert first.stop_reason == "awaiting_human"
        # 批准注入（approve API 或审批存储——按信控真实 API 选其一）
        agent.coordinator.approve_stage("gate_T035", "storyboard", operator="USER")
        second = agent.run_until_human("gate_T035", inputs)
        assert second.stop_reason == "all_completed"
        checked, started = agent.coordinator.get_stage_status("gate_T035", "storyboard")
        assert checked

    def test_stage_failure_writes_failed_checkpoint(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        inputs = {"footage": {"shotlist": [{"beat": "b"}]}, "storyboard": {"episode_manifest": _manifest("failed_T041")}}
        agent = _agent(tmp_path)

        def boom(_self, stage_id, episode_code, stage_inputs, live=False):
            assert stage_id == "storyboard"
            raise RuntimeError("kaboom")

        monkeypatch.setattr(sa.ShowAgent, "_dispatch", boom)
        result = agent.run_until_human("failed_T041", inputs)
        assert result.stop_reason == "failed"
        checkpoint = sa.read_checkpoint(tmp_path, "failed_T041", "storyboard")
        assert checkpoint["status"] == "failed"


class TestExecuteLive:
    def test_budget_stopped(self, tmp_path, monkeypatch):
        import aicomic.core.show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        monkeypatch.setattr(sa, "build_provider_requests", lambda *a, **k: {"requests": [], "jobs": []})
        monkeypatch.setattr(sa, "execute_provider_requests", lambda *a, **k: {"stopped_by_budget_guard": True})
        inputs = {"preview": {"render_plan": {"scene_count": 0, "render_plan": []}}}
        result = _agent(tmp_path).run_until_human("budget_T043", inputs, live=True)
        assert result.stop_reason == "budget_stopped"

    def test_live_success_chain(self, tmp_path, monkeypatch):
        import aicomic.core.show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        monkeypatch.setattr(sa, "build_provider_requests", lambda *a, **k: {"requests": [], "jobs": []})
        monkeypatch.setattr(sa, "execute_provider_requests", lambda *a, **k: {"stopped_by_budget_guard": False})
        inputs = {"preview": {"render_plan": {"scene_count": 0, "render_plan": []}}}
        agent = _agent(tmp_path)
        monkeypatch.setattr(agent.coordinator, "execute_publish_pack", lambda *a, **k: {})
        result = agent.run_until_human("liveok_T043", inputs, live=True)
        assert result.stop_reason == "all_completed"
```

（核心 10 用例：needs_input ×1；runs/gate 防重放/批准续作/失败落账 ×4；execute_live kill/成功链 ×2；其余为 handoff 出口（任务 6）。`read_checkpoint/approve_stage/execute_publish_pack` 的存在性与签名以 checkpoint_store/信控真实源码为准——不匹配处在不改红线的前提下就地校正 monkeypatch 注入点。）

- [x] **步骤 2：运行确认失败**

`.venv/bin/python -m pytest tests/test_show_agent.py -v`
预期：ImportError `show_agent`

- [x] **步骤 3：核心实现**（创建 `src/aicomic/core/show_agent.py`）

```python
"""ShowAgent — SOP 第 6 章『多 Agent 编排（Transformer 闭环）』的工程化落地。

定位：把编排者+执行器收敛成单个 CLI 可驱动的入口：用 PipelineCoordinator 的
状态机逐阶段推进，直到人工卡点（awaiting_human / needs_input）、预算拦截
（budget_stopped）、失败（failed）或全部完成（all_completed）。

- 不越过现有任何单守门人（budget_sentinel/quality_gate/drift_gate 原样调用）；
- gate-protection（规格 §8 红线4）：checkpoint status=awaiting_human 或 级机 gate
  完成-未批准时**不得 begin_stage 重放**（重复烧成本/重复人工）；
- 异常路径与 budget kill 必须显式写 checkpoint=failed，不得静默吞错。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.core.pipeline_coordinator import (
    CHECKPOINT_FAILED, CHECKPOINT_IN_PROGRESS, PipelineCoordinator,
)
from aicomic.core.checkpoint_store import read_checkpoint, write_checkpoint

PASSTHROUGH_STAGES = {"project_setup", "story_bible", "episode_outline"}


class ShowRunResult:
    def __init__(self, stop_reason: str, current_stage: str = "", message: str = "") -> None:
        self.stop_reason = stop_reason
        self.current_stage = current_stage
        self.message = message
        self.body: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"ShowRunResult(stop_reason={self.stop_reason!r}, current_stage={self.current_stage!r})"


class _NeedsInput(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class ShowAgent:
    def __init__(
        self,
        state_dir: str | Path = "",
        *,
        coordinator: Any | None = None,
        budget_sentinel: Any | None = None,
        budget: dict[str, Any] | None = None,
        providers_config_path: Any | None = None,
        output_root: Any | None = None,
        handoff_writer: Any | None = None,
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir else ProjectPaths.state_dir()
        self.coordinator = coordinator if coordinator is not None else self._default_coordinator()
        self.budget_sentinel = budget_sentinel
        self.budget = budget if budget is not None else self._budget_snapshot()
        self.providers_config_path = providers_config_path
        self.output_root = output_root
        self.handoff_writer = handoff_writer
        self._last_budget_stop = False

    def _default_coordinator(self) -> Any:
        # PipelineCoordinator 构造签名以真实源码为准；若不接受 state_dir 就退回无参构造
        try:
            return PipelineCoordinator(state_dir=str(self.state_dir))
        except TypeError:
            return PipelineCoordinator()

    def _budget_snapshot(self) -> dict[str, Any]:
        if self.budget_sentinel is None:
            return {"status": "unlimited"}
        status = self.budget_sentinel.dashboard.get_budget_status()
        return {
            "status": getattr(status, "status", "unknown"),
            "total_spent_cents": getattr(status, "total_spent_cents", 0),
            "total_budget_cents": getattr(status, "total_budget_cents", 0),
            "generation_count": getattr(status, "generation_count", 0),
        }
```

（`ProjectPaths` 由 pipeline_coordinator 顶部 import 补齐；`CHECKPOINT_IN_PROGRESS` 仅在 needs_input 出口如需落账时使用，否则从 import 中删除。）

**落码规则（细节以规格为准）：**
1) 构造器已在上面定稿（含 `_budget_snapshot`）；其余落码工作 = `_dispatch` 分发表 + `run_until_human` 主循环 + 四出口 handoff 挂钩。
2) `_dispatch(stage, episode_code, inputs, live, budget_sentinel)`：构建 `per-stage` 分发：

- project_setup/story_bible → 信控现无专用 execute 方法（透传阶段）：begin 后按既有逻辑落 complete；若后续信控补了专用 execute 方法则优先调用
- episode_outline → coordinator.execute_episode_outline（模板驱动）
- footage → coordinator.execute_shot_breakdown
- storyboard → coordinator.execute_storyboard_generation
- synthesis → coordinator.execute_tts_subtitle
- preview → coordinator.execute_preview_render（execute_live 时才链 provider requests）
- publish → coordinator.execute_publish_pack

3) run_until_human 主循环（最终版）：

```python
    def run_until_human(self, episode_code: str, inputs: dict[str, Any], *, live: bool = False) -> ShowRunResult:
        coordinator = self.coordinator
        try:
            for stage in coordinator.stage_list():
                stage_id = stage["id"]
                requires = coordinator.stage_requires_human_approval(stage_id)
                checked, started = coordinator.get_stage_status(episode_code, stage_id)
                started = bool(started)
                if checked:
                    approved = coordinator.is_stage_approved(episode_code, stage_id) if requires else True
                    if not approved:
                        # gate-protection：不 begin_stage 重放 await 中的审批点
                        return ShowRunResult("awaiting_human", stage_id, "gate-unapproved")
                    continue
                if started:
                    cp = coordinator.checkpoint_status(episode_code, stage_id)  # 返回 dict 或 None；签名以现实为准
                    if cp and cp.get("status") == "awaiting_human":
                        return ShowRunResult("awaiting_human", stage_id, "checkpoint-awaiting")
                coordinator.begin_stage(episode_code, stage_id)
                try:
                    self._dispatch(stage_id, episode_code, inputs, live)
                    if requires and not coordinator.stage_completed(episode_code, stage_id):
                        pass  # 信控已把 status 写成 awaiting_human
                    result_stage_bundle = coordinator.complete_stage(episode_code, stage_id, self_review="")
                    self._last_stage = (stage_id, result_stage_bundle)
                except _NeedsInput as exc:
                    return ShowRunResult("needs_input", stage_id, exc.key)
                except Exception as exc:
                    write_checkpoint(self.state_dir, episode_code, stage_id, CHECKPOINT_FAILED, metadata={"error": repr(exc), "budget_status": self._budget_status()})
                    return ShowRunResult("failed", stage_id, repr(exc))
                if live and stage_id == "preview":
                    if getattr(self, "_last_budget_stop", False):
                        write_checkpoint(self.state_dir, episode_code, stage_id, CHECKPOINT_FAILED, metadata={"error": "budget_stopped", "budget_status": self._budget_status()})
                        return ShowRunResult("budget_stopped", stage_id, "live-provider-budget-kill")
            return ShowRunResult("all_completed")
        except Exception as exc:  # 兜底
            return ShowRunResult("failed", "", repr(exc))
```

（`coordinator.stage_list()`/`stage_requires_human_approval`/`checkpoint_status` 等名字以 `aicomic.core.pipeline_coordinator` 实际 API 为准（已确认过 begin/complete/approve/status 族），不匹配处按真实 API 微调。）

4) `_dispatch("preview", …, live=True)` 的次序：先取 `inputs["preview"]["render_plan"]`；缺则用 `inputs["storyboard"]["episode_manifest"]` 经 `build_render_plan(manifest, episode_code, output_root)` 现算；两皆缺则 `raise _NeedsInput("preview.render_plan")`。live 时把产物交给 `build_provider_requests(manifest, jobs, providers_config_path, output_root)` 构建，再 `execute_provider_requests(…, confirm_live=True, budget_sentinel=self.budget_sentinel)`；报告落地 `self._last_budget_stop = bool(report.get("stopped_by_budget_guard"))`。
5) checkpoint 状态用 `checkpoint_store` 的真实常量名与读写签名（上面引用的 `CHECKPOINT_FAILED`/`CHECKPOINT_IN_PROGRESS` 以实际为准）。
6) state 触发器与启动信控一致用 `ProjectPaths.state_dir()`（除非显式 `state_dir`）。

- [x] **步骤 4：运行确认通过**

`.venv/bin/python -m pytest tests/test_show_agent.py -v` → 全部 passed（签名不符处在不改信控既有行为约束下微调）

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/core/show_agent.py tests/test_show_agent.py
git commit -m "feat: ShowAgent 编排核心（级机驱动 run_until_human + gate 防重放）"
```

---

### 任务 6：ShowAgent 收尾（handoff 接入 + CLI show-run/show-handoff）

**文件：** 修改 `src/aicomic/core/show_agent.py`、`src/aicomic/cli/main.py`；测试追加 `tests/test_show_agent.py`、`tests/test_cli_main.py`

- [x] **步骤 1：失败测试**（追加到 `tests/test_show_agent.py`）

```python
class TestHandoffWriting:
    def test_writes_handoff_on_awaiting_exit(self, tmp_path, monkeypatch):
        from aicomic.core import show_agent as sa

        monkeypatch.setattr(sa, "build_manifest_from_template", lambda ep, om=None: _manifest(ep))
        agent = _agent(tmp_path)
        result = agent.run_until_human(
            "handoff_T044",
            {"footage": {"shotlist": "[{'beat': 'xb'}]"}, "storyboard": {"episode_manifest": _manifest("handoff_T044")}},
        )
        assert result.stop_reason == "awaiting_human"
        md_file = tmp_path / "handoff" / "handoff_T044_handoff.md"
        assert md_file.exists()
        body = md_file.read_text(encoding="utf-8")
        assert "budget 汇报" in body
```

（核心断言 = 文件存在 + budget 段在场；不需要额外 helper。）

CLI 失败测试（追加到 `tests/test_cli_main.py`；handler 层直调，不测 argparse 装配——装配本身走代码复审）：

```python
import types
from aicomic.core.pipeline_coordinator import ProjectPaths


class TestShowCommands:
    def test_show_run_wires_agent(self, tmp_path, monkeypatch, capsys):
        from aicomic.cli import main as cli_main

        captured: dict = {}

        class _FakeAgent:
            def __init__(self, state_dir=None, **kw):
                captured["init"] = kw

            def run_until_human(self, episode_code, inputs, live=False):
                captured["ep"], captured["inputs"] = episode_code, inputs
                result = types.SimpleNamespace()
                result.stop_reason, result.current_stage, result.message, result.body = "awaiting_human", "storyboard", "", {}
                return result

        monkeypatch.setattr(cli_main, "ShowAgent", _FakeAgent)
        out = tmp_path / "r.json"
        rc = cli_main.handle_show_run(
            tmp_path / "products.json", tmp_path / "providers.yaml", "kling", True, 0, 1, out, 50, "showrun_T046",
        )
        assert rc == 0
        assert captured["ep"] == "showrun_T046"
        assert captured["inputs"]["budget_cents"] == 50
        body = json.loads(out.read_text(encoding="utf-8"))
        assert body["stop_reason"] == "awaiting_human"
        assert "stop_reason=" in capsys.readouterr().out

    def test_show_handoff_writes_file(self, tmp_path, monkeypatch, capsys):
        from aicomic.cli import main as cli_main

        monkeypatch.setattr(ProjectPaths, "state_dir", classmethod(lambda cls: tmp_path))
        rc = cli_main.handle_show_handoff("showhand_T047", None)
        assert rc == 0
        target = tmp_path / "handoff" / "showhand_T047_handoff.md"
        assert target.exists()
        assert str(target) in capsys.readouterr().out
```

（`test_cli_main.py` 若缺 `import json` 则补。）

- [x] **步骤 2：运行确认失败**

`.venv/bin/python -m pytest tests/test_show_agent.py::TestHandoffWriting tests/test_cli_main.py::TestShowCommands -v`
预期：红（`test_writes_handoff_on_awaiting_exit` 的 md 文件不存在断言失败；CLI 两条 AttributeError 无 handle_show_run/handle_show_handoff）

- [x] **步骤 3：show_agent 收尾实现**

1) 任务 5 的构造器已含 `budget` 与 `handoff_writer`；本任务新增共用出口 helper `_write_handoff_quiet`（语义：写交接包 markdown 到 `handoff_dir`；`handoff_writer` 非空则走注入替身）。`self.budget = self._budget_snapshot()` 已在构造器完成（`dashboard.get_budget_status()` 转 dict：`status`/`total_spent_cents`/`total_budget_cents`/`generation_count`）。
2) `run_until_human` 四出口（awaiting_human / failed / budget_stopped / all_completed）在 return 前统一调：

```python
    def _write_handoff_quiet(self, episode_code: str) -> None:
        try:
            from aicomic.core.handoff import build_handoff_record, render_handoff_markdown, write_handoff

            record = build_handoff_record(
                episode_code, self.coordinator, budget=self.budget,
                failed_stage=self._last_stage_id if isinstance(getattr(self, "_last_stop_reason", ""), str) and self._last_stop_reason == "failed" else None,
            )
            text = render_handoff_markdown(record)
            if self.handoff_writer is not None:
                self.handoff_writer(text, episode_code)
            else:
                write_handoff(text, episode_code, handoff_dir=self.state_dir / "handoff")
        except Exception:
            pass  # 交接包写失败不反噬主流程
```

落码实现不必保留 `_last_result_stop/_last_stage_id` 这类中间名——直接把上面主循环的每个 return 点改成 `出参 = ShowRunResult(...); self._write_handoff_quiet(episode_code); return 出参`，failed 出口在 `build_handoff_record(failed_stage=stage_id, notes=…)` 以真实 stage_id 传入（签名按真实 API 校正）。

3) CLI（`src/aicomic/cli/main.py`）：

```python
def handle_show_run(rr: Path, pc: Path, pr: str, cl: bool, mf: int, out: Path, budget_cents: int = 0, episode: str = "") -> int:
    if budget_cents <= 0:
        try:
            budget_cents = int(os.environ.get("AICOMIC_BUDGET_CENTS", "0"))
        except ValueError:
            budget_cents = 0
        if budget_cents < 0:
            budget_cents = 0
    budget_sentinel = None
    if budget_cents > 0:
        from aicomic.core.budget_sentinel import BudgetSentinel
        from aicomic.core.cost_dashboard import CostDashboard

        budget_sentinel = BudgetSentinel(CostDashboard(storage_dir=str(ProjectPaths.state_dir() / "costs"), budget_cents=budget_cents))
    episode = episode or rr.stem or "show_run"
    inputs: dict[str, Any] = {"providers_config": str(pc), "budget_cents": budget_cents}
    agent = ShowAgent(state_dir=ProjectPaths.state_dir(), budget_sentinel=budget_sentinel, providers_config_path=pc)
    result = agent.run_until_human(episode, inputs, live=cl, max_failures=mf)
    report = {
        "episode": episode,
        "stop_reason": result.stop_reason,
        "current_stage": result.current_stage,
        "stage_result": result.body,
    }
    report_path = out if out is not None else ProjectPaths.state_dir() / "show_run_report.json"
    atomic_write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for key in ("episode", "stop_reason", "current_stage"):
        print(f"{key}={report.get(key)}")
    print(f"output={report_path}")
    return 0 if result.stop_reason in {"awaiting_human", "all_completed", "budget_stopped"} else 1
```

说明：`show-run` 不再重复 provider 执行接线——provider 请求链由 agent 的 `_dispatch(preview/synthesis, live=True)` 内部走 `execute_provider_requests`（与任务 5 一致的门控/哨兵语义）；`--providers/--max-failures` 参数保留 CLI 兼容（`pr` 当前仅透传记录，`mf` 走 `run_until_human(max_failures=…)` 断言）。cli/main.py 顶部需补 `from aicomic.core.show_agent import ShowAgent`（模块级 import，测试的 monkeypatch 点 = `cli_main.ShowAgent`）；`atomic_write_text`/`json`/`os` 按 cli/main.py 现有 import 情况补齐。`run_until_human` 增形参 `max_failures: int = 1`（内部未用也先接住 CLI）。

```python
def handle_show_handoff(episode: str, handoff_dir: Path | None = None) -> int:
    from aicomic.core.handoff import build_handoff_record, render_handoff_markdown, write_handoff
    from aicomic.core.pipeline_coordinator import PipelineCoordinator

    record = build_handoff_record(episode, PipelineCoordinator(), budget=_budget_from_dashboard())
    target = write_handoff(render_handoff_markdown(record), episode, handoff_dir=handoff_dir)
    print(f"handoff={target}")
    return 0
```

（`_budget_from_dashboard()`：读 `<state>/costs` 目录的 dashboard（无预算文件则 `{"status": "unlimited"}`），存在性/构造签名与 `CostDashboard` 真实 API 对齐；show-handoff 必带 episode 位置参数，REGISTRY `args` 即下方两目。）

REGISTRY 两条新目条（跟随现有 lazy/lambda 风格）：

```python
    "show-run": {
        "help": "run pipeline until human gate / budget stop (builds provider requests from products report)",
        "args": [
            (["products_report"], {}),
            (["--providers-config"], {"type": Path, "default": None}),
            (["--providers"], {"default": ""}),
            (["--confirm-live"], {"action": "store_true"}),
            (["--max-failures"], {"type": int, "default": 1}),
            (["--output"], {"type": Path, "default": None}),
            (["--budget-cents"], {"type": int, "default": 0}),
            (["--episode"], {"default": ""}),
        ],
        "handler": lambda a: handle_show_run(a.products_report, a.providers_config, a.providers, a.confirm_live, a.max_failures, a.output, a.budget_cents, a.episode),
    },
    "show-handoff": {
        "help": "write markdown handoff bundle for an episode from current state_dir",
        "args": [(["episode"], {}), (["--handoff-dir"], {"type": Path, "default": None})],
        "handler": lambda a: handle_show_handoff(a.episode, a.handoff_dir),
    },
```

- [x] **步骤 4：运行确认通过 + 回归**

`.venv/bin/python -m pytest tests/test_show_agent.py tests/test_cli_main.py tests/test_pipeline_coordinator.py -v`

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/core/show_agent.py src/aicomic/cli/main.py tests/test_show_agent.py tests/test_cli_main.py
git commit -m "feat: ShowAgent 交接包接入 + CLI show-run/show-handoff"
```

---

### 任务 7：ai_label 合规模块

**文件：** 创建 `src/aicomic/video_synthesis/ai_label.py`；测试创建 `tests/test_ai_label.py`

- [x] **步骤 1：失败测试**（创建 `tests/test_ai_label.py`）

```python
"""AI 合规标识统一测试（SOP §10 #7 合规四向联测）。"""
from __future__ import annotations

import json
from pathlib import Path


def _stub_probe_video(tmp_path) -> Path:
    video = tmp_path / "dummy.mp4"
    video.write_bytes(b"0" * 64)
    return video


class TestEmbedAiLabel:
    def test_remux_carries_metadata_tags(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []
        monkeypatch.setattr(ai, "_run_ffmpeg", lambda cmd: (recorded.append(cmd), 0)[1])
        out = ai.embed_ai_label(video, tmp_path / "out.mp4")
        cmd = recorded[0]
        assert out.name == "out.mp4"
        for frag in ("-c", "copy", "-map_metadata", "0", "-movflags", "+faststart"):
            assert frag in cmd, frag
        for tag in ("ai_generated=true", "ai_generator=AIComics"):
            assert tag in cmd
        assert "comment=" in " ".join(cmd)

    def test_missing_input_raises(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        try:
            ai.embed_ai_label(tmp_path / "nope.mp4")
        except (RuntimeError, FileNotFoundError) as exc:
            assert "不存在" in str(exc)
        else:
            raise AssertionError("应 raise：文件不存在必须显式失败")

    def test_watermark_mode_uses_drawtext(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []
        monkeypatch.setattr(ai, "_run_ffmpeg", lambda cmd: (recorded.append(cmd), 0)[1])
        ai.embed_ai_label(video, watermark=True)
        assert "drawtext" in " ".join(recorded[0]) and "-vf" in recorded[0]

    def test_video_passthrough_default(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []
        monkeypatch.setattr(ai, "_run_ffmpeg", lambda cmd: (recorded.append(cmd), 0)[1])
        result_path = ai.embed_ai_label(video)
        assert result_path == video.resolve() or result_path == video


class TestAiLabelPresent:
    def test_tags_and_negatives(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        def fake_probe(cmd):
            out = cmd[-1]
            __import__("pathlib").Path(out).write_text(json.dumps({"format": {"tags": {"ai_generated": "true"}}}), encoding="utf-8")
            return 0

        monkeypatch.setattr(ai, "_run_probe", fake_probe)
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is True

        monkeypatch.setattr(ai, "_run_probe", lambda cmd: 1)
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is False

        assert ai.ai_label_present(tmp_path / "missing.mp4") is False
```

（`_stub_probe_video` 在文件头已定义（dummy.mp4 bytes）；三个断言分别打 tags 命中 / rc!=0 / 文件不存在。ffprobe fake 向 `cmd[-1]` 落 json 的约定需与实现的 probe 输出方式一致（`-o` 子文件或 stdout 回显，落码时对齐其一）。）

- [x] **步骤 2：运行确认失败**

`ModuleNotFoundError: aicomic.video_synthesis.ai_label`

- [x] **步骤 3：实现**（创建 `src/aicomic/video_synthesis/ai_label.py`）

```python
"""AI 合规标识（SOP §10 监管合规 #7）。默认不可见元数据，可选可见水印。

- 不重编码地改写 mp4 元数据：ffmpeg -c copy -map_metadata 0 + -metadata（追加语义）；
- 不清原生 metadata（`-map_metadata 0` 全保留，AI 三标签覆盖式写入）；
- ai_generated=true 是机检锚点（ai_label_present / 平台 shim），comment 是人读一句；
- ffmpeg 失败 → RuntimeError（调用方决定 fail-soft），tmp 清理后重命名，永不假绿。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

AI_METADATA_TAGS = {
    "ai_generated": "true",
    "comment": "本内容由AI生成（AIComics）",
    "ai_generator": "AIComics",
}
DEFAULT_WATERMARK_TEXT = "本内容为AI生成"


def _run_ffmpeg(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _run_probe(cmd: list[str]) -> int:
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _ffmpeg_bin(ffmpeg_bin: str | Path | None = None) -> str:
    if ffmpeg_bin:
        return str(ffmpeg_bin)
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _ffprobe_bin(ffprobe_bin: str | Path | None = None) -> str:
    if ffprobe_bin:
        return str(ffprobe_bin)
    try:
        return str(Path(_ffmpeg_bin(None)).with_name("ffprobe"))
    except Exception:
        return "ffprobe"


def embed_ai_label(
    video_path: str | Path,
    output_path: str | Path | None = None,
    *,
    watermark: bool = False,
    watermark_text: str = DEFAULT_WATERMARK_TEXT,
    ffmpeg_bin: str | Path | None = None,
) -> Path:
    src = Path(video_path)
    if not src.exists():
        raise RuntimeError(f"input video 不存在: {src}")
    target = Path(output_path) if output_path is not None else src
    tmp_out = target.with_name(f".{target.name}.ailabel.tmp.mp4")
    cmd = [_ffmpeg_bin(ffmpeg_bin), "-y", "-i", str(src)]
    if watermark:
        text = watermark_text.replace(":", "\\:")
        cmd += [
            "-vf",
            f"drawtext=text='{text}':fontsize=28:fontcolor=white@0.8:box=1:boxcolor=black@0.35:boxborderw=12:x=(w-tw)/2:y=h-th-56",
        ]
    cmd += ["-map", "0", "-map_metadata", "0"]
    for key, value in AI_METADATA_TAGS.items():
        cmd += ["-metadata", f"{key}={value}"]
    cmd += ["-c", "copy", "-movflags", "+faststart", str(tmp_out)]
    rc = _run_ffmpeg(cmd)
    if rc != 0:
        try:
            if tmp_out.exists():
                tmp_out.unlink()
        except OSError:
            pass
        raise RuntimeError(f"ffmpeg 写 AI 标识失败（rc={rc}）")
    tmp_out.replace(target)
    return target


def ai_label_present(video_path: str | Path, *, ffprobe_bin: str | Path | None = None) -> bool:
    video = Path(video_path)
    if not video.exists():
        return False
    probe_out = video.with_name(f".{video.name}.ailabel.probe.json")
    try:
        cmd = [_ffprobe_bin(ffprobe_bin), "-show_format", "-of", "json", str(video), "-o", str(probe_out)]
        rc = _run_probe(cmd)
        data: dict[str, Any] = {}
        if rc == 0 and probe_out.exists():
            data = json.loads(probe_out.read_text(encoding="utf-8"))
        tags = ((data.get("format") or {}).get("tags") or {})
        return str(tags.get("ai_generated", "")).lower() == "true"
    except Exception:
        return False
    finally:
        try:
            if probe_out.exists():
                probe_out.unlink()
        except OSError:
            pass
```

（注意：`ffprobe` 不一定有 `-o`——若实测报错，改用 `capture_output` 阶段 stdout+`json.loads(stdout)`，测试 fake 里读 `cmd` 断言 `-show_format` 即可，写成与实现一致。）

- [x] **步骤 4：运行确认通过**

`.venv/bin/python -m pytest tests/test_ai_label.py -v`（本测试 monkeypatch `_run_ffmpeg/_run_probe`，不依赖真实 ffmpeg）

- [x] **步骤 5：Commit**

```bash
git add src/aicomic/video_synthesis/ai_label.py tests/test_ai_label.py
git commit -m "feat: AI 合规标识模块（remux 元数据 + ffprobe 校验 + 可选水印）"
```

---

### 任务 8：release 自动标识 + CLI ai-label 命令

**文件：** 修改 `src/aicomic/render/release_renderer.py`、`src/aicomic/cli/main.py`；测试追加 `tests/test_phase_c_wiring.py`（新类 `TestReleaseAiLabel`）与 `tests/test_cli_main.py`

- [x] **步骤 1：失败测试**（追加到 `tests/test_phase_c_wiring.py`）

```python
class TestReleaseAiLabel:
    EPISODE = "released_T048"

    def test_embed_invoked_on_success(self, tmp_path, monkeypatch):
        import aicomic.render.release_renderer as rr

        video = tmp_path / "released.mp4"
        video.write_bytes(b"0" * 32)
        fake_render = {"video_path": str(video), "scene_count": 1, "status": "ok"}
        monkeypatch.setattr(rr, "render_preview_video", lambda *a, **k: fake_render)
        monkeypatch.setenv("AICOMIC_AI_LABEL", "1")
        called: list = []
        monkeypatch.setattr(rr, "embed_ai_label", lambda p: called.append(p))
        report = rr.render_release_report(tmp_path / "manifest.json", tmp_path, "release")
        assert report.get("ai_label", {}).get("status") == "embedded"
        assert called

    def test_env_zero_skips_and_unavailable_env_other(self, tmp_path, monkeypatch):
        import aicomic.render.release_renderer as rr

        video = tmp_path / "released.mp4"
        video.write_bytes(b"0" * 32)
        fake_render = {"video_path": str(video), "scene_count": 1, "status": "ok"}
        monkeypatch.setattr(rr, "render_preview_video", lambda *a, **k: fake_render)
        monkeypatch.setenv("AICOMIC_AI_LABEL", "0")
        called: list = []
        monkeypatch.setattr(rr, "embed_ai_label", lambda p: called.append(p))
        rr.render_release_report(tmp_path / "manifest.json", tmp_path, "release")
        assert called == []

    def test_embed_error_is_recorded_not_raised(self, tmp_path, monkeypatch):
        import aicomic.render.release_renderer as rr

        video = tmp_path / "released.mp4"
        video.write_bytes(b"0" * 32)
        fake_render = {"video_path": str(video), "scene_count": 1, "status": "ok"}
        monkeypatch.setattr(rr, "render_preview_video", lambda *a, **k: fake_render)
        monkeypatch.setenv("AICOMIC_AI_LABEL", "1")

        def boom(_p):
            raise RuntimeError("disk 9% full")

        monkeypatch.setattr(rr, "embed_ai_label", boom)
        report = rr.render_release_report(tmp_path / "manifest.json", tmp_path, "release")
        assert report["ai_label"] == {"status": "error"}
```

（若真实入口/参数 ≠ `render_release_report(manifest, out_root, profile)`，读 `src/aicomic/render/release_renderer.py` 现名代入；`render_preview_video` stub 参数同理对齐真实签名。）

CLI 失败测试（追加 `tests/test_cli_main.py`）：

```python
class TestAiLabelCommands:
    def test_embed_command(self, tmp_path, monkeypatch):
        from aicomic.cli import main as cli_main

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 16)
        called: dict = {}
        monkeypatch.setattr(
            cli_main,
            "ai_label_embed",
            lambda p, o=None, wm=False: called.update(p=p, o=o, wm=wm),
        )
        assert cli_main.handle_ai_label_embed(video, None, False) == 0
        assert called["p"] == video and called["wm"] is False

    def test_check_command_rc_and_print(self, tmp_path, monkeypatch, capsys):
        from aicomic.cli import main as cli_main

        monkeypatch.setattr(cli_main, "ai_label_check", lambda p: True)
        assert cli_main.handle_ai_label_check(tmp_path / "v.mp4") == 0
        assert "ai_label=embedded" in capsys.readouterr().out
        monkeypatch.setattr(cli_main, "ai_label_check", lambda p: False)
        assert cli_main.handle_ai_label_check(tmp_path / "v.mp4") == 1
        assert "ai_label=missing" in capsys.readouterr().out
```

（Patch 点策略：CLI handler 内 lazy import，`handle_ai_label_embed/check` 采用与测试同名的薄壳——`ai_label_embed(p, o, wm)`/`ai_label_check(p)` 为模块级薄函数直接转发，测试 patch 薄壳；保持 lazy import 的注册风格同时 patch 点稳定。）

- [x] **步骤 2：运行确认失败**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py::TestReleaseAiLabel tests/test_cli_main.py::TestAiLabelCommands -v`

- [x] **步骤 3：release 接线**（`src/aicomic/render/release_renderer.py`）

在 `"render_profile": "release"` 写入 report 的那行之后追加：

```python
    if os.environ.get("AICOMIC_AI_LABEL", "1") != "0":
        try:
            from aicomic.video_synthesis.ai_label import embed_ai_label

            video_path = report.get("video_path") or report.get("output_path")
            if video_path and Path(video_path).exists():
                embed_ai_label(video_path)
                report["ai_label"] = {"status": "embedded"}
        except Exception as exc:
            report["ai_label"] = {"status": "error", "error": str(exc)}
```

（`import os`/`from pathlib import Path` 若文件缺失则补；report 字段名以现文件真实键为准。）

- [x] **步骤 4：CLI**（`src/aicomic/cli/main.py` 薄壳 + 两条 registry 目条）

```python
def ai_label_embed(video, out=None, wm=False):
    from aicomic.video_synthesis.ai_label import embed_ai_label

    return embed_ai_label(video, out, watermark=wm)


def ai_label_check(video):
    from aicomic.video_synthesis.ai_label import ai_label_present

    return ai_label_present(video)


def handle_ai_label_embed(video: Path, out: Path | None, watermark: bool = False) -> int:
    ai_label_embed(video, out, watermark)
    return 0


def handle_ai_label_check(video: Path) -> int:
    present = ai_label_check(video)
    print(f"ai_label={'embedded' if present else 'missing'}")
    return 0 if present else 1
```

REGISTRY：

```python
    "ai-label-embed": {
        "help": "embed AI compliance metadata tags (optionally visible watermark) into mp4",
        "args": [(["video"], {"type": Path}), (["--output"], {"type": Path, "default": None}), (["--watermark"], {"action": "store_true"})],
        "handler": lambda a: handle_ai_label_embed(a.video, a.output, a.watermark),
    },
    "ai-label-check": {
        "help": "check whether a video carries ai_generated=true metadata (exit 0/1)",
        "args": [(["video"], {"type": Path})],
        "handler": lambda a: handle_ai_label_check(a.video),
    },
```

- [x] **步骤 5：运行确认通过 + 回归**

`.venv/bin/python -m pytest tests/test_phase_c_wiring.py tests/test_cli_main.py -v`

- [x] **步骤 6：Commit**

```bash
git add src/aicomic/render/release_renderer.py src/aicomic/cli/main.py tests/test_phase_c_wiring.py tests/test_cli_main.py
git commit -m "feat: release 自动 AI 标识 + CLI ai-label-embed/check"
```

---

### 任务 9：全局核验 + 变异自检 + 汇报

- [x] **步骤 1：全套回归**

`.venv/bin/python -m pytest`
预期：基线 1384 passed + 1 skipped + Phase C 新增全过，0 fail 0 err。任何倒退先修复再继续。

- [x] **步骤 2：lint**

`.venv/bin/python -m pyflakes src/aicomic`
预期：零告警（注意：落码期新建的薄壳/helper 都须被使用点引用，无未用 import）。

- [x] **步骤 3：变异自检**（每项：改代码 → 跑目标测试确认变红 → 还原 → 重跑目标测试确认回绿）

1) **budget kill 失效**：将 `src/aicomic/core/budget_sentinel.py` 的 `guard` 尾段从"超限判定"改成恒 `return True`。
   预期 `pytest tests/test_budget_sentinel.py -v` 至少 2 用例红（`test_guard_refuses_over_budget_without_recording` / `test_guard_kills_after_budget_reached`）→ 还原。
2) **AI 标识丢失**：注释掉 `src/aicomic/video_synthesis/ai_label.py` 中 `for key, value in AI_METADATA_TAGS.items():` 循环。
   预期 `pytest tests/test_ai_label.py tests/test_phase_c_wiring.py::TestReleaseAiLabel -v` 红 → 还原。
3) **失败路径不写 checkpoint**：删除 `src/aicomic/core/show_agent.py` 失败出口的 `write_checkpoint(... CHECKPOINT_FAILED ...)`。
   预期 `pytest tests/test_show_agent.py -v` 红 → 还原。

- [x] **步骤 4：汇报**

```bash
git log --oneline -12
```

报告内容：①通过矩阵（全套 pytest 数值、pyflakes 零告警、3 个变异自检均红过）；②四个新模块/四处窄改清单；③未接线项（平台 shim 不实现，留给发布阶段）与 Phase D 建议清单。

---

## 执行纪律

- 严格 红 → 绿 → commit 三段；commit message 按各任务给定文案。
- 接缝 API 与计划不符（信控方法名、`checkpoint_store` 签名、release_renderer 真名/真键）时：**以真实代码为准**——先读源码，再最小调整测试断言或实现细节；七个红线（规格 §8）不可放宽：
  1. TDD 不可跳（每任务先红后绿）；
  2. 预算哨兵 kill 语义 `>=`，拒绝时不记账；
  3. execute_provider_requests 既有行为不变（回归 9 用例 + phase A/B 全绿）；
  4. gate-protection：awaiting_human / 已 approve 过的卡点不得 begin_stage 重放；
  5. needs_input / budget_stopped / failed 必须写 checkpoint（failed 显式、needs_input 留 in_progress）；
  6. handoff/ai_label 若底层失败：handoff fail-soft、ai_label "error" 显式入 report（release 导出不中断）；
  7. 失败即停：任何无法落地的步骤停下来向用户报告，不绕过。
- 进度实时勾选本文件 `- [x]`。

## 执行前自检（已做）

- [x] 无"待补/伪代码/TODO"残留：全部步骤可执行。
- [x] 无多方案冲突：本计划为唯一方案（A/B 档已在 brainstorm 阶段裁决，A 档弃用）。
- [x] 冲突源核对：与《AI漫剧多Agent工业化SOP.md》§9/§8/§10、`docs/superpowers/specs/2026-10-17-phase-c-sop-wiring-design.md`、PipelineCoordinator/checkpoint_store 现有 API 三方一致；接缝级不确定点已在各任务标注"以真实代码为准"。
- [x] 落码时应实测的接缝（按真实源码对齐）：`PIPELINE_STAGES` 形状、`get_stage_status` 返回三元组、`checkpoint_store` 读写签名、`CostDashboard.get_budget_status` 字段名、`cli/main.py` REGISTRY 条目结构、`release_renderer` 入口函数名与 report 键名。


## 执行进度（收尾补录 2026-10-18）

- 9 个任务全部执行完毕，红线 7 纪律遵守（红→绿分记、commit 前 pyflakes、nginx MN 等未发生）。
- 已知实测差异（计划假设 vs 真实 API）：见执行中 commit message——真实管线 8 阶段/双门禁、mp4 muxer 需 use_metadata_tags、本机 ffprobe 坏架构走 ffmetadata/banner 兜底、CostDashboard._load 覆盖预算需 set_budget 后置。
- 变异自检：3 个全部单测级红过并还原（guard 恒放行 3 红 / ffmetadata 循环拆除 1 红 / 失败不写 checkpoint 2 红）。
- 全套回归基线：Phase C 收点 1429 passed + 1 skipped、pyflakes 零告警。
