"""Tests for the shot versioning module — CRUD, diff, rollback, tags, board."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from aicomic.core.shot_versioning import (
    ShotVersionRecord,
    VersionDiff,
    VersionTagRecord,
    initialize_shot_versioning_schema,
    create_shot_version,
    get_shot_version,
    get_latest_shot_version,
    list_shot_versions,
    list_episode_versions,
    delete_shot_version,
    compare_versions,
    compare_versions_compact,
    rollback_to_version,
    tag_shot_version,
    list_version_tags,
    remove_version_tag,
    find_versions_by_tag,
    build_version_board,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    """Create an in-memory SQLite database with the shot versioning schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_shot_versioning_schema(conn)
    return conn


SAMPLE_SHOT = {
    "shot_id": "S001",
    "duration": 6,
    "scene": "老宅堂屋",
    "characters": ["返乡青年", "守夜老人"],
    "visual": "老宅堂屋，开场禁忌第 1 个镜头，主角背影停在画面前景，民俗恐怖氛围，taboo 节拍。",
    "action": "守夜老人压低声音指向符纸，主角停下脚步。",
    "dialogue": "村里老人说，夜里不能回头看井口。",
    "emotion": "压低、禁忌、悬念",
    "camera": "背影中景，缓慢推进",
    "ai_video": False,
    "priority": "high",
    "act_id": "A1",
    "horror_beat": "taboo",
    "continuity_anchor": "符纸",
    "avoidance_strategy": "back_view",
    "sound_cue": "低频风声",
    "regeneration_reason": "",
}

SAMPLE_SHOT_V2 = {**SAMPLE_SHOT, "duration": 8, "visual": "updated visual description", "emotion": "加强恐怖感"}

SAMPLE_SHOT_V3 = {**SAMPLE_SHOT_V2, "dialogue": "新的对话内容", "action": "新的动作描述", "scene": "村口枯井"}


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


class TestInitializeSchema:
    def test_tables_created(self, db: sqlite3.Connection) -> None:
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        assert "shot_versions" in tables
        assert "shot_version_tags" in tables

    def test_idempotent(self, db: sqlite3.Connection) -> None:
        initialize_shot_versioning_schema(db)  # second call should not raise
        initialize_shot_versioning_schema(db)


# ---------------------------------------------------------------------------
# Create & read versions
# ---------------------------------------------------------------------------


