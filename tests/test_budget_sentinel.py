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
