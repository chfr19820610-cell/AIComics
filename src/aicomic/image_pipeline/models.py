"""Model path management + availability checking for image pipeline."""
from __future__ import annotations

from pathlib import Path


class ModelManager:
    """Manage ComfyUI model paths and check availability."""

    def __init__(self, comfyui_root: Path) -> None:
        self.root = Path(comfyui_root)
        self.models_dir = self.root / "models"

    def _scan_dir(self, subdir: str) -> list[str]:
        d = self.models_dir / subdir
        if not d.exists():
            return []
        return [f.name for f in d.iterdir() if f.is_file() and not f.name.startswith("put_")]

    def check_available(self) -> dict[str, list[str]]:
        """Check which models are available."""
        return {
            "checkpoints": self._scan_dir("checkpoints"),
            "controlnet": self._scan_dir("controlnet"),
            "upscale": self._scan_dir("upscale_models"),
            "ipadapter": self._scan_dir("ipadapter"),
            "unet": self._scan_dir("unet"),
            "vae": self._scan_dir("vae"),
        }

    def get_download_instructions(self) -> dict[str, list[str]]:
        """Return download URLs for missing models."""
        return {
            "controlnet": [
                "huggingface.co/stabilityai/control-lora — canny/depth/openpose SDXL",
            ],
            "upscale": [
                "github.com/xinntex/Real-ESRGAN — RealESRGAN_x4plus.pth (67MB)",
                "github.com/xinntex/Real-ESRGAN — RealESRGAN_x4plus_anime_6B.pth (6MB)",
            ],
            "rmbg": [
                "github.com/briaai/ComfyUI-BRIA-RMBG — RMBG-2.0 node (550MB)",
            ],
            "ipadapter": [
                "huggingface.co/h94/IP-Adapter — ip-adapter-plus_sdxl_vit-h.safetensors",
            ],
            "flux": [
                "huggingface.co/Quantization/flux.1-dev — Q4_0 GGUF (~6GB)",
            ],
        }
