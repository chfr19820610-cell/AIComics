#!/usr/bin/env python3
"""ComfyUI 真出图验证 — 调用真实 ComfyUI API 生成一张 txt2img 图片。

用法:
    python scripts/validate_comfyui_real_image.py [host] [port] [out_dir]

从 ComfyUI /object_info 探测可用的 checkpoints，优先使用 anythingV5 / v1-5，
生成一张竖屏动漫图并保存到 out_dir，最后打印一行 JSON（含 saved 字段）。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request


def http_get(url: str, timeout: int = 30) -> dict:
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read().decode())


def http_post(url: str, body: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def pick_checkpoint(base_url: str) -> str:
    try:
        info = http_get(f"{base_url}/object_info/CheckpointLoaderSimple")
        names = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])
        available = [n for n in names[0] if isinstance(n, str)]
    except Exception:
        available = []
    for preferred in ("anythingV5.safetensors", "v1-5-pruned-emaonly.safetensors", "animagine-xl-4.0-opt.safetensors"):
        if preferred in available:
            return preferred
    return available[0] if available else ""


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv) > 2 else "8188"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "/tmp/aicomic_real_output"
    base = f"http://{host}:{port}"
    os.makedirs(out_dir, exist_ok=True)

    ckpt = pick_checkpoint(base)
    if not ckpt:
        print(json.dumps({"ok": False, "error": "no checkpoint available"}, ensure_ascii=False))
        return 1

    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "1girl, anime style, city night, neon lights, detailed, high quality", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "low quality, blurry, watermark, text", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": 42, "steps": 15, "cfg": 7.0, "sampler_name": "euler",
            "scheduler": "normal", "denoise": 1.0,
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "aicomic_real", "images": ["6", 0]}},
    }

    resp = http_post(f"{base}/prompt", {"prompt": wf, "client_id": "aicomic-real-gen"})
    pid = resp.get("prompt_id", "")
    if not pid:
        print(json.dumps({"ok": False, "error": "no prompt_id"}, ensure_ascii=False))
        return 1

    meta = None
    deadline = time.time() + 180
    while time.time() < deadline:
        hist = http_get(f"{base}/history/{pid}")
        outputs = (hist.get(pid, {}) or {}).get("outputs", {})
        for out in outputs.values():
            for art in out.get("images") or []:
                meta = art
                break
            if meta:
                break
        if meta:
            break
        status = (hist.get(pid, {}) or {}).get("status", {})
        for msg in status.get("messages", []):
            if len(msg) == 2 and msg[0] == "execution_error":
                print(json.dumps({"ok": False, "error": msg[1].get("exception_message", "")}, ensure_ascii=False))
                return 1
        time.sleep(1)

    if not meta:
        print(json.dumps({"ok": False, "error": "timeout waiting for image"}, ensure_ascii=False))
        return 1

    q = f"filename={meta['filename']}&subfolder={meta.get('subfolder', '')}&type={meta.get('type', 'output')}"
    data = urllib.request.urlopen(f"{base}/view?{q}", timeout=30).read()
    saved = os.path.join(out_dir, meta["filename"])
    with open(saved, "wb") as f:
        f.write(data)
    print(json.dumps({"ok": True, "saved": saved, "bytes": len(data), "checkpoint": ckpt,
                      "prompt_id": pid, "filename": meta["filename"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
