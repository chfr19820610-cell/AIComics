from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from web.backend.services.creator_service import (
    load_project_runtime_metadata,
    read_json,
    resolve_project_documents,
    resolve_project_root_by_id,
)
from web.backend.settings import WebSettings
from aicomic.utils.atomic_io import atomic_write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_asset_url(project_id: str, relative_path: str) -> str:
    return f"/api/creator/assets?project_id={quote(project_id)}&path={quote(relative_path)}"


def resolve_relative_project_path(project_root: Path, raw_path: str) -> str:
    if not raw_path:
        return ""
    candidate = Path(raw_path)
    generated_prefix = ("state", "generated_projects", project_root.name)
    if not candidate.is_absolute() and candidate.parts[:3] == generated_prefix:
        candidate = Path(*candidate.parts[3:])
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(project_root.resolve())
    except (OSError, ValueError):
        return ""
    return relative.as_posix()


def resolve_project_asset_path(settings: WebSettings, project_id: str, raw_path: str, user_id: str = "") -> Path:
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=user_id)
    relative_path = resolve_relative_project_path(project_root, raw_path)
    if not relative_path:
        raise ValueError("非法文件路径。")
    resolved = (project_root / relative_path).resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(relative_path)
    return resolved


def sample_review_report_path(project_root: Path, episode_code: str) -> Path:
    return project_root / "reports" / f"sample_review_{episode_code}.json"


def build_review_issue(raw_issue: dict[str, Any], index: int) -> dict[str, Any]:
    detail = str(raw_issue.get("detail", "")).strip()
    shot_id = str(raw_issue.get("shot_id", "")).strip()
    if not shot_id:
        for token in detail.replace("，", " ").replace(",", " ").split():
            normalized = token.strip().upper()
            if normalized.startswith("S") and len(normalized) >= 3 and normalized[1:].replace("-", "").isdigit():
                shot_id = normalized
                break
    return {
        "issue_id": str(raw_issue.get("issue_id", f"issue_{index:03d}")),
        "severity": str(raw_issue.get("severity", "review_required")) or "review_required",
        "category": str(raw_issue.get("category", "general")) or "general",
        "shot_id": shot_id,
        "detail": detail,
        "status": str(raw_issue.get("status", "open")) or "open",
        "resolution_note": str(raw_issue.get("resolution_note", "")),
    }


def default_autopilot_state() -> dict[str, Any]:
    return {
        "autopilot_status": "draft_ready",
        "autopilot_run_id": "",
        "policy_version": "auto_review_policy_v1",
        "repair_cycle_count": 0,
        "max_repair_cycles": 3,
        "last_decision": "",
        "last_decision_at": "",
        "last_transition_reason": "",
    }


def default_candidate_release() -> dict[str, Any]:
    return {
        "candidate_status": "",
        "candidate_run_id": "",
        "candidate_created_at": "",
        "release_output_path": "",
        "publish_pack_output_path": "",
        "quality_score": 0,
        "quality_summary": {
            "blocking_findings": 0,
            "review_required_findings": 0,
            "manual_required_count": 0,
            "queue_count": 0,
        },
    }


def default_autopilot_audit() -> dict[str, Any]:
    return {
        "total_runtime_seconds": 0,
        "total_repaired_shots": 0,
        "repaired_shot_ids": [],
        "last_escalation_reason": "",
        "final_route": "",
        "last_contact_sheet_path": "",
    }


def default_export_audit() -> dict[str, Any]:
    return {
        "export_count": 0,
        "current_publish_version": "",
        "last_exported_at": "",
        "last_export_run_id": "",
        "last_exported_by_user_id": "",
        "last_release_output_path": "",
        "last_publish_pack_output_path": "",
        "last_candidate_run_id": "",
        "last_candidate_created_at": "",
        "last_confirmed_publish_at": "",
        "last_confirmed_by_user_id": "",
    }


