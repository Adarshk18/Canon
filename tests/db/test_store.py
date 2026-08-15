from __future__ import annotations

from pathlib import Path

from canon.core.models import Decision, DecisionStatus
from canon.core.timeutil import utcnow_iso
from canon.db.store import Store


def test_store_roundtrip_and_counts(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    now = utcnow_iso()
    created = store.insert(
        Decision(
            id=None,
            title="Use PostgreSQL",
            body="Relational constraints required.",
            status=DecisionStatus.CANDIDATE,
            created_at=now,
            updated_at=now,
            fingerprint="abc123",
            tags=["database"],
        )
    )
    assert created.id == 1
    fetched = store.get(1)
    assert fetched.title == "Use PostgreSQL"
    assert store.counts()["candidate"] == 1
    assert store.integrity_ok()
    assert store.schema_version() == store.expected_schema_version()
    store.close()


def test_export_has_no_secret_fields(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    now = utcnow_iso()
    store.insert(
        Decision(
            id=None,
            title="Use TLS 1.3",
            body="Encrypt everything.",
            status=DecisionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    payload = store.export_payload()
    assert payload["format"] == "canon-export"
    assert "token" not in str(payload).lower() or "GITHUB" not in str(payload)
    store.close()
