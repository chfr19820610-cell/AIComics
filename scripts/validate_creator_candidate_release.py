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

from web.backend.services.creator_action_service import (
    build_jobs_action,
    build_provider_requests_action,
    build_candidate_publish_pack_action,
    refresh_creator_reports_action,
    render_release_action,
    resolve_providers_config,
)
from web.backend.services.creator_review_service import (
    confirm_candidate_publish,
    load_creator_sample_review,
    record_candidate_release,
)
from web.backend.services.creator_service import (
    create_creator_project,
    resolve_project_documents,
    upsert_creator_episode,
    upsert_creator_shot,
)
from web.backend.services.pipeline_run_service import submit_creator_action_run
from web.backend.settings import load_web_settings


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    settings = load_web_settings()
    project_id = f"creator_candidate_validation_{datetime.now().strftime('%H%M%S')}"
    created = create_creator_project(
        settings,
        {
            "project_name": "Creator 候选片验证项目",
            "project_id": project_id,
            "genre": "民俗恐怖",
            "style_profile": "动漫漫剧",
            "protagonist_name": "阿禾",
            "episode_target_count": 1,
        },
    )
    revision_summary = dict(created.get("revision_summary", {}))
    episode_result = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "井口不要回头",
            "status": "shotlist_ready",
            "publish_title": "听见井里有人喊你名字，不要回头",
            "cover_text": "井口不能回头",
            "creator_goal": "验证候选片闭环",
            "ending_hook": "井底声音说出了她小时候的乳名。",
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
            "duration": 4,
            "scene": "老井边",
            "characters": ["阿禾"],
            "visual": "深夜老井边，阿禾背对镜头停住脚步，井口贴着发黄符纸。",
            "action": "阿禾停下，风声压低。",
            "dialogue": "别回头。",
            "emotion": "禁忌、悬念",
            "camera": "背影中景",
            "ai_video": False,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )
    revision_summary = dict(first_shot_result.get("revision_summary", revision_summary))
    upsert_creator_shot(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "shot_id": "S02",
            "duration": 4,
            "scene": "井口特写",
            "characters": ["阿禾"],
            "visual": "井口黑暗中像有一张脸浮出又沉下，镜头只给井沿和水面。",
            "action": "水面轻微震动。",
            "dialogue": "阿禾……",
            "emotion": "惊悚、压迫",
            "camera": "局部特写",
            "ai_video": False,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
    )

    project_root = Path(str(created["project_root"]))
    documents = resolve_project_documents(settings, project_root)
    providers_config_path = resolve_providers_config(settings, project_root)
    asset_root = Path(documents["state_dir"]) / "demo_assets"
    build_jobs_action(settings, project_root, documents, "E01")
    documents = resolve_project_documents(settings, project_root)
    build_provider_requests_action(settings, project_root, documents, "E01", providers_config_path, asset_root)
    documents = resolve_project_documents(settings, project_root)
    render_release_action(documents, "E01", asset_root)
    documents = resolve_project_documents(settings, project_root)
    build_candidate_publish_pack_action(documents, "E01")
    documents = resolve_project_documents(settings, project_root)
    refresh_creator_reports_action(settings, project_root, documents, ensure_jobs_if_missing=False)

    review_payload = load_creator_sample_review(settings, project_id, "E01")
    if not review_payload.get("release_video", {}).get("exists"):
        raise RuntimeError("候选片验证前置失败：正式版视频未生成。")

    record_candidate_release(
        settings,
        project_id,
        "E01",
        candidate_run_id="candidate_validation_run",
        release_output_path=str(Path(documents["state_dir"]) / "preview_outputs" / "E01_release.mp4"),
        publish_pack_output_path=str(Path(documents["reports_dir"]) / "publish_pack_E01.json"),
    )
    confirm_result = submit_creator_action_run(
        settings,
        "",
        "confirm_candidate_publish",
        project_id=project_id,
        episode_code="E01",
    )
    confirmed_review = load_creator_sample_review(settings, project_id, "E01")
    manual_confirm = confirm_candidate_publish(settings, project_id, "E01")

    checks = {
        "candidate_ready_written": confirmed_review.get("candidate_release", {}).get("candidate_status") == "ready",
        "confirm_action_completed": str(confirm_result.get("status", "")) == "completed",
        "confirm_sets_review_approved": confirmed_review.get("review_status") == "approved",
        "export_audit_has_version": bool(confirmed_review.get("export_audit", {}).get("current_publish_version", "")),
        "export_audit_has_confirm_time": bool(confirmed_review.get("export_audit", {}).get("last_confirmed_publish_at", "")),
        "manual_confirm_idempotent": manual_confirm.get("review_status") == "approved",
    }
    payload = {
        "run_at": run_at,
        "project_id": project_id,
        "checks": checks,
        "confirm_result": confirm_result,
        "candidate_release": confirmed_review.get("candidate_release", {}),
        "export_audit": confirmed_review.get("export_audit", {}),
        "passed": all(checks.values()),
    }
    report_path = PROJECT_ROOT / "reports" / "creator_candidate_release_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
