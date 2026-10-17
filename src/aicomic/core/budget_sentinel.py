"""预算哨兵 — SOP §9 #9（成本爆炸对策）的执行层落地。

- 在 live Provider 请求执行**前**估算本次成本并记账（API 提交即扣费）；
- 已花费 + 本次估计 >= 预算 → 拒绝，把 kill 决定交回调用方（stopped_by_budget）；
- 拒绝语义含等号：预算恰好用满时不再发起下一次（执行每条都对应真金白银）；
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
