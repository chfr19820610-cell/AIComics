"""Model cascade router — Jev's difficulty-based model selection pattern.

Jev's insight: don't send every request to the most expensive handler.
Classify difficulty first, then route to the appropriate model tier.

AIComics adaptation: classify each shot's generation difficulty and
route to the right video provider:
  - Easy (static, simple motion) → Wan (cheap, fast, local)
  - Medium (moderate motion, dialogue) → Seedance (balanced)
  - Hard (complex action, fast cuts) → Kling (best quality, paid)
  - Extreme (multi-character, VFX) → escalate to human direction

This saves budget by not burning Kling credits on simple talking-head shots.

Usage:
    from aicomic.intelligence.model_cascade import ModelCascade, CascadeRoute

    cascade = ModelCascade()
    route = cascade.route(
        shot_description="Close-up of warrior leaping across rooftops, sword swing",
        motion_intensity="high",
        character_count=2,
    )
    print(f"Use {route.provider} (confidence: {route.confidence:.2f})")
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aicomic.intelligence.calibrated_decision import DecisionEngine, Choice


class Difficulty(Enum):
    """Generation difficulty tiers."""
    TRIVIAL = "trivial"    # static frame, no motion
    EASY = "easy"          # simple motion, single character
    MEDIUM = "medium"      # moderate action, dialogue
    HARD = "hard"          # complex action, fast cuts
    EXTREME = "extreme"    # multi-character VFX, escalate


@dataclass
class CascadeRoute:
    """Result of model cascade routing."""
    provider: str
    difficulty: Difficulty
    confidence: float
    reasoning: str
    estimated_cost: float = 0.0  # in cents
    should_escalate: bool = False


class ModelCascade:
    """Route video generation to the appropriate provider based on difficulty.

    Jev pattern: classify difficulty with calibrated scoring, then route
    to the cheapest provider that can handle it. Confidence-gated: if
    difficulty is ambiguous, default to the safer (more capable) option.
    """

    # Provider cost in cents per second of output
    PROVIDER_COSTS: dict[str, float] = {
        "wan": 0.0,       # local, free
        "seedance": 2.0,  # cheap API
        "kling": 8.0,     # premium API
        "human": 0.0,     # manual, cost is time not money
    }

    # Provider capabilities (0-10 per dimension)
    PROVIDER_CAPS: dict[str, dict[str, int]] = {
        "wan": {"motion": 3, "quality": 5, "speed": 9, "cost_efficiency": 10},
        "seedance": {"motion": 6, "quality": 7, "speed": 7, "cost_efficiency": 7},
        "kling": {"motion": 9, "quality": 9, "speed": 5, "cost_efficiency": 4},
        "human": {"motion": 10, "quality": 10, "speed": 1, "cost_efficiency": 1},
    }

    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()

    def classify_difficulty(
        self,
        shot_description: str,
        motion_intensity: str = "medium",
        character_count: int = 1,
        has_vfx: bool = False,
    ) -> Difficulty:
        """Classify the generation difficulty of a shot.

        Args:
            shot_description: Natural language shot description.
            motion_intensity: low/medium/high/extreme.
            character_count: Number of characters in frame.
            has_vfx: Whether VFX/particles are needed.

        Returns:
            Difficulty tier.
        """
        if has_vfx or character_count >= 3:
            return Difficulty.EXTREME

        intensity_map = {
            "none": Difficulty.TRIVIAL,
            "low": Difficulty.EASY,
            "medium": Difficulty.MEDIUM,
            "high": Difficulty.HARD,
            "extreme": Difficulty.EXTREME,
        }
        base = intensity_map.get(motion_intensity.lower(), Difficulty.MEDIUM)

        # Bump difficulty for multiple characters
        if character_count == 2 and base == Difficulty.MEDIUM:
            base = Difficulty.HARD

        # Check for action keywords in description
        action_words = {"leap", "jump", "fly", "explode", "fight", "chase", "run", "swing", "crash"}
        desc_lower = shot_description.lower()
        if any(w in desc_lower for w in action_words):
            if base == Difficulty.EASY:
                base = Difficulty.MEDIUM
            elif base == Difficulty.MEDIUM:
                base = Difficulty.HARD

        return base

    def route(
        self,
        shot_description: str,
        motion_intensity: str = "medium",
        character_count: int = 1,
        has_vfx: bool = False,
        budget_aware: bool = True,
    ) -> CascadeRoute:
        """Route a shot to the best provider.

        Args:
            shot_description: Natural language shot description.
            motion_intensity: low/medium/high/extreme.
            character_count: Number of characters.
            has_vfx: VFX flag.
            budget_aware: If True, prefer cheaper providers when safe.

        Returns:
            CascadeRoute with provider, difficulty, confidence, cost estimate.
        """
        difficulty = self.classify_difficulty(
            shot_description, motion_intensity, character_count, has_vfx
        )

        # Direct routing for extreme difficulty
        if difficulty == Difficulty.EXTREME:
            return CascadeRoute(
                provider="human",
                difficulty=difficulty,
                confidence=0.9,
                reasoning="VFX or 3+ characters — needs human direction",
                estimated_cost=0.0,
                should_escalate=True,
            )

        # Use calibrated choice for provider selection
        provider_options = {
            "wan": "static simple motion low quality fast cheap local",
            "seedance": "moderate motion dialogue balanced quality speed cost",
            "kling": "complex action fast cuts high quality premium expensive",
        }

        # Build state from difficulty + description
        state = f"{difficulty.value} {shot_description} {motion_intensity} {character_count}chars"

        choice: Choice = self.engine.choice(state=state, options=provider_options)

        # Map difficulty to minimum provider tier
        min_tier = {
            Difficulty.TRIVIAL: ["wan", "seedance", "kling"],
            Difficulty.EASY: ["wan", "seedance", "kling"],
            Difficulty.MEDIUM: ["seedance", "kling", "wan"],
            Difficulty.HARD: ["kling", "seedance", "wan"],
        }

        # Pick highest-probability provider that meets minimum tier
        tier_order = min_tier.get(difficulty, ["kling", "seedance", "wan"])
        selected = tier_order[0]
        for provider in tier_order:
            if provider in choice.probabilities:
                selected = provider
                break

        # Budget-aware override: if difficulty is easy/trivial and budget-aware, prefer wan
        if budget_aware and difficulty in (Difficulty.TRIVIAL, Difficulty.EASY):
            selected = "wan"

        cost = self.PROVIDER_COSTS.get(selected, 0.0)

        return CascadeRoute(
            provider=selected,
            difficulty=difficulty,
            confidence=choice.confidence,
            reasoning=f"Difficulty={difficulty.value}, provider={selected} (budget_aware={budget_aware})",
            estimated_cost=cost,
            should_escalate=False,
        )

    def estimate_batch_cost(self, routes: list[CascadeRoute], duration_seconds: float = 5.0) -> float:
        """Estimate total cost for a batch of routes.

        Args:
            routes: List of CascadeRoute results.
            duration_seconds: Output duration per shot.

        Returns:
            Total estimated cost in cents.
        """
        return sum(r.estimated_cost * duration_seconds for r in routes)
