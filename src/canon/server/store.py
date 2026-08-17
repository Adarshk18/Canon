from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from canon.core.timeutil import utcnow_iso

SEATS = {"free": 0, "pro": 5, "team": 25}


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CloudStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = _connect(path)
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                polar_customer TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS device_codes (
                device_code TEXT PRIMARY KEY,
                user_code TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                user_id TEXT REFERENCES users(id),
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspaces (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memberships (
                workspace TEXT NOT NULL REFERENCES workspaces(slug),
                user_id TEXT NOT NULL REFERENCES users(id),
                role TEXT NOT NULL,
                PRIMARY KEY (workspace, user_id)
            );
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                workspace TEXT NOT NULL REFERENCES workspaces(slug),
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                workspace TEXT PRIMARY KEY REFERENCES workspaces(slug),
                payload TEXT NOT NULL,
                count INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            );
            """
        )

    def create_device(self, *, ttl: float = 300.0) -> dict[str, Any]:
        import time

        device_code = secrets.token_urlsafe(24)
        user_code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        self.conn.execute(
            "INSERT INTO device_codes (device_code, user_code, status, expires_at) VALUES (?,?,?,?)",
            (device_code, user_code, "pending", time.time() + ttl),
        )
        return {"device_code": device_code, "user_code": user_code}

    def get_device(self, *, device_code: str | None = None, user_code: str | None = None) -> dict[str, Any] | None:
        if device_code:
            row = self.conn.execute(
                "SELECT * FROM device_codes WHERE device_code = ?", (device_code,)
            ).fetchone()
        elif user_code:
            row = self.conn.execute(
                "SELECT * FROM device_codes WHERE user_code = ?", (user_code.upper(),)
            ).fetchone()
        else:
            return None
        return dict(row) if row else None

    def approve_device(self, user_code: str, *, email: str, name: str) -> dict[str, Any]:
        import time

        row = self.get_device(user_code=user_code)
        if row is None or float(row["expires_at"]) < time.time():
            raise KeyError("invalid")
        user = self.upsert_user(email=email, name=name)
        self.conn.execute(
            "UPDATE device_codes SET status = 'approved', user_id = ? WHERE user_code = ?",
            (user["id"], user_code.upper()),
        )
        return user

    def finish_device(self, device_code: str) -> dict[str, Any] | None:
        import time

        row = self.get_device(device_code=device_code)
        if row is None or float(row["expires_at"]) < time.time():
            return {"status": "expired"}
        if row["status"] != "approved" or not row["user_id"]:
            return {"status": "pending"}
        user = self.get_user(str(row["user_id"]))
        if user is None:
            return {"status": "pending"}
        token = secrets.token_urlsafe(32)
        self.conn.execute(
            "INSERT INTO tokens (token_hash, user_id, created_at) VALUES (?,?,?)",
            (hash_token(token), user["id"], utcnow_iso()),
        )
        self.conn.execute("DELETE FROM device_codes WHERE device_code = ?", (device_code,))
        return {
            "status": "approved",
            "token": token,
            "email": user["email"],
            "plan": user["plan"],
            "user_id": user["id"],
        }

    def upsert_user(self, *, email: str, name: str) -> dict[str, Any]:
        email = email.strip().lower()
        existing = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return dict(existing)
        user_id = secrets.token_hex(8)
        self.conn.execute(
            "INSERT INTO users (id, email, name, plan, created_at) VALUES (?,?,?,?,?)",
            (user_id, email, name.strip() or email, "free", utcnow_iso()),
        )
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert row is not None
        return dict(row)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def user_from_token(self, token: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT users.* FROM tokens
            JOIN users ON users.id = tokens.user_id
            WHERE tokens.token_hash = ?
            """,
            (hash_token(token),),
        ).fetchone()
        return dict(row) if row else None

    def set_plan(self, user_id: str, plan: str, *, polar_customer: str | None = None) -> None:
        if polar_customer:
            self.conn.execute(
                "UPDATE users SET plan = ?, polar_customer = ? WHERE id = ?",
                (plan, polar_customer, user_id),
            )
        else:
            self.conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))

    def user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def ensure_workspace(self, slug: str, owner: dict[str, Any]) -> dict[str, Any]:
        slug = slug.strip().lower()
        row = self.conn.execute("SELECT * FROM workspaces WHERE slug = ?", (slug,)).fetchone()
        if row:
            return dict(row)
        self.conn.execute(
            "INSERT INTO workspaces (slug, name, owner_id, created_at) VALUES (?,?,?,?)",
            (slug, slug, owner["id"], utcnow_iso()),
        )
        self.conn.execute(
            "INSERT INTO memberships (workspace, user_id, role) VALUES (?,?,?)",
            (slug, owner["id"], "owner"),
        )
        created = self.conn.execute("SELECT * FROM workspaces WHERE slug = ?", (slug,)).fetchone()
        assert created is not None
        return dict(created)

    def membership(self, slug: str, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM memberships WHERE workspace = ? AND user_id = ?",
            (slug, user_id),
        ).fetchone()
        return dict(row) if row else None

    def member_count(self, slug: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM memberships WHERE workspace = ?", (slug,)
        ).fetchone()
        return int(row["n"]) if row else 0

    def add_member(self, slug: str, user_id: str, role: str = "member") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO memberships (workspace, user_id, role) VALUES (?,?,?)",
            (slug, user_id, role),
        )

    def create_invite(self, slug: str, email: str) -> str:
        code = secrets.token_urlsafe(10)
        self.conn.execute(
            "INSERT INTO invites (code, workspace, email, created_at) VALUES (?,?,?,?)",
            (code, slug, email.strip().lower(), utcnow_iso()),
        )
        return code

    def accept_invite(self, code: str, user: dict[str, Any]) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
        if row is None:
            raise KeyError("invite")
        workspace = str(row["workspace"])
        self.add_member(workspace, user["id"])
        self.conn.execute("DELETE FROM invites WHERE code = ?", (code,))
        return {"workspace": workspace}

    def members(self, slug: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT users.email, users.plan, memberships.role
            FROM memberships
            JOIN users ON users.id = memberships.user_id
            WHERE memberships.workspace = ?
            ORDER BY memberships.role DESC, users.email
            """,
            (slug,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_snapshot(self, slug: str, payload: dict[str, Any], user_id: str) -> int:
        decisions = payload.get("decisions")
        count = len(decisions) if isinstance(decisions, list) else 0
        self.conn.execute(
            """
            INSERT INTO snapshots (workspace, payload, count, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workspace) DO UPDATE SET
                payload = excluded.payload,
                count = excluded.count,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (slug, json.dumps(payload), count, utcnow_iso(), user_id),
        )
        return count

    def load_snapshot(self, slug: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload, count, updated_at FROM snapshots WHERE workspace = ?",
            (slug,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload"]))
        if not isinstance(payload, dict):
            return None
        return {"snapshot": payload, "count": int(row["count"]), "updated_at": row["updated_at"]}


def default_db_path() -> Path:
    override = os.environ.get("CANON_CLOUD_DB")
    if override:
        return Path(override)
    return Path(os.environ.get("CANON_CLOUD_HOME", Path.home() / ".canon-cloud")) / "cloud.db"
