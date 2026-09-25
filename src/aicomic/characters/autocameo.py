"""AutoCameo — selfie-to-comic face replacement engine.

Users upload a selfie → facial features are extracted → character faces
in generated animation are replaced with the user's face.

Inspired by ViMax's AutoCameo feature (12.1K GitHub stars).

Pipeline:
  1. Selfie upload → face detection + feature extraction
  2. Feature vector stored as Content Anchor reference
  3. During generation, face swap prompts injected into provider requests
  4. Optional: post-generation face swap via insightface/roop

Usage:
    cameo = AutoCameo()
    session = cameo.register_user("user_001", Path("selfie.jpg"))
    prompt = cameo.inject_face_prompt(base_prompt="少年站在悬崖边", character="主角")
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aicomic.image_consistency.content_anchor import ContentAnchor

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FaceFeatures:
    """Extracted facial features from a selfie."""

    face_shape: str = ""       # oval, round, square, heart, diamond
    skin_tone: str = ""        # fair, tan, dark, etc.
    hair_color: str = ""       # black, brown, blonde, etc.
    hair_style: str = ""       # short, long, ponytail, etc.
    eye_color: str = ""        # brown, blue, green, etc.
    eye_shape: str = ""        # almond, round, monolid, etc.
    nose_shape: str = ""       # straight, round, pointed
    lip_shape: str = ""        # full, thin, medium
    jawline: str = ""          # sharp, round, square
    gender_guess: str = ""     # male, female, ambiguous
    age_guess: str = ""        # young, adult, middle, senior
    feature_vector: dict[str, Any] = field(default_factory=dict)
    source_image: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "face_shape": self.face_shape,
            "skin_tone": self.skin_tone,
            "hair_color": self.hair_color,
            "hair_style": self.hair_style,
            "eye_color": self.eye_color,
            "eye_shape": self.eye_shape,
            "nose_shape": self.nose_shape,
            "lip_shape": self.lip_shape,
            "jawline": self.jawline,
            "gender_guess": self.gender_guess,
            "age_guess": self.age_guess,
            "feature_vector": self.feature_vector,
            "source_image": self.source_image,
        }


@dataclass
class AutoCameoSession:
    """A user's AutoCameo registration session."""

    user_id: str
    character_id: str  # which character they're replacing
    face_features: FaceFeatures
    selfie_path: str
    registered_at: str = ""
    consent_given: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "character_id": self.character_id,
            "face_features": self.face_features.to_dict(),
            "selfie_path": self.selfie_path,
            "registered_at": self.registered_at,
            "consent_given": self.consent_given,
        }


