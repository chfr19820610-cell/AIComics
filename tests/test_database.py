from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aicomic.core.database import (
    collect_job_status_by_episode,
    collect_statistics,
    connect_database,
    initialize_schema,
    insert_batch,
    insert_batch_runs,
    insert_episode_states,
    insert_episodes,
    insert_jobs,
    insert_project,
    insert_provider_requests,
    insert_season,
)
from aicomic.core.models import (
    BatchRecord,
    BatchRunRecord,
    EpisodeRecord,
    EpisodeStateRecord,
    JobRecord,
    ProjectRecord,
    ProviderRequestRecord,
    SeasonRecord,
)


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    path = tmp_path / "test.db"
    conn = connect_database(path)
    initialize_schema(conn)
    return conn


class TestConnectDatabase:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        path = tmp_path / "new.db"
        conn = connect_database(path)
        assert path.exists()
        conn.close()

    def test_returns_connection(self) -> None:
        conn = connect_database(Path("/tmp/aicomic_test_conn.db"))
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


class TestInitializeSchema:
    def test_creates_all_tables(self, db: sqlite3.Connection) -> None:
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        assert "projects" in tables
        assert "seasons" in tables
        assert "episodes" in tables
        assert "jobs" in tables
        assert "episode_states" in tables
        assert "provider_requests" in tables
        assert "batches" in tables
        assert "batch_runs" in tables

    def test_idempotent(self, db: sqlite3.Connection) -> None:
        initialize_schema(db)  # second run should not fail


class TestInsertProject:
    def test_insert_and_query(self, db: sqlite3.Connection) -> None:
        record = ProjectRecord(project_id="P001", project_name="Test", genre="horror", status="active")
        insert_project(db, record)
        row = db.execute("SELECT * FROM projects WHERE project_id = ?", ("P001",)).fetchone()
        assert row[0] == "P001"
        assert row[1] == "Test"

    def test_replace_existing(self, db: sqlite3.Connection) -> None:
        r1 = ProjectRecord(project_id="P001", project_name="Old", genre="drama", status="inactive")
        r2 = ProjectRecord(project_id="P001", project_name="New", genre="horror", status="active")
        insert_project(db, r1)
        insert_project(db, r2)
        row = db.execute("SELECT * FROM projects WHERE project_id = ?", ("P001",)).fetchone()
        assert row[1] == "New"


class TestInsertSeason:
    def test_insert_and_query(self, db: sqlite3.Connection) -> None:
        record = SeasonRecord(project_id="P001", season=1, season_title="第一季", status="running")
        insert_season(db, record)
        row = db.execute("SELECT * FROM seasons WHERE project_id = ? AND season = ?", ("P001", 1)).fetchone()
        assert row[2] == "第一季"


class TestInsertEpisodes:
    def test_insert_multiple(self, db: sqlite3.Connection) -> None:
        records = [
            EpisodeRecord(episode_code="E01", title="第一集", status="running", shot_count=5),
            EpisodeRecord(episode_code="E02", title="第二集", status="planned", shot_count=8),
        ]
        insert_episodes(db, records)
        count = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        assert count == 2

    def test_empty_list(self, db: sqlite3.Connection) -> None:
        insert_episodes(db, [])  # should not raise


class TestInsertJobs:
    def test_insert_multiple(self, db: sqlite3.Connection) -> None:
        records = [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual_web", status="pending"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="windows_tts", status="succeeded"),
        ]
        insert_jobs(db, records)
        count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 2


class TestInsertEpisodeStates:
    def test_insert_multiple(self, db: sqlite3.Connection) -> None:
        records = [
            EpisodeStateRecord(episode_code="E01", status="running", completed_jobs=3, total_jobs=10),
        ]
        insert_episode_states(db, records)
        row = db.execute("SELECT * FROM episode_states WHERE episode_code = ?", ("E01",)).fetchone()
        assert row[1] == "running"


class TestInsertProviderRequests:
    def test_insert_multiple(self, db: sqlite3.Connection) -> None:
        records = [
            ProviderRequestRecord(
                request_id="REQ_1", job_id="J1", provider="manual_web", job_type="image",
                request_status="pending", endpoint="/api/generate", payload_path="/tmp/payload.json",
            ),
        ]
        insert_provider_requests(db, records)
        count = db.execute("SELECT COUNT(*) FROM provider_requests").fetchone()[0]
        assert count == 1


class TestInsertBatch:
    def test_insert_and_query(self, db: sqlite3.Connection) -> None:
        record = BatchRecord(
            batch_id="B001", batch_type="full", scope_type="episode", scope_value="E01-E03",
            target_steps="scan,render", provider_filter="", status="planned", summary_path="/tmp/summary.json",
        )
        insert_batch(db, record)
        row = db.execute("SELECT * FROM batches WHERE batch_id = ?", ("B001",)).fetchone()
        assert row[0] == "B001"


class TestInsertBatchRuns:
    def test_insert_multiple(self, db: sqlite3.Connection) -> None:
        records = [
            BatchRunRecord(run_id="R1", batch_id="B001", step_name="scan", status="completed", output_path="/tmp/out.json"),
        ]
        insert_batch_runs(db, records)
        count = db.execute("SELECT COUNT(*) FROM batch_runs").fetchone()[0]
        assert count == 1


class TestCollectStatistics:
    def test_empty_db(self, db: sqlite3.Connection) -> None:
        stats = collect_statistics(db)
        assert stats["projects_count"] == 0
        assert stats["jobs_count"] == 0
        assert stats["batch_runs_count"] == 0

    def test_with_data(self, db: sqlite3.Connection) -> None:
        insert_project(db, ProjectRecord(project_id="P001", project_name="T", genre="h", status="active"))
        insert_jobs(db, [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="succeeded"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="pending"),
        ])
        stats = collect_statistics(db)
        assert stats["projects_count"] == 1
        assert stats["jobs_count"] == 2
        assert stats["succeeded_jobs_count"] == 1


class TestCollectJobStatusByEpisode:
    def test_no_jobs(self, db: sqlite3.Connection) -> None:
        assert collect_job_status_by_episode(db) == {}

    def test_grouped_by_episode(self, db: sqlite3.Connection) -> None:
        insert_jobs(db, [
            JobRecord(job_id="J1", episode_code="E01", job_type="image", provider="manual", status="succeeded"),
            JobRecord(job_id="J2", episode_code="E01", job_type="tts", provider="manual", status="succeeded"),
            JobRecord(job_id="J3", episode_code="E02", job_type="image", provider="manual", status="pending"),
        ])
        summary = collect_job_status_by_episode(db)
        assert summary["E01"]["succeeded"] == 2
        assert summary["E02"]["pending"] == 1
