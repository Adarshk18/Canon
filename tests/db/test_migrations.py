from __future__ import annotations

import sqlite3
from pathlib import Path

from canon.db.migrations import apply_migrations, current_version
from canon.db.store import Store


def test_fresh_install_applies_latest(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    assert store.schema_version() == store.expected_schema_version()
    store.close()


def test_existing_database_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "canon.db"
    first = Store(path)
    first.close()
    second = Store(path)
    assert second.schema_version() == second.expected_schema_version()
    second.close()


def test_corrupt_database_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "canon.db"
    store = Store(path)
    store.close()
    path.write_bytes(b"not a sqlite database")
    opened: Store | None = None
    try:
        opened = Store(path)
        raise AssertionError("corrupt database should not open")
    except Exception as exc:
        assert "database" in str(exc).lower() or "sqlite" in str(exc).lower()
    finally:
        if opened is not None:
            opened.close()


def test_apply_on_empty_connection(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path)
    assert current_version(conn) == 0
    applied = apply_migrations(conn)
    assert applied == [1, 2]
    assert current_version(conn) == 2
    conn.close()
