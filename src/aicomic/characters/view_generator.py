"""角色四视图生成器 —— 把四个角度的 prompt 真正送进图像 provider 并落盘。

背景
----
`character_views.py` 已提供：
- `generate_four_view_prompts()`  —— 四角度 prompt 构建
- `get_negative_prompt_for_angle()` —— 逐角度负面词
以及 `character_views` 表的 CRUD。

**唯独缺"驱动层"**：没有人把 prompt 送进出图链路并写回记录。
本模块补这一层，参考 ai-comic-studio 的「角色四视图」用途 —— 用同一角色的
正面/四分之三/侧/背四张参考图，约束后续分镜的角色一致性。

设计
----
- `generate_fn(prompt, negative_prompt, output_path) -> dict` 可注入（便于单测）
- 不注入时用内置 ComfyUI 实现（懒导入，避免循环依赖）
- 逐视图独立成败，单个失败不影响其它三个；整体 `ok` 只在全成功时为 True
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aicomic.characters.character_views import (
    ViewAngle,
    generate_view_prompt,
    get_negative_prompt_for_angle,
)

GenerateFn = Callable[[str, str, Path], dict[str, Any]]


def _default_comfyui_generate(prompt: str, negative_prompt: str, output_path: Path) -> dict[str, Any]:
    """内置 ComfyUI 出图实现（延迟导入，避免与 providers 循环依赖）。"""
    import json as _json
    import urllib.request

    from aicomic.core.config import ProjectPaths
    from aicomic.providers.local_adapter import (
        LOCAL_COMFYUI_PROVIDER,
        get_comfyui_settings,
        load_comfyui_workflow,
        load_provider_settings,
    )

    cfg_path = ProjectPaths.providers_config_path()
    payload = {
        "prompt": prompt,
        "negative_prompt_override": negative_prompt,
        "episode_code": "CHAR",
        "shot_id": output_path.stem,
    }
    settings = get_comfyui_settings(load_provider_settings(cfg_path), cfg_path, payload, LOCAL_COMFYUI_PROVIDER)
    repl = dict(settings["replacements"])
    # 用逐角度负面词覆盖配置里的通用负面词
    repl["{{negative_prompt}}"] = negative_prompt
    workflow = load_comfyui_workflow({**settings, "replacements": repl})

    def _sub(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: (_sub(v) if isinstance(v, (dict, list)) else (repl.get(v, v) if isinstance(v, str) else v))
                    for k, v in node.items()}
        return node

    workflow = _sub(workflow)
    base = str(settings.get("base_url", "http://127.0.0.1:8188")).rstrip("/")
    req = urllib.request.Request(
        f"{base}/prompt",
        data=_json.dumps({"prompt": workflow}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pid = _json.loads(resp.read())["prompt_id"]
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "path": "", "error": f"submit failed: {exc}"}

    # 轮询 history
    import time as _time

    deadline = _time.time() + 900
    while _time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/history/{pid}", timeout=10) as resp:
                hist = _json.loads(resp.read())
        except Exception:
            _time.sleep(4)
            continue
        if pid in hist:
            images = []
            for out in (hist[pid].get("outputs") or {}).values():
                images.extend(out.get("images") or [])
            if images:
                return {"ok": True, "path": "", "remote_filename": images[0].get("filename", ""),
                        "subfolder": images[0].get("subfolder", ""), "prompt_id": pid}
            return {"ok": False, "path": "", "error": "workflow produced no image", "prompt_id": pid}
        _time.sleep(4)
    return {"ok": False, "path": "", "error": "timeout waiting for ComfyUI", "prompt_id": pid}


def generate_views(
    character_name: str,
    character_description: str,
    output_dir: str | Path,
    *,
    generate_fn: GenerateFn | None = None,
    extra_instructions: str = "",
    angles: list[str] | None = None,
) -> dict[str, Any]:
    """为角色生成多角度参考图（默认四视图：正/四分之三/侧/背）。

    Args:
        character_name: 角色名（会拼进 prompt）
        character_description: 角色的视觉描述
        output_dir: 产出目录
        generate_fn: 注入的出图函数；不注入则用内置 ComfyUI 实现
        extra_instructions: 追加指令（如统一风格词）
        angles: 限定角度子集，默认四视图全量

    Returns:
        {"ok", "views": {angle: {...}}, "failed": [angle...]}
    """
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    fn: GenerateFn = generate_fn or _default_comfyui_generate

    targets = angles or [a.value for a in ViewAngle.ordered()]
    results: dict[str, Any] = {}
    failed: list[str] = []

    for angle in targets:
        prompt = generate_view_prompt(character_description, angle, character_name, extra_instructions)
        negative = get_negative_prompt_for_angle(angle)
        target = out_root / f"{angle}.png"
        try:
            r = fn(prompt, negative, target)
        except Exception as exc:  # noqa: BLE001 - 单视图失败不阻断其它视图
            r = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        entry = {
            "ok": bool(r.get("ok")),
            "prompt": prompt,
            "negative_prompt": negative,
            "path": str(r.get("path") or target),
            "error": r.get("error", ""),
        }
        if r.get("remote_filename"):
            entry["remote_filename"] = r["remote_filename"]
        results[angle] = entry
        if not entry["ok"]:
            failed.append(angle)

    return {
        "ok": not failed,
        "angle_count": len(targets),
        "views": results,
        "failed": failed,
    }