class TestCreateShotVersion:
    def test_create_basic(self, db: sqlite3.Connection) -> None:
        record = create_shot_version(db, "E01", SAMPLE_SHOT)
        assert record.version_id == "VER_E01_S001_v0001"
        assert record.episode_code == "E01"
        assert record.shot_id == "S001"
        assert record.version_number == 1
        assert record.parent_version_id is None
        assert record.label == ""
        assert record.description == ""

    def test_snapshot_stored_correctly(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT, label="first_version")
        cursor = db.cursor()
        cursor.execute("SELECT snapshot_json FROM shot_versions WHERE version_id = ?", ("VER_E01_S001_v0001",))
        raw = cursor.fetchone()[0]
        parsed = json.loads(raw)
        assert parsed["shot_id"] == "S001"
        assert parsed["dialogue"] == "村里老人说，夜里不能回头看井口。"

    def test_auto_increment(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        v3 = create_shot_version(db, "E01", SAMPLE_SHOT_V3)
        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v3.version_number == 3
        assert v1.version_id == "VER_E01_S001_v0001"
        assert v2.version_id == "VER_E01_S001_v0002"
        assert v3.version_id == "VER_E01_S001_v0003"

    def test_parent_version_link(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2, parent_version_id=v1.version_id)
        assert v2.parent_version_id == v1.version_id

    def test_label_and_description(self, db: sqlite3.Connection) -> None:
        record = create_shot_version(
            db, "E01", SAMPLE_SHOT, label="wip", description="审核通过后第一次修改"
        )
        assert record.label == "wip"
        assert record.description == "审核通过后第一次修改"

    def test_multiple_shots_same_episode(self, db: sqlite3.Connection) -> None:
        shot_a = dict(SAMPLE_SHOT, shot_id="S001")
        shot_b = dict(SAMPLE_SHOT, shot_id="S002", scene="村口枯井")
        va = create_shot_version(db, "E01", shot_a)
        vb = create_shot_version(db, "E01", shot_b)
        assert va.shot_id == "S001"
        assert vb.shot_id == "S002"
        assert va.version_number == 1
        assert vb.version_number == 1  # separate counter per shot


class TestGetShotVersion:
    def test_get_existing(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        record = get_shot_version(db, "VER_E01_S001_v0001")
        assert record is not None
        assert record.episode_code == "E01"

    def test_get_missing(self, db: sqlite3.Connection) -> None:
        record = get_shot_version(db, "VER_NONEXIST")
        assert record is None

    def test_get_latest(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        create_shot_version(db, "E01", SAMPLE_SHOT_V3)
        latest = get_latest_shot_version(db, "E01", "S001")
        assert latest is not None
        assert latest.version_number == 3

    def test_get_latest_no_versions(self, db: sqlite3.Connection) -> None:
        latest = get_latest_shot_version(db, "E01", "S001")
        assert latest is None


class TestListVersions:
    def test_list_shot_versions_ordered(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        create_shot_version(db, "E01", SAMPLE_SHOT_V3)
        versions = list_shot_versions(db, "E01", "S001")
        assert len(versions) == 3
        assert [v.version_number for v in versions] == [1, 2, 3]

    def test_list_shot_versions_empty(self, db: sqlite3.Connection) -> None:
        versions = list_shot_versions(db, "E01", "S999")
        assert versions == []

    def test_list_episode_versions(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        create_shot_version(db, "E02", SAMPLE_SHOT)  # different episode
        versions = list_episode_versions(db, "E01")
        assert len(versions) == 2


class TestDeleteVersion:
    def test_delete_existing(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        assert get_shot_version(db, "VER_E01_S001_v0001") is not None
        deleted = delete_shot_version(db, "VER_E01_S001_v0001")
        assert deleted is True
        assert get_shot_version(db, "VER_E01_S001_v0001") is None

    def test_delete_missing(self, db: sqlite3.Connection) -> None:
        deleted = delete_shot_version(db, "VER_NONEXIST")
        assert deleted is False


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


class TestCompareVersions:
    def test_identical_versions_no_changes(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT)
        diff = compare_versions(db, v1.version_id, v2.version_id)
        assert diff.has_changes is False
        assert diff.fields_changed == {}
        assert diff.fields_added == {}
        assert diff.fields_removed == []

    def test_detect_field_changes(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        diff = compare_versions(db, v1.version_id, v2.version_id)
        assert diff.has_changes is True
        assert "duration" in diff.fields_changed
        assert diff.fields_changed["duration"] == (6, 8)

    def test_detect_fields_added(self, db: sqlite3.Connection) -> None:
        # v2 has an extra field
        shot_with_extra = {**SAMPLE_SHOT, "new_field": "extra_value"}
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", shot_with_extra)
        diff = compare_versions(db, v1.version_id, v2.version_id)
        assert "new_field" in diff.fields_added

    def test_detect_fields_removed(self, db: sqlite3.Connection) -> None:
        shot_removed = {k: v for k, v in SAMPLE_SHOT.items() if k != "sound_cue"}
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", shot_removed)
        diff = compare_versions(db, v1.version_id, v2.version_id)
        assert "sound_cue" in diff.fields_removed

    def test_raises_on_missing_version(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        with pytest.raises(ValueError, match="not found"):
            compare_versions(db, "VER_E01_S001_v0001", "VER_NONEXIST")

    def test_compact_wrapper(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        compact = compare_versions_compact(db, v1.version_id, v2.version_id)
        assert isinstance(compact, dict)
        assert compact["has_changes"] is True
        assert compact["changed_count"] >= 1
        assert "fields_changed" in compact
        assert "fields_added" in compact
        assert "fields_removed" in compact


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_creates_new_version(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        rolled_back = rollback_to_version(db, "E01", v2.version_id)
        assert rolled_back.version_number == 3
        assert rolled_back.parent_version_id == v2.version_id

    def test_rollback_restores_original_data(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        rolled_back = rollback_to_version(db, "E01", v1.version_id)
        restored = json.loads(rolled_back.snapshot_json)
        assert restored["duration"] == SAMPLE_SHOT["duration"]
        assert restored["dialogue"] == SAMPLE_SHOT["dialogue"]

    def test_rollback_updates_latest_version(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        rollback_to_version(db, "E01", v2.version_id)
        latest = get_latest_shot_version(db, "E01", "S001")
        assert latest is not None
        assert latest.version_number == 3

    def test_rollback_label_and_description(self, db: sqlite3.Connection) -> None:
        create_shot_version(db, "E01", SAMPLE_SHOT)
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2)
        rolled = rollback_to_version(
            db, "E01", v2.version_id,
            label="revert",
            description="审核后回退到第二版",
        )
        assert rolled.label == "revert"
        assert rolled.description == "审核后回退到第二版"

    def test_rollback_invalid_source(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="not found"):
            rollback_to_version(db, "E01", "VER_NONEXIST")


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestTags:
    def test_tag_shot_version(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        tag_record = tag_shot_version(db, v1.version_id, "approved")
        assert tag_record.tag == "approved"
        assert tag_record.version_id == v1.version_id

    def test_list_version_tags(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        tag_shot_version(db, v1.version_id, "approved")
        tag_shot_version(db, v1.version_id, "final")
        tags = list_version_tags(db, v1.version_id)
        assert len(tags) == 2
        assert {t.tag for t in tags} == {"approved", "final"}

    def test_list_version_tags_empty(self, db: sqlite3.Connection) -> None:
        tags = list_version_tags(db, "VER_NONEXIST")
        assert tags == []

    def test_remove_tag(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        t1 = tag_shot_version(db, v1.version_id, "wip")
        t2 = tag_shot_version(db, v1.version_id, "approved")
        removed = remove_version_tag(db, t1.tag_id)
        assert removed is True
        tags = list_version_tags(db, v1.version_id)
        assert len(tags) == 1
        assert tags[0].tag == "approved"

    def test_remove_missing_tag(self, db: sqlite3.Connection) -> None:
        removed = remove_version_tag(db, "TAG_NONEXIST")
        assert removed is False

    def test_find_versions_by_tag(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT, label="initial")
        v2 = create_shot_version(db, "E01", SAMPLE_SHOT_V2, label="v2")
        v3 = create_shot_version(db, "E02", SAMPLE_SHOT, label="other_ep")
        tag_shot_version(db, v1.version_id, "approved")
        tag_shot_version(db, v2.version_id, "approved")
        tag_shot_version(db, v3.version_id, "wip")

        found = find_versions_by_tag(db, "E01", "approved")
        assert len(found) == 2
        assert {r.version_id for r in found} == {v1.version_id, v2.version_id}

    def test_tag_cascade_on_version_delete(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        tag_shot_version(db, v1.version_id, "wip")
        delete_shot_version(db, v1.version_id)
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM shot_version_tags WHERE version_id = ?", (v1.version_id,))
        assert cursor.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Version board (kanban)
# ---------------------------------------------------------------------------


class TestVersionBoard:
    def test_build_board(self, db: sqlite3.Connection) -> None:
        # Create multiple shot versions across different shots
        create_shot_version(db, "E01", SAMPLE_SHOT, label="v1")
        create_shot_version(db, "E01", SAMPLE_SHOT_V2, label="v2")
        shot2 = dict(SAMPLE_SHOT, shot_id="S002", scene="村口枯井")
        create_shot_version(db, "E01", shot2, label="first_S002")

        board = build_version_board(db, "E01")
        assert board["episode_code"] == "E01"
        assert board["shot_count"] == 2
        assert board["total_versions"] == 3
        assert "S001" in board["shots"]
        assert "S002" in board["shots"]
        assert len(board["shots"]["S001"]) == 2
        assert len(board["shots"]["S002"]) == 1

    def test_board_includes_tags(self, db: sqlite3.Connection) -> None:
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT)
        tag_shot_version(db, v1.version_id, "final")
        board = build_version_board(db, "E01")
        tags = board["shots"]["S001"][0]["tags"]
        assert "final" in tags

    def test_board_empty_episode(self, db: sqlite3.Connection) -> None:
        board = build_version_board(db, "E99")
        assert board["shot_count"] == 0
        assert board["total_versions"] == 0
        assert board["shots"] == {}


# ---------------------------------------------------------------------------
# Integration scenarios
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_workflow(self, db: sqlite3.Connection) -> None:
        """Simulate a realistic version management session."""
        # 1. Creator builds initial shot
        v1 = create_shot_version(db, "E01", SAMPLE_SHOT, label="initial")
        assert v1.version_number == 1

        # 2. Review — tag as wip
        tag_shot_version(db, v1.version_id, "wip")

        # 3. Edit duration and visual
        v2 = create_shot_version(
            db, "E01", SAMPLE_SHOT_V2,
            label="edit_v1",
            parent_version_id=v1.version_id,
        )
        assert v2.version_number == 2

        # 4. Compare v1 and v2 — should see duration change
        diff = compare_versions(db, v1.version_id, v2.version_id)
        assert diff.has_changes is True
        assert diff.fields_changed["duration"] == (6, 8)

        # 5. Third edit — more changes
        v3 = create_shot_version(
            db, "E01", SAMPLE_SHOT_V3,
            label="edit_v2",
            parent_version_id=v2.version_id,
        )
        assert v3.version_number == 3

        # 6. Diff v1 vs v3 — should show multiple changes
        diff13 = compare_versions(db, v1.version_id, v3.version_id)
        assert diff13.has_changes is True
        assert "duration" in diff13.fields_changed
        assert "scene" in diff13.fields_changed
        assert "dialogue" in diff13.fields_changed

        # 7. Rollback to v2
        rolled = rollback_to_version(db, "E01", v2.version_id, label="revert", description="回退到编辑版1")
        assert rolled.version_number == 4
        restored_data = json.loads(rolled.snapshot_json)
        assert restored_data["duration"] == 8  # v2's value
        assert restored_data["visual"] == SAMPLE_SHOT_V2["visual"]

        # 8. List all versions
        all_versions = list_shot_versions(db, "E01", "S001")
        assert len(all_versions) == 4

        # 9. Board view
        board = build_version_board(db, "E01")
        assert board["total_versions"] == 4
        assert len(board["shots"]["S001"]) == 4

        # 10. Latest is the rollback
        latest = get_latest_shot_version(db, "E01", "S001")
        assert latest is not None
        assert latest.version_number == 4
        assert latest.label == "revert"

    def test_multi_episode_isolation(self, db: sqlite3.Connection) -> None:
        """Versions in one episode should not leak into another."""
        create_shot_version(db, "E01", SAMPLE_SHOT)
        create_shot_version(db, "E02", dict(SAMPLE_SHOT, shot_id="S001"))
        assert len(list_shot_versions(db, "E01", "S001")) == 1
        assert len(list_episode_versions(db, "E01")) == 1
        assert len(list_episode_versions(db, "E02")) == 1
