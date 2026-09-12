"""LoRA training config builder — generates SDXL character LoRA training configs.

Doesn't run training (that needs GPU + ComfyUI); produces a config dict
that can be passed to a training script or written to JSON for manual use.
"""

from __future__ import annotations

from typing import Any


def build_lora_training_config(
    character_name: str,
    training_images_dir: str,
    output_dir: str,
    *,
    lora_rank: int = 32,
    learning_rate: float = 1e-4,
    max_train_steps: int = 1500,
    batch_size: int = 1,
    resolution: int = 1024,
    trigger_word: str | None = None,
) -> dict[str, Any]:
    """Build a LoRA training configuration for a character.

    Args:
        character_name: Character identifier (used in output filename).
        training_images_dir: Directory containing training images.
        output_dir: Where to save the trained LoRA weights.
        lora_rank: LoRA rank (4-128, higher = more capacity + slower).
        learning_rate: Training learning rate (1e-6 to 1e-3).
        max_train_steps: Maximum training steps (100-10000).
        batch_size: Training batch size.
        resolution: Image resolution (512 or 1024 for SDXL).
        trigger_word: Optional trigger word for the LoRA (defaults to character name).

    Returns:
        Config dict with all parameters needed to launch training.
    """
    trigger = trigger_word or character_name.lower().replace(" ", "_")
    return {
        "character_name": character_name,
        "training_images_dir": training_images_dir,
        "output_dir": output_dir,
        "lora_rank": lora_rank,
        "learning_rate": learning_rate,
        "max_train_steps": max_train_steps,
        "batch_size": batch_size,
        "resolution": resolution,
        "trigger_word": trigger,
        "model_base": "stabilityai/stable-diffusion-xl-base-1.0",
        "output_filename": f"{trigger}_lora.safetensors",
        "seed": 42,
        "gradient_accumulation_steps": 4,
        "mixed_precision": "fp16",
        "enable_xformers": True,
        "save_every_n_steps": 500,
    }


def write_training_config(config: dict[str, Any], path: str) -> str:
    """Write training config to a JSON file.

    Returns the path written.
    """
    import json
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)
