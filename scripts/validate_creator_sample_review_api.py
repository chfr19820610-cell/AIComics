from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from web.backend.app import app
from web.backend.auth.auth_service import connect_auth_database, ensure_auth_schema, load_user_by_id
from web.backend.auth.jwt_service import build_jwt_token
from web.backend.services.creator_action_service import (
    build_jobs_action,
    build_provider_requests_action,
    refresh_creator_reports_action,
    render_release_action,
    resolve_providers_config,
)
from web.backend.services.creator_service import (
    create_creator_project,
    resolve_project_documents,
    upsert_creator_episode,
    upsert_creator_shot,
)
from web.backend.services.edition_policy import load_edition_policy
from web.backend.settings import load_web_settings


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


MINIMAL_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAQEA8QDw8PDw8QEA8PDw8QFREWFhURFRUY"
    "HSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGi0fHyUtLS0tLS0tLS0tLS0t"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAX"
    "AAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAA"
    "n//EABQQAQAAAAAAAAAAAAAAAAAAACD/2gAIAQEAAT8Af//EABQRAQAAAAAAAAAAAAAAAAAAACD/"
    "2gAIAQIBAT8Af//EABQRAQAAAAAAAAAAAAAAAAAAACD/2gAIAQMBAT8Af//Z"
)


