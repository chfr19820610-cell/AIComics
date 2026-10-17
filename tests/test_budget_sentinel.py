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
