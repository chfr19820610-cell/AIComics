#!/usr/bin/env python3
"""测量每句 TTS 的精确时长（不落盘音频，只要时长）

用法: python scripts/measure_tts.py <lines.json> <out.json>
  lines.json: {"S01": "台词1", "S03": "台词2"}
  out.json:   {"S01": 2.67, "S03": 2.21}

关键：必须在文件里跑（piper 用 multiprocessing spawn，stdin 会失败）
"""
import json
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "local_providers" / "piper" / "python"))

MODEL = BASE / "local_providers" / "piper" / "models" / "zh_CN-chaowen-medium.onnx"


def main():
    if len(sys.argv) != 3:
        print("用法: measure_tts.py <lines.json> <out.json>")
        return 1

    lines_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    lines = json.loads(lines_path.read_text(encoding="utf-8"))

    from piper import PiperVoice
    print(f"加载模型… ({len(lines)} 句)", flush=True)
    voice = PiperVoice.load(str(MODEL))
    sr = voice.config.sample_rate

    result = {}
    for sid, text in lines.items():
        text = (text or "").strip()
        if not text:
            continue
        # 去掉 "角色：" 前缀
        say = text.split("：", 1)[-1] if "：" in text else text
        pcm = bytearray()
        try:
            for chunk in voice.synthesize(say):
                pcm.extend(chunk.audio_int16_bytes)
            dur = len(pcm) / 2 / sr
            result[sid] = round(dur, 3)
            print(f"  {sid}: {dur:.3f}s | {say[:20]}", flush=True)
        except Exception as ex:
            print(f"  ❌ {sid}: {ex}", flush=True)

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 输出 {len(result)} 句时长 → {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
