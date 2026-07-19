from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo
from aicomic.providers.openai_provider import OpenAIProvider, DALL_EProvider
from aicomic.providers.seedance_provider import SeedanceProvider
from aicomic.providers.comfyui_provider import ComfyUIProvider
from aicomic.providers.manual_provider import ManualProvider, PiperTTSProvider
from aicomic.providers.provider_registry import (
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def providers_config_path(tmp_path: Path) -> Path:
    path = tmp_path / "providers.yaml"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture
def openai_request_item() -> dict[str, Any]:
    return {
        "request_id": "REQ_TEST_001",
        "payload": {
            "job_id": "JOB_TEST_001",
            "episode_code": "E01",
            "shot_id": "S001",
            "job_type": "image",
            "provider": "openai_image",
            "prompt": "A test image prompt",
            "output_path": "/tmp/test_output.png",
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# IProvider ABC
# ═══════════════════════════════════════════════════════════════════════


class TestIProviderBase:

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            IProvider()  # type: ignore[abstract]

    def test_abstract_methods_must_be_implemented(self) -> None:
        # Attempt to create a minimal concrete subclass missing an abstract method
        with pytest.raises(TypeError):

            class Incomplete(IProvider):  # type: ignore[misc, reportAbstractUsage]
                provider_name = "test"
                display_name = "Test"
                capabilities = ProviderCapability(
                    job_types=("test",),
                    dispatch_channel="manual",
                    auth_required=False,
                    required_env=(),
                )

            Incomplete()  # type: ignore[abstract]  # missing validate_config, build_request, etc.

    def test_concrete_minimal_subclass(self) -> None:
        """A fully concrete subclass should instantiate without error."""

        class MinimalProvider(IProvider):
            provider_name = "minimal"
            display_name = "Minimal"
            capabilities = ProviderCapability(
                job_types=("test",),
                dispatch_channel="manual",
                auth_required=False,
                required_env=(),
            )

            def validate_config(self) -> dict[str, Any]:
                return {"ready": True, "errors": [], "warnings": []}

            def build_request(
                self,
                request_item: dict[str, Any],
                providers_config_path: Path,
            ) -> dict[str, Any]:
                return {"method": "GET", "url": "", "headers": {}, "body": {}, "preflight": {"ready": True}}

            def execute_request(
                self,
                request_item: dict[str, Any],
                providers_config_path: Path,
            ) -> dict[str, Any]:
                return {"provider": "minimal", "output_path": "", "content_type": ""}

            def get_provider_info(self) -> ProviderInfo:
                return ProviderInfo(
                    provider_name="minimal",
                    display_name="Minimal",
                    capabilities=self.capabilities,
                    run_mode="test",
                )

        provider = MinimalProvider()
        assert provider.is_ready() is True
        info = provider.get_provider_info()
        assert info.provider_name == "minimal"
        assert info.capabilities.job_types == ("test",)


# ═══════════════════════════════════════════════════════════════════════
# OpenAIProvider
# ═══════════════════════════════════════════════════════════════════════


class TestOpenAIProvider:

    def test_provider_info(self) -> None:
        provider = OpenAIProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "openai"
        assert "image" in info.capabilities.job_types
        assert "tts" in info.capabilities.job_types
        assert info.capabilities.auth_required is True

    def test_validate_config_no_key(self) -> None:
        provider = OpenAIProvider()
        # Ensure no key
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = provider.validate_config()
            assert result["ready"] is False
            assert len(result["errors"]) > 0
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_validate_config_with_key(self) -> None:
        provider = OpenAIProvider()
        os.environ["OPENAI_API_KEY"] = "sk-test-fake-key"
        try:
            result = provider.validate_config()
            assert result["ready"] is True
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_is_ready_no_key(self) -> None:
        provider = OpenAIProvider()
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            assert provider.is_ready() is False
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_is_ready_with_key(self) -> None:
        provider = OpenAIProvider()
        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            assert provider.is_ready() is True
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_build_request_openai_image(self, providers_config_path: Path) -> None:
        provider = OpenAIProvider()
        item = {
            "request_id": "R1",
            "payload": {
                "provider": "openai_image",
                "prompt": "test image",
                "output_path": "/tmp/out.png",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "POST"
        assert "/v1/images/generations" in preview["url"]
        assert preview["body"]["prompt"] == "test image"
        assert preview["body"]["n"] == 1
        assert preview["preflight"]["ready"] is False  # no key

    def test_build_request_openai_tts(self, providers_config_path: Path) -> None:
        provider = OpenAIProvider()
        item = {
            "request_id": "R2",
            "payload": {
                "provider": "openai_tts",
                "prompt": "test speech",
                "output_path": "/tmp/out.wav",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "POST"
        assert "/v1/audio/speech" in preview["url"]
        assert preview["body"]["input"] == "test speech"

    def test_build_request_unknown_provider(self, providers_config_path: Path) -> None:
        provider = OpenAIProvider()
        item = {
            "request_id": "R3",
            "payload": {
                "provider": "unknown_sub_provider",
                "prompt": "test",
                "output_path": "/tmp/out",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["url"] == ""
        assert preview["preflight"]["ready"] is False
        assert "unsupported" in preview["preflight"]["notes"].lower()

    def test_execute_request_fails_no_key(self, providers_config_path: Path) -> None:
        provider = OpenAIProvider()
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                provider.execute_request(
                    {"payload": {"provider": "openai_image", "output_path": "/tmp/x.png"}},
                    providers_config_path,
                )
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key


# ═══════════════════════════════════════════════════════════════════════
# DALL_EProvider
# ═══════════════════════════════════════════════════════════════════════


class TestDALL_EProvider:

    def test_provider_info(self) -> None:
        provider = DALL_EProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "dall_e"
        assert "image" in info.capabilities.job_types

    def test_build_request_routes_to_openai_image(self, providers_config_path: Path) -> None:
        provider = DALL_EProvider()
        item = {
            "request_id": "R1",
            "payload": {
                "provider": "dall_e",
                "prompt": "DALL-E test",
                "output_path": "/tmp/dalle.png",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert "/v1/images/generations" in preview["url"]

    def test_execute_request_routes_to_openai(self, providers_config_path: Path) -> None:
        provider = DALL_EProvider()
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                provider.execute_request(
                    {"payload": {"provider": "dall_e", "output_path": "/tmp/dalle.png"}},
                    providers_config_path,
                )
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key


# ═══════════════════════════════════════════════════════════════════════
# SeedanceProvider
# ═══════════════════════════════════════════════════════════════════════


class TestSeedanceProvider:

    def test_provider_info(self) -> None:
        provider = SeedanceProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "seedance"
        assert "video" in info.capabilities.job_types
        assert info.capabilities.auth_required is True

    def test_validate_config_no_key(self) -> None:
        provider = SeedanceProvider()
        old_key = os.environ.pop("SEEDANCE_API_KEY", None)
        try:
            result = provider.validate_config()
            assert result["ready"] is False
        finally:
            if old_key is not None:
                os.environ["SEEDANCE_API_KEY"] = old_key

    def test_validate_config_with_key(self) -> None:
        provider = SeedanceProvider()
        os.environ["SEEDANCE_API_KEY"] = "sk-seedance-test"
        os.environ["SEEDANCE_MODEL"] = "test-model-v1"
        try:
            result = provider.validate_config()
            assert result["ready"] is True
            assert result["model"] == "test-model-v1"
        finally:
            del os.environ["SEEDANCE_API_KEY"]
            del os.environ["SEEDANCE_MODEL"]

    def test_build_request_text_to_video(self, providers_config_path: Path) -> None:
        provider = SeedanceProvider()
        item = {
            "request_id": "R1",
            "payload": {
                "provider": "seedance",
                "prompt": "A cat walking in a park",
                "job_type": "video",
                "output_path": "/tmp/test_video.mp4",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "POST"
        assert "contents/generations/tasks" in preview["url"]
        assert preview["body"]["model"]
        assert preview["body"]["content"][0]["text"] == "A cat walking in a park"
        assert preview["preflight"]["ready"] is False  # no key
        assert preview["body"]["watermark"] is False

    def test_build_request_image_to_video(self, providers_config_path: Path) -> None:
        provider = SeedanceProvider()
        item = {
            "request_id": "R2",
            "payload": {
                "provider": "seedance",
                "prompt": "Animate this scene",
                "first_frame": "/tmp/frame.png",
                "last_frame": "/tmp/last.png",
                "job_type": "video",
                "output_path": "/tmp/animated.mp4",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        # Should have first_frame and last_frame content items
        content = preview["body"]["content"]
        image_items = [c for c in content if c["type"] == "image_url"]
        assert len(image_items) >= 2  # first_frame + last_frame

    def test_resolve_image_path_url_passthrough(self) -> None:
        provider = SeedanceProvider()
        # URLs should pass through unchanged
        result = provider._resolve_image_path("https://example.com/img.png")
        assert result == "https://example.com/img.png"
        result2 = provider._resolve_image_path("data:image/png;base64,abc")
        assert result2 == "data:image/png;base64,abc"

    def test_resolve_image_path_local_file(self, tmp_path: Path) -> None:
        provider = SeedanceProvider()
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        result = provider._resolve_image_path(str(img_path))
        assert result.startswith("data:image/png;base64,")

    def test_execute_request_fails_no_key(self, providers_config_path: Path) -> None:
        provider = SeedanceProvider()
        old_key = os.environ.pop("SEEDANCE_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="SEEDANCE_API_KEY"):
                provider.execute_request(
                    {"payload": {"provider": "seedance", "output_path": "/tmp/v.mp4"}},
                    providers_config_path,
                )
        finally:
            if old_key is not None:
                os.environ["SEEDANCE_API_KEY"] = old_key


# ═══════════════════════════════════════════════════════════════════════
# ComfyUIProvider
# ═══════════════════════════════════════════════════════════════════════


class TestComfyUIProvider:

    def test_provider_info(self) -> None:
        provider = ComfyUIProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "comfyui"
        assert "image" in info.capabilities.job_types
        assert "video" in info.capabilities.job_types

    def test_validate_config_no_runtime(self) -> None:
        # Create with a non-existent project root
        provider = ComfyUIProvider(project_root=Path("/tmp/nonexistent_project_xyz"))
        result = provider.validate_config()
        # Should not crash — will report errors/warnings
        assert "errors" in result
        assert "warnings" in result
        # ready will be False because comfyui_root doesn't exist
        assert result["ready"] is False

    def test_build_request_delegates_to_local_adapter(self, providers_config_path: Path) -> None:
        provider = ComfyUIProvider(project_root=Path("/tmp/nonexistent"))
        item = {
            "request_id": "R1",
            "payload": {
                "provider": "local_comfyui_image",
                "prompt": "test",
                "output_path": "/tmp/out.png",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        # Should produce a valid preview dict even if runtime doesn't exist
        assert isinstance(preview, dict)
        assert "preflight" in preview
        assert "method" in preview


# ═══════════════════════════════════════════════════════════════════════
# ManualProvider
# ═══════════════════════════════════════════════════════════════════════


class TestManualProvider:

    def test_provider_info(self) -> None:
        provider = ManualProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "manual"
        assert "image" in info.capabilities.job_types
        assert "video" in info.capabilities.job_types
        assert "tts" in info.capabilities.job_types

    def test_validate_config(self) -> None:
        provider = ManualProvider()
        result = provider.validate_config()
        assert result["ready"] is True

    def test_is_ready(self) -> None:
        provider = ManualProvider()
        assert provider.is_ready() is True

    def test_build_request(self, providers_config_path: Path) -> None:
        provider = ManualProvider()
        item = {"payload": {"provider": "manual_web", "prompt": "test"}}
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "NONE"
        assert preview["preflight"]["ready"] is True

    def test_execute_request(self, providers_config_path: Path) -> None:
        provider = ManualProvider()
        result = provider.execute_request(
            {"payload": {"provider": "manual_web", "output_path": "/tmp/manual.png"}},
            providers_config_path,
        )
        assert result["provider"] == "manual_web"
        assert "Manual provider" in result["metadata"]["note"]


# ═══════════════════════════════════════════════════════════════════════
# ProviderRegistry
# ═══════════════════════════════════════════════════════════════════════


class TestProviderRegistry:

    def setup_method(self) -> None:
        reset_provider_registry()

    def test_default_registry_has_builtins(self) -> None:
        registry = get_provider_registry()
        registered = registry.list_registered()
        assert "openai" in registered
        assert "dall_e" in registered
        assert "seedance" in registered
        assert "comfyui" in registered
        assert "manual" in registered
        assert "piper_tts" in registered

    def test_get_provider(self) -> None:
        registry = get_provider_registry()
        provider = registry.get("openai")
        assert provider is not None
        assert isinstance(provider, OpenAIProvider)

    def test_get_unknown_provider_returns_none(self) -> None:
        registry = get_provider_registry()
        assert registry.get("nonexistent_provider") is None

    def test_get_or_fail_raises(self) -> None:
        registry = get_provider_registry()
        with pytest.raises(KeyError):
            registry.get_or_fail("unknown")

    def test_list_available_all(self) -> None:
        registry = get_provider_registry()
        providers = registry.list_available()
        assert len(providers) >= 6

    def test_list_available_filter_by_job_type(self) -> None:
        registry = get_provider_registry()
        image_providers = registry.list_available(job_type="image")
        assert all("image" in p.capabilities.job_types for p in image_providers)

        video_providers = registry.list_available(job_type="video")
        assert all("video" in p.capabilities.job_types for p in video_providers)
        # seedance only does video, comfyui does both
        seedance_found = any(p.provider_name == "seedance" for p in video_providers)
        assert seedance_found

    def test_resolve_for_job_direct_match(self) -> None:
        registry = get_provider_registry()
        provider = registry.resolve_for_job("openai")
        assert provider is not None
        assert provider.provider_name == "openai"

    def test_resolve_for_job_name_remapping(self) -> None:
        registry = get_provider_registry()
        # openai_image -> openai
        provider = registry.resolve_for_job("openai_image")
        assert provider is not None
        assert provider.provider_name == "openai"

        # local_comfyui_image -> comfyui
        provider = registry.resolve_for_job("local_comfyui_image")
        assert provider is not None
        assert provider.provider_name == "comfyui"

        # local_piper_tts -> piper_tts
        provider = registry.resolve_for_job("local_piper_tts")
        assert provider is not None
        assert provider.provider_name == "piper_tts"

        # manual_web -> manual
        provider = registry.resolve_for_job("manual_web")
        assert provider is not None
        assert provider.provider_name == "manual"

    def test_custom_registry(self) -> None:
        registry = ProviderRegistry()

        class TestProv(IProvider):
            provider_name = "test_prov"
            display_name = "TestProv"
            capabilities = ProviderCapability(
                job_types=("test",), dispatch_channel="manual",
                auth_required=False, required_env=(),
            )
            def validate_config(self) -> dict[str, Any]:
                return {"ready": True, "errors": [], "warnings": []}
            def build_request(  # type: ignore[override]
                self, request_item: dict[str, Any], providers_config_path: Path
            ) -> dict[str, Any]:
                return {"method": "GET", "url": "", "headers": {}, "body": {}, "preflight": {"ready": True}}
            def execute_request(  # type: ignore[override]
                self, request_item: dict[str, Any], providers_config_path: Path
            ) -> dict[str, Any]:
                return {"provider": "test", "output_path": "", "content_type": ""}
            def get_provider_info(self) -> ProviderInfo:
                return ProviderInfo(provider_name="test_prov", display_name="Test", capabilities=self.capabilities, run_mode="test")

        registry.register(TestProv)
        assert "test_prov" in registry.list_registered()
        provider = registry.get("test_prov")
        assert provider is not None
        assert provider.provider_name == "test_prov"

        registry.unregister("test_prov")
        assert "test_prov" not in registry.list_registered()

    def test_set_project_root_clears_cache(self) -> None:
        registry = ProviderRegistry()
        registry.register(OpenAIProvider)
        p1 = registry.get("openai")
        registry.set_project_root(Path("/tmp/test_root"))
        p2 = registry.get("openai")
        # Should be a new instance after clearing cache
        assert p2 is not None and p2 is not p1


# ═══════════════════════════════════════════════════════════════════════
# ProviderCapability / ProviderInfo dataclasses
# ═══════════════════════════════════════════════════════════════════════


class TestProviderCapability:

    def test_frozen(self) -> None:
        cap = ProviderCapability(
            job_types=("image",),
            dispatch_channel="api",
            auth_required=True,
            required_env=("OPENAI_API_KEY",),
        )
        with pytest.raises(AttributeError):
            cap.job_types = ("video",)  # type: ignore[misc]

    def test_slots(self) -> None:
        cap = ProviderCapability(
            job_types=("tts",),
            dispatch_channel="local",
            auth_required=False,
            required_env=(),
        )
        with pytest.raises((AttributeError, TypeError)):
            cap.new_attr = "x"  # type: ignore[attr-defined]
