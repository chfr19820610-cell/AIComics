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

from web.backend.services.creator_runtime_service import RevisionConflictError
from web.backend.services.creator_service import create_creator_project, upsert_creator_episode
from web.backend.settings import load_web_settings


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    settings = load_web_settings()
    project_id = f"creator_revision_validation_{datetime.now().strftime('%H%M%S')}"
    created = create_creator_project(
        settings,
        {
            "project_name": "Creator 修订冲突验证项目",
            "project_id": project_id,
            "genre": "都市逆袭",
            "style_profile": "动漫漫剧",
            "protagonist_name": "林晚",
            "episode_target_count": 2,
        },
    )
    initial_revision_summary = dict(created.get("revision_summary", {}))
    first_save = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "第一次正确保存",
            "status": "idea",
            "expected_episode_manifest_revision_id": initial_revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    latest_revision_summary = dict(first_save.get("revision_summary", initial_revision_summary))
    stale_conflict_message = ""
    stale_conflict_raised = False
    try:
        upsert_creator_episode(
            settings,
            project_id,
            {
                "episode_code": "E01",
                "title": "这次应该冲突",
                "status": "script_ready",
                "expected_episode_manifest_revision_id": initial_revision_summary.get("episode_manifest_revision_id", ""),
            },
        )
    except RevisionConflictError as error:
        stale_conflict_raised = True
        stale_conflict_message = str(error)

    second_save = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "刷新修订后再次保存",
            "status": "script_ready",
            "expected_episode_manifest_revision_id": latest_revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    final_revision_summary = dict(second_save.get("revision_summary", latest_revision_summary))
    checks = {
        "stale_conflict_raised": stale_conflict_raised,
        "stale_conflict_mentions_revision": "修订版本" in stale_conflict_message or "revision" in stale_conflict_message,
        "latest_save_succeeds": bool(second_save.get("updated")),
        "revision_advanced": (
            str(final_revision_summary.get("episode_manifest_revision_id", ""))
            != str(initial_revision_summary.get("episode_manifest_revision_id", ""))
        ),
    }
    payload = {
        "run_at": run_at,
        "project_id": project_id,
        "project_root": str(created.get("project_root", "")),
        "checks": checks,
        "initial_revision_summary": initial_revision_summary,
        "latest_revision_summary": latest_revision_summary,
        "final_revision_summary": final_revision_summary,
        "stale_conflict_message": stale_conflict_message,
        "passed": all(checks.values()),
    }
    report_path = PROJECT_ROOT / "reports" / "creator_revision_conflicts_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
