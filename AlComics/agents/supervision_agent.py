#!/usr/bin/env python3
"""AIComics 监督层 Agent — 验证产出质量，R1-R4红线+A/B/C/D评分，输出 verdict.json+report.md"""
import argparse, difflib, json, os, re, sys
from typing import Optional
from datetime import datetime
from pathlib import Path

MIN_SIZE = 100
ALLOWED_SUFFIXES = {".mp4", ".png", ".jpg", ".json", ".md"}
NAMING_OK = {"SANDBOX_REPORT.md", "README.md", "index.md"}
NAMING_PATTERN = re.compile(r'^(E\d{2}|ep\d{2})_.+\.\w+$')


def find_files(target: Path) -> list[Path]:
    return sorted(
        f for f in target.rglob("*")
        if f.is_file() and f.suffix.lower() in ALLOWED_SUFFIXES and "supervision" not in f.parts
    )


def list_assets(ap: Path) -> set[str]:
    return {f.name for f in ap.iterdir() if f.is_file()} if ap.is_dir() else set()
def extract_refs(text: str) -> set[str]:
    """从文本中提取 asset:// URI 引用"""
    return set(re.findall(r'asset://([^\s"\')\]]+)', text))


def check_l1(target: Path) -> tuple[bool, list[dict]]:
    checks = []
    if not target.is_dir():
        checks.append({"name": "路径存在", "passed": False, "detail": f"路径不存在: {target}"})
        return False, checks
    checks.append({"name": "路径存在", "passed": True, "detail": f"路径存在: {target}"})
    files = find_files(target)
    if not files:
        checks.append({"name": "产出文件", "passed": False, "detail": "无产出文件"})
        return False, checks
    checks.append({"name": "产出文件", "passed": True, "detail": f"找到 {len(files)} 个产出文件"})

    small = [f"{f.name}({f.stat().st_size}B)" for f in files if f.stat().st_size < MIN_SIZE]
    if small:
        checks.append({"name": "文件大小", "passed": False, "detail": f"小于阈值({MIN_SIZE}B): {', '.join(small)}"})
    else:
        checks.append({"name": "文件大小", "passed": True, "detail": f"全部 ≥ {MIN_SIZE}B"})

    bad = [str(f.relative_to(target)) for f in files
           if not NAMING_PATTERN.match(f.name) and f.name not in NAMING_OK]
    if bad:
        checks.append({"name": "命名规范", "passed": False, "detail": "不符合:\n  " + "\n  ".join(bad)})
    else:
        checks.append({"name": "命名规范", "passed": True, "detail": "全部符合约定"})
    return all(c["passed"] for c in checks), checks


