from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.project_initializer import initialize_project
from web.backend.services.creator_service import load_creator_workspace, load_projects
from web.backend.settings import load_web_settings


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    settings = load_web_settings()
    created = initialize_project(
        settings.state_dir / "generated_projects",
        "Creator 工作台验证项目",
        "豪门反转",
        "动漫漫剧",
        "creator_workspace_validation",
        protagonist_name="苏晚",
        episode_target_count=6,
    )
    projects_payload = load_projects(settings)
    workspace_payload = load_creator_workspace(settings, project_id=str(created["project_id"]))

    checks = {
        "project_count_at_least_two": int(projects_payload.get("count", 0)) >= 2,
        "workspace_project_id_matches": str(workspace_payload.get("project", {}).get("project_id", "")) == str(created["project_id"]),
        "workspace_has_steps": len(workspace_payload.get("steps", [])) >= 6,
        "workspace_has_story_bible": bool(workspace_payload.get("story_bible_summary", {}).get("exists", False)),
        "workspace_has_episode_blueprint": bool(workspace_payload.get("episode_blueprint_summary", {}).get("exists", False)),
        "workspace_has_release_checklist": bool(workspace_payload.get("release_checklist_exists", False)),
        "workspace_has_next_actions": len(workspace_payload.get("next_actions", [])) >= 1,
    }

    payload = {
        "run_at": run_at,
        "generated_project_id": created["project_id"],
        "projects_count": projects_payload.get("count", 0),
        "workspace_project_name": workspace_payload.get("project", {}).get("project_name", ""),
        "checks": checks,
        "passed": all(checks.values()),
    }

    report_path = PROJECT_ROOT / "reports" / "creator_workspace_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