def normalize_autopilot_state(raw_payload: Any) -> dict[str, Any]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    normalized = default_autopilot_state()
    normalized["autopilot_status"] = str(payload.get("autopilot_status", normalized["autopilot_status"])) or normalized["autopilot_status"]
    normalized["autopilot_run_id"] = str(payload.get("autopilot_run_id", ""))
    normalized["policy_version"] = str(payload.get("policy_version", normalized["policy_version"])) or normalized["policy_version"]
    normalized["repair_cycle_count"] = int(payload.get("repair_cycle_count", 0) or 0)
    normalized["max_repair_cycles"] = int(payload.get("max_repair_cycles", normalized["max_repair_cycles"]) or normalized["max_repair_cycles"])
    normalized["last_decision"] = str(payload.get("last_decision", ""))
    normalized["last_decision_at"] = str(payload.get("last_decision_at", ""))
    normalized["last_transition_reason"] = str(payload.get("last_transition_reason", ""))
    return normalized


def normalize_candidate_release(raw_payload: Any) -> dict[str, Any]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    normalized = default_candidate_release()
    quality_summary = payload.get("quality_summary", {})
    normalized["candidate_status"] = str(payload.get("candidate_status", ""))
    normalized["candidate_run_id"] = str(payload.get("candidate_run_id", ""))
    normalized["candidate_created_at"] = str(payload.get("candidate_created_at", ""))
    normalized["release_output_path"] = str(payload.get("release_output_path", ""))
    normalized["publish_pack_output_path"] = str(payload.get("publish_pack_output_path", ""))
    normalized["quality_score"] = int(payload.get("quality_score", 0) or 0)
    normalized["quality_summary"] = {
        "blocking_findings": int(quality_summary.get("blocking_findings", 0) or 0) if isinstance(quality_summary, dict) else 0,
        "review_required_findings": int(quality_summary.get("review_required_findings", 0) or 0) if isinstance(quality_summary, dict) else 0,
        "manual_required_count": int(quality_summary.get("manual_required_count", 0) or 0) if isinstance(quality_summary, dict) else 0,
        "queue_count": int(quality_summary.get("queue_count", 0) or 0) if isinstance(quality_summary, dict) else 0,
    }
    return normalized


def normalize_autopilot_audit(raw_payload: Any) -> dict[str, Any]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    normalized = default_autopilot_audit()
    normalized["total_runtime_seconds"] = int(payload.get("total_runtime_seconds", 0) or 0)
    normalized["total_repaired_shots"] = int(payload.get("total_repaired_shots", 0) or 0)
    normalized["repaired_shot_ids"] = [str(item) for item in payload.get("repaired_shot_ids", []) if str(item).strip()] if isinstance(payload.get("repaired_shot_ids", []), list) else []
    normalized["last_escalation_reason"] = str(payload.get("last_escalation_reason", ""))
    normalized["final_route"] = str(payload.get("final_route", ""))
    normalized["last_contact_sheet_path"] = str(payload.get("last_contact_sheet_path", ""))
    return normalized


def normalize_export_audit(raw_payload: Any) -> dict[str, Any]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    normalized = default_export_audit()
    for key in normalized:
        if key == "export_count":
            normalized[key] = int(payload.get(key, 0) or 0)
        else:
            normalized[key] = str(payload.get(key, ""))
    return normalized


def compute_candidate_quality_score(review_payload: dict[str, Any]) -> int:
    quality_summary = review_payload.get("quality_summary", {})
    provider_summary = review_payload.get("provider_summary", {})
    release_video = review_payload.get("release_video", {})
    score = 100
    score -= int(quality_summary.get("blocking_findings", 0)) * 30
    score -= int(quality_summary.get("review_required_findings", 0)) * 5
    score -= int(provider_summary.get("manual_required_count", 0)) * 10
    score -= int(provider_summary.get("queue_count", 0)) * 5
    score -= int(release_video.get("used_placeholder_count", 0)) * 10
    return max(0, score)


