"""Cost dashboard — cumulative cost tracking + budget gate for cloud generation.

Based on godogen methodology: "confirm the spend with the user before the
first paid generation" + asset table with cost column.

Tracks:
  - Per-generation cost (provider × model × credits/cents)
  - Cumulative spend per project/episode
  - Budget gates (warn at 80%, block at 100%)
  - Asset cost ledger (path/size/cost per generated asset)

Usage:
    dashboard = CostDashboard(storage_dir="state/costs")
    dashboard.record_generation("kling", "action_shot_01", credits=10, cents=15.0)
    status = dashboard.get_budget_status()
    if not dashboard.check_budget():
        # Block generation — over budget
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CostEntry:
    """A single cost record for one generation."""

    timestamp: float
    provider: str
    model: str = ""
    asset_id: str = ""  # shot ID, image ID, etc.
    asset_path: str = ""
    credits: float = 0.0  # provider credits consumed
    cents: float = 0.0  # actual cost in cents
    asset_size_mb: float = 0.0
    episode_code: str = ""
    project_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "provider": self.provider,
            "model": self.model,
            "asset_id": self.asset_id,
            "asset_path": self.asset_path,
            "credits": self.credits,
            "cents": self.cents,
            "asset_size_mb": self.asset_size_mb,
            "episode_code": self.episode_code,
            "project_id": self.project_id,
            "notes": self.notes,
        }


@dataclass
class BudgetStatus:
    """Current budget status."""

    total_budget_cents: float = 0.0
    total_spent_cents: float = 0.0
    remaining_cents: float = 0.0
    spent_pct: float = 0.0
    status: str = "ok"  # ok / warning / exceeded
    generation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_budget_cents": self.total_budget_cents,
            "total_spent_cents": round(self.total_spent_cents, 2),
            "remaining_cents": round(self.remaining_cents, 2),
            "spent_pct": round(self.spent_pct, 1),
            "status": self.status,
            "generation_count": self.generation_count,
        }


class CostDashboard:
    """Cumulative cost tracking + budget gate.

    Args:
        storage_dir: Directory for cost ledger files.
        budget_cents: Total budget in cents (0 = unlimited).
        warn_pct: Warning threshold percentage (default 80).
    """

    def __init__(
        self,
        storage_dir: Path | str = "state/costs",
        budget_cents: float = 0,
        warn_pct: float = 80.0,
    ) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self._dir / "cost_ledger.json"
        self._budget_cents = budget_cents
        self._warn_pct = warn_pct
        self._entries: list[CostEntry] = []
        self._load()

    def _load(self) -> None:
        """Load cost ledger from disk."""
        if not self._ledger_path.exists():
            return
        try:
            data = json.loads(self._ledger_path.read_text(encoding="utf-8"))
            self._entries = [CostEntry(**e) for e in data.get("entries", [])]
            self._budget_cents = data.get("budget_cents", self._budget_cents)
        except (json.JSONDecodeError, TypeError):
            pass

    def _save(self) -> None:
        """Save cost ledger to disk."""
        data = {
            "budget_cents": self._budget_cents,
            "entries": [e.to_dict() for e in self._entries],
        }
        self._ledger_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set_budget(self, cents: float) -> None:
        """Set or update the budget limit."""
        self._budget_cents = cents
        self._save()

    def record_generation(
        self,
        provider: str,
        asset_id: str = "",
        credits: float = 0,
        cents: float = 0,
        model: str = "",
        asset_path: str = "",
        asset_size_mb: float = 0,
        episode_code: str = "",
        project_id: str = "",
        notes: str = "",
    ) -> CostEntry:
        """Record a single generation cost.

        Args:
            provider: Provider name (kling, seedance, wan, etc.).
            asset_id: Asset identifier (shot number, image ID).
            credits: Credits consumed.
            cents: Actual cost in cents.
            model: Model used.
            asset_path: Path to generated asset.
            asset_size_mb: Asset file size in MB.
            episode_code: Episode this asset belongs to.
            project_id: Project this asset belongs to.

        Returns:
            The recorded CostEntry.
        """
        entry = CostEntry(
            timestamp=time.time(),
            provider=provider,
            model=model,
            asset_id=asset_id,
            asset_path=asset_path,
            credits=credits,
            cents=cents,
            asset_size_mb=asset_size_mb,
            episode_code=episode_code,
            project_id=project_id,
            notes=notes,
        )
        self._entries.append(entry)
        self._save()
        return entry

    def check_budget(self) -> bool:
        """Check if generation can proceed under budget.

        Returns:
            True if under budget (or no budget set), False if exceeded.
        """
        if self._budget_cents <= 0:
            return True  # unlimited
        spent = sum(e.cents for e in self._entries)
        return spent < self._budget_cents

    def get_budget_status(self) -> BudgetStatus:
        """Get current budget status."""
        spent = sum(e.cents for e in self._entries)
        budget = self._budget_cents
        remaining = max(0, budget - spent) if budget > 0 else -1
        pct = (spent / budget * 100) if budget > 0 else 0

        if budget > 0:
            if spent >= budget:
                status = "exceeded"
            elif pct >= self._warn_pct:
                status = "warning"
            else:
                status = "ok"
        else:
            status = "unlimited"

        return BudgetStatus(
            total_budget_cents=budget,
            total_spent_cents=spent,
            remaining_cents=remaining,
            spent_pct=pct,
            status=status,
            generation_count=len(self._entries),
        )

    def get_cost_by_provider(self) -> dict[str, dict[str, float]]:
        """Get cost breakdown by provider.

        Returns:
            {provider: {total_cents, total_credits, count}}
        """
        breakdown: dict[str, dict[str, float]] = {}
        for entry in self._entries:
            if entry.provider not in breakdown:
                breakdown[entry.provider] = {"total_cents": 0, "total_credits": 0, "count": 0}
            breakdown[entry.provider]["total_cents"] += entry.cents
            breakdown[entry.provider]["total_credits"] += entry.credits
            breakdown[entry.provider]["count"] += 1
        return breakdown

    def get_cost_by_episode(self) -> dict[str, dict[str, float]]:
        """Get cost breakdown by episode.

        Returns:
            {episode_code: {total_cents, count}}
        """
        breakdown: dict[str, dict[str, float]] = {}
        for entry in self._entries:
            ep = entry.episode_code or "unassigned"
            if ep not in breakdown:
                breakdown[ep] = {"total_cents": 0, "count": 0}
            breakdown[ep]["total_cents"] += entry.cents
            breakdown[ep]["count"] += 1
        return breakdown

    def get_asset_table(self) -> list[dict[str, Any]]:
        """Get asset cost ledger as a table (godogen-style asset table).

        Returns:
            List of {path, size_mb, cost_cents, provider, episode}
        """
        return [
            {
                "asset_path": e.asset_path,
                "asset_id": e.asset_id,
                "size_mb": e.asset_size_mb,
                "cost_cents": e.cents,
                "credits": e.credits,
                "provider": e.provider,
                "model": e.model,
                "episode_code": e.episode_code,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]

    def get_total_cost(self) -> float:
        """Get total cost in cents."""
        return sum(e.cents for e in self._entries)

    def get_total_credits(self) -> float:
        """Get total credits consumed."""
        return sum(e.credits for e in self._entries)

    def export_dashboard(self) -> dict[str, Any]:
        """Export full dashboard data for display."""
        return {
            "budget_status": self.get_budget_status().to_dict(),
            "total_cost_cents": self.get_total_cost(),
            "total_credits": self.get_total_credits(),
            "cost_by_provider": self.get_cost_by_provider(),
            "cost_by_episode": self.get_cost_by_episode(),
            "asset_count": len(self._entries),
            "can_proceed": self.check_budget(),
        }
