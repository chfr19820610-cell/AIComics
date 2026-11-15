#!/usr/bin/env python3
"""单集自动验收：E01 完成时自动跑

检查项（对应 docs/E01_ACCEPTANCE.md）：
1. 70 镜齐全
2. 分辨率 512x384
3. 成片时长 180-240s
4. 音视频轨齐全
5. 字幕条数 = 台词数
6. 字幕时间轴单调
7. 风格动漫率（用 analyze_style 的逻辑）

用法:
  python accept_one.py E01
  python accept_one.py E01 --wait    # 等待完成后再验收（每 10 分钟查一次）
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
FFMPEG = "/Users/eric/.local/bin/ffmpeg"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    """用 ffmpeg -i 读取视频信息（不用 ffprobe，因为本机 ffprobe 是 x86_64）"""
    r = run([FFMPEG, "-hide_banner", "-i", str(path)])
    info = r.stderr
    out = {}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        out["duration"] = h * 3600 + mi * 60 + s
    m = re.search(r"yuv[0-9a-z]+\([a-z]+\), (\d+)x(\d+)", info)
    if m:
        out["resolution"] = f"{m.group(1)}x{m.group(2)}"
    out["has_video"] = "Stream" in info and "Video:" in info
    out["has_audio"] = "Audio:" in info
    return out


def parse_srt(path):
    """解析 SRT，返回 [(idx, start, end, text)]"""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = re.match(r"(\d+):(\d+):([\d,]+) --> (\d+):(\d+):([\d,]+)", lines[1])
        if not m:
            continue
        def to_sec(h, mi, s):
            return int(h) * 3600 + int(mi) * 60 + float(s.replace(",", "."))
        start = to_sec(m.group(1), m.group(2), m.group(3))
        end = to_sec(m.group(4), m.group(5), m.group(6))
        txt = "\n".join(lines[2:]).strip()
        out.append((idx, start, end, txt))
    return out


def check_episode(ep):
    """返回 (passed: bool, report: list[str])"""
    report = []
    ok = True

    def add(status, msg):
        nonlocal ok
        report.append(f"  {status} {msg}")
        if status == "❌":
            ok = False

    # 1. 镜数
    vdir = D / "assets" / ep / "h3video"
    n = len(list(vdir.glob("*.mp4"))) if vdir.exists() else 0
    add("✅" if n == 70 else "❌", f"镜数: {n}/70")

    # 2. 成片
    final = D / "assets" / ep / f"{ep}_H3_REAL.mp4"
    if not final.exists() or final.stat().st_size < 10000:
        add("❌", f"成片缺失或过小: {final.name}")
        return ok, report
    info = probe(final)
    add("✅" if info.get("resolution") == "512x384" else "❌",
        f"分辨率: {info.get('resolution')}")

    # 3. 时长
    dur = info.get("duration", 0)
    add("✅" if 180 <= dur <= 240 else "❌",
        f"成片时长: {dur:.1f}s（目标 180-240s）")

    # 4. 音视频轨
    add("✅" if info.get("has_video") else "❌", "视频轨")
    add("✅" if info.get("has_audio") else "❌", "音频轨")

    # 5. 字幕条数 = 台词数
    shots = D / "shots" / f"{ep}_70.json"
    srt = D / "runs" / ep / "cut" / f"{ep}_r2.srt"
    if shots.exists() and srt.exists():
        doc = json.loads(shots.read_text(encoding="utf-8"))
        n_dial = sum(1 for s in doc["shots"] if (s.get("dialogue") or "").strip())
        entries = parse_srt(srt)
        add("✅" if len(entries) == n_dial else "❌",
            f"字幕: {len(entries)} 条 vs 台词 {n_dial} 句")

        # 6. 时间轴单调
        if entries:
            prev_end = 0
            bad = []
            for idx, st, en, _ in entries:
                if st < prev_end - 0.01:
                    bad.append(idx)
                prev_end = en
            add("✅" if not bad else "❌", f"字幕时间轴: {'正常' if not bad else f'异常 {bad}'}")

            # 7. 字幕在视频范围内
            over = [idx for idx, st, en, _ in entries if en > dur + 0.5]
            add("✅" if not over else "⚠️", f"字幕超出视频: {over if over else '无'}")
    else:
        add("⚠️", f"缺少 shots 或 srt（{shots.exists()}/{srt.exists()}）")

    # 8. 风格分析
    try:
        r = run([sys.executable, str(BASE / "scripts" / "analyze_style.py"), ep])
        lines = r.stdout.splitlines()
        for line in lines:
            if line.strip().startswith(ep):
                parts = line.split()
                if len(parts) >= 7:
                    pct = parts[-2]
                    add("✅" if float(pct.rstrip('%')) >= 45 else "⚠️",
                        f"风格动漫率: {pct}")
                break
    except Exception:
        add("⚠️", "风格分析失败")

    return ok, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--wait", action="store_true", help="等待 70 镜完成后再验收")
    args = ap.parse_args()

    ep = args.episode
    vdir = D / "assets" / ep / "h3video"

    if args.wait:
        print(f"=== 等待 {ep} 的 70 镜完成 ===")
        while True:
            n = len(list(vdir.glob("*.mp4"))) if vdir.exists() else 0
            if n >= 70:
                print(f"  ✅ 70 镜完成（{time.strftime('%H:%M')}）")
                break
            print(f"  ⏳ {n}/70（{time.strftime('%H:%M')}）", flush=True)
            time.sleep(600)

    print()
    print(f"=== {ep} 自动验收（{time.strftime('%m-%d %H:%M')}）===")
    ok, report = check_episode(ep)
    for line in report:
        print(line)
    print()
    print(f"=== 结论: {'✅ 通过' if ok else '❌ 有问题'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
