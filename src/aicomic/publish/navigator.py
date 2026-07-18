from __future__ import annotations

from pathlib import Path
from typing import Any


def build_episode_navigator(episode_code: str, outputs: list[dict[str, Any]]) -> str:
    items = []
    for output in outputs:
        label = output["label"]
        path = output["path"]
        status = output["status"]
        items.append(f"<li><strong>{label}</strong> - {status}<br><code>{path}</code></li>")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{episode_code} 成品导航</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#111; color:#eee; padding:24px; }}
    h1 {{ margin-bottom: 16px; }}
    li {{ margin-bottom: 14px; line-height: 1.5; }}
    code {{ color: #87d7ff; }}
  </style>
</head>
<body>
  <h1>{episode_code} 成品导航</h1>
  <ul>
    {''.join(items)}
  </ul>
</body>
</html>"""


def write_navigator(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")