def build_auto_review_decision(review_payload: dict[str, Any]) -> dict[str, Any]:
    autopilot_state = normalize_autopilot_state(review_payload.get("autopilot_state", {}))
    quality_summary = review_payload.get("quality_summary", {})
    provider_summary = review_payload.get("provider_summary", {})
    release_video = review_payload.get("release_video", {})
    blocking_findings = int(quality_summary.get("blocking_findings", 0) or 0)
    review_required_findings = int(quality_summary.get("review_required_findings", 0) or 0)
    manual_required_count = int(provider_summary.get("manual_required_count", 0) or 0)
    queue_count = int(provider_summary.get("queue_count", 0) or 0)
    used_placeholder_count = int(release_video.get("used_placeholder_count", 0) or 0)
    release_exists = bool(release_video.get("exists"))
    repair_cycle_count = int(autopilot_state.get("repair_cycle_count", 0) or 0)
    max_repair_cycles = int(autopilot_state.get("max_repair_cycles", 3) or 3)
    reasons: list[str] = []
    measured_metrics = {
        "blocking_findings": blocking_findings,
        "review_required_findings": review_required_findings,
        "manual_required_count": manual_required_count,
        "queue_count": queue_count,
        "used_placeholder_count": used_placeholder_count,
        "release_exists": release_exists,
        "repair_cycle_count": repair_cycle_count,
        "max_repair_cycles": max_repair_cycles,
        "quality_score": compute_candidate_quality_score(review_payload),
    }
    if (
        release_exists
        and blocking_findings == 0
        and manual_required_count == 0
        and queue_count == 0
        and used_placeholder_count == 0
    ):
        return {
            "decision": "pass_to_candidate",
            "reasons": ["当前样片已满足候选片标准。"],
            "policy_version": "auto_review_policy_v1",
            "measured_metrics": measured_metrics,
            "next_action": "record_candidate_release",
        }
    if repair_cycle_count < max_repair_cycles and (manual_required_count > 0 or queue_count > 0 or used_placeholder_count > 0):
        if manual_required_count > 0:
            reasons.append(f"仍有 {manual_required_count} 个 manual_required 任务待处理。")
        if queue_count > 0:
            reasons.append(f"仍有 {queue_count} 个重生成队列项待处理。")
        if used_placeholder_count > 0:
            reasons.append(f"正式版仍含 {used_placeholder_count} 个占位镜头。")
        return {
            "decision": "repair_and_retry",
            "reasons": reasons or ["仍需自动修复后再审片。"],
            "policy_version": "auto_review_policy_v1",
            "measured_metrics": measured_metrics,
            "next_action": "auto_repair_episode",
        }
    if blocking_findings > 0:
        reasons.append(f"仍有 {blocking_findings} 个阻塞级问题。")
    if not release_exists:
        reasons.append("正式版视频不存在。")
    if repair_cycle_count >= max_repair_cycles:
        reasons.append("已达到自动修复轮数上限。")
    if review_required_findings > 0 and not reasons:
        reasons.append(f"仍有 {review_required_findings} 个待人工判断问题。")
    return {
        "decision": "escalate_to_human",
        "reasons": reasons or ["当前样片不适合继续自动推进，需人工介入。"],
        "policy_version": "auto_review_policy_v1",
        "measured_metrics": measured_metrics,
        "next_action": "human_hold",
    }


