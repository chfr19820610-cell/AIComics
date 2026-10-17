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
