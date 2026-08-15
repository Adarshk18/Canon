from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from canon.core.models import Decision, DecisionStatus
from canon.core.timeutil import utcnow_iso
from canon.db.migrations import apply_migrations, current_version, latest_schema_version
from canon.errors import DatabaseError, UsageError


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    except sqlite3.Error as exc:
        raise DatabaseError(
            "Canon could not open the local decision database.",
            f"Path: {path}",
        ) from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = _connect(path)
        apply_migrations(self.conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def integrity_ok(self) -> bool:
        row = self.conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and str(row[0]).lower() == "ok"

    def schema_version(self) -> int:
        return current_version(self.conn)

    def expected_schema_version(self) -> int:
        return latest_schema_version()

    def get(self, decision_id: int) -> Decision:
        row = self.conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            raise UsageError(
                f"No decision with id {decision_id}.",
                "Run `canon list --all` to see stored decisions.",
            )
        return Decision.from_row(dict(row))

    def find_by_fingerprint(self, fingerprint: str) -> Decision | None:
        row = self.conn.execute(
            "SELECT * FROM decisions WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return Decision.from_row(dict(row)) if row else None

    def list(
        self,
        *,
        statuses: Sequence[DecisionStatus] | None = None,
        tag: str | None = None,
        category: str | None = None,
    ) -> list[Decision]:
        sql = "SELECT * FROM decisions"
        clauses: list[str] = []
        params: list[Any] = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(status.value for status in statuses)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id ASC"
        rows = [Decision.from_row(dict(row)) for row in self.conn.execute(sql, params)]
        if tag:
            wanted = tag.lower()
            rows = [item for item in rows if wanted in {t.lower() for t in item.tags}]
        return rows

    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in DecisionStatus}
        for row in self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM decisions GROUP BY status"
        ):
            result[str(row["status"])] = int(row["n"])
        return result

    def insert(self, decision: Decision) -> Decision:
        now = utcnow_iso()
        payload = decision.to_row()
        payload["created_at"] = payload["created_at"] or now
        payload["updated_at"] = now
        columns = [
            "title",
            "body",
            "status",
            "created_at",
            "updated_at",
            "confirmed_at",
            "confirmed_by",
            "source_type",
            "source_repository",
            "source_pr",
            "source_commit",
            "source_url",
            "source_date",
            "supersedes_id",
            "superseded_by_id",
            "superseded_at",
            "rejected_at",
            "rejection_reason",
            "confidence",
            "authority",
            "tags",
            "category",
            "evidence",
            "fingerprint",
            "extra",
        ]
        values = [
            payload["title"],
            payload["body"],
            payload["status"],
            payload["created_at"],
            payload["updated_at"],
            payload["confirmed_at"],
            payload["confirmed_by"],
            payload["source_type"],
            payload["source_repository"],
            payload["source_pr"],
            payload["source_commit"],
            payload["source_url"],
            payload["source_date"],
            payload["supersedes_id"],
            payload["superseded_by_id"],
            payload["superseded_at"],
            payload["rejected_at"],
            payload["rejection_reason"],
            payload["confidence"],
            payload["authority"],
            json.dumps(payload["tags"]),
            payload["category"],
            payload["evidence"],
            payload["fingerprint"],
            json.dumps(payload["extra"]),
        ]
        try:
            cursor = self.conn.execute(
                f"INSERT INTO decisions ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                values,
            )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(
                "Canon could not store that decision.",
                "A decision with the same source fingerprint already exists.",
            ) from exc
        except sqlite3.Error as exc:
            raise DatabaseError("Canon could not store that decision.") from exc
        last_id = cursor.lastrowid
        if last_id is None:
            raise DatabaseError("Canon could not store that decision.")
        return self.get(int(last_id))

    def update(self, decision: Decision) -> Decision:
        if decision.id is None:
            raise DatabaseError("Cannot update a decision without an id.")
        payload = decision.to_row()
        payload["updated_at"] = utcnow_iso()
        try:
            self.conn.execute(
                """
                UPDATE decisions SET
                    title = ?, body = ?, status = ?, updated_at = ?,
                    confirmed_at = ?, confirmed_by = ?,
                    source_type = ?, source_repository = ?, source_pr = ?,
                    source_commit = ?, source_url = ?, source_date = ?,
                    supersedes_id = ?, superseded_by_id = ?, superseded_at = ?,
                    rejected_at = ?, rejection_reason = ?,
                    confidence = ?, authority = ?, tags = ?, category = ?,
                    evidence = ?, fingerprint = ?, extra = ?
                WHERE id = ?
                """,
                (
                    payload["title"],
                    payload["body"],
                    payload["status"],
                    payload["updated_at"],
                    payload["confirmed_at"],
                    payload["confirmed_by"],
                    payload["source_type"],
                    payload["source_repository"],
                    payload["source_pr"],
                    payload["source_commit"],
                    payload["source_url"],
                    payload["source_date"],
                    payload["supersedes_id"],
                    payload["superseded_by_id"],
                    payload["superseded_at"],
                    payload["rejected_at"],
                    payload["rejection_reason"],
                    payload["confidence"],
                    payload["authority"],
                    json.dumps(payload["tags"]),
                    payload["category"],
                    payload["evidence"],
                    payload["fingerprint"],
                    json.dumps(payload["extra"]),
                    decision.id,
                ),
            )
        except sqlite3.Error as exc:
            raise DatabaseError("Canon could not update that decision.") from exc
        return self.get(decision.id)

    def record_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        safe = payload or {}
        # Never persist decision bodies or secrets in the event log.
        blocked = {"body", "token", "secret", "authorization", "password"}
        cleaned = {key: value for key, value in safe.items() if key not in blocked}
        self.conn.execute(
            "INSERT INTO events (type, created_at, payload) VALUES (?, ?, ?)",
            (event_type, utcnow_iso(), json.dumps(cleaned)),
        )

    def export_payload(self) -> dict[str, Any]:
        decisions = [item.to_row() for item in self.list()]
        return {
            "format": "canon-export",
            "schema_version": self.schema_version(),
            "exported_at": utcnow_iso(),
            "decisions": decisions,
        }
