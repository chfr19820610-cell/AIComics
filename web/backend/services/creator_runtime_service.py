from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CreatorRuntimeError(Exception):
    pass


class ProjectNotFoundError(CreatorRuntimeError):
    pass


class ProjectAccessDeniedError(CreatorRuntimeError):
    pass


class RevisionConflictError(CreatorRuntimeError):
    pass


AUTHORING_DOCUMENT_NAMES = (
    "project_manifest",
    "season_manifest",
    "episode_manifest",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def revision_identifier(content_sha: str) -> str:
    return f"rev_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{content_sha[:12]}"


def document_key(project_id: str, document_name: str) -> str:
    return f"{project_id}:{document_name}"


def resolve_authoring_document_paths(project_root: Path) -> dict[str, Path]:
    manifests_dir = project_root / "manifests"
    return {
        "project_manifest": manifests_dir / "project_manifest.json",
        "season_manifest": manifests_dir / "season_manifest.json",
        "episode_manifest": manifests_dir / "episode_manifest.json",
    }


def compute_content_sha(raw_content: str) -> str:
    return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()


def read_document_text(path: Path) -> str:
    if not path.exists():
        return "{}"
    return path.read_text(encoding="utf-8")


def ensure_creator_runtime_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_project_owners (
            project_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            project_root TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS authoring_revisions (
            revision_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            document_name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            content_sha TEXT NOT NULL,
            parent_revision_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS authoring_revision_heads (
            document_key TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            document_name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            revision_id TEXT NOT NULL,
            content_sha TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_project_owners_user_id ON creator_project_owners(user_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_authoring_revisions_project_doc_created_at ON authoring_revisions(project_id, document_name, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_authoring_revision_heads_project_doc ON authoring_revision_heads(project_id, document_name)"
    )
    connection.commit()


def ensure_project_owner(
    connection: sqlite3.Connection,
    project_id: str,
    project_root: Path,
    user_id: str,
) -> dict[str, str]:
    if not user_id:
        return {
            "project_id": project_id,
            "user_id": "",
            "project_root": str(project_root),
        }
    row = connection.execute(
        """
        SELECT project_id, user_id, project_root, created_at, updated_at
        FROM creator_project_owners
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    timestamp = now_iso()
    if row is None:
        connection.execute(
            """
            INSERT INTO creator_project_owners (
                project_id,
                user_id,
                project_root,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, user_id, str(project_root), timestamp, timestamp),
        )
        connection.commit()
        return {
            "project_id": project_id,
            "user_id": user_id,
            "project_root": str(project_root),
        }
    owner_user_id = str(row[1])
    if owner_user_id != user_id:
        raise ProjectAccessDeniedError(
            f"项目 `{project_id}` 属于其他用户，当前用户 `{user_id}` 无权修改。"
        )
    if str(row[2]) != str(project_root):
        connection.execute(
            """
            UPDATE creator_project_owners
            SET project_root = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (str(project_root), timestamp, project_id),
        )
        connection.commit()
    return {
        "project_id": project_id,
        "user_id": owner_user_id,
        "project_root": str(project_root),
    }


def lookup_project_owner(connection: sqlite3.Connection, project_id: str) -> dict[str, str] | None:
    row = connection.execute(
        """
        SELECT project_id, user_id, project_root
        FROM creator_project_owners
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "project_id": str(row[0]),
        "user_id": str(row[1]),
        "project_root": str(row[2]),
    }


def ensure_document_revision_head(
    connection: sqlite3.Connection,
    project_id: str,
    document_name: str,
    source_path: Path,
    created_by: str = "system_sync",
) -> dict[str, str]:
    raw_content = read_document_text(source_path)
    content_sha = compute_content_sha(raw_content)
    key = document_key(project_id, document_name)
    row = connection.execute(
        """
        SELECT document_key, project_id, document_name, source_path, revision_id, content_sha, updated_at
        FROM authoring_revision_heads
        WHERE document_key = ?
        """,
        (key,),
    ).fetchone()
    if row is not None and str(row[5]) == content_sha:
        return {
            "document_key": str(row[0]),
            "project_id": str(row[1]),
            "document_name": str(row[2]),
            "source_path": str(row[3]),
            "revision_id": str(row[4]),
            "content_sha": str(row[5]),
            "updated_at": str(row[6]),
        }

    parent_revision_id = str(row[4]) if row is not None else ""
    created_at = now_iso()
    revision_id = revision_identifier(content_sha)
    connection.execute(
        """
        INSERT INTO authoring_revisions (
            revision_id,
            project_id,
            document_name,
            source_path,
            content_sha,
            parent_revision_id,
            created_at,
            created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision_id,
            project_id,
            document_name,
            str(source_path),
            content_sha,
            parent_revision_id,
            created_at,
            created_by,
        ),
    )
    connection.execute(
        """
        INSERT INTO authoring_revision_heads (
            document_key,
            project_id,
            document_name,
            source_path,
            revision_id,
            content_sha,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_key) DO UPDATE SET
            source_path = excluded.source_path,
            revision_id = excluded.revision_id,
            content_sha = excluded.content_sha,
            updated_at = excluded.updated_at
        """,
        (key, project_id, document_name, str(source_path), revision_id, content_sha, created_at),
    )
    connection.commit()
    return {
        "document_key": key,
        "project_id": project_id,
        "document_name": document_name,
        "source_path": str(source_path),
        "revision_id": revision_id,
        "content_sha": content_sha,
        "updated_at": created_at,
    }


def load_authoring_revision_summary(
    connection: sqlite3.Connection,
    project_root: Path,
    project_id: str,
) -> dict[str, str]:
    summary: dict[str, str] = {}
    for document_name, source_path in resolve_authoring_document_paths(project_root).items():
        head = ensure_document_revision_head(connection, project_id, document_name, source_path)
        summary[f"{document_name}_revision_id"] = head["revision_id"]
    return summary


def assert_expected_revision(
    connection: sqlite3.Connection,
    project_id: str,
    document_name: str,
    source_path: Path,
    expected_revision_id: str,
) -> dict[str, str]:
    current_head = ensure_document_revision_head(connection, project_id, document_name, source_path)
    normalized_expected_revision_id = expected_revision_id.strip()
    if not normalized_expected_revision_id:
        raise RevisionConflictError(
            f"缺少 `{document_name}` 的期望修订版本，请刷新工作台后重试。"
        )
    if normalized_expected_revision_id != current_head["revision_id"]:
        raise RevisionConflictError(
            f"`{document_name}` 修订版本已过期。expected={normalized_expected_revision_id}, current={current_head['revision_id']}"
        )
    return current_head


def write_json_document_with_revision(
    connection: sqlite3.Connection,
    project_id: str,
    document_name: str,
    source_path: Path,
    payload: dict[str, Any],
    expected_revision_id: str,
    actor_user_id: str,
) -> dict[str, str]:
    current_head = assert_expected_revision(
        connection,
        project_id,
        document_name,
        source_path,
        expected_revision_id,
    )
    serialized_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    content_sha = compute_content_sha(serialized_payload)
    if content_sha == current_head["content_sha"]:
        return current_head
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(serialized_payload, encoding="utf-8")
    created_at = now_iso()
    revision_id = revision_identifier(content_sha)
    connection.execute(
        """
        INSERT INTO authoring_revisions (
            revision_id,
            project_id,
            document_name,
            source_path,
            content_sha,
            parent_revision_id,
            created_at,
            created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision_id,
            project_id,
            document_name,
            str(source_path),
            content_sha,
            current_head["revision_id"],
            created_at,
            actor_user_id or "system_anonymous",
        ),
    )
    connection.execute(
        """
        UPDATE authoring_revision_heads
        SET revision_id = ?, content_sha = ?, updated_at = ?
        WHERE document_key = ?
        """,
        (
            revision_id,
            content_sha,
            created_at,
            document_key(project_id, document_name),
        ),
    )
    connection.commit()
    return {
        "document_key": document_key(project_id, document_name),
        "project_id": project_id,
        "document_name": document_name,
        "source_path": str(source_path),
        "revision_id": revision_id,
        "content_sha": content_sha,
        "updated_at": created_at,
    }


def synchronize_project_runtime(
    connection: sqlite3.Connection,
    project_root: Path,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    ensure_project_owner(connection, project_id, project_root, user_id)
    return {
        "owner": lookup_project_owner(connection, project_id) or {},
        "revision_summary": load_authoring_revision_summary(connection, project_root, project_id),
    }
