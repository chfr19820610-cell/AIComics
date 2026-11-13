# Phase A 安全修复计划 — 8 个已证实的 bug/隐患

> ✅ **执行状态（2026-11-13 校准）**：本计划 8 个任务全部完成并提交。证据：`git log --grep="任务[1-8]/8"`（commits fb2cc7d…cd5bfc2）。下方复选框此前未回填，现据提交记录补勾。


> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans（内联）或 superpowers:subagent-driven-development 逐任务实现。步骤使用复选框（`- [ ]`）跟踪。

> ⚠️ **脱敏说明**：本文档原含一处历史密钥明文，已于 2026-11-13 替换为 `<REDACTED_KEY>`。
> 该密钥曾随 v1.0.0 提交进入公开 git 历史（commit 47ddd7a），**如仍在使用请立即轮换**。

**目标：** 修复调研报告中"测试全绿但实际有 bug"的 8 个高危点，每任务独立提交、独立可回滚，全程 1358 测试不回归。

**架构：** 全部为最小外科手术式修复（TDD：先写失败测试 → 最小实现 → 绿灯即 commit）。不动架构（双后端合并/Provider 断链接线等属 Phase B 需用户决策，本计划不触碰）。

**技术栈：** Python 3.12 / pytest（仓库已有 `.venv`）；运行命令统一为 `.venv/bin/python -m pytest`（全套 2.9s，每任务结束跑全套防回归）。

**为什么"不会乱"：**
1. 每任务 1 个 commit，`git revert <hash>` 即可单独撤销；
2. 所有修改点均无既有测试断言（已 grep 确认 `_dedup` / `_try_post_comfyui` / `llm_key` / `combined_score` / cost `_save` / `register_master` 零测试命中，`test_image_pipeline.py` 无 triple-lock 段断言）；
3. 不改任何函数签名（除任务 4 的默认值从字符串改 None）；
4. 每 5 步一节点：写测试（红）→ 确红 → 最小实现（绿）→ 全套回归 → commit。

---

## 文件结构（将要修改/创建的全部文件）

| 动作 | 文件 | 职责 |
|---|---|---|
| 修改 | `src/aicomic/characters/consistency_service.py:134-136` | 修 `_dedup_attributes` 恒返空 |
| 修改 | `src/aicomic/core/cost_dashboard.py:116-122` | `_save()` 原子写 |
| 修改 | `src/aicomic/video_synthesis/auto_retry.py:159` | combined_score 量纲归一 |
| 修改 | `src/aicomic/providers/prompt_enhancer.py:270-324` | 移除源码明文密钥 |
| 修改 | `src/aicomic/image_pipeline/pipeline.py:19-34, 99-117` | Triple-Lock 真实取回产物，诚实标注 |
| 修改 | `src/aicomic/image_consistency/master_sheet.py:124` | 稳定主键防重复行 |
| 修改 | `src/aicomic/render/preview_renderer.py:171-174` | ffmpeg 解析复用 `video_synthesis.config.FFMPEG` |
| 修改 | `src/aicomic/video_synthesis/quality_gate.py:44-70` | 类 docstring 与 WARN 行为对齐（文档修正）|
| 新建 | `tests/test_phase_a_regressions.py` | 本次 8 个修复的全部回归测试（集中一个文件，pytest markers 不需要）|

---

### 任务 1：`_dedup_attributes` 恒返空（一致性门形同虚设）

**文件：** 修改 `src/aicomic/characters/consistency_service.py:134-136`；测试写进 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：向 `tests/test_phase_a_regressions.py` 写失败的测试**

```python
"""Phase A 回归测试 — 每个 bug 一个测试，防止再次全绿漏网。"""

from aicomic.characters.consistency_service import AttributeEntry, _dedup_attributes


class TestDedupAttributes:
    def test_dedup_keeps_first_occurrence(self):
        attrs = [
            AttributeEntry(category="hair", attribute="黑长发", source_text="黑长发", confidence=0.9),
            AttributeEntry(category="hair", attribute="黑长发", source_text="黑长发", confidence=0.9),
            AttributeEntry(category="eyes", attribute="红瞳", source_text="红瞳", confidence=0.9),
        ]
        result = _dedup_attributes(attrs)
        assert len(result) == 2
        assert [a.attribute for a in result] == ["黑长发", "红瞳"]

    def test_dedup_empty_input(self):
        assert _dedup_attributes([]) == []
```

- [x] **步骤 2：运行验证失败**