def discover_project_id() -> str:
    marker_path = PROJECT_ROOT / "state" / "horror_real_sample_project_id.txt"
    if marker_path.exists():
        return marker_path.read_text(encoding="utf-8").strip()
    for manifest_path in sorted((PROJECT_ROOT / "state" / "generated_projects").glob("*/manifests/project_manifest.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        project_id = str(payload.get("project_id", "")).strip()
        if project_id:
            return project_id
    raise RuntimeError("未找到样片项目 ID。")


def build_project_owner_headers(project_id: str) -> dict[str, str]:
    settings = load_web_settings()
    if not load_edition_policy(settings).auth_enabled:
        return {}
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    try:
        row = connection.execute(
            "SELECT user_id FROM creator_project_owners WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            user = load_user_by_id(connection, "user_creator")
            if not user:
                raise RuntimeError(f"项目 `{project_id}` 没有 owner 记录。")
        else:
            user = load_user_by_id(connection, str(row[0]))
        if not user:
            raise RuntimeError(f"项目 `{project_id}` 的 owner 用户不存在。")
    finally:
        connection.close()
    token = build_jwt_token(settings, user["user_id"], user["display_name"], user["default_role"])
    return {"Authorization": f"Bearer {token}"}


def default_creator_user_id() -> str:
    settings = load_web_settings()
    if not load_edition_policy(settings).auth_enabled:
        return ""
    connection = connect_auth_database()
    ensure_auth_schema(connection)
    try:
        user = load_user_by_id(connection, "user_creator")
        return str(user["user_id"]) if user else ""
    finally:
        connection.close()


def bootstrap_validation_project(settings) -> str:
    project_id = f"creator_sample_review_api_{datetime.now().strftime('%H%M%S')}"
    actor_user_id = default_creator_user_id()
    created = create_creator_project(
        settings,
        {
            "project_name": "Sample Review API 验证项目",
            "project_id": project_id,
            "genre": "民俗恐怖",
            "style_profile": "动漫漫剧",
            "protagonist_name": "阿禾",
            "episode_target_count": 1,
        },
        actor_user_id=actor_user_id,
    )
    revision_summary = dict(created.get("revision_summary", {}))
    episode_result = upsert_creator_episode(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "title": "井边夜声",
            "status": "shotlist_ready",
            "publish_title": "井边有人叫你名字，别回头",
            "cover_text": "井口回声",
            "creator_goal": "验证 sample review API 回读",
            "ending_hook": "她听见井底叫了她乳名。",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
        actor_user_id=actor_user_id,
    )
    revision_summary = dict(episode_result.get("revision_summary", revision_summary))
    first_shot = upsert_creator_shot(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "shot_id": "S01",
            "duration": 4,
            "scene": "井边",
            "characters": ["阿禾"],
            "visual": "井边背影，符纸轻轻晃动。",
            "action": "风吹符纸。",
            "dialogue": "别回头。",
            "emotion": "压低、禁忌",
            "camera": "背影中景",
            "ai_video": False,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
        actor_user_id=actor_user_id,
    )
    revision_summary = dict(first_shot.get("revision_summary", revision_summary))
    upsert_creator_shot(
        settings,
        project_id,
        {
            "episode_code": "E01",
            "shot_id": "S02",
            "duration": 4,
            "scene": "井口特写",
            "characters": ["阿禾"],
            "visual": "井沿与黑水，局部阴影像一张脸。",
            "action": "水面轻轻起皱。",
            "dialogue": "阿禾……",
            "emotion": "惊悚、压迫",
            "camera": "局部特写",
            "ai_video": False,
            "priority": "high",
            "expected_episode_manifest_revision_id": revision_summary.get("episode_manifest_revision_id", ""),
        },
        actor_user_id=actor_user_id,
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
    refresh_creator_reports_action(settings, project_root, documents, ensure_jobs_if_missing=False)
    for source_path in sorted((PROJECT_ROOT / "reports").glob("horror_contact_sheet_E01*.jpg"))[:1]:
        target_path = Path(documents["reports_dir"]) / source_path.name
        target_path.write_bytes(source_path.read_bytes())
    if not list(Path(documents["reports_dir"]).glob("horror_contact_sheet_E01*.jpg")):
        target_path = Path(documents["reports_dir"]) / "horror_contact_sheet_E01_validation.jpg"
        target_path.write_bytes(base64.b64decode(MINIMAL_JPEG_BASE64))
    return project_id


def main() -> int:
    project_id = discover_project_id()
    episode_code = "E01"
    run_id = f"creator_sample_review_api_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    review_path = PROJECT_ROOT / "state" / "generated_projects" / project_id / "reports" / f"sample_review_{episode_code}.json"
    original_bytes = review_path.read_bytes() if review_path.exists() else b""
    original_exists = review_path.exists()

    try:
        client = TestClient(app)
        auth_headers = build_project_owner_headers(project_id)

        response = client.get(
            f"/api/creator/sample-review?project_id={project_id}&episode_code={episode_code}",
            headers=auth_headers,
        )
        if response.status_code == 404:
            project_id = bootstrap_validation_project(load_web_settings())
            auth_headers = build_project_owner_headers(project_id)
            response = client.get(
                f"/api/creator/sample-review?project_id={project_id}&episode_code={episode_code}",
                headers=auth_headers,
            )
        if response.status_code != 200:
            raise RuntimeError(f"sample review load failed: {response.status_code} {response.text}")
        payload = response.json()
        if not payload.get("release_video", {}).get("exists"):
            raise RuntimeError("release video should exist for the real sample review")
        if int(payload.get("provider_summary", {}).get("succeeded_count", 0)) < 0:
            raise RuntimeError("provider succeeded_count mismatch")
        if not payload.get("contact_sheets"):
            raise RuntimeError("contact sheets should not be empty")

        save_response = client.put(
            "/api/creator/sample-review",
            headers=auth_headers,
            json={
                "project_id": project_id,
                "episode_code": episode_code,
                "review_status": "changes_requested",
                "decision_summary": "保留结尾氛围，先收掉剩余文本痕迹。",
                "review_notes": "验证脚本写入：确认审核记录可保存并回读。",
                "issues": payload.get("issues", []),
            },
        )
        if save_response.status_code != 200:
            raise RuntimeError(f"sample review save failed: {save_response.status_code} {save_response.text}")
        saved_payload = save_response.json()
        if saved_payload.get("review_status") != "changes_requested":
            raise RuntimeError("review_status save mismatch")

        asset_response = client.get(
            f"/api/creator/assets?project_id={project_id}&path={payload['contact_sheets'][0]['relative_path']}",
            headers=auth_headers,
        )
        if asset_response.status_code != 200:
            raise RuntimeError(f"asset endpoint failed: {asset_response.status_code} {asset_response.text}")

        report_payload = {
            "run_id": run_id,
            "project_id": project_id,
            "episode_code": episode_code,
            "review_status": saved_payload.get("review_status", ""),
            "contact_sheet_count": len(payload.get("contact_sheets", [])),
            "provider_succeeded_count": int(payload.get("provider_summary", {}).get("succeeded_count", 0)),
            "asset_content_type": asset_response.headers.get("content-type", ""),
        }
        report_path = PROJECT_ROOT / "reports" / "creator_sample_review_api_validation_report.json"
        write_json(report_path, report_payload)
        print(json.dumps({**report_payload, "report_path": str(report_path)}, ensure_ascii=False, indent=2))
        return 0
    finally:
        if original_exists:
            review_path.write_bytes(original_bytes)
        elif review_path.exists():
            review_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
