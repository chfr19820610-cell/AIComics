#!/usr/bin/env python3
"""风格分布分析：在生成前预测每集的视觉一致性

基于 SOP §17.7 的规律：
  风格 = 景别 × 描述类型
  - 单人 closeup + 情绪化描述 → 赛璐璐动漫 ✅
  - closeup + 材质/光学描述 → 3D 写实 ❌
  - 双人/多人 medium → 偏 Q 版 ⚠️
  - wide/environment（无人）→ 3D CG ⚠️

用法:
  python analyze_style.py E01
  python analyze_style.py --all
"""
import argparse
import json
import re
import sys
from pathlib import Path

D = Path("/Users/eric/Desktop/hermes/AlComics/state/projects/xianxia-12")
EPS = [f"E{i:02d}" for i in range(1, 13)]

# 材质/光学词 → 导致 3D 写实
MATERIAL_WORDS = [
    "反光", "光泽", "金属", "绸缎", "锦袍", "金线", "景深", "虚化",
    "质感", "皮肤纹理", "皮革", "锈", "油光", "折射", "倒影", "镜面",
    "琉璃", "玉质", "银光", "铜", "铁", "大理石", "石纹",
]

# 情绪/动作词 → 保持动漫风
EMOTION_WORDS = [
    "隐忍", "冷笑", "颤抖", "咬牙", "皱眉", "低垂", "抬头", "握紧",
    "后退", "瞪", "眯眼", "咬牙", "怒", "悲", "喜", "惊恐", "疑惑",
    "坚定", "犹豫", "痛苦", "呻吟", "喘息",
]


def classify_shot(shot):
    """返回 (风格预测, 原因)"""
    st = shot.get("shot_type", "")
    scene = shot.get("scene", "")
    chars = shot.get("characters", [])
    n_chars = len(chars) if isinstance(chars, list) else 0

    has_material = any(w in scene for w in MATERIAL_WORDS)
    has_emotion = any(w in scene for w in EMOTION_WORDS)

    if st in ("wide", "environment"):
        return "CG", f"{st} + 无人物"
    if st in ("closeup", "extreme_closeup"):
        if has_material:
            return "REALISTIC", f"closeup + 材质词({[w for w in MATERIAL_WORDS if w in scene][:2]})"
        if has_emotion:
            return "ANIME", "closeup + 情绪词"
        return "ANIME?", "closeup（无标记）"
    if st in ("medium", "over_shoulder"):
        if n_chars >= 2:
            return "CHIBI", f"{st} + {n_chars}人"
        if has_material:
            return "REALISTIC", f"{st} + 材质词"
        return "MIXED", f"{st} 单人"
    if st == "action":
        return "MIXED", "action"
    if st == "hand" or st == "detail":
        return "ANIME?", f"{st}（局部）"
    return "UNKNOWN", st


def analyze(ep):
    p = D / "shots" / f"{ep}_70.json"
    if not p.exists():
        print(f"  ❌ {ep}: 缺文件")
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    shots = doc.get("shots", [])

    from collections import Counter
    results = Counter()
    details = []
    for s in shots:
        style, reason = classify_shot(s)
        results[style] += 1
        details.append((s.get("shot_id"), s.get("shot_type"), style, reason))

    return {"ep": ep, "n": len(shots), "results": results, "details": details}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not args.all and not args.episode:
        ap.error("需要 episode 或 --all")

    eps = EPS if args.all else [args.episode]

    print("=== 风格分布分析（基于 SOP §17.7 规律）===")
    print()
    print(f"{'集':5s} {'动漫':6s} {'CG':6s} {'Q版':6s} {'写实':6s} {'混合':6s} {'动漫率':7s}")
    print("-" * 55)

    all_anime = 0
    all_total = 0
    for ep in eps:
        r = analyze(ep)
        if not r:
            continue
        c = r["results"]
        anime = c.get("ANIME", 0) + c.get("ANIME?", 0)
        cg = c.get("CG", 0)
        chibi = c.get("CHIBI", 0)
        real = c.get("REALISTIC", 0)
        mixed = c.get("MIXED", 0)
        n = r["n"]
        pct = anime / n * 100 if n else 0
        all_anime += anime
        all_total += n
        flag = "✅" if pct >= 60 else ("⚠️" if pct >= 40 else "❌")
        print(f"{ep:5s} {anime:6d} {cg:6d} {chibi:6d} {real:6d} {mixed:6d} {pct:5.0f}% {flag}")

        if args.verbose:
            print()
            for sid, st, style, reason in r["details"]:
                if style in ("REALISTIC", "CHIBI", "CG"):
                    print(f"    {sid} [{st}] → {style}: {reason}")
            print()

    if all_total:
        print()
        print(f"总计: 动漫 {all_anime}/{all_total} = {all_anime/all_total*100:.0f}%")
        print()
        print("判定标准：")
        print("  ≥60% 动漫 → 整体像动漫 ✅")
        print("  40-59%    → 可以接受（有割裂）⚠️")
        print("  <40%      → 像 CG 电影，不是动漫 ❌")


if __name__ == "__main__":
    sys.exit(main() or 0)
