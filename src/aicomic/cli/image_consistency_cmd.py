"""CLI 命令：图像级角色一致性（image-consistency）— ACOM-0.7.1。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from aicomic.characters.database import (
    connect_character_database,
    ensure_character_schema,
)
from aicomic.image_consistency.comfyui_locks import (
    build_locked_workflow,
    probe_lock_models,
    validate_locked_workflow,
)
from aicomic.image_consistency.image_consistency import ImageConsistencyService
from aicomic.image_consistency.master_sheet import (
    ensure_master_sheet_schema,
    get_master_by_name,
    list_masters,
    mark_locked,
    register_master,
)
from aicomic.image_consistency.one_shot_pipeline import (
    OneShotPipeline,
    ShotSpec,
    write_pipeline_report,
)

ACTION_NAMES = ("register", "list", "lock", "probe", "pipeline")


def _open_db(database: str) -> sqlite3.Connection:
    conn = connect_character_database(Path(database))
    ensure_character_schema(conn)
    ensure_master_sheet_schema(conn)
    return conn


def _ensure_character(conn: sqlite3.Connection, character_id: str, character_name: str) -> None:
    """master_sheets.character_id 外键引用 characters(id)，注册母版前若角色行不存在则先创建。"""
    from aicomic.characters.database import get_character_by_id, insert_character
    if not character_id:
        return
    if get_character_by_id(conn, character_id) is not None:
        return
    from aicomic.characters.models import now_utc_iso
    insert_character(conn, {
        "id": character_id, "name": character_name or character_id,
        "tags": [], "created_at": now_utc_iso(), "updated_at": now_utc_iso(),
    })


def handle_image_consistency(args: Any) -> int:
    action = args.action
    if action not in ACTION_NAMES:
        print(f"未知 action: {action}，可选 {ACTION_NAMES}")
        return 2

    if action == "register":
        conn = _open_db(str(args.database))
        _ensure_character(conn, args.character_id, args.character_name)
        entry = register_master(
            conn, args.character_id, args.character_name, args.master_image,
            source_prompt=args.source_prompt,
        )
        print(json.dumps(entry.to_dict(), ensure_ascii=False, indent=2))
        conn.close()
        return 0

    if action == "list":
        conn = _open_db(str(args.database))
        for m in list_masters(conn):
            print(json.dumps(m.to_dict(), ensure_ascii=False))
        conn.close()
        return 0

    if action == "lock":
        conn = _open_db(str(args.database))
        master = get_master_by_name(conn, args.character_name)
        if master is None:
            print(f"未找到角色 {args.character_name} 的立绘母版")
            conn.close()
            return 1
        mark_locked(conn, master.id, True)
        print(f"已锁定 {args.character_name} 立绘母版：{master.id}")
        conn.close()
        return 0

    if action == "probe":
        status = probe_lock_models(args.comfyui_url, args.model_root, timeout=args.timeout)
        print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if action == "pipeline":
        # 从 JSON 文件读 characters + shots
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        characters: list[dict[str, Any]] = spec.get("characters", [])
        shots = [
            ShotSpec(
                shot_id=s["shot_id"], character_name=s["character_name"],
                scene=s.get("scene", ""), action=s.get("action", ""),
                emotion=s.get("emotion", ""), dialogue=s.get("dialogue", ""),
                duration_s=float(s.get("duration_s", 2.5)),
            )
            for s in spec.get("shots", [])
        ]
        pipe = OneShotPipeline(args.work_dir, comfyui_base_url=args.comfyui_url,
                               threshold=args.threshold)
        report = pipe.run(characters, shots, mode=args.mode)
        out = write_pipeline_report(args.report_output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n[report] {out}")
        return 0

    return 0
