from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> None:
    """原子写入JSON文件：写临时文件 → rename覆盖。

    先写入一个同目录下的临时文件（.tmp.随机后缀），成功后通过
    pathlib.Path.replace() 覆盖目标路径。写入过程中如果进程崩溃
    或磁盘满，临时文件被清理（missing_ok），目标文件保持原样。
    """
    tmp = path.with_suffix(path.suffix + ".tmp." + os.urandom(4).hex())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
