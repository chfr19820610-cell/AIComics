from __future__ import annotations

import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DEFAULT_DB_PATH = PROJECT_ROOT / "state" / "aicomic_demo.db"
VALIDATION_RUNS_DIR = PROJECT_ROOT / "state" / "validation_runs"


def build_child_env(database_path: Path, state_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    # Intentionally drop any inherited PYTHONPATH (e.g. Hermes agent 3.11 paths)
    # so all sub-processes only load the project's own venv packages.
    pythonpath_items = [str(SRC_DIR), str(PROJECT_ROOT)]
    env["PYTHONPATH"] = os.pathsep.join(item for item in pythonpath_items if item)
    env["AICOMIC_DATABASE_PATH"] = str(database_path)
    if state_dir is not None:
        env["AICOMIC_STATE_DIR"] = str(state_dir)
    return env


def isolated_database_path(run_id: str) -> Path:
    return VALIDATION_RUNS_DIR / run_id / "aicomic_validation.db"


def isolated_script_database_path(run_id: str, script_name: str) -> Path:
    script_stem = Path(script_name).stem
    return VALIDATION_RUNS_DIR / run_id / "scripts" / script_stem / "aicomic_validation.db"


def isolated_script_state_dir(run_id: str, script_name: str) -> Path:
    script_stem = Path(script_name).stem
    return VALIDATION_RUNS_DIR / run_id / "scripts" / script_stem / "state"


def clone_database(source_path: Path, target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()
    source_connection = sqlite3.connect(source_path) if source_path.exists() else None
    target_connection = sqlite3.connect(target_path)
    try:
        if source_connection is not None:
            source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        if source_connection is not None:
            source_connection.close()
    return target_path
