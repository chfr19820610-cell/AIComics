#!/usr/bin/env python3
"""数据格式校验：确保 12 集的 shots/*_70.json 字段格式一致

基于 SOP §19 的教训：
5 集 shot_type 是中文 → 口型保护静默失效（49 镜本该降级但不会降级）

本脚本做 5 类检查：
1. 枚举字段必须是固定值集合（挡中文/非法值）
2. 必需字段不能为空
3. shot_id 唯一且数量 70
4. duration 在合法范围
5. 四幕结构（≥3 种 act_id）

用法:
  python validate_fields.py            # 校验全部 12 集
  python validate_fields.py E01        # 校验单集
  python validate_fields.py --fix      # 自动修复中文枚举值
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

D = Path("/Users/eric/Desktop/hermes/AlComics/state/projects/xianxia-12")
EPS = [f"E{i:02d}" for i in range(1, 13)]

# 合法值集合
VALID = {
    "shot_type": {"closeup", "extreme_closeup", "medium", "wide",
                  "environment", "action", "hand", "over_shoulder"},
    "act_id": {"underdog", "awaken", "rise", "truth"},
    "priority": {"normal", "high", "low"},
}

# 中文 → 英文映射（修复用）
FIX_MAP = {
    "shot_type": {
        "大特写": "extreme_closeup", "特写": "closeup", "近景": "closeup",
        "中景": "medium", "全景": "wide", "远景": "wide", "大全景": "wide",
        "全身": "wide", "建立镜头": "environment",
        "full": "wide", "establishing": "environment", "key_moment": "closeup",
    },
    "act_id": {
        "逆境": "underdog", "觉醒": "awaken", "崛起": "rise", "真相": "truth",
    },
    "priority": {
        "普通": "normal", "高": "high", "低": "low",
    },
}

REQUIRED_NON_EMPTY = ["shot_id", "shot_type", "scene", "action", "camera", "emotion", "sound_cue"]


def has_cn(s):
    return any('\u4e00' <= ch <= '\u9fff' for ch in str(s))


def validate_one(ep, fix=False):
    p = D / "shots" / f"{ep}_70.json"
    if not p.exists():
        return [f"缺文件 {p.name}"], 0

    doc = json.loads(p.read_text(encoding="utf-8"))
    shots = doc["shots"]
    issues = []
    fixed = 0

    # 0) 自动修复（如果开启）
    if fix:
        for s in shots:
            for field, mm in FIX_MAP.items():
                v = s.get(field, "")
                if v in mm:
                    s[field] = mm[v]
                    fixed += 1
        if fixed:
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    # 1) 枚举字段
    for field, valid_set in VALID.items():
        vals = Counter(s.get(field, "") for s in shots)
        cn = [v for v in vals if has_cn(v)]
        if cn:
            issues.append(f"{field} 含中文: {cn}")
        illegal = [v for v in vals if v and v not in valid_set]
        if illegal:
            issues.append(f"{field} 非法值: {illegal}")

    # 2) 必需字段非空
    for field in REQUIRED_NON_EMPTY:
        empty = [s.get("shot_id", "?") for s in shots if not str(s.get(field) or "").strip()]
        if empty:
            issues.append(f"{field} 有 {len(empty)} 个空值: {empty[:3]}")

    # 3) shot_id 唯一 + 数量
    ids = [s.get("shot_id") for s in shots]
    if len(ids) != 70:
        issues.append(f"镜数 {len(ids)} != 70")
    if len(set(ids)) != len(ids):
        issues.append("shot_id 有重复")

    # 4) duration
    bad = []
    for s in shots:
        try:
            d = float(s.get("duration") or 0)
            if not (0.5 <= d <= 10):
                bad.append(f"{s.get('shot_id')}={d}")
        except (ValueError, TypeError):
            bad.append(f"{s.get('shot_id')}=非数字")
    if bad:
        issues.append(f"duration 异常: {bad[:3]}")

    # 5) 四幕
    acts = len(set(s.get("act_id") for s in shots))
    if acts < 3:
        issues.append(f"只有 {acts} 幕（至少 3）")

    return issues, fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--fix", action="store_true", help="自动修复中文枚举值")
    args = ap.parse_args()

    eps = [args.episode] if args.episode else EPS
    print(f"=== 数据格式校验（{len(eps)} 集）===")
    print()

    fail = 0
    total_fixed = 0
    for ep in eps:
        issues, fixed = validate_one(ep, fix=args.fix)
        total_fixed += fixed
        if issues:
            fail += 1
            print(f"  ❌ {ep}:")
            for i in issues:
                print(f"       - {i}")
        else:
            print(f"  ✅ {ep}: 全部通过" + (f"（修复 {fixed} 处）" if fixed else ""))

    print()
    if args.fix and total_fixed:
        print(f"🔧 自动修复 {total_fixed} 处")
    if fail:
        print(f"❌ {fail}/{len(eps)} 集有问题" + ("（用 --fix 尝试修复）" if not args.fix else ""))
        return 1
    print(f"🎉 全部 {len(eps)} 集字段格式合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
