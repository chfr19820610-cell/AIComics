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

from web.backend.services.creator_service import create_creator_project, load_creator_workspace, upsert_creator_episode, upsert_creator_shot
from web.backend.services.pipeline_run_service import list_creator_runs, submit_creator_action_run
from web.backend.settings import load_web_settings


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    settings = load_web_settings()
    project_id = f"creator_pipeline_validation_{datetime.now().strftime('%H%M%S')}"
    created = create_creator_project(
        settings,
        {
            "project_name": "Creator Pipeline 运行验证项目",
            "project_id": project_id,
            "genre": "都市情绪反转",
            "style_profile": "动漫漫剧",
            "protagonist_name": "许澄",
            "episode_target_count": 3,
        },
    )
    revision_summary = dict(created.get("revision_summary", {}))
    episode_result = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "她决定不再忍让",
            "status": "shotlist_ready",
            "creator_goal": "验证 creator run ledger 与最近运行列表",
            "ending_hook": "老板突然改口",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    revision_summary = dict(episode_result.get("revision_summary", revision_summary))
    for shot_payload in [
        {
            "shot_id": "S01",
            "duration": 3,
            "scene": "工位前",
            "characters": ["许澄", "主管"],
            "visual": "许澄压住情绪看向主管。",
            "action": "文件被放回桌面",
            "dialogue": "这次我不会再替你背锅。",
            "emotion": "克制、反击",
            "camera": "中景推进",
            "ai_video": False,
            "priority": "high",
        },
        {
            "shot_id": "S02",
            "duration": 4,
            "scene": "会议室门口",
            "characters": ["许澄", "老板"],
            "visual": "老板推门而入，所有人停下。",
            "action": "镜头切向门口",
            "dialogue": "从现在起，这个项目她负责。",
            "emotion": "反转、压场",
            "camera": "低角度中景",
            "ai_video": True,
            "priority": "high",
        },
    ]:
        shot_result = upsert_creator_shot(
            settings,
            project_id,
            {
                "episode_code": "E01",
                **shot_payload,
                "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
            },
        )
        revision_summary = dict(shot_result.get("revision_summary", revision_summary))

    build_jobs_run = submit_creator_action_run(settings, "", "build_jobs", project_id=project_id, episode_code="E01")
    provider_requests_run = submit_creator_action_run(
        settings,
        "",
        "build_provider_requests",
        project_id=project_id,
        episode_code="E01",
    )
    recent_runs = list_creator_runs(settings, "", project_id=project_id, limit=10)
    workspace = load_creator_workspace(settings, project_id=project_id, user_id="")

    checks = {
        "build_jobs_completed": build_jobs_run.get("status") == "completed",
        "build_jobs_step_count_correct": int(build_jobs_run.get("step_count", 0)) == 1,
        "provider_requests_completed": provider_requests_run.get("status") == "completed",
        "provider_requests_step_count_correct": int(provider_requests_run.get("step_count", 0)) == 2,
        "provider_requests_has_run_id": bool(str(provider_requests_run.get("run_id", "")).strip()),
        "provider_requests_current_step_cleared": str(provider_requests_run.get("current_step_key", "")) == "",
        "recent_runs_count": len(recent_runs) >= 2,
        "latest_run_visible": any(
            str(item.get("run_id", "")) == str(provider_requests_run.get("run_id", "")) for item in recent_runs
        ),
        "workspace_recent_runs_visible": any(
            str(item.get("run_id", "")) == str(provider_requests_run.get("run_id", ""))
            for item in workspace.get("recent_runs", [])
        ),
        "provider_requests_artifacts_recorded": len(provider_requests_run.get("artifacts", [])) >= 1,
    }
    payload = {
        "run_at": run_at,
        "project_id": project_id,
        "project_root": str(created.get("project_root", "")),
        "checks": checks,
        "build_jobs_run": build_jobs_run,
        "provider_requests_run": provider_requests_run,
        "recent_runs": recent_runs,
        "workspace_recent_runs": workspace.get("recent_runs", []),
        "passed": all(checks.values()),
    }
    report_path = PROJECT_ROOT / "reports" / "creator_pipeline_runs_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
