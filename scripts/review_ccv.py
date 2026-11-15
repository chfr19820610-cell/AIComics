#!/usr/bin/env python3
"""CCV 三轮评审（P6 版）：对 70 镜分镜表做 Hook/Curve/Cliffhanger 评分

CCV = Content Critic & Verifier
- hook_score: 开头钩子强度（1-10）—— 前 8 镜能不能抓住人
- curve_score: 情绪曲线（1-10）—— 有没有起伏，还是平的
- cliffhanger_score: 结尾悬念（1-10）—— 想不想看下一集

用法:
  python review_ccv.py E01              # 第一轮评审
  python review_ccv.py E01 --round 2    # 第二轮（看是否改进）
  python review_ccv.py --all            # 全部 12 集
  python review_ccv.py E01 --fix        # 评审 + 给改进建议（不自动改）

输出: reviews/ccv/E01_review_r{round}.json
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
EPS = [f"E{i:02d}" for i in range(1, 13)]


def _load_key():
    env_path = BASE / ".env.local"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.environ.get("AICOMIC_OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")


def call_llm(msgs, temp=0.3, max_tokens=6000):
    key = _load_key()
    if not key:
        raise RuntimeError("缺少 API key（.env.local 的 AICOMIC_OPENAI_API_KEY）")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps({
            "model": "deepseek-chat",
            "messages": msgs,
            "temperature": temp,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def build_prompt(ep, doc):
    """构造评审 prompt"""
    shots = doc.get("shots", [])
    lines = []
    for s in shots:
        d = (s.get("dialogue") or "").strip()
        dstr = f' 台词「{d}」' if d else ""
        lines.append(
            f'{s.get("shot_id","?")} [{s.get("act_id","?")}/{s.get("shot_type","?")}] '
            f'{s.get("scene","")[:60]} | 动作:{s.get("action","")[:30]} | 情绪:{s.get("emotion","")}{dstr}'
        )
    body = "\n".join(lines)

    return f"""你是漫剧评审专家（CCV）。对 {ep} 的 70 镜分镜表做三项评分（1-10 分）。

**本集信息**
- 集数: {ep}
- 标题: {doc.get('title', '?')}
- 镜数: {len(shots)}
- 总时长: {doc.get('total_seconds', '?')} 秒

**70 镜分镜表**
{body}

**评分标准**

1. **hook_score（开头钩子）**：前 8 镜能不能抓住人？
   - 9-10: 开场即冲突/悬念，忍不住往下看
   - 7-8: 有吸引力，但铺垫稍长
   - 5-6: 平铺直叙，缺钩子
   - 1-4: 无聊/看不懂在讲什么

2. **curve_score（情绪曲线）**：整集有没有起伏？
   - 9-10: 有明确的高潮和低谷，张弛有度
   - 7-8: 有起伏但不明显
   - 5-6: 平的，一直一个情绪
   - 1-4: 混乱或全程无波动

3. **cliffhanger_score（结尾悬念）**：最后 5 镜想不想看下一集？
   - 9-10: 强烈悬念，必须看下一集
   - 7-8: 有悬念
   - 5-6: 收得完整但没追看欲
   - 1-4: 结尾散/突兀

**输出严格 JSON**（不要 markdown 代码块）：
{{
  "hook_score": <1-10>,
  "curve_score": <1-10>,
  "cliffhanger_score": <1-10>,
  "verdict": "PASS" | "CONCERNS" | "FAIL",
  "issues": [
    {{"shot_id": "S05", "type": "PACING|CLARITY|EMOTION|CONTINUITY|DIALOGUE", "desc": "具体问题"}}
  ],
  "suggestions": [
    {{"shot_id": "S05", "action": "具体改法", "priority": "HIGH|MEDIUM|LOW"}}
  ],
  "strengths": ["这集做得好的地方"]
}}

**判定规则**：
- 三项平均 ≥ 7.5 → PASS
- 三项平均 5.0-7.4 → CONCERNS
- 三项平均 < 5.0 → FAIL

**issues 至少 3 条，suggestions 至少 3 条。诚实评分，不要放水。**"""


def review_one(ep, rnd=1):
    p = D / "shots" / f"{ep}_70.json"
    if not p.exists():
        print(f"  ❌ {ep}: 缺 {p.name}")
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    prompt = build_prompt(ep, doc)

    print(f"  评审 {ep}（第 {rnd} 轮）…", flush=True)
    raw = call_llm([{"role": "user", "content": prompt}])

    # 解析 JSON（容错）
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s < 0 or e <= 0:
            print(f"  ❌ {ep}: 返回非 JSON: {raw[:100]}")
            return None
        data = json.loads(raw[s:e])

    data["episode"] = ep
    data["reviewed_at"] = date.today().isoformat()
    data["round"] = rnd

    out = D / "reviews" / "ccv" / f"{ep}_review_r{rnd}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    h = data.get("hook_score", 0)
    c = data.get("curve_score", 0)
    cf = data.get("cliffhanger_score", 0)
    avg = (h + c + cf) / 3
    print(f"  {ep}: hook={h} curve={c} cliff={cf} avg={avg:.1f} → {data.get('verdict')}")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", nargs="?", help="集数（E01）")
    ap.add_argument("--all", action="store_true", help="全部 12 集")
    ap.add_argument("--round", type=int, default=1, help="第几轮（默认 1）")
    args = ap.parse_args()

    if not args.all and not args.episode:
        ap.error("需要 episode 或 --all")

    eps = EPS if args.all else [args.episode]
    print(f"=== CCV 评审 第 {args.round} 轮（{len(eps)} 集）===")

    results = []
    for ep in eps:
        try:
            r = review_one(ep, args.round)
            if r:
                results.append(r)
        except Exception as exc:
            print(f"  ❌ {ep}: {type(exc).__name__}: {exc}")

    if not results:
        return 1

    print()
    print("=== 汇总 ===")
    for r in results:
        h = r.get("hook_score", 0); c = r.get("curve_score", 0); cf = r.get("cliffhanger_score", 0)
        print(f"  {r['episode']}: {h}/{c}/{cf} avg={(h+c+cf)/3:.1f} {r.get('verdict')}")

    avg_all = sum((r.get("hook_score",0)+r.get("curve_score",0)+r.get("cliffhanger_score",0))/3 for r in results) / len(results)
    passes = sum(1 for r in results if r.get("verdict") == "PASS")
    print()
    print(f"总平均: {avg_all:.2f} | PASS {passes}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
