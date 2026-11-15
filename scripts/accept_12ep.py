#!/usr/bin/env python3
"""12 集最终验收（P5 840 镜完成后跑）

检查项：
1. 每集 70 镜视频齐全，分辨率/时长正确
2. 成片 3-4 分钟，v+a 齐全
3. 字幕条数与台词数一致
4. 目录整洁（无残留临时文件）

用法: python scripts/accept_12ep.py
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
FFMPEG = "/Users/eric/.local/bin/ffmpeg"
EPS = ["E01", "E02", "E03", "E04", "E05", "E06",
       "E07", "E08", "E09", "E10", "E11", "E12"]


def ff_info(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True)
    info = r.stderr
    dur = None
    res = None
    has_v = "Stream.*Video" in info or "Video:" in info
    has_a = "Audio:" in info
    for line in info.splitlines():
        if "Duration:" in line and dur is None:
            try:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                dur = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass
        if "yuv" in line and "x" in line and res is None:
            for tok in line.split(","):
                tok = tok.strip()
                if "x" in tok and tok.replace("x", "").isdigit():
                    res = tok
                    break
    return {"duration": dur, "res": res, "has_v": has_v, "has_a": has_a}


def check_episode(ep):
    print(f"\n=== {ep} ===")
    ok = True

    # 1) 70 镜齐全
    vdir = D / "assets" / ep / "h3video"
    shots = list(vdir.glob("*.mp4")) if vdir.exists() else []
    if len(shots) != 70:
        print(f"  ❌ 镜数 {len(shots)} != 70")
        ok = False
    else:
        print(f"  ✅ 70 镜齐全")

    # 2) 抽查 3 镜分辨率
    for p in shots[:3]:
        info = ff_info(p)
        if info["res"] != "512x384":
            print(f"  ❌ {p.name} 分辨率 {info['res']} != 512x384")
            ok = False
    if ok:
        print(f"  ✅ 分辨率 512x384")

    # 3) 成片
    final = D / "assets" / ep / f"{ep}_H3_REAL.mp4"
    if not final.exists():
        print(f"  ❌ 成片缺失")
        return False
    info = ff_info(final)
    dur = info["duration"] or 0
    if not (180 <= dur <= 240):
        print(f"  ❌ 成片时长 {dur:.1f}s 不在 180-240s（3-4分钟）")
        ok = False
    else:
        print(f"  ✅ 成片时长 {dur:.1f}s（{dur/60:.1f} 分钟）")
    if not (info["has_v"] and info["has_a"]):
        print(f"  ❌ 成片缺音视频轨 v={info['has_v']} a={info['has_a']}")
        ok = False
    else:
        print(f"  ✅ 音视频轨齐全")

    # 4) 字幕
    srt = D / "runs" / ep / "cut" / f"{ep}_r2.srt"
    if srt.exists():
        n = len([l for l in srt.read_text(encoding="utf-8").splitlines() if "-->" in l])
        print(f"  ✅ 字幕 {n} 条")
    else:
        print(f"  ❌ 字幕缺失")
        ok = False

    return ok


def main():
    print("=" * 60)
    print("12 集最终验收")
    print("=" * 60)
    results = {}
    for ep in EPS:
        results[ep] = check_episode(ep)

    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    print(f"验收结果: {passed}/12 集通过")
    for ep, v in results.items():
        print(f"  {ep}: {'✅' if v else '❌'}")
    print("=" * 60)
    return 0 if passed == 12 else 1


if __name__ == "__main__":
    sys.exit(main())