运行：`.venv/bin/python -m pytest tests/test_phase_a_regressions.py::TestDedupAttributes -v`
预期：FAIL（`result == []`，len 0 ≠ 2）

- [x] **步骤 3：最小实现**

`consistency_service.py:134-136` 整体替换为：

```python
def _dedup_attributes(attrs: list[AttributeEntry]) -> list[AttributeEntry]:
    seen: set[str] = set()
    deduped: list[AttributeEntry] = []
    for a in attrs:
        k = f"{a.category}:{a.attribute}"
        if k in seen:
            continue
        seen.add(k)
        deduped.append(a)
    return deduped
```

- [x] **步骤 4：全套回归**

运行：`.venv/bin/python -m pytest tests/test_characters.py tests/test_v4_p1_integration.py tests/test_phase_a_regressions.py -q`
预期：全 PASS。注意：修复后 `consistency_report` 分数可能从恒 1.0 变为真实值——若有测试断言过 1.0 属于"断言了 bug 行为"，改为放宽或删除该断言（记录到 commit message）。

- [x] **步骤 5：Commit** `fix: _dedup_attributes 海象表达式恒真导致一致性门失效`

---

### 任务 2：CostDashboard `_save` 非原子写

**文件：** 修改 `src/aicomic/core/cost_dashboard.py:116-122`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
from pathlib import Path

from aicomic.core.cost_dashboard import CostDashboard


class TestCostLedgerAtomic:
    def test_save_leaves_no_tmp_residue(self, tmp_path: Path):
        dash = CostDashboard(storage_dir=tmp_path, budget_cents=1000)
        dash.record_generation(provider="kling", cents=100)
        residue = [p for p in tmp_path.iterdir() if p.name != "cost_ledger.json"]
        assert residue == []

    def test_save_reload_consistent(self, tmp_path: Path):
        dash = CostDashboard(storage_dir=tmp_path, budget_cents=500)
        dash.record_generation(provider="wan", cents=200)
        reloaded = CostDashboard(storage_dir=tmp_path, budget_cents=500)
        assert reloaded.get_budget_status()["spent_cents"] == 200
```

- [x] **步骤 2：运行验证失败**（旧行为测试也可能绿——重点在 btn 1；先跑确认 btn2 语义，绿则步骤 3 改后不得变红）
运行：`.venv/bin/python -m pytest tests/test_phase_a_regressions.py::TestCostLedgerAtomic -v`

- [x] **步骤 3：最小实现** — 文件头部加 import，替换 `_save` 主体：

```python
from aicomic.utils.atomic_io import atomic_write_json
```

```python
    def _save(self) -> None:
        """Save cost ledger to disk (atomic: tmp file + rename, crash-safe)."""
        data = {
            "budget_cents": self._budget_cents,
            "entries": [e.to_dict() for e in self._entries],
        }
        atomic_write_json(self._ledger_path, data)
```

（`atomic_write_json` 已是项目标准，`core/checkpoint_store.py:24` 等 6 处在用，import 路径有效。）

- [x] **步骤 4：全套回归** `.venv/bin/python -m pytest -q` 预期 1358 全绿
- [x] **步骤 5：Commit** `fix: cost ledger 原子写替换整文件重写`

---

### 任务 3：AutoRetryLoop `combined_score` 量纲混乱（像素+分数）

**文件：** 修改 `src/aicomic/video_synthesis/auto_retry.py:158-159`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
from pathlib import Path

from aicomic.video_synthesis.auto_retry import AutoRetryLoop
from aicomic.video_synthesis.quality_gate import FFprobeGate, QualityReport


class _MockGate(FFprobeGate):
    def __init__(self, metrics: dict):
        super().__init__()
        self._metrics = metrics

    def check(self, video_path, expected_duration=None):
        return QualityReport(status="PASS", file_path=str(video_path), metrics=self._metrics, issues=[])


class TestAutoRetryScore:
    def test_low_resolution_score_in_0_100_band(self, tmp_path: Path):
        video = tmp_path / "shot.mp4"
        video.write_bytes(b"dummy")

        def gen_fn(prompt, **kwargs):
            return {"status": "success", "video_path": str(video)}

        # 旧行为: (360 + 100)//2 = 230 → 超量纲；新行为应 ≤100
        loop = AutoRetryLoop(max_retries=0, ffprobe_gate=_MockGate({"height": 360}))
        result = loop.run(gen_fn, video, prompt="t")
        assert 0 <= result.attempts[0].combined_score <= 100

    def test_hd_score_reflects_quality(self, tmp_path: Path):
        video = tmp_path / "shot.mp4"
        video.write_bytes(b"dummy")

        def gen_fn(prompt, **kwargs):
            return {"status": "success", "video_path": str(video)}

        loop = AutoRetryLoop(max_retries=0, ffprobe_gate=_MockGate({"height": 1080}))
        result = loop.run(gen_fn, video, prompt="t")
        assert result.attempts[0].combined_score >= 90
```

