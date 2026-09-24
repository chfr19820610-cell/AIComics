"""Content Anchor — structured character memory for cross-episode consistency.

Based on Gloria (CVPR 2026) and SlotMem research: maintains a structured
set of anchor frames for each character (front/side/back/45°/expression set)
that persists across episodes and can be used to enforce visual consistency.

Usage:
    anchor = ContentAnchor(character_id="char_001")
    anchor.add_reference("front", Path("refs/front.png"), metadata={...})
    anchor.add_reference("side", Path("refs/side.png"))
    score = anchor.check_consistency(Path("generated/shot_001.png"))
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Standard anchor views for character reference
STANDARD_VIEWS = [
    "front",        # 正面
    "side_left",    # 左侧面
    "side_right",   # 右侧面
    "back",         # 背面
    "three_quarter",  # 45°斜侧
]

# Standard expression set
STANDARD_EXPRESSIONS = [
    "neutral",
    "happy",
    "angry",
    "sad",
    "surprised",
]


@dataclass
class AnchorFrame:
    """A single reference frame in the content anchor."""

    view: str  # e.g. "front", "side_left", "happy"
    image_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
    # Feature vector for comparison (placeholder for future ML integration)
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "view": self.view,
            "image_path": self.image_path,
            "metadata": self.metadata,
            "features": self.features,
        }


class ContentAnchor:
    """Structured character anchor memory for cross-episode consistency.

    Each character has:
      - 5 standard views (front/side_left/side_right/back/three_quarter)
      - 5 standard expressions (neutral/happy/angry/sad/surprised)
      - Custom views for specific scenes
      - Feature vectors for automated consistency checking
    """

    def __init__(self, character_id: str, character_name: str = "") -> None:
        self.character_id = character_id
        self.character_name = character_name
        self.frames: dict[str, AnchorFrame] = {}
        self._episode_history: list[dict[str, Any]] = []

    def add_reference(
        self,
        view: str,
        image_path: Path | str,
        metadata: dict[str, Any] | None = None,
        features: dict[str, Any] | None = None,
    ) -> None:
        """Add or update a reference frame for a specific view.

        Args:
            view: View name (e.g. "front", "happy", "custom_battle_stance").
            image_path: Path to the reference image.
            metadata: Optional metadata (e.g. episode, scene, lighting).
            features: Optional feature dict for automated comparison.
        """
        self.frames[view] = AnchorFrame(
            view=view,
            image_path=str(image_path),
            metadata=metadata or {},
            features=features or {},
        )

    def get_reference(self, view: str) -> AnchorFrame | None:
        """Get a reference frame by view name."""
        return self.frames.get(view)

    def get_all_views(self) -> list[str]:
        """Get all available view names."""
        return sorted(self.frames.keys())

    def get_completeness_score(self) -> float:
        """How complete is this anchor (0.0-1.0).

        Checks how many of the 5 standard views + 5 expressions are present.
        """
        standard = set(STANDARD_VIEWS + STANDARD_EXPRESSIONS)
        present = standard.intersection(self.frames.keys())
        return len(present) / len(standard) if standard else 1.0

    def get_missing_views(self) -> list[str]:
        """Get list of missing standard views and expressions."""
        standard = set(STANDARD_VIEWS + STANDARD_EXPRESSIONS)
        return sorted(standard - self.frames.keys())

    def check_consistency(
        self,
        generated_features: dict[str, Any],
        reference_view: str = "front",
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """Check if a generated image is consistent with the anchor.

        Compares feature dicts between generated image and reference frame.
        Returns PASS/WARN/FAIL with similarity score.

        Args:
            generated_features: Feature dict from the generated image.
            reference_view: Which anchor view to compare against.
            threshold: Similarity threshold for PASS (0.0-1.0).

        Returns:
            {status, score, reference_view, diffs}
        """
        ref = self.frames.get(reference_view)
        if ref is None:
            return {
                "status": "WARN",
                "score": 0.0,
                "reference_view": reference_view,
                "diffs": ["Reference frame not found for this view"],
            }

        # Simple feature overlap comparison
        if not ref.features:
            return {
                "status": "WARN",
                "score": 0.0,
                "reference_view": reference_view,
                "diffs": ["No reference features stored — cannot compare"],
            }

        common_keys = set(ref.features.keys()) & set(generated_features.keys())
        if not common_keys:
            return {
                "status": "WARN",
                "score": 0.0,
                "reference_view": reference_view,
                "diffs": ["No common feature keys for comparison"],
            }

        matched = 0
        diffs = []
        for key in common_keys:
            if ref.features[key] == generated_features[key]:
                matched += 1
            else:
                diffs.append(f"{key}: ref={ref.features[key]}, gen={generated_features[key]}")

        score = matched / len(common_keys)
        status = "PASS" if score >= threshold else ("WARN" if score >= threshold * 0.5 else "FAIL")

        return {
            "status": status,
            "score": round(score, 3),
            "reference_view": reference_view,
            "diffs": diffs,
        }

    def record_episode_usage(
        self,
        episode_code: str,
        shot_indices: list[int],
        consistency_scores: list[float] | None = None,
    ) -> None:
        """Record that this character appeared in an episode.

        Builds a usage history for cross-episode drift tracking.

        Args:
            episode_code: Episode identifier (e.g. "E03").
            shot_indices: Shot numbers where this character appeared.
            consistency_scores: Per-shot consistency scores.
        """
        scores = consistency_scores or []
        entry = {
            "episode_code": episode_code,
            "shot_indices": shot_indices,
            "avg_consistency": sum(scores) / len(scores) if scores else 0.0,
            "min_consistency": min(scores) if scores else 0.0,
        }
        self._episode_history.append(entry)

    def get_drift_trend(self) -> dict[str, Any]:
        """Analyze consistency drift across episodes.

        Returns:
            {trend: improving/stable/degrading, episodes: [...], avg_score}
        """
        if len(self._episode_history) < 2:
            return {"trend": "insufficient_data", "episodes": len(self._episode_history)}

        scores = [e["avg_consistency"] for e in self._episode_history]
        avg = sum(scores) / len(scores)

        # Compare first half vs second half
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / max(mid, 1)
        second_half = sum(scores[mid:]) / max(len(scores) - mid, 1)

        if second_half > first_half + 0.05:
            trend = "improving"
        elif second_half < first_half - 0.05:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "episodes": len(self._episode_history),
            "avg_score": round(avg, 3),
            "first_half_avg": round(first_half, 3),
            "second_half_avg": round(second_half, 3),
        }

    def save(self, path: Path | str) -> str:
        """Save anchor to a JSON file."""
        data = {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "frames": {k: v.to_dict() for k, v in self.frames.items()},
            "episode_history": self._episode_history,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)

    @classmethod
    def load(cls, path: Path | str) -> "ContentAnchor":
        """Load anchor from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        anchor = cls(
            character_id=data["character_id"],
            character_name=data.get("character_name", ""),
        )
        for view, frame_data in data.get("frames", {}).items():
            anchor.frames[view] = AnchorFrame(
                view=frame_data["view"],
                image_path=frame_data["image_path"],
                metadata=frame_data.get("metadata", {}),
                features=frame_data.get("features", {}),
            )
        anchor._episode_history = data.get("episode_history", [])
        return anchor
