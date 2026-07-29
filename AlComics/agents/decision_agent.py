#!/usr/bin/env python3
"""AIComics 决策层Agent — 只分析不执行、只决策不执行、指令≤100字"""

import argparse, json, os, re, sys, urllib.request, urllib.error
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4:26b"
MAX_SCRIPT_CHARS = 5000  # token预算有限，只喂开头+结尾
DEBUG_RAW_PATH = "/workspace/decision_agent_raw.json"

AGENT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = AGENT_DIR.parent

SYSTEM_PROMPT = """你是一个AI漫剧决策Agent。分析输入的剧本，生成结构化任务清单。

任务类型列表（仅限以下类型）：
- generate_image: 生图任务（参数：prompt, style, count）
- generate_video: 视频生成（参数：prompt, duration, size）
- generate_tts: 配音任务（参数：text, voice, speed）
- render_3d: 3D渲染（参数：fbx, shot_type, duration）
- compose_scene: 合成渲染（参数：inputs, resolution, fps, output）
- analyze_script: 剧本分析（参数：characters, scenes, rhythm）

输出格式：纯JSON数组，每个元素含：
{{
  "id": "T001",
  "type": "frame_gen",
  "params": {{ "prompt": "...", "style": "默认", "count": 4 }},
  "priority": 1,
  "dependency": [],
  "instruction": "生图任务：生成4张关键帧，竖屏9:16，科幻风格"  # ≤100字
}}

要求：紧凑，每个params放最少必要字段。最多生成8个任务。只输出JSON，不要markdown、不要解释。"""


def parse_args():
    p = argparse.ArgumentParser(description="AIComics 决策层Agent")
    p.add_argument("--script", required=True, help="剧本/小说文件路径")
    p.add_argument("--episodes", type=int, default=1, help="集数 (默认1)")
    p.add_argument("--duration", type=int, default=3, help="每集时长分钟 (默认3)")
    p.add_argument("--style", default="默认竖屏漫剧", help="视觉风格")
    p.add_argument("--output", default=str(PROJECT_DIR / "tasks" / "tasklist.json"), help="输出路径")
    return p.parse_args()


def read_script(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(json.dumps({"error": f"剧本文件不存在: {path}"}), file=sys.stderr)
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    # 太长时截取头尾
    if len(text) > MAX_SCRIPT_CHARS:
        head = text[: MAX_SCRIPT_CHARS // 2]
        tail = text[-(MAX_SCRIPT_CHARS // 2) :]
        return f"[脚本开头]\n{head}\n\n[脚本结尾]\n{tail}\n\n[提示] 脚本过长，已截取头尾各{MAX_SCRIPT_CHARS//2}字。"
    return text


def call_ollama(prompt: str, num_predict: int = 16384, retry: int = 0) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": num_predict, "num_ctx": 16384},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            raw = data.get("response", "")
            if not raw and retry < 2:
                print(json.dumps({"warn": f"Ollama返回空响应, 重试第{retry+1}次"}), file=sys.stderr)
                return call_ollama(prompt, num_predict + 4096, retry + 1)
            return raw
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        if retry < 2:
            print(json.dumps({"warn": f"Ollama调用失败({e}), 重试第{retry+1}次"}), file=sys.stderr)
            return call_ollama(prompt, num_predict + 4096, retry + 1)
        print(json.dumps({"error": f"Ollama调用失败({e}) after {retry+1} retries"}), file=sys.stderr)
        sys.exit(1)


def parse_tasks(raw: str) -> list[dict]:
    """从模型输出中提取JSON任务数组，兼容各种格式"""
    # 去掉 ```json ... ``` 和 markdown 包裹
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"^```.*?$", "", cleaned, flags=re.MULTILINE).strip()
    # 找到第一个 [ 后通过括号计数找到匹配的 ]
    start = cleaned.find("[")
    if start == -1:
        _save_debug(raw)
        print(json.dumps({"error": "模型输出未返回JSON数组", "raw_preview": raw[:500]}), file=sys.stderr)
        sys.exit(1)
    depth = 0
    end = start
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if depth != 0:
        _save_debug(raw)
        print(json.dumps({"error": "JSON括号不匹配，模型输出可能被截断"}), file=sys.stderr)
        sys.exit(1)
    json_str = cleaned[start:end]
    # 修复常见JSON问题：移除尾随逗号
    json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
    try:
        arr = json.loads(json_str)
    except json.JSONDecodeError:
        _save_debug(raw)
        print(json.dumps({"error": "JSON解析失败", "json_preview": json_str[:500]}), file=sys.stderr)
        sys.exit(1)
    # 校验结构
    for t in arr:
        assert "id" in t and "type" in t and "params" in t, f"任务缺少必要字段: {t}"
        t.setdefault("priority", 5)
        t.setdefault("dependency", [])
        if "instruction" not in t:
            t["instruction"] = f"{t['type']}: 请执行"
        if len(t["instruction"]) > 100:
            t["instruction"] = t["instruction"][:97] + "..."
    return arr


def _save_debug(raw: str):
    """保存原始输出用于调试"""
    try:
        Path(DEBUG_RAW_PATH).write_text(raw, encoding="utf-8")
    except OSError:
        pass


def main():
    args = parse_args()
    script_text = read_script(args.script)

    # 构造分析请求（基础版）
    base_prompt = (
        f"请分析以下剧本，生成 {args.episodes} 集×{args.duration}分钟/集的制作任务清单。\n"
        f"视觉风格：{args.style}\n\n"
        f"【剧本内容】\n{script_text}\n\n"
        f"输出JSON任务数组。"
    )

    # 重试逻辑：最多3次，每次增加num_predict并提示模型输出JSON
    MAX_RETRIES = 3
    tasks = None
    for attempt in range(MAX_RETRIES):
        if attempt == 0:
            prompt = base_prompt
        else:
            # 重试时添加更明确的指示
            prompt = base_prompt + (
                f"\n\n⚠️ 第{attempt+1}次尝试：务必只输出纯JSON数组，不要markdown、不要解释。"
                f"确保JSON完整闭合，数组长度≥2个任务。"
            )
        raw = call_ollama(prompt, num_predict=16384 + attempt * 4096, retry=attempt)
        try:
            tasks = parse_tasks(raw)
            break  # 成功解析则退出循环
        except SystemExit:
            if attempt < MAX_RETRIES - 1:
                print(json.dumps({"warn": f"JSON解析失败，重试第{attempt+1}次"}), file=sys.stderr)
                continue
            print(json.dumps({"error": f"JSON解析失败，已达最大重试次数({MAX_RETRIES})"}), file=sys.stderr)
            sys.exit(1)

    output = {
        "meta": {
            "agent": "decision_agent",
            "script": args.script,
            "episodes": args.episodes,
            "duration_minutes": args.duration,
            "style": args.style,
            "task_count": len(tasks),
        },
        "tasks": tasks,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
