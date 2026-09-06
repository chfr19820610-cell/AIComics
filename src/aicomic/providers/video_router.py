"""Multi-model video router — selects the best video provider per shot type.

Shot types and their preferred models (2026 video API landscape):
  - action   → Kling 3.0    (best human motion, fast action sequences)
  - dialogue → Seedance 2.0 (cost-efficient, $0.045/s, natural pacing)
  - creative → Kling 3.0    (stylized / abstract motion)
  - wide     → Wan 2.7      (open-source, controllable, landscape scenes)
  - fallback → Seedance 2.0 (cheapest, always available)

The router reads a shot-type→model mapping from providers.yaml and resolves
to a provider instance.  It does NOT call the API — it only makes the routing
decision.  Callers use the returned provider to build/execute requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aicomic.providers.base import IProvider
from aicomic.providers.kling_provider import KlingProvider
from aicomic.providers.seedance_provider import SeedanceProvider


# ── Shot type enum (string-based for YAML compatibility) ─────────────────

class ShotType:
    """Supported shot type labels for routing decisions."""
    ACTION = "action"
    DIALOGUE = "dialogue"
    CREATIVE = "creative"
    WIDE = "wide"
    TRANSITION = "transition"

    ALL: tuple[str, ...] = (ACTION, DIALOGUE, CREATIVE, WIDE, TRANSITION)


# ── Default routing table (overridable via providers.yaml) ───────────────

DEFAULT_ROUTING: dict[str, str] = {
    ShotType.ACTION: "kling",
    ShotType.DIALOGUE: "seedance",
    ShotType.CREATIVE: "kling",
    ShotType.WIDE: "wan",
    ShotType.TRANSITION: "seedance",
}

# Models not yet implemented as full IProvider adapters — stub for routing.
# When Wan provider is added, replace the stub with the real class.
_PROVIDER_STUBS: dict[str, type] = {
    "kling": KlingProvider,
    "seedance": SeedanceProvider,
    # "wan": WanProvider,  # future
}


@dataclass
class RoutingDecision:
    """The result of a routing decision: which provider + why."""
    shot_type: str
    provider_name: str
    provider: IProvider | None
    reason: str
    flf_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class VideoRouter:
    """Routes video generation requests to the optimal provider by shot type.

    Usage:
        router = VideoRouter.from_config(config_path)
        decision = router.route(shot_type="action", flf=True)
        if decision.provider:
            result = decision.provider.execute_request(req, config_path)
    """

    def __init__(
        self,
        routing_table: dict[str, str] | None = None,
        providers_config_path: Path | None = None,
    ) -> None:
        self.routing_table: dict[str, str] = dict(routing_table or DEFAULT_ROUTING)
        self._config_path = providers_config_path
        self._provider_cache: dict[str, IProvider] = {}

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: Path) -> "VideoRouter":
        """Build a router from a providers.yaml config file.

        Reads the `video_router` section for shot-type→model mappings.
        Falls back to DEFAULT_ROUTING if the section is absent.
        """
        routing = dict(DEFAULT_ROUTING)
        if config_path.exists():
            # Parse the video_router section using the base class loader
            stub = _StubLoader()
            settings = stub._load_settings(config_path)
            vr_section = settings.get("video_router", {})
            for key, value in vr_section.items():
                if key in ("shot_type_mapping", "flf_default"):
                    continue
                # Only accept known shot types
                if key in ShotType.ALL:
                    routing[key] = str(value).strip()
            # Handle nested mapping (if YAML loader captured it differently)
            mapping = vr_section.get("shot_type_mapping")
            if isinstance(mapping, dict):
                for shot, model in mapping.items():
                    if shot in ShotType.ALL:
                        routing[shot] = str(model).strip()

        return cls(routing_table=routing, providers_config_path=config_path)

    # ── Core routing ─────────────────────────────────────────────────────

    def route(
        self,
        shot_type: str,
        flf: bool = False,
        **kwargs: Any,
    ) -> RoutingDecision:
        """Select the best provider for a given shot type.

        Args:
            shot_type: One of ShotType.ALL (action, dialogue, creative, wide, transition).
            flf: If True, signal that First-Last-Frame interpolation is requested.
            **kwargs: Extra metadata for routing (e.g. duration, budget).

        Returns:
            RoutingDecision with the chosen provider (or None if unavailable).
        """
        normalized = shot_type.lower().strip()
        if normalized not in ShotType.ALL:
            normalized = ShotType.DIALOGUE  # safe fallback

        provider_name = self.routing_table.get(normalized, "seedance")
        provider = self._get_provider(provider_name)

        reason = self._explain(normalized, provider_name)
        return RoutingDecision(
            shot_type=normalized,
            provider_name=provider_name,
            provider=provider,
            reason=reason,
            flf_enabled=flf,
            extra=kwargs,
        )

    def route_batch(
        self,
        shots: list[dict[str, Any]],
    ) -> list[RoutingDecision]:
        """Route a batch of shots. Each shot dict must have a 'shot_type' key."""
        results: list[RoutingDecision] = []
        for shot in shots:
            st = shot.get("shot_type", ShotType.DIALOGUE)
            flf = shot.get("flf", False)
            results.append(self.route(st, flf=flf))
        return results

    # ── Introspection ────────────────────────────────────────────────────

    def get_routing_table(self) -> dict[str, str]:
        """Return a copy of the current routing table."""
        return dict(self.routing_table)

    def update_routing(self, shot_type: str, provider_name: str) -> None:
        """Update a single route at runtime (e.g. for A/B testing)."""
        if shot_type in ShotType.ALL:
            self.routing_table[shot_type] = provider_name
            self._provider_cache.pop(provider_name, None)

    # ── Private helpers ──────────────────────────────────────────────────

    def _get_provider(self, name: str) -> IProvider | None:
        """Instantiate (and cache) a provider by name."""
        if name in self._provider_cache:
            return self._provider_cache[name]

        cls = _PROVIDER_STUBS.get(name)
        if cls is None:
            # Provider not yet implemented (e.g. "wan") — return None
            return None

        try:
            instance = cls()
            self._provider_cache[name] = instance
            return instance
        except Exception:
            return None

    def _explain(self, shot_type: str, provider_name: str) -> str:
        """Human-readable reason for the routing choice."""
        reasons = {
            (ShotType.ACTION, "kling"): "Kling 3.0 excels at human motion and action sequences",
            (ShotType.DIALOGUE, "seedance"): "Seedance 2.0 is cost-efficient for dialogue scenes ($0.045/s)",
            (ShotType.CREATIVE, "kling"): "Kling 3.0 handles stylized and abstract motion well",
            (ShotType.WIDE, "wan"): "Wan 2.7 open-source model excels at controllable wide shots",
            (ShotType.TRANSITION, "seedance"): "Seedance 2.0 is cost-efficient for transition shots",
        }
        return reasons.get((shot_type, provider_name), f"Routed to {provider_name} for {shot_type}")


class _StubLoader:
    """Minimal loader to reuse IProvider._load_settings without subclassing IProvider."""

    def _load_settings(self, providers_config_path: Path) -> dict[str, dict[str, object]]:
        """Parse YAML-ish settings file (same logic as IProvider._load_settings)."""
        if not providers_config_path.exists():
            return {}
        settings: dict[str, dict[str, object]] = {}
        current_section = ""
        current_list_key = ""
        for raw_line in providers_config_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.strip().startswith("#"):
                continue
            stripped_line = raw_line.strip()
            if not raw_line.startswith(" ") and stripped_line.endswith(":"):
                current_section = stripped_line[:-1]
                settings.setdefault(current_section, {})
                current_list_key = ""
                continue
            if not current_section:
                continue
            if stripped_line.endswith(":"):
                current_list_key = stripped_line[:-1]
                settings[current_section].setdefault(current_list_key, [])
                continue
            if stripped_line.startswith("- ") and current_list_key:
                list_value = settings[current_section].setdefault(current_list_key, [])
                if isinstance(list_value, list):
                    list_value.append(stripped_line[2:].strip())
                continue
            if ":" in stripped_line:
                key, value = stripped_line.split(":", 1)
                settings[current_section][key.strip()] = value.strip()
        return settings
