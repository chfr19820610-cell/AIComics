#!/usr/bin/env python3
"""下载 ComfyUI Triple-Lock 锁定工作流所需的缺失权重文件。

用法：
    .venv/bin/python scripts/download_comfy_lock_models.py          # 下载全部缺失
    .venv/bin/python scripts/download_comfy_lock_models.py --check  # 只探测，不下载

默认走国内镜像 hf-mirror.com（huggingface.co 直连被墙）。
可用 AICOMIC_MODEL_MIRROR 覆盖，例如：AICOMIC_MODEL_MIRROR=https://huggingface.co
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


MIRROR = os.environ.get("AICOMIC_MODEL_MIRROR", "https://hf-mirror.com").rstrip("/")

# (仓库内目标路径, URL 路径, 最小合法 MB)
TARGETS: tuple[tuple[str, str, int], ...] = (
    (
        "controlnet/openpose.safetensors",
        "/lllyasviel/sd_control_collection/resolve/main/thibaud_xl_openpose.safetensors",
        2000,
    ),
    (
        "vae/sdxl_vae.safetensors",
        "/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors",
        100,
    ),
    (
        "ipadapter/ip-adapter-faceid_sdxl.bin",
        "/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sdxl.bin",
        800,
    ),
    (
        "clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        "/h94/IP-Adapter/resolve/main/sdxl_models/image_encoder/model.safetensors",
        2000,
    ),
)

MODEL_ROOT = Path(
    os.environ.get(
        "AICOMIC_COMFY_MODELS",
        "local_providers/comfyui_runtime/ComfyUI/models",
    )
)


def status_for(target_rel: str, min_mb: int) -> str:
    path = MODEL_ROOT / target_rel
    min_bytes = min_mb * 1024 * 1024
    if not path.exists():
        return "missing"
    if path.stat().st_size < min_bytes:
        return "incomplete"  # 断点续传可继续
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 Triple-Lock 所需模型权重")
    parser.add_argument("--check", action="store_true", help="只探测状态，不下载")
    args = parser.parse_args()

    plan: list[tuple[str, str, int]] = []
    for rel, url_path, min_mb in TARGETS:
        state = status_for(rel, min_mb)
        print(f"{state.upper():<10} {rel:<55} (>={min_mb}MB)")
        if state != "ok":
            plan.append((rel, url_path, min_mb))

    if args.check:
        return 0

    if not plan:
        print("\n所有目标文件已就绪，无需下载。")
        return 0

    failures: list[str] = []
    for rel, url_path, min_mb in plan:
        url = MIRROR + url_path
        path = MODEL_ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n下载 {url} -> {path} (curl -C - 断点续传)")
        cmd = ["curl", "-L", "-C", "-", "--fail", "--retry", "3", "-o", str(path), url]
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            failures.append(rel)
            continue
        state = status_for(rel, min_mb)
        if state != "ok":
            print(f"警告: {rel} 下载后仍 < {min_mb}MB，标记失败")
            failures.append(rel)

    if failures:
        print(f"\n以下文件下载失败（可重跑本脚本续传）: {failures}", file=sys.stderr)
        return 1
    print("\n全部目标文件就绪。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
