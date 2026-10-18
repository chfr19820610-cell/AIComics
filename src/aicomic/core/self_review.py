"""LLM 自审薄壳（SOP §8.1 审美层 + 巨日禄式自动审片）。

- OpenAI 兼容 chat/completions（stdlib urllib），LM Studio 亦可；env 控制端点/模型；
- 无端点或网络错 → 结构化 verdict=error（fail-soft，不假绿不 raise）；
- seam `_request(url, data_bytes, headers, timeout) -> read()` 可 monkeypatch。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "aicomic-self-review"

SYSTEM_PROMPT = (
    "你是漫剧自审员。针对单镜指标，输出 JSON {\"verdict\": \"pass\"|\"revise\", \"issues\": [str]}。"
    "只审审美与一致性问题（构图/运镜/角色一致），不越权改写。"
)

# 规则层阈值（与 quality_check 对齐；金样评估无 LLM 时的判别底座）
RULE_BLACK_FRACTION_MAX = 0.10
RULE_MIN_DURATION_S = 2.0
RULE_MIN_WIDTH = 720


def judge_shots(shots: list[dict[str, Any]], *, episode_code: str = "") -> dict[str, Any]:
    """规则层融合 verdict：任何一个可判指标越线/缺失 ⇒ revise（不依赖 LLM）。"""
    issues: list[str] = []
    if not shots:
        return {"verdict": "error", "issues": ["无镜头可审"], "model": ""}
    for shot in shots:
        shot_id = str(shot.get("shot_id", "?")) if isinstance(shot, dict) else "?"
        if not isinstance(shot, dict) or not any(isinstance(shot.get(k), (int, float)) for k in ("black_fraction", "duration", "width")):
            issues.append(f"[{shot_id}] 无质检指标（missing/未跑质检）")
            continue
        black = shot.get("black_fraction")
        if isinstance(black, (int, float)) and black > RULE_BLACK_FRACTION_MAX:
            issues.append(f"[{shot_id}] 黑帧 {black:.0%} 超 {RULE_BLACK_FRACTION_MAX:.0%}（终局镜黑帧更严）")
        duration = shot.get("duration")
        if isinstance(duration, (int, float)) and float(duration) < RULE_MIN_DURATION_S:
            issues.append(f"[{shot_id}] 时长 {duration}s < {RULE_MIN_DURATION_S}s")
        width = shot.get("width")
        if isinstance(width, (int, float)) and int(width) < RULE_MIN_WIDTH:
            issues.append(f"[{shot_id}] 分辨率宽 {width} < {RULE_MIN_WIDTH}")
    verdict = "revise" if issues else "pass"
    return {"verdict": verdict, "issues": issues, "model": "", "episode_code": episode_code}


def _config() -> dict[str, str]:
    key = os.environ.get("AICOMIC_OPENAI_API_KEY", "")
    base = os.environ.get("AICOMIC_OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("AICOMIC_SELF_REVIEW_MODEL", DEFAULT_MODEL)
    return {"key": key, "base": base, "model": model}


def _request(url: str, data_bytes: bytes, headers: dict[str, str], timeout: float) -> bytes:
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _error(verdict_message: str) -> dict[str, Any]:
    return {
        "verdict": "error",
        "issues": [{"code": "llm_unavailable", "message": verdict_message}],
        "model": _config()["model"],
    }


def review_assets(shots: list[dict[str, Any]], *, episode_code: str = "", timeout: float = 20.0) -> dict[str, Any]:
    cfg = _config()
    user_payload = {"episode_code": episode_code, "shots": shots}
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['key']}",
    }
    data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        raw = _request(f"{cfg['base']}/chat/completions", data_bytes, headers, timeout)
    except Exception as exc:
        return _error(f"自审请求失败: {exc}")
    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    try:
        data = json.loads(text)
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:  # json 解析/键结构异常均结构化透出，便于排障
        return _error(f"自审响应格式不可解析: {type(exc).__name__}: {exc}")
    return _parse_content(content, cfg["model"])


def _parse_content(content: str, model: str) -> dict[str, Any]:
    text = content.strip() if isinstance(content, str) else ""
    try:
        data = json.loads(text)
        verdict = str(data.get("verdict", "")).lower()
        issues_raw = data.get("issues", [])
        issues = [str(item) for item in issues_raw] if isinstance(issues_raw, list) else []
    except json.JSONDecodeError:
        return {
            "verdict": "error",
            "issues": [{"code": "llm_bad_json", "message": f"自审模型返回非 JSON: {text[:200]}"}],
            "model": model,
        }
    if verdict not in {"pass", "revise"}:
        return {
            "verdict": "error",
            "issues": [{"code": "llm_bad_verdict", "message": f"verdict 不合法: {data.get('verdict')!r}"}],
            "model": model,
        }
    return {"verdict": verdict, "issues": issues, "model": model}


def review_with_golden(golden_path: str | Path) -> dict[str, Any]:
    """金样回归（SOP §8.4）：样本 `{name, expected, shots}`；LLM 在无端点时跳过（结构化可见）。

    返回 {total, passed, failed:[{name, expected, actual, issues}], skipped: [{name, reason}]}。
    """
    golden = Path(golden_path)
    report: dict[str, Any] = {"total": 0, "passed": 0, "failed": [], "skipped": []}
    if not golden.exists():
        report["skipped"].append({"name": golden.name, "reason": f"金样库不存在: {golden}"})
        return report
    try:
        raw = json.loads(golden.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report["skipped"].append({"name": golden.name, "reason": f"不可解析: {exc}"})
        return report
    if isinstance(raw, dict):
        raw = raw.get("cases", [])
    for case in raw if isinstance(raw, list) else []:
        report["total"] += 1
        expected = str(case.get("expected", ""))
        shots = case.get("shots", [])
        if not isinstance(shots, list):
            report["skipped"].append({"name": str(case.get("name", "?")), "reason": "shots 非列表"})
            continue
        verdict = judge_shots(shots)["verdict"]
        if expected == "error":
            report["skipped"].append({"name": str(case.get("name", "?")), "reason": f"模型通路未接入（expected={expected}）"})
            continue
        if verdict == expected:
            report["passed"] += 1
        else:
            report["failed"].append({"name": str(case.get("name", "?")), "expected": expected, "actual": verdict, "issues": issues_for(case, shots)})
    return report


def issues_for(case: dict[str, Any], shots: list[dict[str, Any]]) -> list[str]:
    """只用于金样失败汇报：重跑一次取 issues（实现简洁优先）。"""
    return judge_shots(shots)["issues"]