def build_default_sample_review(project_id: str, project_root: Path, episode_code: str, documents: dict[str, Any]) -> dict[str, Any]:
    reports_dir = Path(documents["reports_dir"])
    quality_report = read_json(reports_dir / f"horror_asset_quality_review_{episode_code}.json")
    writeback_report = read_json(reports_dir / f"provider_writeback_{episode_code}.json")
    regeneration_queue = read_json(reports_dir / f"horror_regeneration_queue_{episode_code}.json")
    render_release_report = read_json(reports_dir / f"render_release_{episode_code}_current.json")
    if not render_release_report:
        render_release_report = read_json(reports_dir / f"render_release_{episode_code}.json")
    publish_pack = read_json(reports_dir / f"publish_pack_{episode_code}.json")
    counts = quality_report.get("counts", {}) if isinstance(quality_report.get("counts"), dict) else {}
    raw_issues = quality_report.get("manual_findings", [])
    issues = [build_review_issue(item, index + 1) for index, item in enumerate(raw_issues if isinstance(raw_issues, list) else [])]
    release_output_path = str(render_release_report.get("output_path", ""))
    release_relative_path = resolve_relative_project_path(project_root, release_output_path)
    contact_sheets: list[dict[str, Any]] = []
    for path in sorted(reports_dir.glob(f"horror_contact_sheet_{episode_code}*.jpg")):
        relative_path = resolve_relative_project_path(project_root, str(path))
        if not relative_path:
            continue
        contact_sheets.append(
            {
                "label": path.stem.replace(f"horror_contact_sheet_{episode_code}", episode_code).strip("_") or f"{episode_code} contact sheet",
                "path": str(path),
                "relative_path": relative_path,
                "url": build_asset_url(project_id, relative_path),
                "exists": path.exists(),
            }
        )
    review_required_count = sum(1 for item in issues if item["severity"] != "blocking")
    blocking_count = sum(1 for item in issues if item["severity"] == "blocking")
    recommendations = quality_report.get("recommendations", [])
    if not isinstance(recommendations, list):
        recommendations = []
    queue_recommendations = regeneration_queue.get("recommendations", [])
    if isinstance(queue_recommendations, list):
        for item in queue_recommendations:
            text = str(item).strip()
            if text and text not in recommendations:
                recommendations.append(text)
    return {
        "project_id": project_id,
        "episode_code": episode_code,
        "review_status": "pending",
        "decision_summary": "",
        "review_notes": "",
        "reviewer_user_id": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "review_file_path": str(sample_review_report_path(project_root, episode_code)),
        "release_video": {
            "path": release_output_path,
            "relative_path": release_relative_path,
            "url": build_asset_url(project_id, release_relative_path) if release_relative_path else "",
            "exists": bool(release_relative_path) and (project_root / release_relative_path).exists(),
            "shot_count": int(render_release_report.get("shot_count", 0)),
            "used_placeholder_count": int(render_release_report.get("used_placeholder_count", 0)),
            "render_mode": str(render_release_report.get("render_mode", "")),
        },
        "publish_pack": {
            "title": str(publish_pack.get("title", "")),
            "publish_title": str(publish_pack.get("publish_title", "")),
            "cover_text": str(publish_pack.get("cover_text", "")),
            "description": str(publish_pack.get("description", "")),
            "hashtags": [str(item) for item in publish_pack.get("hashtags", []) if str(item).strip()],
            "comment_seed": str(publish_pack.get("comment_seed", "")),
        },
        "provider_summary": {
            "request_count": int(writeback_report.get("request_count", 0)),
            "job_count": int(writeback_report.get("job_count", 0)),
            "succeeded_count": int(writeback_report.get("succeeded_count", 0)),
            "manual_required_count": int(writeback_report.get("manual_required_count", 0)),
            "changed_count": int(writeback_report.get("changed_count", 0)),
            "queue_count": int(regeneration_queue.get("queue_count", 0)),
            "high_priority_count": int(regeneration_queue.get("high_priority_count", 0)),
        },
        "quality_summary": {
            "image_count": int(counts.get("image_count", 0)),
            "audio_count": int(counts.get("audio_count", 0)),
            "video_count": int(counts.get("video_count", 0)),
            "valid_image_count": int(counts.get("valid_image_count", 0)),
            "valid_audio_count": int(counts.get("valid_audio_count", 0)),
            "valid_video_count": int(counts.get("valid_video_count", 0)),
            "blocking_findings": blocking_count,
            "review_required_findings": review_required_count,
        },
        "contact_sheets": contact_sheets,
        "issues": issues,
        "recommendations": [str(item) for item in recommendations if str(item).strip()],
        "export_gate": {
            "review_status": "",
            "approved_for_export": False,
            "blockers": [],
        },
        "autopilot_state": default_autopilot_state(),
        "candidate_release": default_candidate_release(),
        "autopilot_audit": default_autopilot_audit(),
        "export_audit": default_export_audit(),
    }


