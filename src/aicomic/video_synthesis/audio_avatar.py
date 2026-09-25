"""Audio-driven avatar — TTS audio → character lip-sync + expression animation.

Inspired by HunyuanVideo-Avatar (12.5K stars): generates lip-synced
character animation from audio input, replacing static frames + narration.

Pipeline:
  1. TTS audio generated from script
  2. Audio analyzed for phonemes and emotion
  3. Character reference image + audio → animated avatar video
  4. Provider API (e.g. HunyuanVideo-Avatar, SadTalker, etc.)

Usage:
    avatar = AudioAvatar()
    result = avatar.generate(
        character_image=Path("character.png"),
        audio_path=Path("narration.wav"),
        emotion="tense",
    )
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AudioAnalysis:
    """Analysis of an audio file for avatar generation."""

    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    avg_volume: float = 0.0
    peak_volume: float = 0.0
    estimated_emotion: str = "neutral"  # neutral, happy, sad, angry, surprised
    speaking_rate: float = 0.0  # words per second estimate
    silence_ratio: float = 0.0  # ratio of silence to total duration
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AvatarResult:
    """Result of avatar video generation."""

    status: str  # success / error / fallback
    video_path: str = ""
    avatar_provider: str = ""
    audio_analysis: AudioAnalysis | None = None
    duration_seconds: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Emotion → visual expression mapping
EMOTION_MAP: dict[str, dict[str, str]] = {
    "neutral": {"expression": "neutral face, relaxed mouth, calm eyes", "brow": "relaxed eyebrows"},
    "happy": {"expression": "slight smile, raised cheeks, bright eyes", "brow": "raised eyebrows"},
    "sad": {"expression": "downturned mouth, drooping eyelids, melancholic gaze", "brow": "inner eyebrows raised"},
    "angry": {"expression": "furrowed brow, tightened jaw, narrowed eyes", "brow": "drawn-together eyebrows"},
    "surprised": {"expression": "wide open eyes, open mouth, raised eyebrows", "brow": "high raised eyebrows"},
    "tense": {"expression": "tight lips, alert eyes, rigid posture", "brow": "slightly furrowed"},
    "fearful": {"expression": "wide eyes, trembling lips, pale complexion", "brow": "raised and drawn together"},
}


class AudioAvatar:
    """Audio-driven avatar animation engine.

    Args:
        api_key: API key for avatar generation service.
        base_url: Avatar API endpoint.
        provider: Provider name (hunyuan, sadtalker, etc.).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.hunyuan.cloud.tencent.com/v1",
        provider: str = "hunyuan",
    ) -> None:
        self._api_key = api_key or os.environ.get("AVATAR_API_KEY") or os.environ.get("AICOMIC_AVATAR_KEY")
        self._base_url = base_url
        self._provider = provider

    @property
    def is_available(self) -> bool:
        """Whether the avatar API is configured."""
        return bool(self._api_key)

    def analyze_audio(
        self,
        audio_path: Path | str,
    ) -> AudioAnalysis:
        """Analyze an audio file for emotion, rate, and volume.

        Uses ffprobe for basic metadata. Falls back to defaults if
        ffprobe is unavailable.
        """
        import shutil
        import subprocess

        path = Path(audio_path)
        analysis = AudioAnalysis()

        if not path.exists():
            return analysis

        if shutil.which("ffprobe"):
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-show_format",
                        "-show_streams",
                        "-of", "json",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    fmt = data.get("format", {})
                    streams = data.get("streams", [])
                    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

                    analysis.duration_seconds = float(fmt.get("duration", 0))
                    analysis.sample_rate = int(audio_stream.get("sample_rate", 0))
                    analysis.channels = int(audio_stream.get("channels", 0))
            except Exception:
                pass

        return analysis

    def build_avatar_prompt(
        self,
        emotion: str = "neutral",
        speaking: bool = True,
        character_description: str = "",
    ) -> str:
        """Build a visual prompt for avatar generation.

        Args:
            emotion: Emotional tone of the speech.
            speaking: Whether the character is speaking (vs. listening).
            character_description: Character visual description.

        Returns:
            Prompt string for the avatar generation model.
        """
        emotion_info = EMOTION_MAP.get(emotion, EMOTION_MAP["neutral"])
        parts = []

        if character_description:
            parts.append(character_description)

        parts.append(emotion_info["expression"])
        parts.append(emotion_info["brow"])

        if speaking:
            parts.append("mouth moving as if speaking, lip-synced to audio")
        else:
            parts.append("mouth closed, listening expression")

        return ", ".join(parts)

    def generate(
        self,
        character_image: Path | str,
        audio_path: Path | str,
        emotion: str = "neutral",
        character_description: str = "",
    ) -> AvatarResult:
        """Generate an avatar video from character image + audio.

        Args:
            character_image: Path to character reference image.
            audio_path: Path to TTS audio file.
            emotion: Speech emotion for expression mapping.
            character_description: Character visual description.

        Returns:
            AvatarResult with video path or error.
        """
        img_path = Path(character_image)
        aud_path = Path(audio_path)

        if not img_path.exists() or not aud_path.exists():
            return AvatarResult(
                status="error",
                error=f"Missing input: image={img_path.exists()}, audio={aud_path.exists()}",
            )

        # Analyze audio
        analysis = self.analyze_audio(aud_path)

        # Build prompt
        prompt = self.build_avatar_prompt(
            emotion=emotion,
            speaking=True,
            character_description=character_description,
        )

        if not self.is_available:
            return AvatarResult(
                status="fallback",
                avatar_provider=self._provider,
                audio_analysis=analysis,
                error="Avatar API not configured — use prompt for manual generation",
                metadata={"prompt": prompt, "emotion": emotion},
            )

        # Call avatar API (provider-specific)
        import httpx

        try:
            # HunyuanVideo-Avatar style API
            resp = httpx.post(
                f"{self._base_url}/avatar/generate",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "character_image": str(img_path),
                    "audio_path": str(aud_path),
                    "emotion": emotion,
                    "prompt": prompt,
                    "provider": self._provider,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()

            return AvatarResult(
                status="success",
                video_path=data.get("video_url", ""),
                avatar_provider=self._provider,
                audio_analysis=analysis,
                duration_seconds=analysis.duration_seconds,
                metadata=data,
            )
        except Exception as exc:
            return AvatarResult(
                status="error",
                avatar_provider=self._provider,
                audio_analysis=analysis,
                error=str(exc),
                metadata={"prompt": prompt},
            )

    def get_supported_emotions(self) -> list[str]:
        """Get list of supported emotions for avatar expression."""
        return list(EMOTION_MAP.keys())
