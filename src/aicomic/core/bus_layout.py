"""文件总线骨架（SOP §7.1/§7.2：SSOT/gate=独立可执行检查）。

ensure 担保坐标；validate 只验坐标不生成内容；文件项不存在 → gate 红可见。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def series_layout_targets(series_dir: Path, episode_code: str) -> list[Path]:
    """§7.1 骨架坐标（每剧一仓、每集一 runs 包）。"""
    base = Path(series_dir)
    shots_dir = base / "runs" / episode_code / "shots" / f"{episode_code}S01"
    return [
        base / "specs",
        base / "assets" / "bible.json",
        base / "scripts",
        base / "shots" / f"{episode_code}.json",  # 12 字段分镜表坐标
        base / "routes" / f"{episode_code}.json",  # 每镜路由+预算
        base / "runs" / episode_code,
        shots_dir / "keyframes",
        shots_dir / "clips",
        shots_dir / "metrics.json",
        shots_dir / "salvage",
        base / "runs" / episode_code / "audio",
        base / "runs" / episode_code / "cut",
        base / "runs" / episode_code / "compliance.json",
        base / "runs" / episode_code / "handoff.md",
    ]


_PLACEHOLDER_FILES: dict[str, str] = {
    ".json": "{}",
    ".md": "# handoff (占位)\n",
}


def ensure_series_layout(series_dir: str | Path, episode_code: str) -> list[Path]:
    """骨架坐标担保：目录全建；文件坐标写占位内容（文件即状态，ensure 后 validate 应绿）。"""
    targets = series_layout_targets(Path(series_dir), episode_code)
    for t in targets:
        if t.suffix in _PLACEHOLDER_FILES:
            if not t.exists():
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_text(_PLACEHOLDER_FILES[t.suffix], encoding="utf-8")
        else:
            t.mkdir(parents=True, exist_ok=True)
    return targets


def validate_series_layout(series_dir: str | Path, episode_code: str) -> dict[str, Any]:
    targets = series_layout_targets(Path(series_dir), episode_code)
    missing = [str(t) for t in targets if not t.exists()]
    return {"ok": not missing, "missing": missing, "present": [str(t) for t in targets if t.exists()]}