def load_creator_sample_review(
    settings: WebSettings,
    project_id: str,
    episode_code: str = "E01",
    user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=user_id)
    documents = resolve_project_documents(settings, project_root)
    review_path = sample_review_report_path(project_root, episode_code)
    review_payload = build_default_sample_review(project_id, project_root, episode_code, documents)
    existing = read_json(review_path)
    if existing:
        review_payload["review_status"] = str(existing.get("review_status", review_payload["review_status"]))
        review_payload["decision_summary"] = str(existing.get("decision_summary", ""))
        review_payload["review_notes"] = str(existing.get("review_notes", ""))
        review_payload["reviewer_user_id"] = str(existing.get("reviewer_user_id", ""))
        review_payload["created_at"] = str(existing.get("created_at", review_payload["created_at"]))
        review_payload["updated_at"] = str(existing.get("updated_at", review_payload["updated_at"]))
        review_payload["autopilot_state"] = normalize_autopilot_state(existing.get("autopilot_state", {}))
        review_payload["candidate_release"] = normalize_candidate_release(existing.get("candidate_release", {}))
        review_payload["autopilot_audit"] = normalize_autopilot_audit(existing.get("autopilot_audit", {}))
        review_payload["export_audit"] = normalize_export_audit(existing.get("export_audit", {}))
        existing_issues = existing.get("issues", [])
        if isinstance(existing_issues, list):
            review_payload["issues"] = [build_review_issue(item, index + 1) for index, item in enumerate(existing_issues) if isinstance(item, dict)]
    review_payload["auto_review_decision"] = build_auto_review_decision(review_payload)
    review_payload["export_gate"] = review_gate_status(review_payload)
    return review_payload


def save_creator_sample_review(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    payload: dict[str, Any],
    actor_user_id: str = "",
) -> dict[str, Any]:
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=actor_user_id)
    documents = resolve_project_documents(settings, project_root)
    current_payload = load_creator_sample_review(settings, project_id, episode_code)
    created_at = str(current_payload.get("created_at", now_iso()))
    issues = payload.get("issues", current_payload.get("issues", []))
    normalized_issues = [build_review_issue(item, index + 1) for index, item in enumerate(issues) if isinstance(item, dict)]
    updated_payload = build_default_sample_review(project_id, project_root, episode_code, documents)
    updated_payload["review_status"] = str(payload.get("review_status", current_payload.get("review_status", "pending"))) or "pending"
    updated_payload["decision_summary"] = str(payload.get("decision_summary", current_payload.get("decision_summary", "")))
    updated_payload["review_notes"] = str(payload.get("review_notes", current_payload.get("review_notes", "")))
    updated_payload["reviewer_user_id"] = actor_user_id or str(current_payload.get("reviewer_user_id", ""))
    updated_payload["created_at"] = created_at
    updated_payload["updated_at"] = now_iso()
    updated_payload["issues"] = normalized_issues
    updated_payload["autopilot_state"] = normalize_autopilot_state(current_payload.get("autopilot_state", {}))
    updated_payload["candidate_release"] = normalize_candidate_release(current_payload.get("candidate_release", {}))
    updated_payload["autopilot_audit"] = normalize_autopilot_audit(current_payload.get("autopilot_audit", {}))
    updated_payload["export_audit"] = normalize_export_audit(current_payload.get("export_audit", {}))
    updated_payload["auto_review_decision"] = build_auto_review_decision(updated_payload)
    updated_payload["export_gate"] = review_gate_status(updated_payload)
    review_path = sample_review_report_path(project_root, episode_code)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(review_path, updated_payload)
    return updated_payload