def check_redlines(target: Path, assets_dir: Path, l1_passed: bool) -> tuple[str, str, list[dict]]:
    files = find_files(target)
    assets_set = list_assets(assets_dir)
    redlines = []

    # R1: 资产引用合法
    ref_fail = []; r_valid = r_total = 0
    for f in files:
        if f.suffix not in {".json", ".md", ".txt"}:
            continue
        try:
            refs = extract_refs(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not refs:
            continue
        r_total += len(refs)
        for ref in refs:
            if ref in assets_set:
                r_valid += 1
            else:
                ref_fail.append(f"  {f.name}: 资产 '{ref}' 不存在")
    r1_score = r_valid / r_total if r_total > 0 else 1.0
    if ref_fail:
        redlines.append({"redline": "R1", "passed": False, "detail": "\n".join(ref_fail), "score": round(r1_score, 2)})
    else:
        redlines.append({"redline": "R1", "passed": True,
                         "detail": f"有效 ({r_valid}/{r_total})" if r_total > 0 else "跳过", "score": 1.0})

    # R2: 剧本忠实度
    r2_passed, r2_score, r2_detail = True, 1.0, ""

    def find_script(files, keywords):
        for f in files:
            if f.suffix in {".json", ".md"} and any(kw in f.name.lower() for kw in keywords):
                return f
        return None

    s1, s2 = find_script(files, ["seedance"]), find_script(files, ["发布文案", "抖音文案", "script", "story"])
    if s1 and s2:
        try:
            t1, t2 = s1.read_text(), s2.read_text()
            if t1.strip() == t2.strip():
                r2_detail = "完全一致"
            else:
                sim = len(set(t1.splitlines()) & set(t2.splitlines())) / max(len(set(t1.splitlines())), 1)
                r2_score = max(0.0, sim)
                diff = list(difflib.unified_diff(t1.splitlines(), t2.splitlines(),
                                                  fromfile=s1.name, tofile=s2.name, lineterm=""))[:20]
                r2_detail = f"差异 (相似度: {sim:.1%})\n" + "\n".join(diff)
                r2_passed = sim >= 0.8
        except Exception as e:
            r2_passed, r2_score, r2_detail = False, 0.0, f"对比出错: {e}"
    elif l1_passed:
        r2_detail = "无可对比脚本对，跳过"
    else:
        r2_passed, r2_score, r2_detail = False, 0.0, "无产出"
    redlines.append({"redline": "R2", "passed": r2_passed, "detail": r2_detail, "score": round(r2_score, 2)})

    # R3: 具象可感
    r3_detail = []
    concrete_words = r'(紧张|恐惧|愤怒|喜悦|悲伤|惊讶|焦虑|温暖|冷漠|声音|爆炸|轰鸣|咆哮|脚步|呼吸|心跳|BGM|动作|跳跃|奔跑|挥拳|射击|闪避|颜色|光线|温度|烟雾|火焰|闪电|晶体|碎片)'
    for f in files:
        if f.suffix not in {".json", ".md", ".txt"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        emo = len(re.findall(r'(紧张|恐惧|愤怒|喜悦|悲伤|惊讶|焦虑|温暖|冷漠)', text))
        snd = len(re.findall(r'(声音|爆炸|轰鸣|咆哮|脚步|呼吸|心跳|BGM)', text))
        act = len(re.findall(r'(动作|跳跃|奔跑|挥拳|射击|闪避)', text))
        sen = len(re.findall(r'(颜色|光线|温度|烟雾|火焰|闪电|晶体|碎片)', text))
        total = emo + snd + act + sen
        r3_detail.append(f"  {f.name}: {'情绪×'+str(emo) if emo else ''}{'声音×'+str(snd) if snd else ''}{'动作×'+str(act) if act else ''}{'感官×'+str(sen) if sen else ''}{'无具体感知' if not total else ''}")
    if not r3_detail:
        r3_detail.append("无可读文本")
    r3_passed = any("情绪" in d or "声音" in d or "动作" in d or "感官" in d for d in r3_detail if "无具体感知" not in d)
    r3_all_text = sum(len(re.findall(concrete_words, f.read_text(errors="ignore")))
                      for f in files if f.suffix in {".json", ".md", ".txt"})
    r3_score = min(1.0, r3_all_text / 20.0) if r3_all_text else 0.0
    redlines.append({"redline": "R3", "passed": r3_passed, "detail": "\n".join(r3_detail), "score": round(r3_score, 2)})

    # R4: 命名规范
    r4_bad = [(str(f.relative_to(target)), f.name) for f in files
              if not NAMING_PATTERN.match(f.name) and f.name not in NAMING_OK]
    if r4_bad:
        detail_lines = [f"  {rel}: 不符合 EXX/epXX 格式" for rel, _ in r4_bad]
        r4_detail = "\n".join(detail_lines)
        r4_passed, r4_score = False, 0.3
    else:
        r4_passed, r4_score, r4_detail = True, 1.0, "全部符合命名规范"
    redlines.append({"redline": "R4", "passed": r4_passed, "detail": r4_detail, "score": r4_score})

    # 评分: A/B/C/D
    failed = [r for r in redlines if not r["passed"]]
    avg = sum(r["score"] for r in redlines) / len(redlines) if redlines else 0
    r1_f = any(r["redline"] == "R1" and not r["passed"] for r in redlines)
    r2_f = any(r["redline"] == "R2" and not r["passed"] for r in redlines)
    if r1_f or r2_f:
        grade, rec = "D", "建议重做 - R1/R2红线未通过，退回决策层重新规划"
    elif len(failed) == 0 and avg >= 0.9:
        grade, rec = "A", "完全通过 - 进入最终输出"
    elif len(failed) == 0 and avg >= 0.7:
        grade, rec = "B", "小问题 - 修复后进入"
    elif len(failed) <= 1:
        grade, rec = "C", "需大改 - 退回执行层重做"
    else:
        grade, rec = "D", "建议重做 - 退回决策层重新规划"
    return grade, rec, redlines


def write_output(target: Path, l1_passed: bool, l1_checks: list, grade: str, rec: str, redlines: list, verdict_path: Optional[Path] = None):
    out = target / "supervision"
    out.mkdir(parents=True, exist_ok=True)
    final = "PASS" if l1_passed and grade in ("A", "B") else "FAIL"

    verdict = {
        "meta": {"agent": "supervision_agent.py", "timestamp": datetime.now().isoformat(),
                 "target": str(target)},
        "l1": {"passed": l1_passed, "checks": l1_checks},
        "l2": {"grade": grade, "recommendation": rec, "redlines": redlines},
        "final_verdict": final,
    }
    (out / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    # Also write to custom path if provided
    if verdict_path:
        verdict_path.parent.mkdir(parents=True, exist_ok=True)
        verdict_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [f"# 监督审查报告\n\n**目标**: `{target}`\n**时间**: {datetime.now():%Y-%m-%d %H:%M:%S}\n**Agent**: supervision_agent.py\n"]
    report.append(f"\n## L1 {'✅ PASS' if l1_passed else '❌ FAIL'}\n")
    for c in l1_checks:
        report.append(f"### {'✅' if c['passed'] else '❌'} {c['name']}\n> {c['detail']}\n")
    report.append(f"\n## L2 — 评分: {grade}\n\n**推荐**: {rec}\n")
    for r in redlines:
        i = "✅" if r["passed"] else "❌"
        report.append(f"### {i} {r['redline']} ({r['score']})\n> {r['detail']}\n")
    report.append(f"\n## 最终裁决: {final}\n")
    if final == "PASS":
        report.append("产出通过全部审查。\n")
    else:
        report.append("产出未通过:\n")
        if not l1_passed:
            report.append("- L1未通过\n")
        if grade not in ("A", "B"):
            report.append(f"- L2评分{grade}，未达A/B\n")
    report.append("\n---\n*本报告由 supervision_agent.py 自动生成*")
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    return out / "verdict.json", out / "report.md"


def main():
    ap = argparse.ArgumentParser(description="AIComics 监督层 Agent")
    ap.add_argument("target", help="执行层输出目录")
    ap.add_argument("--assets", default=None, help="资产目录 (默认: <target>/../assets)")
    ap.add_argument("--verdict", default=None, help="自定义裁决文件输出路径")
    ap.add_argument("--min-size", type=int, default=MIN_SIZE)
    args = ap.parse_args()

    target = Path(args.target).resolve()
    assets_dir = Path(args.assets).resolve() if args.assets else target.parent / "assets"
    verdict_path = Path(args.verdict).resolve() if args.verdict else None

    print(f"🔍 AIComics 监督层 Agent\n   目标: {target}\n   资产: {assets_dir}\n")
    l1_pass, l1_checks = check_l1(target)
    grade, rec, redlines = check_redlines(target, assets_dir, l1_pass)
    vp, rp = write_output(target, l1_pass, l1_checks, grade, rec, redlines, verdict_path)
    final = "PASS" if l1_pass and grade in ("A", "B") else "FAIL"
    print(f"\n📋 最终裁决: {final} (L2: {grade})\n   verdict: {vp}\n   report:  {rp}")
    return 0 if final == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
