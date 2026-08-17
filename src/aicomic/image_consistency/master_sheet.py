"""立绘母版 Master Sheet — 图像级角色一致性锁定（ACOM-0.7.1）。

为每个角色锁定一份「视觉 DNA 母版」：
  - master_image_path : 参考立绘（图像级锁脸基准，IPAdapter 参考图）
  - dna               : 文本级 DNA 元数据（妆/发/服装/光线，与 donghua 母版规则一致）
  - lock_config       : 图像级控制配置（ipadapter / controlnet / lora）
  - locked            : 是否已锁定（锁定后分镜帧以此为准做图像级比对）

所有分镜帧以立绘母版为基准做图像级 pHash 比对锁定，杜绝跨镜跳脸。
母版表与字符库共用同一 SQLite（connect_character_database）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aicomic.characters.models import now_utc_iso


# ── 数据模型 ─────────────────────────────────────────────────────────────


@dataclass
class MasterSheetEntry:
    """一个角色的立绘母版条目。"""
    id: str
    character_id: str
    character_name: str = ""
    master_image_path: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    lock_config: dict[str, Any] = field(default_factory=dict)
    locked: bool = False
    source_prompt: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "master_image_path": self.master_image_path,
            "dna": self.dna,
            "lock_config": self.lock_config,
            "locked": self.locked,
            "source_prompt": self.source_prompt,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MasterSheetEntry:
        data = dict(row)
        return cls(
            id=data["id"],
            character_id=data["character_id"],
            character_name=data.get("character_name", "") or "",
            master_image_path=data.get("master_image_path", "") or "",
            dna=_load_json(data.get("dna"), {}),
            lock_config=_load_json(data.get("lock_config"), {}),
            locked=bool(data.get("locked", 0)),
            source_prompt=data.get("source_prompt", "") or "",
            created_at=data.get("created_at", "") or "",
            updated_at=data.get("updated_at", "") or "",
        )


def _load_json(raw: Any, fallback: Any) -> Any:
    if raw is None:
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return fallback


# ── Schema ───────────────────────────────────────────────────────────────


def ensure_master_sheet_schema(connection: sqlite3.Connection) -> None:
    """创建立绘母版表。"""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS master_sheets (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            character_name TEXT DEFAULT '',
            master_image_path TEXT DEFAULT '',
            dna TEXT DEFAULT '{}',
            lock_config TEXT DEFAULT '{}',
            locked INTEGER DEFAULT 0,
            source_prompt TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_master_char ON master_sheets(character_id);
        CREATE INDEX IF NOT EXISTS idx_master_name ON master_sheets(character_name);
        """
    )
    connection.commit()


# ── CRUD ─────────────────────────────────────────────────────────────────


def register_master(
    connection: sqlite3.Connection,
    character_id: str,
    character_name: str,
    master_image_path: str,
    dna: dict[str, Any] | None = None,
    lock_config: dict[str, Any] | None = None,
    source_prompt: str = "",
) -> MasterSheetEntry:
    """注册（或覆盖）一个角色的立绘母版。"""
    now = now_utc_iso()
    entry_id = str(uuid.uuid4())
    connection.execute(
        "INSERT OR REPLACE INTO master_sheets "
        "(id, character_id, character_name, master_image_path, dna, lock_config, "
        " locked, source_prompt, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            entry_id, character_id, character_name, master_image_path,
            json.dumps(dna or {}, ensure_ascii=False),
            json.dumps(lock_config or {}, ensure_ascii=False),
            0, source_prompt, now, now,
        ),
    )
    connection.commit()
    return MasterSheetEntry(
        id=entry_id, character_id=character_id, character_name=character_name,
        master_image_path=master_image_path, dna=dna or {}, lock_config=lock_config or {},
        locked=False, source_prompt=source_prompt, created_at=now, updated_at=now,
    )


def get_master_by_character(
    connection: sqlite3.Connection, character_id: str
) -> MasterSheetEntry | None:
    cursor = connection.execute(
        "SELECT * FROM master_sheets WHERE character_id = ? ORDER BY updated_at DESC",
        (character_id,),
    )
    row = cursor.fetchone()
    return MasterSheetEntry.from_row(row) if row else None


def get_master_by_name(
    connection: sqlite3.Connection, character_name: str
) -> MasterSheetEntry | None:
    cursor = connection.execute(
        "SELECT * FROM master_sheets WHERE character_name = ? ORDER BY updated_at DESC",
        (character_name,),
    )
    row = cursor.fetchone()
    return MasterSheetEntry.from_row(row) if row else None


def list_masters(
    connection: sqlite3.Connection, limit: int = 200
) -> list[MasterSheetEntry]:
    cursor = connection.execute(
        "SELECT * FROM master_sheets ORDER BY updated_at DESC LIMIT ?", (limit,)
    )
    return [MasterSheetEntry.from_row(row) for row in cursor.fetchall()]


def mark_locked(
    connection: sqlite3.Connection, master_id: str, locked: bool = True
) -> bool:
    cursor = connection.execute(
        "UPDATE master_sheets SET locked = ?, updated_at = ? WHERE id = ?",
        (1 if locked else 0, now_utc_iso(), master_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def update_master_dna(
    connection: sqlite3.Connection,
    master_id: str,
    dna: dict[str, Any],
    lock_config: dict[str, Any] | None = None,
) -> bool:
    if lock_config is not None:
        cursor = connection.execute(
            "UPDATE master_sheets SET dna = ?, lock_config = ?, updated_at = ? WHERE id = ?",
            (json.dumps(dna, ensure_ascii=False),
             json.dumps(lock_config, ensure_ascii=False), now_utc_iso(), master_id),
        )
    else:
        cursor = connection.execute(
            "UPDATE master_sheets SET dna = ?, updated_at = ? WHERE id = ?",
            (json.dumps(dna, ensure_ascii=False), now_utc_iso(), master_id),
        )
    connection.commit()
    return cursor.rowcount > 0


def default_lock_config(master_image_path: str) -> dict[str, Any]:
    """构造默认的图像级锁脸配置（IPAdapter 参考图 + ControlNet + LoRA 占位）。

    说明：权重模型文件需联网下载后才能真实执行（见 comfyui_locks.probe_lock_models）。
    """
    return {
        "ipadapter": {
            "enabled": True,
            "reference_image": str(master_image_path),
            "faceid": True,
            "weight": 0.85,
        },
        "controlnet": {
            "enabled": False,
            "type": "openpose",  # 结构锁定；需模型文件存在才启用
            "weight": 0.6,
        },
        "lora": {
            "enabled": True,
            "name": "",  # LoRA 权重文件名，联网下载后填入
            "strength": 0.8,
            "status": "pending_download",  # 诚实标注：待联网
        },
    }
