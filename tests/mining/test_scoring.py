from __future__ import annotations

from canon.mining.extract import extract_title
from canon.mining.scoring import score_change


def test_high_signal_architecture_change_scores_well() -> None:
    score = score_change(
        title="Switch to PostgreSQL for persistent application data",
        body="We decided to use PostgreSQL instead of MongoDB because we need transactions.",
        files=("src/db/engine.py", "alembic/versions/0001.py"),
        is_pr=True,
    )
    assert score.value >= 6
    assert score.category == "database"
    assert not score.noise


def test_typo_and_lockfile_are_filtered() -> None:
    typo = score_change(
        title="fix: typo in comment",
        body="spelling",
        files=("src/auth.py",),
        is_pr=False,
    )
    lock = score_change(
        title="chore: bump lodash",
        body="bump lodash from 4.17.20 to 4.17.21",
        files=("package-lock.json",),
        is_pr=False,
    )
    assert typo.value < 6 or typo.noise
    assert lock.value < 6 or lock.noise


def test_extract_title_from_switch() -> None:
    title = extract_title("feat(db): switch to PostgreSQL for persistence", "database")
    assert title.lower().startswith("use postgresql")


def test_extract_title_keeps_version_numbers() -> None:
    title = extract_title("feat(auth): switch to OAuth 2.1 instead of custom passwords", "auth")
    assert "2.1" in title
