from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from validation_runtime import (
    build_child_env,
    clone_database,
    isolated_database_path,
    isolated_script_database_path,
    isolated_script_state_dir,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DB_PATH = PROJECT_ROOT / "state" / "aicomic_demo.db"
SCRIPT_TIMEOUT_SECONDS = 300


@dataclass
class ValidationRunItem:
    script_name: str
    status: str
    duration_ms: int
    return_code: int
    stdout_tail: str
    stderr_tail: str
    database_path: str


def ensure_validation_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS full_system_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            script_count INTEGER NOT NULL,
            passed_count INTEGER NOT NULL,
            failed_count INTEGER NOT NULL,
            compile_ok INTEGER NOT NULL,
            total_duration_ms INTEGER NOT NULL,
            report_path TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS full_system_validation_run_items (
            item_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            script_name TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            return_code INTEGER NOT NULL,
            stdout_tail TEXT NOT NULL,
            stderr_tail TEXT NOT NULL
        )
        """
    )
    connection.commit()


def discover_validation_scripts() -> list[Path]:
    scripts = sorted(
        path
        for path in SCRIPTS_DIR.glob("validate_*.py")
        if path.name != "validate_full_system_suite.py"
    )
    return scripts


def run_compile_step(scripts: list[Path], child_env: dict[str, str]) -> tuple[bool, str]:
    targets = [
        PROJECT_ROOT / "web" / "backend" / "app.py",
        PROJECT_ROOT / "web" / "backend" / "services" / "report_service.py",
        *scripts,
    ]
    for target in targets:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(target)],
            cwd=str(PROJECT_ROOT),
            env=child_env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "").strip()[-2000:]
    return True, ""


def run_validation_script(script: Path, child_env: dict[str, str], database_path: Path) -> ValidationRunItem:
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            env=child_env,
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ValidationRunItem(
            script_name=script.name,
            status="failed",
            duration_ms=duration_ms,
            return_code=124,
            stdout_tail=(error.stdout or "").strip()[-4000:],
            stderr_tail=(f"Validation script timed out after {SCRIPT_TIMEOUT_SECONDS}s.\n{error.stderr or ''}").strip()[-4000:],
            database_path=str(database_path),
        )
    duration_ms = int((time.perf_counter() - start) * 1000)
    return ValidationRunItem(
        script_name=script.name,
        status="passed" if result.returncode == 0 else "failed",
        duration_ms=duration_ms,
        return_code=result.returncode,
        stdout_tail=(result.stdout or "").strip()[-4000:],
        stderr_tail=(result.stderr or "").strip()[-4000:],
        database_path=str(database_path),
    )


def insert_run(connection: sqlite3.Connection, run_id: str, run_at: str, items: list[ValidationRunItem], compile_ok: bool, report_path: str) -> None:
    total_duration_ms = sum(item.duration_ms for item in items)
    passed_count = sum(1 for item in items if item.status == "passed")
    failed_count = sum(1 for item in items if item.status == "failed")
    connection.execute(
        """
        INSERT INTO full_system_validation_runs (
            run_id,
            run_at,
            script_count,
            passed_count,
            failed_count,
            compile_ok,
            total_duration_ms,
            report_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            run_at,
            len(items),
            passed_count,
            failed_count,
            1 if compile_ok else 0,
            total_duration_ms,
            report_path,
        ),
    )
    for index, item in enumerate(items, start=1):
        connection.execute(
            """
            INSERT INTO full_system_validation_run_items (
                item_id,
                run_id,
                script_name,
                status,
                duration_ms,
                return_code,
                stdout_tail,
                stderr_tail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{run_id}_{index:03d}",
                run_id,
                item.script_name,
                item.status,
                item.duration_ms,
                item.return_code,
                item.stdout_tail,
                item.stderr_tail,
            ),
        )
    connection.commit()


def main() -> int:
    run_id = f"full_system_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    run_at = datetime.now().astimezone().isoformat()
    suite_db_path = clone_database(DB_PATH, isolated_database_path(run_id))
    child_env = build_child_env(suite_db_path)
    scripts = discover_validation_scripts()
    compile_ok, compile_error = run_compile_step(scripts, child_env)
    items: list[ValidationRunItem] = []
    if compile_ok:
        for script in scripts:
            script_db_path = clone_database(DB_PATH, isolated_script_database_path(run_id, script.name))
            script_state_dir = isolated_script_state_dir(run_id, script.name)
            script_state_dir.mkdir(parents=True, exist_ok=True)
            script_env = build_child_env(script_db_path, script_state_dir)
            print(f"[validate_full_system_suite] running {script.name}", flush=True)
            items.append(run_validation_script(script, script_env, script_db_path))
    else:
        items.append(
            ValidationRunItem(
                script_name="py_compile",
                status="failed",
                duration_ms=0,
                return_code=1,
                stdout_tail="",
                stderr_tail=compile_error,
                database_path=str(suite_db_path),
            )
        )

    passed_count = sum(1 for item in items if item.status == "passed")
    failed_count = sum(1 for item in items if item.status == "failed")
    total_duration_ms = sum(item.duration_ms for item in items)
    report_payload = {
        "run_id": run_id,
        "run_at": run_at,
        "database_path": str(suite_db_path),
        "base_database_path": str(DB_PATH),
        "script_count": len(items),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "compile_ok": compile_ok,
        "total_duration_ms": total_duration_ms,
        "items": [
            {
                "script_name": item.script_name,
                "status": item.status,
                "duration_ms": item.duration_ms,
                "return_code": item.return_code,
                "stdout_tail": item.stdout_tail,
                "stderr_tail": item.stderr_tail,
                "database_path": item.database_path,
            }
            for item in items
        ],
        "report_path": str(PROJECT_ROOT / "reports" / "full_system_validation_report.json"),
    }

    suite_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(suite_db_path)
    ensure_validation_tables(connection)
    insert_run(connection, run_id, run_at, items, compile_ok, report_payload["report_path"])
    connection.close()

    report_path = PROJECT_ROOT / "reports" / "full_system_validation_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0 if compile_ok and failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
