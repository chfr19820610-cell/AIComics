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
