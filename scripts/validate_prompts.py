#!/usr/bin/env python3
"""Prompt 格式校验：确保 840 条英文 prompt 无中文泄漏、长度合理

基于 Round 46 的教训：
E07/S24 的 prompt 含 "压迫"，会导致 h3stream 卡死 20+ 分钟。

检查项：
1. 无中文字符（会导致 h3stream 卡死）
2. 长度合理（20-500 字符）
3. 非空
4. 与 shot_id 一一对应（70 条/集）

用法:
  python validate_prompts.py           # 校验全部 12 集
  python validate_prompts.py E01
  python validate_prompts.py --fix     # 自动移除中文（用拼音/英文替代）
"""
import argparse
import json
import re
import sys
from pathlib import Path

D = Path("/Users/eric/Desktop/hermes/AlComics/state/projects/xianxia-12")
EPS = [f"E{i:02d}" for i in range(1, 13)]

# 常见中英映射（--fix 用）
FIX_MAP = {
    "压迫": "oppressive",
    "紧张": "tense",
    "愤怒": "angry",
    "悲伤": "sad",
    "恐惧": "fearful",
    "惊讶": "surprised",
    "平静": "calm",
    "黑暗": "darkness",
    "光明": "light",
}

MIN_LEN = 20
MAX_LEN = 600

# 【§20 数据流一致性】有台词的 closeup 镜必须降级为 medium
DOWNGRADE = {"closeup": "medium", "extreme_closeup": "medium"}

# 期望的 prompt 前缀（与 effective_type 对应）
PREFIX = {
    "closeup": "Close-up of ",
    "extreme_closeup": "Extreme close-up of ",
    "medium": "Medium shot of ",
    "wide": "Wide shot of ",
    "environment": "Environment shot of ",
    "action": "Action shot of ",
    "hand": "Close-up of ",
    "over_shoulder": "Medium shot of ",
}


def effective_type(shot):
    """返回该镜实际应使用的景别（有台词 closeup 降级为 medium）"""
    st = shot["shot_type"]
    if (shot.get("dialogue") or "").strip() and st in DOWNGRADE:
        return DOWNGRADE[st]
    return st


def has_cn(s):
    return any('\u4e00' <= ch <= '\u9fff' for ch in str(s))


