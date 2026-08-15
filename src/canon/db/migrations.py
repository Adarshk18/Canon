from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from canon.core.timeutil import utcnow_iso
from canon.errors import DatabaseError

MIGRATIONS: Sequence[tuple[int, str, str]] = (
    (
        1,
        "initial",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('candidate', 'active', 'rejected', 'superseded')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT,
            confirmed_by TEXT,
            source_type TEXT CHECK (source_type IN ('pr', 'commit', 'manual') OR source_type IS NULL),
            source_repository TEXT,
            source_pr TEXT,
            source_commit TEXT,
            source_url TEXT,
            source_date TEXT,
            supersedes_id INTEGER REFERENCES decisions(id),
            superseded_by_id INTEGER REFERENCES decisions(id),
            superseded_at TEXT,
            rejected_at TEXT,
            rejection_reason TEXT,
            confidence TEXT CHECK (confidence IN ('high', 'medium', 'low') OR confidence IS NULL),
            authority TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            category TEXT,
            evidence TEXT,
            fingerprint TEXT,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
        CREATE INDEX IF NOT EXISTS idx_decisions_fingerprint ON decisions(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_decisions_source_pr ON decisions(source_pr);
        CREATE INDEX IF NOT EXISTS idx_decisions_category ON decisions(category);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_fingerprint_unique
            ON decisions(fingerprint) WHERE fingerprint IS NOT NULL;

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}'
        );
        """,
    ),
)


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if row is None:
        return 0
    version_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if version_row is None or version_row[0] is None:
        return 0
    return int(version_row[0])


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    applied: list[int] = []
    try:
        version = current_version(conn)
        for migration_version, name, sql in MIGRATIONS:
            if migration_version <= version:
                continue
            # executescript() commits any open transaction first. Do not wrap
            # it in BEGIN/COMMIT when the connection is in autocommit mode.
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (migration_version, name, utcnow_iso()),
                )
            except sqlite3.Error:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            applied.append(migration_version)
    except sqlite3.Error as exc:
        raise DatabaseError(
            "Canon could not apply database migrations.",
            "The local SQLite database may be corrupt. Restore from a backup "
            "or run `canon export` if the database still opens.",
        ) from exc
    return applied


def latest_schema_version() -> int:
    return max(version for version, _name, _sql in MIGRATIONS)
