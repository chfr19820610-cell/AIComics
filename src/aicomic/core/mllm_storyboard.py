"""MLLM story understanding engine — LLM-powered story→storyboard conversion.

Replaces YAML template填空 with a multimodal LLM that reads a story
outline and produces structured shot JSON with scene descriptions,
character emotions, camera movements, and timing.

Uses OpenAI-compatible chat completions API. Falls back to template
engine when no API key is available.

Usage:
    engine = MLLMStoryboardEngine()
    result = engine.generate_storyboard(
        story_text="一个少年踏上修仙之路...",
        episode_count=12,
        genre="cultivation",
    )
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class StoryboardShot:
    """A single shot in an MLLM-generated storyboard."""
    shot_index: int
    scene_description: str
    characters: list[str]
    emotion: str
    camera_movement: str
    duration_seconds: float
    dialogue: str = ""
    narration: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_index": self.shot_index,
            "scene_description": self.scene_description,
            "characters": self.characters,
            "emotion": self.emotion,
            "camera_movement": self.camera_movement,
            "duration_seconds": self.duration_seconds,
            "dialogue": self.dialogue,
            "narration": self.narration,
        }


class MLLMStoryboardEngine:
    """MLLM-powered storyboard generation engine.

    Args:
        api_key: OpenAI-compatible API key (defaults to env).
        base_url: API endpoint.
        model: Model name (should be a capable MLLM).
    """

    # System prompt for story→storyboard conversion
    SYSTEM_PROMPT = (
        "You are a professional animation storyboard director. "
        "Given a story outline, break it down into individual shots for a "
        "short-form animated series (donghua). For each shot, provide:\n"
        "- scene_description: vivid visual description of the scene\n"
        "- characters: list of character names present\n"
        "- emotion: dominant emotional tone (e.g. tense, hopeful, sad, angry)\n"
        "- camera_movement: camera direction (e.g. close-up, wide, pan-left, zoom-in)\n"
        "- duration_seconds: suggested shot duration (3-8 seconds)\n"
        "- dialogue: any spoken dialogue (empty string if none)\n"
        "- narration: voiceover narration (empty string if none)\n\n"
        "Respond in JSON format: {\"shots\": [...], \"total_duration\": number, "
        "\"episode_summary\": \"one-line summary\"}"
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AICOMIC_LLM_KEY")
        self._base_url = base_url
        self._model = model

    @property
    def is_available(self) -> bool:
        """Whether the MLLM engine is configured and ready."""
        return bool(self._api_key)

    def generate_storyboard(
        self,
        story_text: str,
        episode_count: int = 1,
        genre: str = "cultivation",
        shots_per_episode: int = 30,
        max_duration_seconds: int = 240,
    ) -> dict[str, Any]:
        """Generate a structured storyboard from story text.

        Args:
            story_text: Story outline or script text.
            episode_count: Number of episodes to plan.
            genre: Genre for style guidance.
            shots_per_episode: Target shots per episode.
            max_duration_seconds: Max duration per episode.

        Returns:
            Dict with keys: episodes, total_shots, source (mllm/fallback)
        """
        if not self.is_available:
            return self._fallback(story_text, episode_count, genre)

        import httpx

        user_prompt = (
            f"Genre: {genre}\n"
            f"Episodes: {episode_count}\n"
            f"Target shots per episode: {shots_per_episode}\n"
            f"Max duration per episode: {max_duration_seconds} seconds\n\n"
            f"Story:\n{story_text}\n\n"
            f"Generate the storyboard JSON."
        )

        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"},
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            storyboard = json.loads(content)
            storyboard["source"] = "mllm"
            return storyboard

        except Exception as exc:
            # Fall back to template engine
            fallback = self._fallback(story_text, episode_count, genre)
            fallback["mllm_error"] = str(exc)
            return fallback

    def refine_shot(
        self,
        shot: dict[str, Any],
        feedback: str,
    ) -> dict[str, Any]:
        """Refine a single shot based on feedback (e.g. from quality gate).

        Args:
            shot: The shot dict to refine.
            feedback: Feedback text (e.g. "character's hand looks deformed").

        Returns:
            Refined shot dict with updated scene_description.
        """
        if not self.is_available:
            return shot

        import httpx

        prompt = (
            f"Refine this animation shot based on the feedback. "
            f"Only update the scene_description to address the issue.\n\n"
            f"Current shot: {json.dumps(shot, ensure_ascii=False)}\n\n"
            f"Feedback: {feedback}\n\n"
            f"Return the full updated shot as JSON."
        )

        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            refined = json.loads(content)
            refined["refined"] = True
            return refined
        except Exception:
            return shot

    def _fallback(
        self,
        story_text: str,
        episode_count: int,
        genre: str,
    ) -> dict[str, Any]:
        """Fallback to template engine when MLLM is unavailable."""
        try:
            from aicomic.core.template_engine import build_blueprint_from_template
            bp = build_blueprint_from_template(
                template_name=genre,
                hook=story_text[:100],
                episode_code="E01",
            )
            return {
                "source": "fallback",
                "episodes": [{
                    "episode_code": bp.get("episode_code", "E01"),
                    "shots": [],
                    "blueprint": bp,
                }],
                "total_shots": bp.get("shot_count", 0),
                "note": "MLLM unavailable — used template engine fallback",
            }
        except Exception:
            return {
                "source": "fallback",
                "episodes": [],
                "total_shots": 0,
                "error": "Both MLLM and template fallback failed",
            }