def record_sample_review_export(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    export_run_id: str,
    exported_at: str,
    release_output_path: str,
    publish_pack_output_path: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    current_payload = load_creator_sample_review(settings, project_id, episode_code, user_id=actor_user_id)
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=actor_user_id)
    documents = resolve_project_documents(settings, project_root)
    updated_payload = build_default_sample_review(project_id, project_root, episode_code, documents)
    updated_payload["review_status"] = str(current_payload.get("review_status", "pending"))
    updated_payload["decision_summary"] = str(current_payload.get("decision_summary", ""))
    updated_payload["review_notes"] = str(current_payload.get("review_notes", ""))
    updated_payload["reviewer_user_id"] = str(current_payload.get("reviewer_user_id", ""))
    updated_payload["created_at"] = str(current_payload.get("created_at", now_iso()))
    updated_payload["updated_at"] = now_iso()
    updated_payload["issues"] = list(current_payload.get("issues", []))
    updated_payload["autopilot_state"] = normalize_autopilot_state(current_payload.get("autopilot_state", {}))
    updated_payload["candidate_release"] = normalize_candidate_release(current_payload.get("candidate_release", {}))
    updated_payload["autopilot_audit"] = normalize_autopilot_audit(current_payload.get("autopilot_audit", {}))
    previous_export_audit = normalize_export_audit(current_payload.get("export_audit", {}))
    previous_export_count = int(previous_export_audit.get("export_count", 0))
    export_count = previous_export_count + 1
    updated_payload["export_audit"] = {
        **previous_export_audit,
        "export_count": export_count,
        "current_publish_version": f"release-v{export_count:03d}",
        "last_exported_at": exported_at,
        "last_export_run_id": export_run_id,
        "last_exported_by_user_id": actor_user_id,
        "last_release_output_path": release_output_path,
        "last_publish_pack_output_path": publish_pack_output_path,
        "last_confirmed_publish_at": exported_at,
        "last_confirmed_by_user_id": actor_user_id,
        "last_candidate_run_id": str(current_payload.get("candidate_release", {}).get("candidate_run_id", "")),
        "last_candidate_created_at": str(current_payload.get("candidate_release", {}).get("candidate_created_at", "")),
    }
    updated_payload["auto_review_decision"] = build_auto_review_decision(updated_payload)
    updated_payload["export_gate"] = review_gate_status(updated_payload)
    review_path = sample_review_report_path(project_root, episode_code)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(review_path, updated_payload)
    return updated_payload


