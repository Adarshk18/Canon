from __future__ import annotations

from pathlib import Path

import pytest

from canon.core.models import Decision, DecisionStatus
from canon.core.timeutil import utcnow_iso
from canon.db.store import Store
from canon.errors import SecurityError
from canon.gitutil.runner import run_command


def test_sql_injection_is_data(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    now = utcnow_iso()
    evil = "1; DROP TABLE decisions; --"
    store.insert(
        Decision(
            id=None,
            title=evil,
            body="payload",
            status=DecisionStatus.CANDIDATE,
            created_at=now,
            updated_at=now,
            fingerprint="evil-sql",
        )
    )
    assert store.get(1).title == evil
    assert store.counts()["candidate"] == 1
    store.close()


def test_runner_rejects_unexpected_binary(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        run_command(["curl", "https://attacker.example"], cwd=tmp_path)


def test_runner_never_uses_shell_for_git(tmp_path: Path) -> None:
    result = run_command(["git", "--version"], cwd=tmp_path, check=True)
    assert result.ok
    assert "git version" in result.stdout.lower()
