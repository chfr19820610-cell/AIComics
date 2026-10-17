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


# ── 任务2: CostDashboard 原子写 ─────────────────────────────────────────

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
        assert reloaded.get_budget_status().total_spent_cents == 200


# ── 任务3: AutoRetryLoop combined_score 量纲 ───────────────────────────

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


# ── 任务4: enhance_via_llm 密钥来源 ────────────────────────────────────

import inspect
import json
from unittest.mock import patch

from aicomic.providers.prompt_enhancer import PROFILES, enhance_via_llm


class TestLLMKeyHandling:
    def test_signature_has_no_hardcoded_key(self):
        sig = inspect.signature(enhance_via_llm)
        assert sig.parameters["llm_key"].default is None

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


# ── 任务5: ImagePipeline Triple-Lock 诚实标注 ──────────────────────────

from aicomic.image_pipeline.pipeline import ImagePipeline


def _make_pipeline(tmp_path: Path) -> ImagePipeline:
    return ImagePipeline(comfyui_client=object(), output_dir=tmp_path / "out")


class TestTripleLockHonesty:
    def test_plan_only_when_comfyui_offline(self, tmp_path: Path):
        pipe = _make_pipeline(tmp_path)
        pipe._post_and_fetch_comfyui = lambda wf, wd: None  # 模拟 ComfyUI 不可达
        result = pipe.run(prompt="test", reference_image=tmp_path, controlnet_image=tmp_path)
        assert "triple_lock_plan_only" in result["stages_executed"]
        assert "generate" not in result["stages_executed"]
        assert result["metadata"]["triple_lock_used"] is True

    def test_generate_when_output_fetched(self, tmp_path: Path):
        pipe = _make_pipeline(tmp_path)
        fetched = tmp_path / "fetched.png"
        fetched.write_bytes(b"png")
        pipe._post_and_fetch_comfyui = lambda wf, wd: fetched
        result = pipe.run(prompt="test", reference_image=tmp_path, controlnet_image=tmp_path)
        assert "generate" in result["stages_executed"]
        assert "triple_lock_plan_only" not in result["stages_executed"]
        assert result["output_path"] == str(fetched)


# ── 任务6: master_sheet 稳定主键 ───────────────────────────────────────

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