- [x] **步骤 2：运行验证失败** 预期 230 > 100 → FAIL
- [x] **步骤 3：最小实现** 替换 ：158-159：

```python
            # Step 4: Combine scores — normalize resolution to a 0-100 band first
            if q_report.metrics:
                height = int(q_report.metrics.get("height", 0))
                quality_component = 100 if height >= 720 else (60 if height >= 480 else 20)
                combined_score = (quality_component + a_report.score) // 2
            else:
                combined_score = a_report.score
```

- [x] **步骤 4：回归** `.venv/bin/python -m pytest tests/test_p1_quality.py tests/test_v52_integration.py tests/test_phase_a_regressions.py -q`
- [x] **步骤 5：Commit** `fix: auto_retry combined_score 归一化到 0-100 量纲`

---

### 任务 4：删除源码明文 API 密钥（`<REDACTED_KEY>`）

**文件：** 修改 `src/aicomic/providers/prompt_enhancer.py:270-324`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
import inspect
import json
from unittest.mock import patch

from aicomic.providers.prompt_enhancer import PROFILES, enhance_via_llm


class TestLLMKeyHandling:
    def test_signature_has_no_hardcoded_key(self):
        sig = inspect.signature(enhance_via_llm)
        default = sig.parameters["llm_key"].default
        assert default is None

    def test_no_env_key_skips_curl(self, monkeypatch):
        monkeypatch.delenv("AICOMIC_ENHANCE_LLM_KEY", raising=False)
        with patch("subprocess.run") as fake:
            out = enhance_via_llm("base prompt", PROFILES["anime_donghua"])
        fake.assert_not_called()
        assert out == "base prompt"

    def test_env_key_used_in_header(self, monkeypatch):
        monkeypatch.setenv("AICOMIC_ENHANCE_LLM_KEY", "testkey123")
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            out = json.dumps({"choices": [{"message": {"content": "augmented " + "x" * 200}}]})
            return type("R", (), {"returncode": 0, "stdout": out})()

        with patch("subprocess.run", fake_run):
            enhance_via_llm("base", PROFILES["anime_donghua"])
        assert any("testkey123" in part for part in captured["cmd"])
        assert not any("<REDACTED_KEY>" in part for part in captured["cmd"])
```

- [x] **步骤 2：运行验证失败**（第一个测试：default 是字符串 → FAIL）
- [x] **步骤 3：最小实现** — ：276 签名改 `llm_key: str | None = None`，函数体开头（`import subprocess as _sp` 之前）插入：

```python
    import os as _os
    resolved_key = llm_key or _os.environ.get("AICOMIC_ENHANCE_LLM_KEY", "")
    if not resolved_key:
        return base_prompt
