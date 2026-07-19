from __future__ import annotations

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo
from aicomic.providers.openai_provider import OpenAIProvider, DALL_EProvider
from aicomic.providers.seedance_provider import SeedanceProvider
from aicomic.providers.kling_provider import KlingProvider
from aicomic.providers.comfyui_provider import ComfyUIProvider
from aicomic.providers.manual_provider import ManualProvider, PiperTTSProvider
from aicomic.providers.blender_render import BlenderRenderProvider
from aicomic.providers.provider_registry import (
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
)

__all__ = [
    # Abstract base
    "IProvider",
    "ProviderCapability",
    "ProviderInfo",
    # Adapters
    "OpenAIProvider",
    "DALL_EProvider",
    "SeedanceProvider",
    "KlingProvider",
    "ComfyUIProvider",
    "ManualProvider",
    "PiperTTSProvider",
    "BlenderRenderProvider",
    # Registry
    "ProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry",
]
