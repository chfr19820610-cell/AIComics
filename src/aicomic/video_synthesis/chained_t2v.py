"""反漂移链式视频生成（MiniMax-H3 fl2va 帧锚接力）。

调研结论落地（2026-10-22 全网调研）：
- 纯 T2V 逐镜独立 → 人物必然漂移；同 seed 反而漂移更重（face 与 voice 都漂），
  业界基准是 seed_per_shot ON（identity 住在 conditioning 不在 seed）。
- 身份钳制三板斧：① 帧接力（前镜末帧做本镜首帧锚，AddGuide VAE latent 引导）；
  ② 外观描述 verbatim 逐字重复（文本钉住类别）；③ 镜头短（身份在几秒内稳、
  长镜必漂）。关键镜头（特写/台词）必走 I2V 起手。
- 本机通路：MiniMaxH3AddGuide 直接把首帧 VAE encode 进 conditioning 的
  minimax_keyframes，不经过 mmproj 视觉 token 网格（1344x768 锁死问题的绕行）。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DEFAULT_WIDTH = 448
DEFAULT_HEIGHT = 800
DEFAULT_LENGTH = 124
DEFAULT_STEPS = 6
GUIDE_FRAME_START = 0
UNET_NODE = "1"
clip_NODE = "2"
PROMPT_NODE = "3"
LATENT_NODE = "4"
LOAD_IMAGE_NODE = "5"
VAE_NODE = "6"
ADD_GUIDE_NODE = "7"
SAMPLER_NODE = "8"
DECODE_NODE = "9"
SAVE_NODE = "10"

UNET_NAME = "MiniMax-H3-fl2va-curve-Q4_0.gguf"
CLIP_NAME = "MiniMax-H3-encoder-Q4_K_M.gguf"
VAE_NAME = "minimax_h3_video_vae_fp16.safetensors"


@dataclass(frozen=True)
class CharacterContract:
    """角色圣经：永久身份锚字段 → verbatim 外观块。

    口径（Arcloop/多源共识）：face/hair/outfit/prop 是不可漂移锚；
    pose/expr/相机/灯光/天气是每镜头变量；风格词不背身份。
    """

    name: str
    prompts_face: str
    prompts_outfit: str
    extra_style: str = ""
    prop: str = ""

    def render_block(self) -> str:
        parts = [self.prompts_face.strip(), self.prompts_outfit.strip()]
        if self.prop:
            parts.append(self.prop.strip())
        if self.extra_style:
            parts.append(self.extra_style.strip())
        return ", ".join(parts)

    def compose_prompt(self, action: str, *, scene: str = "") -> str:
        """verbatim 外观块 + 递进动作（动作必须把世界推到新物理状态）。"""
        sep = ", " if scene else ""
        return f"{self.render_block()}{sep}{scene}: {action.strip()}" if scene else f"{self.render_block()}: {action.strip()}"


def build_shot_workflow(
    prompt: str,
    *,
    seed: int,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    length: int = DEFAULT_LENGTH,
    steps: int = DEFAULT_STEPS,
    first_frame_image: str | None = None,
) -> dict[str, dict[str, Any]]:
    """单镜 workflow：无 first_frame → 纯 T2V；有 → AddGuide 帧锚接力 i2v。"""
    wf: dict[str, dict[str, Any]] = {
        UNET_NODE: {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET_NAME}},
        clip_NODE: {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": CLIP_NAME, "type": "minimax"}},
        PROMPT_NODE: {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [clip_NODE, 0]}},
        LATENT_NODE: {"class_type": "EmptyMiniMaxH3LatentAV", "inputs": {"width": width, "height": height, "length": length, "batch_size": 1}},
        VAE_NODE: {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
    }
    positive = [PROMPT_NODE, 0]
    if first_frame_image is not None:
        wf[LOAD_IMAGE_NODE] = {"class_type": "LoadImage", "inputs": {"image": first_frame_image}}
        wf[ADD_GUIDE_NODE] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
            "positive": [PROMPT_NODE, 0], "latent": [LATENT_NODE, 0],
            "frame_idx": GUIDE_FRAME_START, "vae": [VAE_NODE, 0], "image": [LOAD_IMAGE_NODE, 0],
        }}
        positive = [ADD_GUIDE_NODE, 0]
    wf[SAMPLER_NODE] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
        "denoise": 1.0, "model": [UNET_NODE, 0], "positive": positive, "negative": [PROMPT_NODE, 0],
        "latent_image": [LATENT_NODE, 0],
    }}
    wf[DECODE_NODE] = {"class_type": "VAEDecode", "inputs": {"samples": [SAMPLER_NODE, 0], "vae": [VAE_NODE, 0]}}
    wf[SAVE_NODE] = {"class_type": "SaveWEBM", "inputs": {
        "images": [DECODE_NODE, 0], "filename_prefix": "aicomic_chain", "codec": "vp9",
        "fps": 24.0, "crf": 28,
    }}
    return wf


def take_seeds(base_seed: int, shot_index: int, n: int = 2) -> list[int]:
    """take 计划：seed 随镜头序微扰（同 seed 每镜是反模式；同镜多 take 才用邻号）。"""
    base = (base_seed + shot_index * 17 + 1) % (2**31)
    return [base + i for i in range(n)]


def extract_last_frame(
    video_path: str | Path,
    output_png: str | Path,
    *,
    ff_bin: str | None = None,
) -> int:
    """抽片尾帧（接力源）：-sseof -0.2 取最后一帧。"""
    if ff_bin is None:
        import imageio_ffmpeg

        ff_bin = imageio_ffmpeg.get_ffmpeg_exe()
    dst = Path(output_png)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(ff_bin), "-hide_banner", "-loglevel", "error", "-y",
           "-sseof", "-0.2", "-i", str(video_path), "-frames:v", "1", str(dst)]
    return subprocess.run(cmd, capture_output=True).returncode


def run_chain(
    prompts: dict[str, str],
    *,
    submit_fn: Callable[..., Any],
    wait_fn: Callable[..., Any],
    download_fn: Callable[..., Any],
    contract: CharacterContract | None = None,
    base_seed: int = 4242,
    n_takes: int = 1,
    first_frame_image: str | None = None,
) -> list[dict[str, Any]]:
    """帧接力链生成骨架：前一镜末帧作为下一镜首帧锚。

    prompts: shot_id -> action/scene（可由 contract.compose_prompt 已合成）。
    submit_fn/workflow/ronshot 交由调用方注入（真机/录播可替换），
    本函数负责接力决策与 seed 计划；产物路径由 download_fn 决定。
    """
    if contract is not None:
        prompts = {k: contract.compose_prompt(v) for k, v in prompts.items()}
    results: list[dict[str, Any]] = []
    for idx, (shot, prompt) in enumerate(prompts.items()):
        seed = take_seeds(base_seed, idx, n_takes)[0]
        relay = first_frame_image if idx == 0 and first_frame_image else (results[-1]["last_frame"] if results else None)
        wf = build_shot_workflow(prompt, seed=seed, first_frame_image=relay)
        pid = submit_fn(wf)
        ok = wait_fn(pid)
        outputs = download_fn(pid) if ok else []
        last_frame = outputs[0] if outputs else None
        results.append({"shot": shot, "seed": seed, "prompt_id": pid, "ok": ok, "outputs": outputs, "last_frame": last_frame})
    return results
