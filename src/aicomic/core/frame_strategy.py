"""首尾帧三层决策 —— 决定每个镜头用「单帧」还是「首帧+尾帧」。

背景
----
`flf_interpolator.py` 早就提供了 FLF（首尾帧插值）能力，`request_builder` 也只
"把关键帧串成 chain"，但**没有人决定某个镜头到底该不该用双帧**：
- 静态对话镜头用双帧是浪费（双帧调用更贵、更慢，且无运动可插值）
- 动作镜头只给单帧则必然动作僵硬、跨镜跳变

参考 ai-comic-studio 的三层决策：**确定性规则 → LLM 语义判断 → 安全兜底**。
逐层降级，任一层给出高置信结论即停止，永不抛异常。

设计
----
- `decide_frames(shot, *, llm_fn=None)` 返回 `{mode, layer, reason, confidence}`
- `mode`: `"dual"`（首尾帧）或 `"single"`（仅首帧）
- `llm_fn(prompt) -> str` 可注入；不注入则跳过 LLM 层（只跑规则+兜底）
- LLM 回复解析失败一律降级到兜底，不中断管线
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

# ── 规则层词表（中英双语，覆盖本项目模板用语） ─────────────────────────

# 强动作/位移信号：必须双帧
_DUAL_KEYWORDS = (
    "walk", "run", "jump", "turn", "reach", "throw", "fall", "charge", "draw",
    "swing", "hit", "dash", "spin", "enter", "exit", "approach", "retreat",
    "走", "跑", "跳", "转身", "伸手", "推", "拉", "冲", "挥", "打", "落",
    "进", "出", "逼近", "后退", "扑", "抓", "抬", "低头", "回头",
)

# 强静态信号：单帧足够
_SINGLE_KEYWORDS = (
    "close-up", "closeup", "portrait", "still", "static", "establishing",
    "特写", "近景", "静止", "定格", "大景", "空镜", "静",
)

# 镜头类型 → 默认倾向
_SHOT_TYPE_DUAL = {"action", "transition", "key_moment"}
_SHOT_TYPE_SINGLE = {"dialogue", "closeup", "establishing", "flashback"}

# 时长阈值：动作镜头超过该秒数才值得双帧
_DUAL_MIN_DURATION_S = 2.5
# 超过该时长即使静态也建议双帧（长时间静止会显得呆板）
_LONG_SHOT_S = 8.0


def _shot_text(shot: dict[str, Any]) -> str:
    for f in ("motion", "motion_script", "motionScript", "action", "description",
              "scene", "prompt", "visual"):
        v = shot.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _shot_duration(shot: dict[str, Any]) -> float:
    for f in ("duration", "duration_s", "duration_sec"):
        v = shot.get(f)
        try:
            if v is not None:
                return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


def _shot_type(shot: dict[str, Any]) -> str:
    for f in ("shot_type", "type", "camera_type"):
        v = shot.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    return ""


def _has_any(text: str, words: tuple[str, ...]) -> str:
    low = text.lower()
    for w in words:
        if w in low:
            return w
    return ""


def rule_decide(shot: dict[str, Any], *, prev_shot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """规则层：命中即返回结论，未命中返回 None（交给下一层）。"""
    text = _shot_text(shot)
    dur = _shot_duration(shot)
    stype = _shot_type(shot)

    dual_word = _has_any(text, _DUAL_KEYWORDS)
    single_word = _has_any(text, _SINGLE_KEYWORDS)

    # 1) 强静态词优先（避免"特写 + 抬头"被误判为动作镜头）
    if single_word and not dual_word:
        return {"mode": "single", "layer": "rule", "confidence": 0.9,
                "reason": f"静态镜头词命中「{single_word}」"}

    # 2) 强动作词 + 足够时长 → 双帧
    if dual_word:
        if dur >= _DUAL_MIN_DURATION_S or dur == 0.0:
            return {"mode": "dual", "layer": "rule", "confidence": 0.85,
                    "reason": f"动作词命中「{dual_word}」且时长 {dur or '未指定'}s 可容纳位移"}
        return None  # 动作词但时长为正且太短 → 交 LLM 判断

    # 3) 镜头类型倾向
    if stype in _SHOT_TYPE_DUAL:
        return {"mode": "dual", "layer": "rule", "confidence": 0.75,
                "reason": f"镜头类型 {stype} 默认需要运动插值"}
    if stype in _SHOT_TYPE_SINGLE:
        return {"mode": "single", "layer": "rule", "confidence": 0.75,
                "reason": f"镜头类型 {stype} 默认静态"}

    # 4) 超长镜头（无论内容）建议双帧，避免画面呆板
    if dur >= _LONG_SHOT_S:
        return {"mode": "dual", "layer": "rule", "confidence": 0.6,
                "reason": f"时长达 {dur}s，长镜头建议首尾帧以维持节奏"}

    return None


def fallback_decide(shot: dict[str, Any], reason: str = "") -> dict[str, Any]:
    """兜底层：单帧（成本最低、最不易失败）。"""
    return {
        "mode": "single",
        "layer": "fallback",
        "confidence": 0.3,
        "reason": reason or "无明确信号，兜底选择单帧（成本最低、最稳）",
    }


def build_llm_prompt(shot: dict[str, Any], *, prev_shot: dict[str, Any] | None = None) -> str:
    payload = {
        "shot_id": shot.get("shot_id", ""),
        "description": _shot_text(shot),
        "duration_s": _shot_duration(shot),
        "shot_type": _shot_type(shot),
        "prev_shot_description": _shot_text(prev_shot) if prev_shot else "",
    }
    return (
        "你是漫剧分镜技术顾问。判断下面这个镜头生成视频时，应该用"
        "「仅首帧」(single) 还是「首帧+尾帧」(dual) 插值。\n"
        "判断依据：画面内是否有明显位移/肢体动作/镜头运动；静态对话与特写用 single 更省成本，\n"
        "有明显动作或跨镜位移用 dual 才能避免跳变。\n\n"
        f"镜头信息：{json.dumps(payload, ensure_ascii=False)}\n\n"
        '只输出 JSON：{"mode": "single"|"dual", "confidence": 0到1, "reason": "一句话理由"}'
    )


def parse_llm_reply(reply: str) -> dict[str, Any] | None:
    text = (reply or "").strip()
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    mode = str(data.get("mode", "")).strip().lower()
    if mode not in {"single", "dual"}:
        return None
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    return {
        "mode": mode,
        "layer": "llm",
        "confidence": conf,
        "reason": str(data.get("reason", ""))[:200] or "LLM 判定",
    }


def decide_frames(
    shot: dict[str, Any],
    *,
    prev_shot: dict[str, Any] | None = None,
    llm_fn: Callable[[str], str] | None = None,
    llm_confidence_threshold: float = 0.6,
) -> dict[str, Any]:
    """三层决策：规则 → LLM → 兜底。

    Returns:
        {"mode": "dual"|"single", "layer": "rule"|"llm"|"fallback",
         "confidence": float, "reason": str}
    """
    ruled = rule_decide(shot, prev_shot=prev_shot)
    if ruled is not None:
        return ruled

    if llm_fn is not None:
        try:
            reply = llm_fn(build_llm_prompt(shot, prev_shot=prev_shot))
            parsed = parse_llm_reply(reply)
        except Exception as exc:  # noqa: BLE001 - LLM 失败降级，不中断管线
            parsed = None
            ruled_err = f"LLM 调用失败：{type(exc).__name__}"
        else:
            ruled_err = ""
        if parsed is not None and parsed["confidence"] >= llm_confidence_threshold:
            return parsed
        if parsed is not None:
            return fallback_decide(
                shot, f"LLM 判定 {parsed['mode']} 但置信度 {parsed['confidence']:.2f} < "
                      f"{llm_confidence_threshold}，降级兜底")
        return fallback_decide(shot, ruled_err or "LLM 回复无法解析，降级兜底")

    return fallback_decide(shot)


def decide_episode(
    shots: list[dict[str, Any]],
    *,
    llm_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """对整集逐镜做三层决策，并统计分布。"""
    decisions: list[dict[str, Any]] = []
    for i, shot in enumerate(shots):
        prev_shot = shots[i - 1] if i > 0 else None
        d = decide_frames(shot, prev_shot=prev_shot, llm_fn=llm_fn)
        decisions.append({"shot_id": str(shot.get("shot_id", f"S{i+1:02d}")), **d})

    by_layer: dict[str, int] = {}
    dual = 0
    for d in decisions:
        by_layer[d["layer"]] = by_layer.get(d["layer"], 0) + 1
        if d["mode"] == "dual":
            dual += 1
    return {
        "ok": True,
        "shot_count": len(decisions),
        "dual_count": dual,
        "single_count": len(decisions) - dual,
        "by_layer": by_layer,
        "decisions": decisions,
    }