def update_sample_review_autopilot(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    autopilot_state: dict[str, Any] | None = None,
    autopilot_audit: dict[str, Any] | None = None,
    candidate_release: dict[str, Any] | None = None,
    actor_user_id: str = "",
) -> dict[str, Any]:
    current_payload = load_creator_sample_review(settings, project_id, episode_code, user_id=actor_user_id)
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=actor_user_id)
    documents = resolve_project_documents(settings, project_root)
    updated_payload = build_default_sample_review(project_id, project_root, episode_code, documents)
    for key in ("review_status", "decision_summary", "review_notes", "reviewer_user_id", "created_at"):
        updated_payload[key] = current_payload.get(key, updated_payload.get(key, ""))
    updated_payload["updated_at"] = now_iso()
    updated_payload["issues"] = list(current_payload.get("issues", []))
    merged_autopilot_state = normalize_autopilot_state(current_payload.get("autopilot_state", {}))
    if isinstance(autopilot_state, dict):
        merged_autopilot_state.update({key: value for key, value in autopilot_state.items() if value is not None})
    merged_autopilot_audit = normalize_autopilot_audit(current_payload.get("autopilot_audit", {}))
    if isinstance(autopilot_audit, dict):
        merged_autopilot_audit.update({key: value for key, value in autopilot_audit.items() if value is not None})
    merged_candidate_release = normalize_candidate_release(current_payload.get("candidate_release", {}))
    if isinstance(candidate_release, dict):
        candidate_quality_summary = candidate_release.get("quality_summary")
        if isinstance(candidate_quality_summary, dict):
            merged_candidate_release["quality_summary"] = {
                **dict(merged_candidate_release.get("quality_summary", {})),
                **candidate_quality_summary,
            }
        merged_candidate_release.update(
            {
                key: value
                for key, value in candidate_release.items()
                if key != "quality_summary" and value is not None
            }
        )
    updated_payload["autopilot_state"] = normalize_autopilot_state(merged_autopilot_state)
    updated_payload["autopilot_audit"] = normalize_autopilot_audit(merged_autopilot_audit)
    updated_payload["candidate_release"] = normalize_candidate_release(merged_candidate_release)
    updated_payload["export_audit"] = normalize_export_audit(current_payload.get("export_audit", {}))
    updated_payload["auto_review_decision"] = build_auto_review_decision(updated_payload)
    updated_payload["export_gate"] = review_gate_status(updated_payload)
    review_path = sample_review_report_path(project_root, episode_code)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(review_path, updated_payload)
    return updated_payload