def validate_one(ep, fix=False):
    p = D / "prompts" / f"{ep}_70_en.json"
    shots_p = D / "shots" / f"{ep}_70.json"

    issues = []

    if not p.exists():
        return [f"缺文件 {p.name}"], 0
    if not shots_p.exists():
        return [f"缺 {shots_p.name}"], 0

    prompts = json.loads(p.read_text(encoding="utf-8"))
    shots = json.loads(shots_p.read_text(encoding="utf-8"))["shots"]

    fixed = 0

    # 1) 数量
    if len(prompts) != 70:
        issues.append(f"prompt 数 {len(prompts)} != 70")

    # 2) shot_id 对应
    shot_ids = {s["shot_id"] for s in shots}
    prompt_ids = set(prompts.keys())
    missing = shot_ids - prompt_ids
    extra = prompt_ids - shot_ids
    if missing:
        issues.append(f"缺 prompt: {sorted(missing)[:5]}")
    if extra:
        issues.append(f"多余 prompt: {sorted(extra)[:5]}")

    # 3) 逐条检查
    cn_list = []
    empty_list = []
    short_list = []
    long_list = []

    for sid, en in prompts.items():
        # 中文
        if has_cn(en):
            cn_list.append(sid)
            if fix:
                new = en
                for zh, e in FIX_MAP.items():
                    # 修复时注意空格
                    new = new.replace(zh, f" {e} ")
                new = re.sub(r"\s+", " ", new).strip()
                # 如果还有中文，去掉
                new = re.sub(r"[\u4e00-\u9fff]+", "", new).strip()
                new = re.sub(r"\s+", " ", new)
                prompts[sid] = new
                fixed += 1
        # 空
        if not en.strip():
            empty_list.append(sid)
        # 长度
        elif len(en) < MIN_LEN:
            short_list.append((sid, len(en)))
        elif len(en) > MAX_LEN:
            long_list.append((sid, len(en)))

    # 【§20】prompt 前缀 vs effective_type（最隐蔽的 bug）
    bad_prefix = []
    shot_map = {s["shot_id"]: s for s in shots}
    for sid, en in prompts.items():
        if sid not in shot_map or not en:
            continue
        want = effective_type(shot_map[sid])
        want_prefix = PREFIX.get(want, "")
        if want_prefix and not en.startswith(want_prefix):
            bad_prefix.append((sid, want, en[:35]))

    # 【--fix】修复前缀不匹配（技术债：原代码只记录不修复）
    if fix and bad_prefix:
        all_prefixes = sorted(set(PREFIX.values()), key=len, reverse=True)
        for sid, want, _ in bad_prefix:
            want_prefix = PREFIX.get(want, "")
            if not want_prefix:
                continue
            old = prompts[sid]
            # 剥掉旧前缀（从长到短匹配，避免 "Close-up" 被 "of" 干扰）
            for old_prefix in all_prefixes:
                if old.startswith(old_prefix):
                    prompts[sid] = want_prefix + old[len(old_prefix):]
                    fixed += 1
                    break
        # 重新计算（已修复的不再报）
        bad_prefix = [
            (sid, w, prompts[sid][:35])
            for sid, w, _ in bad_prefix
            if PREFIX.get(w, "") and not prompts[sid].startswith(PREFIX.get(w, ""))
        ]

    if cn_list:
        issues.append(f"含中文: {cn_list[:5]}{'...' if len(cn_list) > 5 else ''} ({len(cn_list)} 条)")
    if bad_prefix:
        issues.append(f"前缀不匹配({len(bad_prefix)}条): " +
                      "; ".join(f"{sid}[want={w}]='{en}'" for sid, w, en in bad_prefix[:3]))
    if empty_list:
        issues.append(f"空 prompt: {empty_list[:5]}")
    if short_list:
        issues.append(f"过短(<{MIN_LEN}): {short_list[:3]}")
    if long_list:
        issues.append(f"过长(>{MAX_LEN}): {long_list[:3]}")

    if fix and fixed:
        p.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
        # 修复后重新校验（清空已修复的问题）
        issues, _ = validate_one(ep, fix=False)
        # 追加修复计数
        return issues, fixed

    return issues, fixed


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--dir", help="自定义项目目录（默认 state/projects/xianxia-12），便于用临时数据测试 --fix 而不污染正式数据")
    args = ap.parse_args()

    # 支持 --dir 注入测试目录（技术债修复：原代码硬编码路径，无法自测）
    if args.dir:
        D = Path(args.dir)
        if not D.exists():
            print(f"❌ 目录不存在: {D}")
            return 2

    eps = [args.episode] if args.episode else EPS
    print(f"=== Prompt 格式校验（{len(eps)} 集）===")
    print()

    fail = 0
    total_fixed = 0
    total_prompts = 0
    for ep in eps:
        issues, fixed = validate_one(ep, fix=args.fix)
        total_fixed += fixed

        p = D / "prompts" / f"{ep}_70_en.json"
        if p.exists():
            total_prompts += len(json.loads(p.read_text(encoding="utf-8")))

        if issues:
            fail += 1
            print(f"  ❌ {ep}:")
            for i in issues:
                print(f"       - {i}")
        else:
            print(f"  ✅ {ep}: 全部通过" + (f"（修复 {fixed} 处）" if fixed else ""))

    print()
    print(f"总 prompt: {total_prompts}")
    if args.fix and total_fixed:
        print(f"🔧 自动修复 {total_fixed} 处")
    if fail:
        print(f"❌ {fail}/{len(eps)} 集有问题" + ("（用 --fix 尝试修复）" if not args.fix else ""))
        return 1
    print(f"🎉 全部 {len(eps)} 集 prompt 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
