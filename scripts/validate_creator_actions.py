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

from web.backend.services.creator_service import (
    create_creator_project,
    load_creator_workspace,
    upsert_creator_episode,
    upsert_creator_shot,
)
from web.backend.services.creator_review_service import load_creator_sample_review, save_creator_sample_review
from web.backend.services.pipeline_run_service import list_creator_runs, submit_creator_action_run
from web.backend.settings import load_web_settings


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    settings = load_web_settings()
    project_id = f"creator_actions_validation_{datetime.now().strftime('%H%M%S')}"
    created = create_creator_project(
        settings,
        {
          "project_name": "Creator 动作验证项目",
          "project_id": project_id,
          "genre": "职场反转",
          "style_profile": "动漫漫剧",
          "protagonist_name": "温宁",
          "episode_target_count": 4,
        },
    )
    revision_summary = dict(created.get("revision_summary", {}))
    episode_result = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "被误解的新人",
            "status": "shotlist_ready",
            "publish_title": "所有人都以为她会认输",
            "cover_text": "她没低头",
            "creator_goal": "快速建立冲突和压迫感",
            "ending_hook": "关键人物准备出场",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    revision_summary = dict(episode_result.get("revision_summary", revision_summary))
    first_shot_result = upsert_creator_shot(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "shot_id": "S01",
            "duration": 3,
            "scene": "开放办公区",
            "characters": ["温宁", "主管"],
            "visual": "主管在众人面前压低声音质问温宁，温宁抱着文件站着不动。",
            "action": "主管前倾施压，温宁抬眼",
            "dialogue": "你真以为自己还能留下？",
            "emotion": "压迫、克制",
            "camera": "中近景，轻微推进",
            "ai_video": False,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    revision_summary = dict(first_shot_result.get("revision_summary", revision_summary))
    second_shot_result = upsert_creator_shot(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "shot_id": "S02",
            "duration": 4,
            "scene": "会议室门口",
            "characters": ["温宁", "关键人物"],
            "visual": "门被推开，关键人物出现，所有人安静下来。",
            "action": "镜头从温宁切到门口",
            "dialogue": "她留下，谁都别动。",
            "emotion": "反转、撑腰",
            "camera": "低角度中景",
            "ai_video": True,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    revision_summary = dict(second_shot_result.get("revision_summary", revision_summary))

    action_results = {}
    for action in [
        "build_jobs",
        "build_provider_requests",
        "scan_assets",
        "render_preview",
        "render_release",
        "refresh_creator_reports",
    ]:
        action_results[action] = submit_creator_action_run(
            settings,
            "",
            action,
            project_id=project_id,
            episode_code="E01",
        )
    blocked_publish_pack = submit_creator_action_run(
        settings,
        "",
        "build_publish_pack",
        project_id=project_id,
        episode_code="E01",
    )
    action_results["blocked_publish_pack"] = blocked_publish_pack
    if blocked_publish_pack.get("status") != "failed":
        raise RuntimeError("build_publish_pack should fail before sample review approval")
    save_creator_sample_review(
        settings,
        project_id,
        "E01",
        {
            "review_status": "approved",
            "decision_summary": "验证通过，允许导出。",
            "review_notes": "自动验证脚本写入。",
            "issues": [],
        },
        actor_user_id="",
    )
    action_results["build_publish_pack"] = submit_creator_action_run(
        settings,
        "",
        "build_publish_pack",
        project_id=project_id,
        episode_code="E01",
    )
    action_results["export_approved_release"] = submit_creator_action_run(
        settings,
        "",
        "export_approved_release",
        project_id=project_id,
        episode_code="E01",
    )
    sample_review = load_creator_sample_review(settings, project_id, "E01", user_id="")
    recent_runs = list_creator_runs(settings, "", project_id=project_id, limit=10)
    workspace = load_creator_workspace(settings, project_id=project_id, user_id="")
    recent_run_actions = {str(item.get("action", "")) for item in recent_runs}
    workspace_recent_run_actions = {str(item.get("action", "")) for item in workspace.get("recent_runs", [])}

    project_root = Path(str(created["project_root"]))
    reports_dir = project_root / "reports"
    state_dir = project_root / "state"
    checks = {
        "jobs_exists": (project_root / "jobs" / "episode_jobs.json").exists(),
        "provider_requests_exists": (reports_dir / "provider_requests.json").exists(),
        "asset_scan_exists": (reports_dir / "asset_scan_E01.json").exists(),
        "preview_exists": (state_dir / "preview_outputs" / "E01_preview.mp4").exists() or (reports_dir / "render_preview_E01.json").exists(),
        "publish_pack_exists": (reports_dir / "publish_pack_E01.json").exists(),
        "release_exists": (state_dir / "preview_outputs" / "E01_release.mp4").exists() or (reports_dir / "render_release_E01.json").exists(),
        "creator_validation_exists": (reports_dir / "creator_validation_report.json").exists(),
        "dashboard_exists": (reports_dir / "dashboard.json").exists(),
        "review_metrics_exists": (reports_dir / "review_metrics.json").exists(),
        "gated_publish_pack_failed_before_approval": str(blocked_publish_pack.get("status", "")) == "failed",
        "approved_export_completed": str(action_results["export_approved_release"].get("status", "")) == "completed",
        "export_audit_run_id_written": str(sample_review.get("export_audit", {}).get("last_export_run_id", "")) == str(
            action_results["export_approved_release"].get("run_id", "")
        ),
        "export_audit_version_written": str(sample_review.get("export_audit", {}).get("current_publish_version", "")) == "release-v001",
        "all_required_actions_completed": all(
            str(action_results[key].get("status", "")) == "completed"
            for key in [
                "build_jobs",
                "build_provider_requests",
                "scan_assets",
                "render_preview",
                "render_release",
                "refresh_creator_reports",
                "build_publish_pack",
                "export_approved_release",
            ]
        ),
        "all_actions_have_run_id": all(str(item.get("run_id", "")).strip() for item in action_results.values()),
        "recent_runs_visible": {"build_publish_pack", "export_approved_release"}.issubset(recent_run_actions),
        "workspace_recent_runs_visible": {"build_publish_pack", "export_approved_release"}.issubset(workspace_recent_run_actions),
    }
    payload = {
        "run_at": run_at,
        "project_id": project_id,
        "project_root": str(project_root),
        "revision_summary": revision_summary,
        "checks": checks,
        "action_results": action_results,
        "sample_review_export_audit": sample_review.get("export_audit", {}),
        "recent_runs": recent_runs,
        "workspace_recent_runs": workspace.get("recent_runs", []),
        "passed": all(checks.values()),
    }
    report_path = PROJECT_ROOT / "reports" / "creator_actions_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
