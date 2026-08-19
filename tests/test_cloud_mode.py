"""Cloud mode tests — lightweight API-only mode.

When AICOMIC_CLOUD=1, all local_* providers are skipped in favor of API providers.
"""
from __future__ import annotations

import pytest

from aicomic.providers.cloud_mode import (
    is_cloud_mode,
    filter_cloud_providers,
    get_cloud_defaults,
    apply_cloud_mode,
)


class TestCloudModeDetection:
    """Test cloud mode detection."""

    def test_cloud_mode_off_by_default(self, monkeypatch):
        monkeypatch.delenv("AICOMIC_CLOUD", raising=False)
        assert is_cloud_mode() is False

    def test_cloud_mode_on_with_env(self, monkeypatch):
        monkeypatch.setenv("AICOMIC_CLOUD", "1")
        assert is_cloud_mode() is True

    def test_cloud_mode_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AICOMIC_CLOUD", "true")
        assert is_cloud_mode() is True

    def test_cloud_mode_explicit_off(self, monkeypatch):
        monkeypatch.setenv("AICOMIC_CLOUD", "0")
        assert is_cloud_mode() is False


class TestFilterCloudProviders:
    """Test filtering local providers from config."""

    def test_filters_local_providers(self):
        available = ["openai_image", "local_comfyui_image", "manual_web", "local_comfyui_video"]
        result = filter_cloud_providers(available)
        assert "openai_image" in result
        assert "manual_web" in result
        assert "local_comfyui_image" not in result
        assert "local_comfyui_video" not in result

    def test_preserves_api_providers(self):
        available = ["openai_image", "seedance", "kling", "openai_tts", "edge_tts"]
        result = filter_cloud_providers(available)
        assert result == available

    def test_empty_list(self):
        assert filter_cloud_providers([]) == []


class TestCloudDefaults:
    """Test cloud mode default provider selection."""

    def test_image_default(self):
        defaults = get_cloud_defaults()
        assert defaults["image"] == "openai_image"

    def test_video_default(self):
        defaults = get_cloud_defaults()
        assert defaults["video"] in ("seedance", "kling")

    def test_tts_default(self):
        defaults = get_cloud_defaults()
        assert defaults["tts"] == "openai_tts"


class TestApplyCloudMode:
    """Test applying cloud mode to a providers config dict."""

    def test_replaces_defaults(self):
        config = {
            "image_providers": {"default": "local_comfyui_image", "available": ["openai_image", "local_comfyui_image"]},
            "video_providers": {"default": "local_comfyui_video", "available": ["seedance", "local_comfyui_video"]},
            "tts_providers": {"default": "local_piper_tts", "available": ["openai_tts", "local_piper_tts"]},
        }
        result = apply_cloud_mode(config)
        assert result["image_providers"]["default"] == "openai_image"
        assert "local_comfyui_image" not in result["image_providers"]["available"]
        assert result["video_providers"]["default"] != "local_comfyui_video"
        assert "local_comfyui_video" not in result["video_providers"]["available"]
        assert result["tts_providers"]["default"] == "openai_tts"
        assert "local_piper_tts" not in result["tts_providers"]["available"]

    def test_preserves_non_provider_keys(self):
        config = {
            "image_providers": {"default": "local_comfyui_image", "available": ["openai_image"]},
            "openai_api": {"base_url": "https://api.example.com"},
        }
        result = apply_cloud_mode(config)
        assert result["openai_api"]["base_url"] == "https://api.example.com"

    def test_already_cloud_config_unchanged(self):
        config = {
            "image_providers": {"default": "openai_image", "available": ["openai_image"]},
            "video_providers": {"default": "seedance", "available": ["seedance"]},
            "tts_providers": {"default": "openai_tts", "available": ["openai_tts"]},
        }
        result = apply_cloud_mode(config)
        assert result == config
