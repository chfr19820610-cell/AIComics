"""分镜督导 —— 全集一次性视觉连续性审核与批量重写（借鉴 ai-comic-studio）。

问题背景
--------
逐镜生成时，LLM 每镜独立产出描述，跨镜常出现：
- 场景词漂移（"雨夜街道" / "下雨的街" / "雨夜的城市街道"）
- 光线方向矛盾（上一镜"右侧逆光"，下一镜"左侧顺光"）
- 角色外观描述不一致（"浅蓝衬衫" vs "蓝色上衣"）

单镜层面看不出错，整集连播就是"跳戏"。可靠做法是**一次性读入全部分镜**，
由 LLM 统一场景词与角色描述，再批量回写。

设计要点
--------
- `llm_fn(prompt_text) -> str` 可注入；不注入则走 LLM 通道（无 key 时诚实降级）
- 无 LLM 时退化为**规则层**：只做场景词/角色词的频次归一（不臆造内容）
- 输出始终含 `issues[]`，不静默放行
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Callable

# 规则层：这些字段参与一致性比对
_TEXT_FIELDS = ("scene", "scene_desc", "location", "background", "description", "prompt")
_CHAR_FIELDS = ("character", "characters", "char", "role")

SYSTEM_INSTRUCTION = (
    "你是漫剧分镜督导。请通读整集全部分镜，找出跨镜的**视觉连续性问题**，"
    "并给出统一后的重写结果。只输出 JSON，不要 markdown。"
)


def _shot_text(shot: dict[str, Any]) -> str:
    for f in _TEXT_FIELDS:
        v = shot.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _shot_chars(shot: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for f in _CHAR_FIELDS:
        v = shot.get(f)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, list):
            out.extend(str(x).strip() for x in v if str(x).strip())
    return out


def collect_terms(shots: list[dict[str, Any]]) -> dict[str, Any]:
    """规则层：统计场景词与角色描述的分布，用于发现漂移。"""
    scene_tokens: Counter[str] = Counter()
    char_tokens: Counter[str] = Counter()
    for shot in shots:
        text = _shot_text(shot)
        # 中文按 2-4 字滑窗过于激进，这里只用逗号分段后再按空格/标点切
        for seg in re.split(r"[,，。、;；]", text):
            seg = seg.strip()
            if 2 <= len(seg) <= 12:
                scene_tokens[seg] += 1
        for c in _shot_chars(shot):
            char_tokens[c] += 1
    return {
        "scene_terms": [{"term": t, "count": n} for t, n in scene_tokens.most_common(12)],
        "char_terms": [{"term": t, "count": n} for t, n in char_tokens.most_common(12)],
        "shot_count": len(shots),
    }


def rule_based_issues(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规则层问题：同一实体的多种写法 / 角色描述在不同镜头间不统一。"""
    issues: list[dict[str, Any]] = []
    terms = collect_terms(shots)
    # 场景词只在出现 ≥2 次时才有"归一"价值
    repeated = [t for t in terms["scene_terms"] if t["count"] >= 2]
    if len(repeated) >= 2:
        issues.append({
            "code": "scene_term_drift",
            "severity": "info",
            "message": f"全集出现 {len(repeated)} 个高频场景词，建议统一为单一固定表述",
            "terms": [t["term"] for t in repeated],
        })
    missing = [i + 1 for i, s in enumerate(shots) if not _shot_text(s)]
    if missing:
        issues.append({
            "code": "shot_without_visual_text",
            "severity": "warning",
            "message": f"以下镜号缺少可视化描述，无法做连续性审核: {missing}",
            "shots": missing,
        })
    return issues


