#!/usr/bin/env python3
"""P6 补漏：检查 12 集哪些镜缺失，补跑

用途：P6 批量脚本没有单镜重试（失败就跳过），
跑完后用本脚本找出缺失镜并补生成。

用法:
  python scripts/fill_gaps.py              # 只报告缺失
  python scripts/fill_gaps.py --run        # 补跑缺失镜
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
H3 = Path("/Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac")
PY = BASE / ".venv" / "bin" / "python"

STYLE = ("2d anime, flat cel shading, bold black outlines, hand-drawn animation, "
         "Japanese anime style, xianxia wuxia, animation frames")
ANTI = "serious tone, dramatic, not chibi, realistic proportional anatomy, mature anime proportions"

EPS = ["E01", "E02", "E03", "E04", "E05", "E06",
       "E07", "E08", "E09", "E10", "E11", "E12"]


def find_missing():
    """返回 [(ep, sid, frames, prompt_en), ...]"""
    missing = []
    for ep in EPS:
        align_path = D / "runs" / ep / "alignment.json"
        prompts_path = D / "prompts" / f"{ep}_70_en.json"
        if not align_path.exists():
            print(f"  ⚠️ {ep}: 无 alignment.json，跳过")
            continue
        if not prompts_path.exists():
            print(f"  ⚠️ {ep}: 无 prompts，跳过")
            continue

        align = json.loads(align_path.read_text(encoding="utf-8"))
        prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
        vdir = D / "assets" / ep / "h3video"

        for p in align["plan"]:
            sid = p["shot_id"]
            vp = vdir / f"{ep}_{sid}_h3.mp4"
            if not vp.exists() or vp.stat().st_size < 10000:
                missing.append({
                    "ep": ep, "sid": sid, "frames": p["frames"],
                    "prompt": prompts.get(sid, ""),
                    "actual_sec": p.get("actual_sec"),
                })
    return missing


def main():
    do_run = "--run" in sys.argv
    print("=== 检查 12 集缺失镜 ===")
    missing = find_missing()

    if not missing:
        print("✅ 全部齐全（840 镜）")
        return 0

    print(f"\n❌ 缺失 {len(missing)} 镜:")
    from collections import Counter
    c = Counter(m["ep"] for m in missing)
    for ep in EPS:
        if ep in c:
            print(f"  {ep}: {c[ep]} 镜缺失")

    print(f"\n前 10 个缺失:")
    for m in missing[:10]:
        print(f"  {m['ep']}/{m['sid']} frames={m['frames']} ({m['actual_sec']}s)")

    if not do_run:
        print(f"\n用 --run 参数补跑")
        return 1

    print(f"\n=== 开始补跑 {len(missing)} 镜 ===")
    ok = 0
    fail = 0
    for i, m in enumerate(missing, 1):
        ep, sid, frames = m["ep"], m["sid"], m["frames"]
        en = m["prompt"]
        if not en:
            print(f"  ⚠️ {ep}/{sid} 无 prompt，跳过")
            continue
        out = D / "assets" / ep / "h3video" / f"{ep}_{sid}_h3.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"🎬 [{i}/{len(missing)}] {ep}/{sid} frames={frames}", flush=True)
        cmd = [
            str(H3 / ".venv/bin/h3stream"), "generate",
            "--model-dir", "models", "--width", "512", "--height", "384",
            "--frames", str(frames), "--steps", "8", "--i-understand-experimental",
            "--prompt", f"{STYLE}, {ANTI}, {en}",
            "--output", str(out), "--run-dir", f"runs/fix_{ep}_{sid}",
        ]
        r = subprocess.run(cmd, cwd=str(H3), capture_output=True, text=True, timeout=3600)
        if out.exists() and out.stat().st_size > 10000:
            ok += 1
            print(f"  ✅ {out.stat().st_size//1024}K")
        else:
            fail += 1
            print(f"  ❌ 失败: {r.stderr[-200:] if r.stderr else ''}")

    print(f"\n=== 补跑完成: 成功 {ok}, 失败 {fail} ===")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
