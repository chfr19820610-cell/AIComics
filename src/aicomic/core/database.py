from __future__ import annotations

import sqlite3
from pathlib import Path

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


def connect_database(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(database_path)


def initialize_schema(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            genre TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes (
            episode_code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            shot_count INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS seasons (
            project_id TEXT NOT NULL,
            season INTEGER NOT NULL,
            season_title TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (project_id, season)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            episode_code TEXT NOT NULL,
            job_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS episode_states (
            episode_code TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            completed_jobs INTEGER NOT NULL,
            total_jobs INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_requests (
            request_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            job_type TEXT NOT NULL,
            request_status TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            payload_path TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS batches (
            batch_id TEXT PRIMARY KEY,
            batch_type TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_value TEXT NOT NULL,
            target_steps TEXT NOT NULL,
            provider_filter TEXT NOT NULL,
            status TEXT NOT NULL,
            summary_path TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_runs (
            run_id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL,
            output_path TEXT NOT NULL
        )
        """
    )
    connection.commit()


def insert_project(connection: sqlite3.Connection, record: ProjectRecord) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO projects (project_id, project_name, genre, status)
        VALUES (?, ?, ?, ?)
        """,
        (record.project_id, record.project_name, record.genre, record.status),
    )
    connection.commit()


def insert_season(connection: sqlite3.Connection, record: SeasonRecord) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO seasons (project_id, season, season_title, status)
        VALUES (?, ?, ?, ?)
        """,
        (record.project_id, record.season, record.season_title, record.status),
    )
    connection.commit()


def insert_episodes(connection: sqlite3.Connection, records: list[EpisodeRecord]) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO episodes (episode_code, title, status, shot_count)
        VALUES (?, ?, ?, ?)
        """,
        [(item.episode_code, item.title, item.status, item.shot_count) for item in records],
    )
    connection.commit()


def insert_jobs(connection: sqlite3.Connection, records: list[JobRecord]) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO jobs (job_id, episode_code, job_type, provider, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(item.job_id, item.episode_code, item.job_type, item.provider, item.status) for item in records],
    )
    connection.commit()


def insert_episode_states(connection: sqlite3.Connection, records: list[EpisodeStateRecord]) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO episode_states (episode_code, status, completed_jobs, total_jobs)
        VALUES (?, ?, ?, ?)
        """,
        [(item.episode_code, item.status, item.completed_jobs, item.total_jobs) for item in records],
    )
    connection.commit()


def insert_provider_requests(connection: sqlite3.Connection, records: list[ProviderRequestRecord]) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO provider_requests (
            request_id,
            job_id,
            provider,
            job_type,
            request_status,
            endpoint,
            payload_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.request_id,
                item.job_id,
                item.provider,
                item.job_type,
                item.request_status,
                item.endpoint,
                item.payload_path,
            )
            for item in records
        ],
    )
    connection.commit()


def insert_batch(connection: sqlite3.Connection, record: BatchRecord) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO batches (
            batch_id,
            batch_type,
            scope_type,
            scope_value,
            target_steps,
            provider_filter,
            status,
            summary_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.batch_id,
            record.batch_type,
            record.scope_type,
            record.scope_value,
            record.target_steps,
            record.provider_filter,
            record.status,
            record.summary_path,
        ),
    )
    connection.commit()


def insert_batch_runs(connection: sqlite3.Connection, records: list[BatchRunRecord]) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO batch_runs (
            run_id,
            batch_id,
            step_name,
            status,
            output_path
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                item.run_id,
                item.batch_id,
                item.step_name,
                item.status,
                item.output_path,
            )
            for item in records
        ],
    )
    connection.commit()


def collect_statistics(connection: sqlite3.Connection) -> dict[str, int]:
    cursor = connection.cursor()
    stats = {}
    for table_name in ("projects", "seasons", "episodes", "jobs", "episode_states", "provider_requests", "batches", "batch_runs"):
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        stats[f"{table_name}_count"] = int(cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", ("succeeded",))
    stats["succeeded_jobs_count"] = int(cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM provider_requests WHERE request_status = ?", ("ready",))
    stats["ready_provider_requests_count"] = int(cursor.fetchone()[0])
    return stats


def collect_job_status_by_episode(connection: sqlite3.Connection) -> dict[str, dict[str, int]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT episode_code, status, COUNT(*)
        FROM jobs
        GROUP BY episode_code, status
        ORDER BY episode_code, status
        """
    )
    summary: dict[str, dict[str, int]] = {}
    for episode_code, status, count in cursor.fetchall():
        episode_summary = summary.setdefault(str(episode_code), {})
        episode_summary[str(status)] = int(count)
    return summary