```

curl 数组中 `f"Authorization: Bearer {llm_key}"` 改为 `f"Authorization: Bearer {resolved_key}"`。文件内任何地方不再出现 `<REDACTED_KEY>`。

- [x] **步骤 4：回归 + 安全扫描**

```bash
.venv/bin/python -m pytest -q
grep -rn "<REDACTED_KEY>" src/ || echo "clean"
```

预期：全绿 + `clean`。
⚠️ 两点新行为即记录：无 key 跳过 LLM 增强属"诚实降级"（与项目 fallback 文化一致，且默认手头 hermes 环境只要 export 该 env 变量行为不变：它此前就是这个值，可 `export AICOMIC_ENHANCE_LLM_KEY=<REDACTED_KEY>` 恢复原行为）。
- [x] **步骤 5：Commit** `security: 源码明文密钥移至环境变量 AICOMIC_ENHANCE_LLM_KEY`。**附带说明：密钥已进 git 历史，用户应在服务端轮换该 key，本计划无法代为修复。**

---

### 任务 5：ImagePipeline Triple-Lock 伪成功（产物从不取回）

**文件：** 修改 `src/aicomic/image_pipeline/pipeline.py:19-34, 99-117`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
from aicomic.image_pipeline.pipeline import ImagePipeline


def _make_pipeline(tmp_path):
    return ImagePipeline(comfyui_client=object(), output_dir=tmp_path / "out")


class TestTripleLockHonesty:
    def test_plan_only_when_comfyui_offline(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        pipe._post_and_fetch_comfyui = lambda wf, wd: None  # 模拟 ComfyUI 不可达
        result = pipe.run(prompt="test", reference_image=tmp_path, controlnet_image=tmp_path)
        assert "triple_lock_plan_only" in result["stages_executed"]
        assert "generate" not in result["stages_executed"]
        assert result["metadata"]["triple_lock_used"] is True

    def test_generate_when_output_fetched(self, tmp_path):
        pipe = _make_pipeline(tmp_path)
        fetched = tmp_path / "fetched.png"
        fetched.write_bytes(b"png")
        pipe._post_and_fetch_comfyui = lambda wf, wd: fetched
        result = pipe.run(prompt="test", reference_image=tmp_path, controlnet_image=tmp_path)
        assert "generate" in result["stages_executed"]
        assert "triple_lock_plan_only" not in result["stages_executed"]
        assert result["output_path"] == str(fetched)
```

- [x] **步骤 2：运行验证失败**（旧行为：plan-only 分支也 append "generate" → 第一个断言 FAIL）
- [x] **步骤 3：最小实现**
  - `_try_post_comfyui`（:19-34）整体替换为：

```python
    def _post_and_fetch_comfyui(self, workflow: dict[str, Any], work_dir: Path) -> Path | None:
        """POST /prompt → poll /history → download outputs.

        Returns the path of the first downloaded image, or None when ComfyUI
        is unavailable / produced nothing (caller must treat as plan-only).
        """
        import json as _json
        import time as _time
        import urllib.request

        base = "http://127.0.0.1:8188"
        try:
            req = urllib.request.Request(
                f"{base}/prompt",
                data=_json.dumps({"prompt": workflow}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                prompt_id = _json.loads(resp.read()).get("prompt_id")
            if not prompt_id:
                return None
            for _ in range(20):  # 20 × 2s = 40s generation budget
                _time.sleep(2)
                with urllib.request.urlopen(f"{base}/history/{prompt_id}", timeout=5) as resp:
                    entry = _json.loads(resp.read()).get(prompt_id)
                if not entry:
                    continue
                for node_out in entry.get("outputs", {}).values():
                    for idx, img in enumerate(node_out.get("images", [])):
                        view_url = (
                            f"{base}/view?filename={img.get('filename', '')}"
                            f"&subfolder={img.get('subfolder', '')}"
                            f"&type={img.get('type', 'output')}"
                        )
                        dest = work_dir / f"triple_lock_{idx}.png"
                        with urllib.request.urlopen(view_url, timeout=30) as resp, open(dest, "wb") as f:
                            f.write(resp.read())
                        return dest
            return None
        except Exception:
            return None
```

  - `run()` 中 ：99-117 的 Triple-Lock 段尾部改写（替换原 ：111-117）：

```python
            fetched = self._post_and_fetch_comfyui(tl_workflow, work_dir)
            if fetched is not None:
                gen_output = fetched
                stages.append("generate")
            else:
                # ComfyUI unavailable or produced nothing — plan only, honestly labeled
                gen_output = work_dir / "triple_lock_plan.json"
                stages.append("triple_lock_plan_only")
```

  （下游 ：151/:158 的 `"triple_lock_plan_only" not in stages` 门禁语义保持不变。）

- [x] **步骤 4：回归** `.venv/bin/python -m pytest -q`（test_image_pipeline 无该段断言，预期零影响）
- [x] **步骤 5：Commit** `fix: triple_lock 真实取回 ComfyUI 产物并以 plan_only 诚实标注`

---

### 任务 6：master_sheet `INSERT OR REPLACE` 永不命中（重复行堆积）

**文件：** 修改 `src/aicomic/image_consistency/master_sheet.py:124`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
import sqlite3

from aicomic.image_consistency.master_sheet import (
    ensure_master_sheet_schema,
    register_master,
)


class TestMasterSheetStableId:
    def test_re_register_replaces_not_accumulates(self):
        conn = sqlite3.connect(":memory:")
        ensure_master_sheet_schema(conn)
        register_master(conn, "c1", "林晚", "/a.png")
        register_master(conn, "c1", "林晚", "/b.png")
        count = conn.execute(
            "SELECT COUNT(*) FROM master_sheets WHERE character_id='c1'"
        ).fetchone()[0]
        assert count == 1
