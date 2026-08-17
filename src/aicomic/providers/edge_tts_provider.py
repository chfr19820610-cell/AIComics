"""Edge TTS provider — 免费 Microsoft Edge TTS.

Distilled from MoneyPrinterTurbo voice.py.
零成本、高质量中文TTS，作为Piper的backup.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class EdgeTTSProvider(IProvider):
    """Edge TTS provider — free, high quality, no API key needed."""

    PROVIDER_NAME = "edge_tts"

    # 常用中文音色
    VOICES = {
        "female_xiaoxiao": "zh-CN-XiaoxiaoNeural",
        "female_xiaoyi": "zh-CN-XiaoyiNeural",
        "male_yunyang": "zh-CN-YunyangNeural",
        "male_yunxi": "zh-CN-YunxiNeural",
        "female_xiaohan": "zh-CN-XiaohanNeural",
        "en_female_aria": "en-US-AriaNeural",
        "en_male_guy": "en-US-GuyNeural",
    }

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._default_voice = self.config.get("voice", "zh-CN-XiaoxiaoNeural")
        self._rate = self.config.get("rate", 1.0)
        self._volume = self.config.get("volume", 1.0)

    def validate_config(self) -> bool:
        return True  # No config needed — it's free!

    def is_ready(self) -> bool:
        return True

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.PROVIDER_NAME,
            display_name="Edge TTS (Free)",
            capabilities=ProviderCapability(
                job_types=("tts",),
                dispatch_channel="sync",
                auth_required=False,
                required_env=(),
            ),
            run_mode="local",
            notes="Free Microsoft Edge TTS. No API key required.",
        )

    def build_request(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "text": job.get("text", ""),
            "voice": job.get("voice", self._default_voice),
            "rate": job.get("rate", self._rate),
            "volume": job.get("volume", self._volume),
            "output_path": job.get("output_path", ""),
        }

    def execute_request(self, request: dict[str, Any]) -> dict[str, Any]:
        output = Path(request["output_path"]) if request["output_path"] else None
        result_path = self.synthesize(
            text=request["text"],
            voice=request["voice"],
            rate=request["rate"],
            volume=request["volume"],
            output_path=output,
        )
        return {"audio_path": str(result_path), "success": result_path is not None}

    def synthesize(
        self,
        text: str,
        voice: str = "",
        rate: float = 1.0,
        volume: float = 1.0,
        output_path: Path | None = None,
    ) -> Path | None:
        """Synthesize text to speech. Returns audio file path."""
        voice_name = self.VOICES.get(voice, voice or self._default_voice)
        if not output_path:
            output_path = Path(tempfile.mktemp(suffix=".mp3"))

        try:
            return asyncio.run(self._synth(text, voice_name, rate, volume, output_path))
        except Exception:
            return None

    async def _synth(
        self, text: str, voice: str, rate: float, volume: float, output: Path
    ) -> Path:
        try:
            import edge_tts
        except ImportError:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")
        rate_str = f"{'+%d%%' % int((rate - 1) * 100) if rate > 1 else '-%d%%' % int((1 - rate) * 100) if rate < 1 else '+0%%'}"
        vol_str = f"{'+%d%%' % int((volume - 1) * 100) if volume > 1 else '-%d%%' % int((1 - volume) * 100) if volume < 1 else '+0%%'}"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, volume=vol_str)
        await communicate.save(str(output))
        return output if output.exists() else None
