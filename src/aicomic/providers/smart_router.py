"""Provider 7-dimension smart router — dynamic provider scoring & fallback.

Scores each video provider on 7 dimensions and routes requests to the
best-scoring provider. Automatically degrades when a provider fails or
hits rate limits.

Dimensions:
  1. quality       — output quality (0-100)
  2. speed         — generation latency (seconds)
  3. cost          — cost per second of video ($)
  4. availability  — uptime ratio (0-1)
  5. quota         — remaining quota (0-1)
  6. latency       — API response latency (ms)
  7. success_rate  — historical success ratio (0-1)

Usage:
    router = SmartProviderRouter()
    router.update_metric("kling", "success_rate", 0.95)
    decision = router.route(shot_type="action")
    if decision.provider:
        result = decision.provider.execute_request(...)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderMetrics:
    """7-dimension metrics for a single provider."""

    quality: float = 80.0        # 0-100
    speed: float = 60.0          # seconds per generation
    cost: float = 0.10           # $ per second of video
    availability: float = 0.99   # 0-1
    quota: float = 1.0           # 0-1 (1.0 = full quota)
    latency: float = 500.0       # ms API response time
    success_rate: float = 0.90   # 0-1

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality,
            "speed": self.speed,
            "cost": self.cost,
            "availability": self.availability,
            "quota": self.quota,
            "latency": self.latency,
            "success_rate": self.success_rate,
        }


@dataclass
class RoutingDecision:
    """Result of a smart routing decision."""

    provider_name: str
    score: float
    metrics: ProviderMetrics
    reason: str
    fallback_chain: list[str] = field(default_factory=list)


class SmartProviderRouter:
    """7-dimension dynamic provider router with automatic fallback.

    Scores each provider using weighted dimensions and routes to the
    best-scoring one. When a provider fails, it's penalized and the
    router falls back to the next best option.
    """

    # Default dimension weights (sum to 1.0)
    DEFAULT_WEIGHTS: dict[str, float] = {
        "quality": 0.25,
        "speed": 0.15,
        "cost": 0.10,
        "availability": 0.15,
        "quota": 0.10,
        "latency": 0.10,
        "success_rate": 0.15,
    }

    # Default providers with initial metrics
    DEFAULT_PROVIDERS: dict[str, ProviderMetrics] = {
        "kling": ProviderMetrics(quality=90, speed=45, cost=0.15, availability=0.98, success_rate=0.95),
        "seedance": ProviderMetrics(quality=75, speed=30, cost=0.05, availability=0.97, success_rate=0.92),
        "wan": ProviderMetrics(quality=70, speed=60, cost=0.02, availability=0.95, success_rate=0.85),
    }

    # Shot-type → preferred provider (soft preference, not hard routing)
    SHOT_PREFERENCES: dict[str, str] = {
        "action": "kling",
        "dialogue": "seedance",
        "creative": "kling",
        "wide": "wan",
        "transition": "seedance",
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        providers: dict[str, ProviderMetrics] | None = None,
    ) -> None:
        self.weights = weights if weights is not None else dict(self.DEFAULT_WEIGHTS)
        self.providers: dict[str, ProviderMetrics] = providers if providers is not None else {
            k: ProviderMetrics(**vars(v)) for k, v in self.DEFAULT_PROVIDERS.items()
        }
        self._failure_counts: dict[str, int] = {k: 0 for k in self.providers}
        self._total_requests: dict[str, int] = {k: 0 for k in self.providers}

    def update_metric(self, provider: str, dimension: str, value: float) -> None:
        """Update a single metric dimension for a provider."""
        if provider not in self.providers:
            self.providers[provider] = ProviderMetrics()
            self._failure_counts[provider] = 0
            self._total_requests[provider] = 0
        setattr(self.providers[provider], dimension, value)

    def record_success(self, provider: str) -> None:
        """Record a successful generation — improves success_rate."""
        if provider not in self.providers:
            return
        self._total_requests[provider] += 1
        self._failure_counts[provider] = 0  # reset failure streak
        # Exponential moving average for success_rate
        current = self.providers[provider].success_rate
        self.providers[provider].success_rate = current * 0.9 + 1.0 * 0.1

    def record_failure(self, provider: str) -> None:
        """Record a failed generation — penalizes success_rate and availability."""
        if provider not in self.providers:
            return
        self._total_requests[provider] += 1
        self._failure_counts[provider] += 1
        # Exponential moving average
        current = self.providers[provider].success_rate
        self.providers[provider].success_rate = current * 0.9 + 0.0 * 0.1
        # Reduce availability on consecutive failures
        if self._failure_counts[provider] >= 3:
            self.providers[provider].availability *= 0.9

    def _score_provider(self, name: str, metrics: ProviderMetrics) -> float:
        """Calculate weighted score for a provider (0-100)."""
        # Normalize each dimension to 0-100
        quality_score = metrics.quality  # already 0-100
        speed_score = max(0, 100 - metrics.speed)  # lower speed = higher score
        cost_score = max(0, 100 - metrics.cost * 1000)  # lower cost = higher score
        avail_score = metrics.availability * 100
        quota_score = metrics.quota * 100
        latency_score = max(0, 100 - metrics.latency / 10)  # lower latency = higher score
        success_score = metrics.success_rate * 100

        w = self.weights
        total = (
            quality_score * w.get("quality", 0.25) +
            speed_score * w.get("speed", 0.15) +
            cost_score * w.get("cost", 0.10) +
            avail_score * w.get("availability", 0.15) +
            quota_score * w.get("quota", 0.10) +
            latency_score * w.get("latency", 0.10) +
            success_score * w.get("success_rate", 0.15)
        )
        return round(total, 2)

    def route(self, shot_type: str = "") -> RoutingDecision:
        """Route to the best-scoring provider for a given shot type.

        Args:
            shot_type: Optional shot type for soft preference.

        Returns:
            RoutingDecision with provider name, score, and fallback chain.
        """
        if not self.providers:
            return RoutingDecision(
                provider_name="",
                score=0,
                metrics=ProviderMetrics(),
                reason="No providers configured",
            )

        # Score all providers
        scored = [
            (name, self._score_provider(name, m), m)
            for name, m in self.providers.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Apply shot-type preference bonus (small, +5 points)
        preferred = self.SHOT_PREFERENCES.get(shot_type, "")
        if preferred and preferred in self.providers:
            scored = [
                (n, s + (5 if n == preferred else 0), m)
                for n, s, m in scored
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

        best_name, best_score, best_metrics = scored[0]
        fallback = [n for n, _, _ in scored[1:]]

        reason = f"Best score {best_score}/100"
        if preferred and best_name == preferred:
            reason += f" (preferred for {shot_type})"

        return RoutingDecision(
            provider_name=best_name,
            score=best_score,
            metrics=best_metrics,
            reason=reason,
            fallback_chain=fallback,
        )

    def get_rankings(self) -> list[dict[str, Any]]:
        """Get all providers ranked by score."""
        scored = [
            (name, self._score_provider(name, m), m)
            for name, m in self.providers.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {"provider": n, "score": s, "metrics": m.to_dict()}
            for n, s, m in scored
        ]

    def get_provider_status(self, provider: str) -> dict[str, Any]:
        """Get detailed status for a single provider."""
        if provider not in self.providers:
            return {"provider": provider, "status": "not_configured"}
        m = self.providers[provider]
        return {
            "provider": provider,
            "score": self._score_provider(provider, m),
            "metrics": m.to_dict(),
            "failures": self._failure_counts.get(provider, 0),
            "total_requests": self._total_requests.get(provider, 0),
        }
