from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.core.edition import load_edition_capability
from web.backend.app import health
from web.backend.services.edition_service import load_edition_summary


def ensure_edition_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            edition_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            auth_enabled INTEGER NOT NULL,
            multi_user_enabled INTEGER NOT NULL,
            oidc_enabled INTEGER NOT NULL,
            audit_enabled INTEGER NOT NULL,
            source_path TEXT NOT NULL
        )
        """
    )
    connection.commit()


def insert_edition_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO edition_validation_runs (
            run_id,
            run_at,
            edition_name,
            display_name,
            auth_enabled,
            multi_user_enabled,
            oidc_enabled,
            audit_enabled,
            source_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            str(payload["edition_name"]),
            str(payload["display_name"]),
            int(bool(payload["auth_enabled"])),
            int(bool(payload["multi_user_enabled"])),
            int(bool(payload["oidc_enabled"])),
            int(bool(payload["audit_enabled"])),
            str(payload["source_path"]),
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            edition_name,
            display_name,
            auth_enabled,
            multi_user_enabled,
            oidc_enabled,
            audit_enabled,
            source_path
        FROM edition_validation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "edition_name": row[2],
        "display_name": row[3],
        "auth_enabled": bool(row[4]),
        "multi_user_enabled": bool(row[5]),
        "oidc_enabled": bool(row[6]),
        "audit_enabled": bool(row[7]),
        "source_path": row[8],
    }


def main() -> int:
    edition = load_edition_capability()
    summary = load_edition_summary()
    health_payload = health()
    run_at = datetime.now().astimezone().isoformat()
    run_id = f"edition_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if edition.edition_name != "creator":
        raise RuntimeError(f"edition must stay creator-only: {edition.edition_name}")
    if not edition.auth_enabled:
        raise RuntimeError("creator-only edition should keep personal auth enabled")
    if edition.multi_user_enabled or edition.oidc_enabled or edition.audit_enabled:
        raise RuntimeError(
            "creator-only edition should not expose multi-user, OIDC, or audit capabilities"
        )

    payload = {
        "run_id": run_id,
        "run_at": run_at,
        "edition_name": edition.edition_name,
        "display_name": edition.display_name,
        "auth_enabled": edition.auth_enabled,
        "multi_user_enabled": edition.multi_user_enabled,
        "oidc_enabled": edition.oidc_enabled,
        "audit_enabled": edition.audit_enabled,
        "batch_enabled": edition.batch_enabled,
        "default_database": edition.default_database,
        "default_storage": edition.default_storage,
        "deployment_mode": edition.deployment_mode,
        "default_entry": edition.default_entry,
        "source_path": summary["source"],
        "health_payload": health_payload,
        "database_path": str(ProjectPaths.default_database_path()),
        "report_path": str(PROJECT_ROOT / "reports" / "edition_validation_report.json"),
        "database_row": {},
    }

    connection = sqlite3.connect(ProjectPaths.default_database_path())
    ensure_edition_validation_table(connection)
    insert_edition_validation_run(connection, payload)
    payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "edition_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
