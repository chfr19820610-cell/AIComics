"""Shot version management for AIComics — version tracking, diffing, and rollback.

Each version captures a full snapshot of a shot's data at a point in time.
Versions form a directed acyclic graph (DAG) via parent_version_id, enabling
branch/compare/rollback workflows similar to AIComicBuilder's storyboard
version board.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ShotVersionRecord:
    """A single version snapshot of a shot."""

    version_id: str
    episode_code: str
    shot_id: str
    version_number: int
    parent_version_id: str | None
    label: str
    description: str
    snapshot_json: str  # serialised JSON of the full shot dict
    created_at: str  # ISO-8601


@dataclass(slots=True)
class VersionDiff:
    """Result of comparing two shot versions."""

    version_id_a: str
    version_id_b: str
    fields_changed: dict[str, tuple[Any, Any]]  # field → (old, new)
    fields_added: dict[str, Any]
    fields_removed: list[str]
    has_changes: bool


@dataclass(slots=True)
class VersionTagRecord:
    """A tag attached to a shot version (e.g. 'approved', 'wip')."""

    tag_id: str
    version_id: str
    tag: str


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

SHOT_VERSIONING_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS shot_versions (
    version_id        TEXT PRIMARY KEY,
    episode_code      TEXT NOT NULL,
    shot_id           TEXT NOT NULL,
    version_number    INTEGER NOT NULL,
    parent_version_id TEXT,
    label             TEXT NOT NULL DEFAULT '',
    description       TEXT NOT NULL DEFAULT '',
    snapshot_json     TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shot_versions_episode
    ON shot_versions(episode_code);

CREATE INDEX IF NOT EXISTS idx_shot_versions_shot
    ON shot_versions(episode_code, shot_id);

CREATE TABLE IF NOT EXISTS shot_version_tags (
    tag_id     TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES shot_versions(version_id) ON DELETE CASCADE,
    tag        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_version_tags_version
    ON shot_version_tags(version_id);

CREATE INDEX IF NOT EXISTS idx_version_tags_tag
    ON shot_version_tags(tag);
"""


def initialize_shot_versioning_schema(connection: Any) -> None:
    """Create shot versioning tables if they do not exist."""
    cursor = connection.cursor()
    cursor.executescript(SHOT_VERSIONING_SCHEMA_SQL)
    connection.commit()


# ---------------------------------------------------------------------------
# Version ID helpers
# ---------------------------------------------------------------------------

def _generate_version_id(episode_code: str, shot_id: str, version_number: int) -> str:
    return f"VER_{episode_code}_{shot_id}_v{version_number:04d}"


def _generate_tag_id(version_id: str, tag: str, index: int) -> str:
    return f"TAG_{version_id}_{index:04d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD API
# ---------------------------------------------------------------------------


