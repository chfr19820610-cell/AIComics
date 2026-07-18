from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from validation_runtime import clone_database, isolated_database_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths


def ensure_validation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_runtime_isolation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            env_override_active INTEGER NOT NULL,
            project_path_matches_env INTEGER NOT NULL,
            uses_default_project_db INTEGER NOT NULL
        )
        """
    )
    connection.commit()


def insert_validation_run(connection: sqlite3.Connection, payload: dict[str, object]) -> None:
    connection.execute(
        """
        INSERT INTO validation_runtime_isolation_runs (
            run_id,
            run_at,
            env_override_active,
            project_path_matches_env,
            uses_default_project_db
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(payload["run_id"]),
            str(payload["run_at"]),
            1 if payload["env_override_active"] else 0,
            1 if payload["project_path_matches_env"] else 0,
            1 if payload["uses_default_project_db"] else 0,
        ),
    )
    connection.commit()


def collect_validation_row(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            run_id,
            run_at,
            env_override_active,
            project_path_matches_env,
            uses_default_project_db
        FROM validation_runtime_isolation_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "run_at": row[1],
        "env_override_active": bool(row[2]),
        "project_path_matches_env": bool(row[3]),
        "uses_default_project_db": bool(row[4]),
    }


def main() -> int:
    run_id = f"validation_runtime_isolation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    run_at = datetime.now().astimezone().isoformat()
    env_database_path = os.environ.get("AICOMIC_DATABASE_PATH", "").strip()
    default_project_db = PROJECT_ROOT / "state" / "aicomic_demo.db"

    if not env_database_path:
        isolated_path = clone_database(default_project_db, isolated_database_path(run_id))
        os.environ["AICOMIC_DATABASE_PATH"] = str(isolated_path)
        env_database_path = str(isolated_path)

    effective_database_path = ProjectPaths.default_database_path()
    connection = sqlite3.connect(effective_database_path)
    ensure_validation_table(connection)

    payload: dict[str, object] = {
        "run_id": run_id,
        "run_at": run_at,
        "env_database_path": env_database_path,
        "effective_database_path": str(effective_database_path),
        "default_project_database_path": str(default_project_db),
        "env_override_active": bool(env_database_path),
        "project_path_matches_env": str(effective_database_path) == env_database_path,
        "uses_default_project_db": str(effective_database_path) == str(default_project_db),
        "report_path": str(PROJECT_ROOT / "reports" / "validation_runtime_isolation_report.json"),
        "database_row": {},
    }

    if not payload["env_override_active"]:
        raise RuntimeError("AICOMIC_DATABASE_PATH override should be active")
    if not payload["project_path_matches_env"]:
        raise RuntimeError("ProjectPaths.default_database_path() did not follow AICOMIC_DATABASE_PATH")
    if payload["uses_default_project_db"]:
        raise RuntimeError("Validation runtime should not reuse the default project database path")

    insert_validation_run(connection, payload)
    payload["database_row"] = collect_validation_row(connection, run_id)
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "validation_runtime_isolation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
