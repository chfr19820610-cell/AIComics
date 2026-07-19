"""Tests for BlenderRenderProvider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from aicomic.providers.blender_render import BlenderRenderProvider
from aicomic.providers.base import ProviderCapability, ProviderInfo


# ═══════════════════════════════════════════════════════════════════════
# BlenderRenderProvider
# ═══════════════════════════════════════════════════════════════════════


class TestBlenderRenderProvider:

    def test_provider_info(self) -> None:
        provider = BlenderRenderProvider()
        info = provider.get_provider_info()
        assert info.provider_name == "blender"
        assert "video" in info.capabilities.job_types
        assert "image" in info.capabilities.job_types
        assert info.capabilities.auth_required is False
        assert info.capabilities.dispatch_channel == "local"

    def test_capabilities(self) -> None:
        provider = BlenderRenderProvider()
        cap = provider.capabilities
        assert isinstance(cap, ProviderCapability)
        assert "video" in cap.job_types
        assert "image" in cap.job_types
        assert cap.dispatch_channel == "local"
        assert cap.auth_required is False
        assert cap.required_env == ()

    def test_validate_config(self) -> None:
        """validate_config should check Blender existence without crashing."""
        provider = BlenderRenderProvider()
        result = provider.validate_config()
        assert "ready" in result
        assert "errors" in result
        assert "warnings" in result
        assert "blender_path" in result
        assert "blender_exists" in result
        # If Blender is installed, ready should be True
        blender_path = provider._find_blender()
        if Path(blender_path).exists():
            assert result["ready"] is True, f"Blender at {blender_path} but validate says not ready: {result['errors']}"
            assert result["blender_exists"] is True
            assert result["bpy_ok"] is True

    def test_find_blender_default(self) -> None:
        provider = BlenderRenderProvider()
        path = provider._find_blender()
        assert "/Blender" in path or "blender" in path.lower()

    def test_build_request_video(self, providers_config_path: Path) -> None:
        provider = BlenderRenderProvider()
        item = {
            "request_id": "R1",
            "payload": {
                "provider": "blender_local",
                "job_type": "video",
                "frame_start": 1,
                "frame_end": 72,
                "output_path": "/tmp/blender_test_out/frame_###",
                "prompt": "A test scene render",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "SUBPROCESS"
        assert "command" in preview["body"]
        cmd = preview["body"]["command"]
        assert len(cmd) >= 4
        assert cmd[-1].endswith("render_frame.py") or "render_frame" in cmd[-1]
        assert "preflight" in preview
        assert "output_dir" in preview["preflight"]

    def test_build_request_image(self, providers_config_path: Path) -> None:
        provider = BlenderRenderProvider()
        item = {
            "request_id": "R2",
            "payload": {
                "provider": "blender_local",
                "job_type": "image",
                "output_path": "/tmp/blender_test_out.png",
                "prompt": "A test image render",
            },
        }
        preview = provider.build_request(item, providers_config_path)
        assert preview["method"] == "SUBPROCESS"
        assert "command" in preview["body"]

    def test_is_ready(self) -> None:
        provider = BlenderRenderProvider()
        # Should not crash
        ready = provider.is_ready()
        blender_path = provider._find_blender()
        if Path(blender_path).exists():
            assert ready is True
        else:
            assert ready is False

    def test_execute_request_no_blender_raises(self, tmp_path: Path) -> None:
        """If Blender is somehow not found, execute should raise."""
        provider = BlenderRenderProvider()

        # Create an empty providers.yaml
        config_path = tmp_path / "providers.yaml"
        config_path.write_text("", encoding="utf-8")

        item = {
            "payload": {
                "provider": "blender_local",
                "output_path": str(tmp_path / "out.png"),
            },
        }

        # If blender doesn't exist, it'll raise RuntimeError
        if not Path(provider._find_blender()).exists():
            with pytest.raises(RuntimeError, match="Blender not found"):
                provider.execute_request(item, config_path)
        else:
            # Blender exists, but we need a valid .blend file in the subprocess
            # Test that at least it builds the command correctly
            result = provider.build_request(item, config_path)
            assert result["method"] == "SUBPROCESS"

    def test_scripts_directory_exists(self) -> None:
        """Check that the Blender scripts directory exists."""
        scripts_dir = Path(__file__).resolve().parents[2] / "10_System" / "local_providers" / "blender" / "scripts"
        assert scripts_dir.exists(), f"Scripts dir not found: {scripts_dir}"
        assert (scripts_dir / "render_frame.py").exists()
        assert (scripts_dir / "create_scene.py").exists()


# ═══════════════════════════════════════════════════════════════════════
# BlenderRenderProvider in Registry
# ═══════════════════════════════════════════════════════════════════════


class TestBlenderInRegistry:

    def test_registered_in_default_registry(self) -> None:
        from aicomic.providers.provider_registry import (
            get_provider_registry,
            reset_provider_registry,
        )
        reset_provider_registry()
        registry = get_provider_registry()
        registered = registry.list_registered()
        assert "blender" in registered

    def test_resolve_blender_local(self) -> None:
        from aicomic.providers.provider_registry import (
            get_provider_registry,
            reset_provider_registry,
        )
        reset_provider_registry()
        registry = get_provider_registry()
        provider = registry.resolve_for_job("blender_local")
        assert provider is not None
        assert provider.provider_name == "blender"

    def test_registered_in_init(self) -> None:
        from aicomic.providers import BlenderRenderProvider
        assert BlenderRenderProvider is not None
        assert BlenderRenderProvider.provider_name == "blender"


# ═══════════════════════════════════════════════════════════════════════
# Provider Planner
# ═══════════════════════════════════════════════════════════════════════


class TestBlenderInProviderPlanner:

    def test_profile_exists(self) -> None:
        from aicomic.providers.provider_planner import PROVIDER_PROFILES
        assert "blender_local" in PROVIDER_PROFILES
        profile = PROVIDER_PROFILES["blender_local"]
        assert "video" in profile.supported_job_types
        assert "image" in profile.supported_job_types
        assert profile.dispatch_channel == "local"
        assert profile.auth_required is False

    def test_resolve_provider_profile(self) -> None:
        from aicomic.providers.provider_planner import resolve_provider_profile
        profile = resolve_provider_profile("blender_local")
        assert profile.provider == "blender_local"
        assert "video" in profile.supported_job_types