def record_candidate_release(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    candidate_run_id: str,
    release_output_path: str,
    publish_pack_output_path: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    current_payload = load_creator_sample_review(settings, project_id, episode_code, user_id=actor_user_id)
    quality_summary = current_payload.get("quality_summary", {})
    provider_summary = current_payload.get("provider_summary", {})
    contact_sheets = current_payload.get("contact_sheets", [])
    last_contact_sheet_path = ""
    if isinstance(contact_sheets, list) and contact_sheets:
        last_contact_sheet_path = str(contact_sheets[-1].get("path", ""))
    updated_payload = update_sample_review_autopilot(
        settings,
        project_id,
        episode_code,
        autopilot_state={
            "autopilot_status": "candidate_ready",
            "autopilot_run_id": candidate_run_id,
            "last_decision": "pass_to_candidate",
            "last_decision_at": now_iso(),
            "last_transition_reason": "候选片已生成。",
        },
        autopilot_audit={
            "final_route": "candidate_ready",
            "last_contact_sheet_path": last_contact_sheet_path,
        },
        candidate_release={
            "candidate_status": "ready",
            "candidate_run_id": candidate_run_id,
            "candidate_created_at": now_iso(),
            "release_output_path": release_output_path,
            "publish_pack_output_path": publish_pack_output_path,
            "quality_score": compute_candidate_quality_score(current_payload),
            "quality_summary": {
                "blocking_findings": int(quality_summary.get("blocking_findings", 0) or 0),
                "review_required_findings": int(quality_summary.get("review_required_findings", 0) or 0),
                "manual_required_count": int(provider_summary.get("manual_required_count", 0) or 0),
                "queue_count": int(provider_summary.get("queue_count", 0) or 0),
            },
        },
        actor_user_id=actor_user_id,
    )
    updated_payload["export_audit"] = {
        **normalize_export_audit(updated_payload.get("export_audit", {})),
        "last_candidate_run_id": candidate_run_id,
        "last_candidate_created_at": str(updated_payload.get("candidate_release", {}).get("candidate_created_at", "")),
    }
    project_root = resolve_project_root_by_id(settings, project_id)
    review_path = sample_review_report_path(project_root, episode_code)
    atomic_write_json(review_path, updated_payload)
    return updated_payload


def require_candidate_ready(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    user_id: str = "",
) -> dict[str, Any]:
    review_payload = load_creator_sample_review(settings, project_id, episode_code, user_id=user_id)
    candidate_release = normalize_candidate_release(review_payload.get("candidate_release", {}))
    if candidate_release.get("candidate_status") != "ready":
        raise ValueError("当前剧集尚未生成候选片，不能确认发布。")
    return review_payload


def confirm_candidate_publish(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    actor_user_id: str = "",
) -> dict[str, Any]:
    current_payload = require_candidate_ready(settings, project_id, episode_code, user_id=actor_user_id)
    project_root = resolve_project_root_by_id(settings, project_id)
    if project_id:
        load_project_runtime_metadata(project_root, project_id, user_id=actor_user_id)
    documents = resolve_project_documents(settings, project_root)
    updated_payload = build_default_sample_review(project_id, project_root, episode_code, documents)
    updated_payload["review_status"] = "approved"
    updated_payload["decision_summary"] = str(current_payload.get("decision_summary", "")) or "候选片通过最终放行。"
    updated_payload["review_notes"] = str(current_payload.get("review_notes", ""))
    updated_payload["reviewer_user_id"] = actor_user_id or str(current_payload.get("reviewer_user_id", ""))
    updated_payload["created_at"] = str(current_payload.get("created_at", now_iso()))
    updated_payload["updated_at"] = now_iso()
    updated_payload["issues"] = list(current_payload.get("issues", []))
    updated_payload["autopilot_state"] = normalize_autopilot_state(current_payload.get("autopilot_state", {}))
    updated_payload["autopilot_state"]["autopilot_status"] = "publish_ready"
    updated_payload["autopilot_state"]["last_transition_reason"] = "候选片已确认发布。"
    updated_payload["autopilot_state"]["last_decision_at"] = now_iso()
    updated_payload["candidate_release"] = normalize_candidate_release(current_payload.get("candidate_release", {}))
    updated_payload["autopilot_audit"] = normalize_autopilot_audit(current_payload.get("autopilot_audit", {}))
    updated_payload["autopilot_audit"]["final_route"] = "publish_ready"
    updated_payload["export_audit"] = normalize_export_audit(current_payload.get("export_audit", {}))
    updated_payload["auto_review_decision"] = build_auto_review_decision(updated_payload)
    updated_payload["export_gate"] = review_gate_status(updated_payload)
    review_path = sample_review_report_path(project_root, episode_code)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(review_path, updated_payload)
    return updated_payload


def review_gate_status(review_payload: dict[str, Any]) -> dict[str, Any]:
    review_status = str(review_payload.get("review_status", "pending"))
    release_video = review_payload.get("release_video", {})
    provider_summary = review_payload.get("provider_summary", {})
    quality_summary = review_payload.get("quality_summary", {})
    blockers: list[str] = []
    if review_status != "approved":
        blockers.append("样片审核尚未通过，必须先把审核状态改为 approved。")
    if not bool(release_video.get("exists")):
        blockers.append("正式版视频不存在，不能进入发布导出。")
    if int(provider_summary.get("manual_required_count", 0)) > 0:
        blockers.append("仍有 manual_required 任务未收口。")
    if int(provider_summary.get("queue_count", 0)) > 0:
        blockers.append("仍有重生成队列未清空。")
    if int(quality_summary.get("blocking_findings", 0)) > 0:
        blockers.append("仍有阻塞级审核问题未关闭。")
    return {
        "review_status": review_status,
        "approved_for_export": not blockers,
        "blockers": blockers,
    }


def require_sample_review_approved(
    settings: WebSettings,
    project_id: str,
    episode_code: str,
    user_id: str = "",
) -> dict[str, Any]:
    review_payload = load_creator_sample_review(settings, project_id, episode_code, user_id=user_id)
    gate = review_gate_status(review_payload)
    if not gate["approved_for_export"]:
        raise ValueError("发布闸门未通过：" + "；".join(str(item) for item in gate["blockers"]))
    return review_payload