class AutoCameo:
    """Selfie-to-comic face replacement engine.

    Args:
        api_key: OpenAI-compatible API key for VLM face analysis.
        base_url: API endpoint.
        model: VLM model name.
        storage_dir: Directory to store selfie images and features.
    """

    VLM_PROMPT = (
        "Analyze this selfie photo and extract facial features for "
        "anime-style character generation. Respond in JSON format:\n"
        '{\n'
        '  "face_shape": "oval|round|square|heart|diamond",\n'
        '  "skin_tone": "fair|tan|dark|medium",\n'
        '  "hair_color": "black|brown|blonde|red|gray|other",\n'
        '  "hair_style": "short|medium|long|ponytail|bun|bald",\n'
        '  "eye_color": "brown|blue|green|hazel|black",\n'
        '  "eye_shape": "almond|round|monolid|hooded",\n'
        '  "nose_shape": "straight|round|pointed|wide",\n'
        '  "lip_shape": "full|thin|medium|wide",\n'
        '  "jawline": "sharp|round|square|heart",\n'
        '  "gender_guess": "male|female|ambiguous",\n'
        '  "age_guess": "young|adult|middle|senior"\n'
        '}'
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        storage_dir: Path | str = "state/autocameo",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AICOMIC_LLM_KEY")
        self._base_url = base_url
        self._model = model
        self._storage = Path(storage_dir)
        self._storage.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, AutoCameoSession] = {}

    @property
    def is_available(self) -> bool:
        """Whether VLM-based face analysis is available."""
        return bool(self._api_key)

    def register_user(
        self,
        user_id: str,
        selfie_path: Path | str,
        character_id: str = "protagonist",
        consent: bool = True,
    ) -> AutoCameoSession:
        """Register a user's selfie for face replacement.

        Args:
            user_id: Unique user identifier.
            selfie_path: Path to the selfie image.
            character_id: Which character to replace with this face.
            consent: User consent for face usage (required).

        Returns:
            AutoCameoSession with extracted features.
        """
        if not consent:
            raise ValueError("User consent is required for AutoCameo face replacement")

        path = Path(selfie_path)
        if not path.exists():
            raise FileNotFoundError(f"Selfie not found: {path}")

        # Copy selfie to storage
        stored_path = self._storage / user_id / "selfie" / path.name
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(path.read_bytes())

        # Extract features
        features = self._extract_features(stored_path)
        features.source_image = str(stored_path)

        import datetime
        session = AutoCameoSession(
            user_id=user_id,
            character_id=character_id,
            face_features=features,
            selfie_path=str(stored_path),
            registered_at=datetime.datetime.now().isoformat(),
            consent_given=True,
        )
        self._sessions[user_id] = session

        # Save session
        session_file = self._storage / user_id / "session.json"
        session_file.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        return session

    def _extract_features(self, image_path: Path) -> FaceFeatures:
        """Extract facial features from a selfie using VLM.

        Falls back to empty features if VLM is unavailable.
        """
        if not self.is_available:
            return FaceFeatures(source_image=str(image_path))

        import base64
        import httpx

        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.VLM_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        ],
                    }],
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)

            return FaceFeatures(
                face_shape=data.get("face_shape", ""),
                skin_tone=data.get("skin_tone", ""),
                hair_color=data.get("hair_color", ""),
                hair_style=data.get("hair_style", ""),
                eye_color=data.get("eye_color", ""),
                eye_shape=data.get("eye_shape", ""),
                nose_shape=data.get("nose_shape", ""),
                lip_shape=data.get("lip_shape", ""),
                jawline=data.get("jawline", ""),
                gender_guess=data.get("gender_guess", ""),
                age_guess=data.get("age_guess", ""),
                feature_vector=data,
                source_image=str(image_path),
            )
        except Exception:
            return FaceFeatures(source_image=str(image_path))

    def inject_face_prompt(
        self,
        base_prompt: str,
        user_id: str = "",
        character_name: str = "",
    ) -> str:
        """Inject face description into a generation prompt.

        Args:
            base_prompt: Original generation prompt.
            user_id: Registered user whose face to inject.
            character_name: Character name in the scene.

        Returns:
            Enhanced prompt with face description appended.
        """
        session = self._sessions.get(user_id)
        if session is None:
            return base_prompt

        f = session.face_features
        parts: list[str] = []
        if f.face_shape:
            parts.append(f"{f.face_shape} face shape")
        if f.skin_tone:
            parts.append(f"{f.skin_tone} skin")
        if f.hair_color or f.hair_style:
            hair = " ".join(filter(None, [f.hair_color, f.hair_style + " hair"]))
            parts.append(hair)
        if f.eye_color:
            parts.append(f"{f.eye_color} eyes")
        if f.jawline:
            parts.append(f"{f.jawline} jawline")
        if f.gender_guess:
            parts.append(f"{f.gender_guess}")

        if not parts:
            return base_prompt

        face_desc = ", ".join(parts)
        if character_name:
            return f"{base_prompt} {character_name} appearance: {face_desc}."
        return f"{base_prompt} Character appearance: {face_desc}."

    def get_session(self, user_id: str) -> AutoCameoSession | None:
        """Get a user's session."""
        return self._sessions.get(user_id)

    def load_session(self, user_id: str) -> AutoCameoSession | None:
        """Load a saved session from disk."""
        session_file = self._storage / user_id / "session.json"
        if not session_file.exists():
            return None
        data = json.loads(session_file.read_text(encoding="utf-8"))
        features = FaceFeatures(**data.get("face_features", {}))
        session = AutoCameoSession(
            user_id=data["user_id"],
            character_id=data.get("character_id", ""),
            face_features=features,
            selfie_path=data.get("selfie_path", ""),
            registered_at=data.get("registered_at", ""),
            consent_given=data.get("consent_given", False),
        )
        self._sessions[user_id] = session
        return session

    def to_content_anchor(self, user_id: str) -> "ContentAnchor":
        """Convert a user's face features to a ContentAnchor reference.

        This bridges AutoCameo with the cross-episode consistency system.
        """
        from aicomic.image_consistency.content_anchor import ContentAnchor

        session = self._sessions.get(user_id)
        if session is None:
            raise ValueError(f"User {user_id} not registered")

        anchor = ContentAnchor(
            character_id=f"cameo_{user_id}",
            character_name=f"User {user_id}",
        )
        anchor.add_reference(
            "selfie",
            session.selfie_path,
            features=session.face_features.feature_vector,
            metadata={"source": "autocameo", "user_id": user_id},
        )
        return anchor
