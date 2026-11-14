"""批量 Piper 合成：一次加载模型，按音频计划合成整集 WAV。

背景：单条调用 piper 每次都要重新加载 onnx + g2pw + torch（约 2m53s），
12 集 × 3-6 条台词 = 数百次加载，不可行。
本脚本在**同一进程内**加载一次，循环合成所有台词并按时间轴拼接。
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "local_providers" / "piper" / "python"))


def load_piper():
    from piper import PiperVoice
    return PiperVoice


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model", type=Path,
                    default=PROJECT_ROOT / "local_providers/piper/models/zh_CN-chaowen-medium.onnx")
    ap.add_argument("--total-seconds", type=int, default=0)
    ap.add_argument("--sample-rate", type=int, default=22050)
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    tracks = list(plan.get("tracks") or [])
    print(f"计划: {len(tracks)} 条台词", flush=True)

    PiperVoice = load_piper()
    print("加载模型…", flush=True)
    voice = PiperVoice.load(str(args.model))
    print("模型已加载", flush=True)

    rendered = []
    errors = []
    for tr in tracks:
        text = str(tr.get("text", "")).strip()
        if not text:
            continue
        start = int(tr.get("start", 0))
        try:
            # 去掉 "角色：" 前缀，只念台词
            say = text.split("：", 1)[-1] if "：" in text else text
            pcm = bytearray()
            for chunk in voice.synthesize(say):
                pcm.extend(chunk.audio_int16_bytes)
            rendered.append((start, bytes(pcm)))
            print(f"  ✅ {tr.get('shot_id')} [{start}s] {say[:20]} → {len(pcm)/2/voice.config.sample_rate:.2f}s", flush=True)
        except Exception as exc:
            errors.append(f"{tr.get('shot_id')}: {exc}")
            print(f"  ❌ {tr.get('shot_id')}: {exc}", flush=True)

    sr = args.sample_rate
    total = args.total_seconds or (max((int(t.get("end", 0)) for t in tracks), default=0) or 1)
    buf = bytearray(b"\x00\x00" * int(total * sr))
    for start, raw in rendered:
        off = int(start * sr) * 2
        end = min(off + len(raw), len(buf))
        if off < len(buf):
            buf[off:end] = raw[: end - off]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sr)
        out.writeframes(bytes(buf))

    print(f"\n完成: {len(rendered)}/{len(tracks)} 条, 错误 {len(errors)}, "
          f"输出 {args.output} ({args.output.stat().st_size} bytes)", flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