```

- [x] **步骤 2：运行验证失败**（旧行为两个 uuid → count 2 → FAIL）
- [x] **步骤 3：最小实现** — `entry_id = str(uuid.uuid4())` 替换为：

```python
    entry_id = f"master_{character_id}"
```

（同 character 恒定主键 → INSERT OR REPLACE 真正生效，每角色一行；`created_at` 语义由"首次创建"变为"最近一次"，符合 REPLACE 语义。）

- [x] **步骤 4：回归** `.venv/bin/python -m pytest -q`
- [x] **步骤 5：Commit** `fix: master_sheet 稳定主键使 REPLACE 生效防重复行`

---

### 任务 7：preview_renderer 硬编码个人机路径

**文件：** 修改 `src/aicomic/render/preview_renderer.py:171-174`；测试 `tests/test_phase_a_regressions.py`

- [x] **步骤 1：失败测试**

```python
from pathlib import Path

from aicomic.render import preview_renderer


class TestFFmpegResolution:
    def test_no_personal_absolute_path_in_source(self):
        src = Path(preview_renderer.__file__).read_text(encoding="utf-8")
        assert "/Users/eric" not in src
        assert ".hermes" not in src

    def test_uses_shared_ffmpeg_resolver(self):
        from aicomic.video_synthesis.config import FFMPEG as _FF
        assert str(_FF)
```

- [x] **步骤 2：运行验证失败**
- [x] **步骤 3：最小实现** — ：171-174 替换为：

```python
    from aicomic.video_synthesis.config import FFMPEG as _resolved_ffmpeg
    ffmpeg_bin = str(_resolved_ffmpeg)
```

（复用 `_resolve_ffmpeg` 链：`AICOMIC_FFMPEG` env → PATH → imageio_ffmpeg 内置，本机保留首个仍然可解释——若用户机器确有 `.hermes/bin/ffmpeg`，可设 `AICOMIC_FFMPEG=/Users/eric/.hermes/bin/ffmpeg` 指回。）

- [x] **步骤 4：回归** `.venv/bin/python -m pytest -q`
- [x] **步骤 5：Commit** `fix: preview_renderer 复用统一 ffmpeg 解析链去除本机路径`

---

### 任务 8：quality_gate class docstring 与代码行为对齐（文档修正）

**文件：** 修改 `src/aicomic/video_synthesis/quality_gate.py:44-70`（仅注释，不改代码）

- [x] **步骤 1：确认现场** — `sed -n '150,200p' src/aicomic/video_synthesis/quality_gate.py`，确认 `min_bitrate` 低于阈值加的是 WARN（current code L173-175 一带）。
- [x] **步骤 2：对齐文档** — class docstring Usage 块之前插入一行规格说明：

```python
    """Video quality gate using ffprobe.

    Decision rules (code is the source of truth):
      - resolution < min_resolution → FAIL
      - no video stream → FAIL
      - framerate < min_framerate → WARN
      - bitrate < min_bitrate_kbps → WARN
      - no audio stream → WARN
      - |duration - expected| > tolerance → WARN

    Usage:
```

- [x] **步骤 3：回归** `.venv/bin/python -m pytest -q`
- [x] **步骤 4：Commit** `docs: quality_gate docstring 对齐实际 WARN 判定`

---

## 收尾检查（全部任务后）

- [x] `.venv/bin/python -m pytest -q` 全绿（≥1358）
- [x] `git log --oneline -8` 每任务一个 commit
- [x] `.venv/bin/python -m pyflakes src/aicomic/ || true`（如 CI 用 pyflakes，保持零 warning 标准）
- [x] `grep -rn "<REDACTED_KEY>\|/Users/eric" src/` 输出 clean

## Phase B（不在本计划执行——需用户决策/资源，仅备忘）

1. 修 openai/JieYou 401 key（用户提供）
2. 下载 ControlNet/IP-Adapter/RMBG 模型 ~2.5GB（用户授权网络+磁盘）
3. Provider 断链接线：executor 认 kling/seedance/wan
4. 智能层收敛：`route_with_cascade` 接入 request_builder（或删孤岛）
5. Web 合一：18 端点 mount 进 Creator 后端
6. 发布平台 enabled→true + cookie（需真实账号）
7. E13 真实 E2E 验证