def build_supervisor_prompt(shots: list[dict[str, Any]], episode_code: str = "") -> str:
    payload = [
        {
            "index": i + 1,
            "shot_id": s.get("shot_id", f"S{i+1:02d}"),
            "visual": _shot_text(s),
            "characters": _shot_chars(s),
        }
        for i, s in enumerate(shots)
    ]
    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"集号: {episode_code or '(未命名)'}\n"
        f"全部分镜（JSON）:\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n\n"
        "输出 JSON，格式：\n"
        '{"issues": [{"shot_id": "...", "code": "...", "message": "..."}],\n'
        ' "rewrites": [{"shot_id": "...", "visual": "统一后的可视化描述"}]}'
    )


def parse_supervisor_reply(reply: str, shots: list[dict[str, Any]]) -> dict[str, Any]:
    """解析 LLM 回复；解析失败返回 error 而非抛异常（fail-soft）。"""
    text = (reply or "").strip()
    if not text:
        return {"ok": False, "error": "empty reply", "issues": [], "rewrites": []}
    # 容忍 ```json 包裹
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"ok": False, "error": "no json object in reply", "issues": [], "rewrites": []}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"json decode: {exc}", "issues": [], "rewrites": []}
    issues = data.get("issues") if isinstance(data.get("issues"), list) else []
    rewrites = data.get("rewrites") if isinstance(data.get("rewrites"), list) else []
    valid_ids = {str(s.get("shot_id", f"S{i+1:02d}")) for i, s in enumerate(shots)}
    # 丢弃指向不存在镜头的重写，避免污染
    kept = [r for r in rewrites if isinstance(r, dict) and str(r.get("shot_id", "")) in valid_ids]
    return {"ok": True, "error": "", "issues": issues, "rewrites": kept,
            "dropped_rewrites": len(rewrites) - len(kept)}


def review_episode(
    shots: list[dict[str, Any]],
    *,
    episode_code: str = "",
    llm_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """全集一次性审核。llm_fn 不注入时只跑规则层（诚实降级）。"""
    if not shots:
        return {"ok": False, "error": "no shots", "issues": [], "rewrites": [],
                "terms": {"scene_terms": [], "char_terms": [], "shot_count": 0}, "llm_used": False}

    terms = collect_terms(shots)
    issues = rule_based_issues(shots)
    result: dict[str, Any] = {
        "ok": True,
        "error": "",
        "issues": issues,
        "rewrites": [],
        "terms": terms,
        "llm_used": False,
    }

    if llm_fn is None:
        return result

    prompt = build_supervisor_prompt(shots, episode_code)
    try:
        reply = llm_fn(prompt)
    except Exception as exc:  # noqa: BLE001 - 外部 LLM 失败属数据，不是崩溃
        result["ok"] = False
        result["error"] = f"llm error: {type(exc).__name__}: {exc}"
        return result

    parsed = parse_supervisor_reply(reply, shots)
    result["llm_used"] = True
    result["llm_issues"] = parsed.get("issues", [])
    result["rewrites"] = parsed.get("rewrites", [])
    if not parsed.get("ok"):
        result["ok"] = False
        result["error"] = parsed.get("error", "llm parse failed")
    result["dropped_rewrites"] = parsed.get("dropped_rewrites", 0)
    return result


def apply_rewrites(shots: list[dict[str, Any]], rewrites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把重写结果回写到分镜（不修改入参，返回新列表）。"""
    by_id = {str(r.get("shot_id", "")): r for r in rewrites if isinstance(r, dict)}
    out: list[dict[str, Any]] = []
    for i, shot in enumerate(shots):
        sid = str(shot.get("shot_id", f"S{i+1:02d}"))
        rw = by_id.get(sid)
        if not rw:
            out.append(dict(shot))
            continue
        merged = dict(shot)
        new_visual = rw.get("visual")
        if isinstance(new_visual, str) and new_visual.strip():
            # 写回第一个存在的文本字段，否则新建 scene
            for f in _TEXT_FIELDS:
                if isinstance(merged.get(f), str) and merged[f].strip():
                    merged[f] = new_visual.strip()
                    break
            else:
                merged["scene"] = new_visual.strip()
        out.append(merged)
    return out
