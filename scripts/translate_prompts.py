#!/usr/bin/env python3
"""批量翻译 840 镜的中文 scene 为英文 prompt

原因：实测中文混拼 prompt 会让 h3stream 的文本编码器卡住（20+ 分钟不到 step1），
必须转成纯英文。

用法: python scripts/translate_prompts.py [E01 E02 ...]
输出: state/projects/xianxia-12/prompts/{ep}_70_en.json
"""
import json
import os
import sys
import time
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"

env_path = BASE / ".env.local"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
KEY = os.environ.get("AICOMIC_OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")

import urllib.request


def call_llm(msgs, temp=0.3, max_tokens=6000):
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps({"model": "deepseek-chat", "messages": msgs,
                         "temperature": temp, "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def translate_batch(shots):
    """把一批中文镜头翻成英文 prompt"""
    items = "\n".join(
        f'{s["shot_id"]} | {s["shot_type"]} | {s.get("camera","")} | {s.get("characters", [])} | {s["scene"]}'
        for s in shots
    )
    prompt = f"""Translate these Chinese manga storyboard shots into concise English image prompts.

Rules:
- Output ONE English prompt per shot, 20-45 words
- Describe: subject + action + setting + camera angle + lighting/mood
- Keep character names as pinyin (Lin Zhao / Zhao Qian / Yan Chong / Mo Lin Jiao / Lao Mo / Su Qingyin / Xuan Chenzi / Golden Figure)
- Do NOT add style words (style is prepended separately)
- Do NOT add "anime" or "chibi" (handled separately)
- Be concrete and visual, no metaphors

Shots:
{items}

Output strict JSON array ONLY:
[{{"shot_id":"S01","prompt_en":"..."}}]
No explanation."""
    raw = call_llm([{"role": "user", "content": prompt}])
    s = raw.find("["); e = raw.rfind("]") + 1
    arr = json.loads(raw[s:e])
    return {x["shot_id"]: x.get("prompt_en", "") for x in arr}


def process_episode(ep):
    shots_path = D / "shots" / f"{ep}_70.json"
    if not shots_path.exists():
        print(f"  {ep}: 无 70 镜分镜表，跳过")
        return False
    out_path = D / "prompts" / f"{ep}_70_en.json"
    if out_path.exists():
        print(f"  {ep}: 已翻译，跳过")
        return True

    doc = json.loads(shots_path.read_text(encoding="utf-8"))
    shots = doc["shots"]
    print(f"  {ep}: {len(shots)} 镜待翻译")

    result = {}
    BATCH = 20
    for i in range(0, len(shots), BATCH):
        batch = shots[i:i + BATCH]
        try:
            m = translate_batch(batch)
            result.update(m)
            print(f"    批次 {i//BATCH+1}/{(len(shots)+BATCH-1)//BATCH}: {len(m)} 镜", flush=True)
        except Exception as ex:
            print(f"    批次 {i//BATCH+1} 失败: {str(ex)[:60]}", flush=True)
        time.sleep(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {ep}: {len(result)}/{len(shots)} 镜翻译完成", flush=True)
    return True


if __name__ == "__main__":
    eps = sys.argv[1:] if len(sys.argv) > 1 else [
        "E01", "E02", "E03", "E04", "E05", "E06",
        "E07", "E08", "E09", "E10", "E11", "E12"]
    ok = 0
    for ep in eps:
        if process_episode(ep):
            ok += 1
    print(f"\n=== 完成 {ok}/{len(eps)} 集 ===")
