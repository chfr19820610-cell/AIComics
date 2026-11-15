#!/usr/bin/env python3
"""测试 Piper TTS 能否返回每句精确时长

结论用于设计「先定配音再定镜长」的对齐工作流。
"""
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "local_providers" / "piper" / "python"))

MODEL = BASE / "local_providers" / "piper" / "models" / "zh_CN-chaowen-medium.onnx"


def main():
    from piper import PiperVoice

    print("加载模型…", flush=True)
    voice = PiperVoice.load(str(MODEL))
    sr = voice.config.sample_rate
    print(f"采样率: {sr}", flush=True)

    lines = [
        "废物的手，也只配擦地。",
        "爬起来啊，杂役。",
        "……第三次了。",
        "它，睁开眼睛了。",
    ]
    print("\n=== 逐句时长 ===", flush=True)
    total = 0.0
    for line in lines:
        pcm = bytearray()
        for chunk in voice.synthesize(line):
            pcm.extend(chunk.audio_int16_bytes)
        dur = len(pcm) / 2 / sr
        total += dur
        print(f"  {dur:.3f}s | {line}", flush=True)
    print(f"\n合计: {total:.3f}s", flush=True)
    print("\n✅ TTS 直接给出精确时长，无需 WhisperX", flush=True)


if __name__ == "__main__":
    main()
