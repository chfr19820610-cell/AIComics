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
# 人脸词（判断画面是否真的有人的脸）
FACE_WORDS = [
    # 严格的"脸"相关词（避免"面前"这种歧义）
    '脸', '面孔', '面容', '侧脸', '正脸', '脸上', '面部', '脸庞',
    '眼', '眸', '唇', '嘴', '眉', '鼻', '下巴', '额头',
    '神情', '表情', '瞳孔', '眼角', '嘴角',
]

MATERIAL_WORDS = [
    "反光", "光泽", "金属", "绸缎", "锦袍", "金线", "景深", "虚化",
    "质感", "皮肤纹理", "皮革", "锈", "油光", "折射", "倒影", "镜面",
    "琉璃", "玉质", "银光", "铜", "铁", "大理石", "石纹",
]

# 情绪/动作词 → 保持动漫风
EMOTION_WORDS = [
    # 情绪
    "隐忍", "冷笑", "咬牙", "皱眉", "怒", "悲", "喜", "惊恐", "疑惑",
    "坚定", "犹豫", "痛苦", "呻吟", "喘息", "惊惶", "厉", "狠", "冷",
    "讥", "嘲", "哀", "惧", "振奋", "亢奋", "虚弱", "疲惫",
    # 动作
    "低垂", "抬头", "握紧", "后退", "瞪", "眯眼", "转身", "抬手",
    "震动", "颤抖", "抽动", "滑落", "迸溅", "四溅", "砸", "劈", "砍",
    "撞", "撕", "拽", "推", "拉", "撑", "踏", "踩", "碾", "跪",
    "站起", "坐下", "躺", "翻滚", "跳", "奔", "逃", "扑", "挡",
    "松手", "抓紧", "敲", "拂袖", "回身", "低头", "仰头", "闭眼",
    # 副词（动作修饰）
    "重重", "轻轻", "缓缓", "急促", "猛地", "骤然", "微微", "剧烈",
    "慢慢", "突然", "渐渐", "猛然", "狠狠", "死死", "静静",
    # 表情/状态
    "紧绷", "发白", "抽搐", "青筋", "扭曲", "收缩", "涣散",
    # 手部动作（补充 Round 74）
    "捏", "捏住", "抓", "握住", "攥", "掐", "钳", "揪", "扯", "拖", "拽住",
    "按", "压", "摁", "拍", "扇", "捶", "掏", "伸", "探", "举", "挥", "甩", "抛",
    "接", "递", "扔", "投", "掷", "叩", "击", "刺", "斩", "削", "划", "戳",
    # 身体动作（补充）
    "俯", "俯身", "俯下", "弯", "倒", "跃", "跑", "冲", "撤", "躲", "闪",
    "避", "爬", "跨", "跺", "踢", "踹", "蹲", "靠", "倚", "扑倒",
    # 头部/视线（补充）
    "转头", "扭头", "侧身", "凑近", "贴", "瞄", "瞟", "扫", "瞥", "盯", "瞅", "望",
    "睁眼", "抿嘴", "张嘴", "叫", "喊", "喝", "吼", "骂", "笑", "哭", "叹", "哼",
    # 变化（补充）
    "弹开", "弹出", "裂", "碎", "断", "炸", "爆", "燃", "烧", "冒", "腾", "升", "降",
    "沉", "浮", "摇", "晃", "震", "抖", "颤", "扭", "歪", "倾", "斜", "偏", "转",
    "旋", "绕", "卷", "翻腾", "翻", "压成", "抽回", "钳住", "压住", "拖到", "围成",
    "悬空", "绷", "紧", "松", "落", "坠", "掉", "迸", "溅", "散",
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
        # 修正：材质词 + 动作/情绪词 → 仍是动漫（动作词能压过材质词）
        # 证据：S14「靴底碾住抹布，指节发白，微微发抖」→ 赛璐璐动漫
        # 而 S11「晨光在锦袍金线上反光」（纯材质）→ 3D 写实
        if has_material and has_emotion:
            return "ANIME", "closeup + 材质+动作（动作压过材质）"
        if has_material:
            return "REALISTIC", f"closeup + 纯材质词({[w for w in MATERIAL_WORDS if w in scene][:2]})"
        if has_emotion:
            return "ANIME", "closeup + 情绪词"
        return "ANIME?", "closeup（无标记）"
    if st in ("medium", "over_shoulder"):
        # 优先级：强动作/情绪 > 多人人脸（CHIBI）> 材质 > 兜底
        # 证据：S15「捏住下巴/脸压成暗影/尘土翻」有强动作 → 实际是动漫
        has_face = any(w in scene for w in FACE_WORDS)
        if has_face and has_emotion:
            return "ANIME", f"{st} + 人脸 + 动作/情绪"
        if n_chars >= 2 and has_face:
            return "CHIBI", f"{st} + {n_chars}人 + 人脸（无动作）"
        if has_material and not has_emotion:
            return "REALISTIC", f"{st} + 材质词（无脸）"
        return "MIXED", f"{st}（{n_chars}人，{'有脸' if has_face else '无脸'}）"
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
