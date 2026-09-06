"""Composite service — Pillow alpha blending for layer compositing."""
from __future__ import annotations

from pathlib import Path

from PIL import Image


class CompositeService:
    """Composite foreground (RGBA) onto background (RGB) using alpha blending."""

    def composite(
        self,
        foreground: Path,
        background: Path,
        x: int = 0,
        y: int = 0,
        output_path: Path | None = None,
    ) -> Path:
        """Paste foreground onto background at (x, y), save to output_path."""
        fg = Image.open(str(foreground)).convert("RGBA")
        bg = Image.open(str(background)).convert("RGBA")
        bg.paste(fg, (x, y), fg)  # Use fg's alpha as mask
        # Convert back to RGB for output
        result = bg.convert("RGB")
        if output_path is None:
            output_path = foreground.parent / "composite_output.png"
        result.save(str(output_path))
        return output_path