def create_shot_version(
    connection: Any,
    episode_code: str,
    shot_data: dict[str, Any],
    *,
    label: str = "",
    description: str = "",
    parent_version_id: str | None = None,
) -> ShotVersionRecord:
    """Create a new version snapshot of *shot_data* and persist it.

    The version number is auto-incremented per (episode_code, shot_id).
    """
    cursor = connection.cursor()

    # Determine next version number for this shot
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM shot_versions "
        "WHERE episode_code = ? AND shot_id = ?",
        (episode_code, shot_data.get("shot_id", "")),
    )
    next_ver = int(cursor.fetchone()[0]) + 1
    shot_id = str(shot_data.get("shot_id", ""))

    version_id = _generate_version_id(episode_code, shot_id, next_ver)
    snapshot_json = json.dumps(shot_data, ensure_ascii=False)
    created_at = _now_iso()

    cursor.execute(
        """INSERT INTO shot_versions
           (version_id, episode_code, shot_id, version_number,
            parent_version_id, label, description, snapshot_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version_id,
            episode_code,
            shot_id,
            next_ver,
            parent_version_id,
            label,
            description,
            snapshot_json,
            created_at,
        ),
    )
    connection.commit()

    return ShotVersionRecord(
        version_id=version_id,
        episode_code=episode_code,
        shot_id=shot_id,
        version_number=next_ver,
        parent_version_id=parent_version_id,
        label=label,
        description=description,
        snapshot_json=snapshot_json,
        created_at=created_at,
    )


def get_shot_version(
    connection: Any,
    version_id: str,
) -> ShotVersionRecord | None:
    """Retrieve a single version by its ID, or *None* if not found."""
    cursor = connection.cursor()
    cursor.execute(
        """SELECT version_id, episode_code, shot_id, version_number,
                  parent_version_id, label, description, snapshot_json, created_at
           FROM shot_versions WHERE version_id = ?""",
        (version_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return ShotVersionRecord(*row)


def get_latest_shot_version(
    connection: Any,
    episode_code: str,
    shot_id: str,
) -> ShotVersionRecord | None:
    """Return the latest version for a given shot, or *None*."""
    cursor = connection.cursor()
    cursor.execute(
        """SELECT version_id, episode_code, shot_id, version_number,
                  parent_version_id, label, description, snapshot_json, created_at
           FROM shot_versions
           WHERE episode_code = ? AND shot_id = ?
           ORDER BY version_number DESC LIMIT 1""",
        (episode_code, shot_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return ShotVersionRecord(*row)


def list_shot_versions(
    connection: Any,
    episode_code: str,
    shot_id: str,
) -> list[ShotVersionRecord]:
    """List all versions for a specific shot, oldest first."""
    cursor = connection.cursor()
    cursor.execute(
        """SELECT version_id, episode_code, shot_id, version_number,
                  parent_version_id, label, description, snapshot_json, created_at
           FROM shot_versions
           WHERE episode_code = ? AND shot_id = ?
           ORDER BY version_number ASC""",
        (episode_code, shot_id),
    )
    return [ShotVersionRecord(*row) for row in cursor.fetchall()]


def list_episode_versions(
    connection: Any,
    episode_code: str,
) -> list[ShotVersionRecord]:
    """List all versions across all shots in an episode, newest first."""
    cursor = connection.cursor()
    cursor.execute(
        """SELECT version_id, episode_code, shot_id, version_number,
                  parent_version_id, label, description, snapshot_json, created_at
           FROM shot_versions
           WHERE episode_code = ?
           ORDER BY created_at DESC""",
        (episode_code,),
    )
    return [ShotVersionRecord(*row) for row in cursor.fetchall()]


def delete_shot_version(
    connection: Any,
    version_id: str,
) -> bool:
    """Delete a shot version by ID. Returns *True* if a row was removed."""
    cursor = connection.cursor()
    cursor.execute("DELETE FROM shot_versions WHERE version_id = ?", (version_id,))
    connection.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Recursively flatten nested dicts for field-level diffing."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_dict(value, full_key))
        else:
            result[full_key] = value
    return result


def compare_versions(
    connection: Any,
    version_id_a: str,
    version_id_b: str,
) -> VersionDiff:
    """Compare two shot versions and return structured field-level diffs."""
    va = get_shot_version(connection, version_id_a)
    vb = get_shot_version(connection, version_id_b)

    if va is None:
        raise ValueError(f"Version not found: {version_id_a}")
    if vb is None:
        raise ValueError(f"Version not found: {version_id_b}")

    data_a: dict[str, Any] = json.loads(va.snapshot_json)
    data_b: dict[str, Any] = json.loads(vb.snapshot_json)

    flat_a = _flatten_dict(data_a)
    flat_b = _flatten_dict(data_b)

    keys_a = set(flat_a.keys())
    keys_b = set(flat_b.keys())

    common = keys_a & keys_b
    fields_changed: dict[str, tuple[Any, Any]] = {}
    for key in sorted(common):
        if flat_a[key] != flat_b[key]:
            fields_changed[key] = (flat_a[key], flat_b[key])

    fields_added: dict[str, Any] = {k: flat_b[k] for k in sorted(keys_b - keys_a)}
    fields_removed: list[str] = sorted(keys_a - keys_b)

    return VersionDiff(
        version_id_a=version_id_a,
        version_id_b=version_id_b,
        fields_changed=fields_changed,
        fields_added=fields_added,
        fields_removed=fields_removed,
        has_changes=bool(fields_changed or fields_added or fields_removed),
    )


def compare_versions_compact(
    connection: Any,
    version_id_a: str,
    version_id_b: str,
) -> dict[str, Any]:
    """Convenience wrapper that returns a JSON-serialisable diff dict."""
    diff = compare_versions(connection, version_id_a, version_id_b)
    return {
        "version_id_a": diff.version_id_a,
        "version_id_b": diff.version_id_b,
        "has_changes": diff.has_changes,
        "fields_changed": {
            k: {"old": v[0], "new": v[1]} for k, v in diff.fields_changed.items()
        },
        "fields_added": diff.fields_added,
        "fields_removed": diff.fields_removed,
        "changed_count": len(diff.fields_changed),
        "added_count": len(diff.fields_added),
        "removed_count": len(diff.fields_removed),
    }


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback_to_version(
    connection: Any,
    episode_code: str,
    version_id: str,
    *,
    label: str = "rollback",
    description: str = "",
) -> ShotVersionRecord:
    """Roll back a shot to a previous version.

    Creates a *new* version whose snapshot is a copy of *version_id*'s
    data.  The new version carries *version_id* as its parent so the
    rollback is auditable and reversible.
    """
    source = get_shot_version(connection, version_id)
    if source is None:
        raise ValueError(f"Source version not found: {version_id}")

    shot_data: dict[str, Any] = json.loads(source.snapshot_json)

    # Persist the label from the source if none given
    rollback_label = label or f"rollback_to_{source.version_id}"
    rollback_desc = description or f"Rollback to {version_id} (v{source.version_number})"

    return create_shot_version(
        connection,
        episode_code,
        shot_data,
        label=rollback_label,
        description=rollback_desc,
        parent_version_id=version_id,
    )


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def tag_shot_version(
    connection: Any,
    version_id: str,
    tag: str,
) -> VersionTagRecord:
    """Attach a tag to a version.  Returns the new tag record."""
    cursor = connection.cursor()

    # Determine next tag index for ID generation
    cursor.execute(
        "SELECT COUNT(*) FROM shot_version_tags WHERE version_id = ?",
        (version_id,),
    )
    tag_index = int(cursor.fetchone()[0]) + 1

    tag_id = _generate_tag_id(version_id, tag, tag_index)
    cursor.execute(
        "INSERT INTO shot_version_tags (tag_id, version_id, tag) VALUES (?, ?, ?)",
        (tag_id, version_id, tag),
    )
    connection.commit()
    return VersionTagRecord(tag_id=tag_id, version_id=version_id, tag=tag)


def list_version_tags(
    connection: Any,
    version_id: str,
) -> list[VersionTagRecord]:
    """List all tags attached to a version."""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT tag_id, version_id, tag FROM shot_version_tags WHERE version_id = ? ORDER BY tag_id",
        (version_id,),
    )
    return [VersionTagRecord(*row) for row in cursor.fetchall()]


def remove_version_tag(
    connection: Any,
    tag_id: str,
) -> bool:
    """Remove a tag by its ID.  Returns *True* if a row was removed."""
    cursor = connection.cursor()
    cursor.execute("DELETE FROM shot_version_tags WHERE tag_id = ?", (tag_id,))
    connection.commit()
    return cursor.rowcount > 0


def find_versions_by_tag(
    connection: Any,
    episode_code: str,
    tag: str,
) -> list[ShotVersionRecord]:
    """Find all versions in an episode that have a specific tag."""
    cursor = connection.cursor()
    cursor.execute(
        """SELECT sv.version_id, sv.episode_code, sv.shot_id, sv.version_number,
                  sv.parent_version_id, sv.label, sv.description, sv.snapshot_json, sv.created_at
           FROM shot_versions sv
           INNER JOIN shot_version_tags t ON t.version_id = sv.version_id
           WHERE sv.episode_code = ? AND t.tag = ?
           ORDER BY sv.created_at DESC""",
        (episode_code, tag),
    )
    return [ShotVersionRecord(*row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Kanban-style metadata helpers (for frontend board rendering)
# ---------------------------------------------------------------------------


def build_version_board(
    connection: Any,
    episode_code: str,
) -> dict[str, Any]:
    """Build a kanban-board view of all shot versions in an episode.

    Returns a dict keyed by *shot_id*, with each value containing the
    version timeline plus tags for that shot.  This is the data structure
    a front-end kanban board would consume.
    """
    versions = list_episode_versions(connection, episode_code)

    # Group by shot_id, sorted by version
    shots: dict[str, list[dict[str, Any]]] = {}
    for ver in versions:
        shot_data: dict[str, Any] = json.loads(ver.snapshot_json)
        tags = list_version_tags(connection, ver.version_id)
        entry = {
            "version_id": ver.version_id,
            "version_number": ver.version_number,
            "parent_version_id": ver.parent_version_id,
            "label": ver.label,
            "description": ver.description,
            "created_at": ver.created_at,
            "snapshot": shot_data,
            "tags": [t.tag for t in tags],
        }
        shots.setdefault(ver.shot_id, []).append(entry)

    return {
        "episode_code": episode_code,
        "shots": shots,
        "shot_count": len(shots),
        "total_versions": len(versions),
    }
