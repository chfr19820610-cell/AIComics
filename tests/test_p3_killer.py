"""Tests for v5.0 P3 killer features: AutoCameo, AudioAvatar, PublishOrchestrator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── AutoCameo ─────────────────────────────────────────────────────────────


class TestAutoCameo:
    def test_engine_unavailable_without_key(self):
        from aicomic.characters.autocameo import AutoCameo
        cameo = AutoCameo(api_key="", storage_dir="/tmp/test_cameo")
        assert cameo.is_available is False

    def test_engine_available_with_key(self):
        from aicomic.characters.autocameo import AutoCameo
        cameo = AutoCameo(api_key="test_key", storage_dir="/tmp/test_cameo")
        assert cameo.is_available is True

    def test_register_requires_consent(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        selfie = tmp_path / "selfie.jpg"
        selfie.write_bytes(b"fake image")
        with pytest.raises(ValueError, match="consent"):
            cameo.register_user("user_001", selfie, consent=False)

    def test_register_missing_selfie(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        with pytest.raises(FileNotFoundError):
            cameo.register_user("user_001", tmp_path / "nonexistent.jpg")

    def test_register_success(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo, FaceFeatures
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        selfie = tmp_path / "selfie.jpg"
        selfie.write_bytes(b"fake image data")
        session = cameo.register_user("user_001", selfie, consent=True)
        assert session.user_id == "user_001"
        assert session.consent_given is True
        assert session.selfie_path != ""

    def test_inject_face_prompt(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo, FaceFeatures, AutoCameoSession
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        # Manually create a session
        features = FaceFeatures(
            face_shape="oval", skin_tone="fair", hair_color="black",
            hair_style="short", eye_color="brown", jawline="sharp",
            gender_guess="male",
        )
        cameo._sessions["user_001"] = AutoCameoSession(
            user_id="user_001",
            character_id="protagonist",
            face_features=features,
            selfie_path="",
        )
        result = cameo.inject_face_prompt("少年站在悬崖边", "user_001", "主角")
        assert "oval face" in result
        assert "fair skin" in result
        assert "brown eyes" in result

    def test_inject_face_prompt_unknown_user(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        result = cameo.inject_face_prompt("test prompt", "unknown_user")
        assert result == "test prompt"  # unchanged

    def test_to_content_anchor(self, tmp_path):
        from aicomic.characters.autocameo import AutoCameo, FaceFeatures, AutoCameoSession
        cameo = AutoCameo(api_key="", storage_dir=str(tmp_path / "cameo"))
        features = FaceFeatures(face_shape="round", feature_vector={"custom": "data"})
        cameo._sessions["u1"] = AutoCameoSession(
            user_id="u1", character_id="prot", face_features=features, selfie_path="/test.jpg",
        )
        anchor = cameo.to_content_anchor("u1")
        assert anchor.character_id == "cameo_u1"
        assert "selfie" in anchor.frames

    def test_face_features_to_dict(self):
        from aicomic.characters.autocameo import FaceFeatures
        f = FaceFeatures(face_shape="oval", skin_tone="fair")
        d = f.to_dict()
        assert d["face_shape"] == "oval"
        assert d["skin_tone"] == "fair"


# ── AudioAvatar ───────────────────────────────────────────────────────────


class TestAudioAvatar:
    def test_engine_unavailable(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        assert avatar.is_available is False

    def test_analyze_nonexistent_audio(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        analysis = avatar.analyze_audio("/nonexistent.wav")
        assert analysis.duration_seconds == 0.0

    def test_build_avatar_prompt(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        prompt = avatar.build_avatar_prompt(emotion="angry", speaking=True)
        assert "furrowed" in prompt.lower()
        assert "lip-synced" in prompt

    def test_build_avatar_prompt_neutral(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        prompt = avatar.build_avatar_prompt(emotion="neutral", speaking=False)
        assert "neutral" in prompt
        assert "mouth closed" in prompt

    def test_build_avatar_prompt_with_description(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        prompt = avatar.build_avatar_prompt(
            emotion="happy",
            character_description="young man with black hair",
        )
        assert "young man" in prompt
        assert "smile" in prompt

    def test_generate_missing_files(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        result = avatar.generate("/nonexistent.png", "/nonexistent.wav")
        assert result.status == "error"
        assert "Missing" in result.error

    def test_generate_fallback_no_api(self, tmp_path):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        img = tmp_path / "char.png"
        img.write_bytes(b"fake")
        audio = tmp_path / "voice.wav"
        audio.write_bytes(b"fake")
        result = avatar.generate(img, audio, emotion="tense")
        assert result.status == "fallback"
        assert "prompt" in result.metadata

    def test_supported_emotions(self):
        from aicomic.video_synthesis.audio_avatar import AudioAvatar
        avatar = AudioAvatar(api_key="")
        emotions = avatar.get_supported_emotions()
        assert "neutral" in emotions
        assert "happy" in emotions
        assert "angry" in emotions
        assert "tense" in emotions

    def test_avatar_result_dataclass(self):
        from aicomic.video_synthesis.audio_avatar import AvatarResult
        r = AvatarResult(status="success", video_path="/test.mp4", duration_seconds=10.5)
        assert r.status == "success"
        assert r.duration_seconds == 10.5


# ── PublishOrchestrator ───────────────────────────────────────────────────


class TestPublishOrchestrator:
    def test_supported_platforms(self):
        from aicomic.publish.orchestrator import PublishOrchestrator
        orch = PublishOrchestrator()
        platforms = orch.get_supported_platforms()
        assert "douyin" in platforms["domestic"]
        assert "bilibili" in platforms["domestic"]
        assert "youtube" in platforms["international"]
        assert "tiktok" in platforms["international"]

    def test_unknown_platform_skipped(self):
        from aicomic.publish.orchestrator import PublishOrchestrator
        orch = PublishOrchestrator()
        result = orch.publish_all(
            video_path="/test.mp4",
            platforms=["unknown_platform"],
            config={},
        )
        assert "unknown_platform" in result.skipped

    def test_publish_result_success_rate(self):
        from aicomic.publish.orchestrator import PublishResult
        r = PublishResult(
            total_platforms=4,
            succeeded=["youtube", "tiktok"],
            failed=["douyin"],
            skipped=["bilibili"],
        )
        assert r.success_rate == 0.5

    def test_publish_result_to_dict(self):
        from aicomic.publish.orchestrator import PublishResult
        r = PublishResult(total_platforms=2, succeeded=["youtube"], failed=["tiktok"])
        d = r.to_dict()
        assert d["total_platforms"] == 2
        assert d["success_rate"] == 0.5
        assert "youtube" in d["succeeded"]

    def test_domestic_platforms_set(self):
        from aicomic.publish.orchestrator import PublishOrchestrator
        assert "douyin" in PublishOrchestrator.DOMESTIC_PLATFORMS
        assert "xiaohongshu" in PublishOrchestrator.DOMESTIC_PLATFORMS

    def test_international_platforms_set(self):
        from aicomic.publish.orchestrator import PublishOrchestrator
        assert "youtube" in PublishOrchestrator.INTERNATIONAL_PLATFORMS
        assert "instagram" in PublishOrchestrator.INTERNATIONAL_PLATFORMS
