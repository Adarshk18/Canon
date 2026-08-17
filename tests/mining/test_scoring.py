from __future__ import annotations

from canon.mining.extract import extract_body, extract_title
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


def test_product_policy_commits_score() -> None:
    drop = score_change(
        title="feat(product): drop user analytics pages, restore four-agent landing",
        body="",
        files=("src/app/analytics/page.tsx", "src/app/page.tsx"),
        is_pr=False,
    )
    rename = score_change(
        title="feat(debrief): rename Rejection Debrief to Interview Debrief end-to-end",
        body="",
        files=("src/debrief/title.ts",),
        is_pr=False,
    )
    model = score_change(
        title="fix(ai): DeepSeek text path uses v4-flash + thinking disabled",
        body="",
        files=("src/ai/deepseek.ts",),
        is_pr=False,
    )
    only = score_change(
        title="fix(pricing): show only 3 moat features and 4 agents",
        body="",
        files=("src/pricing/moat.ts",),
        is_pr=False,
    )
    assert drop.value >= 6 and not drop.noise
    assert rename.value >= 6 and not rename.noise
    assert model.value >= 6 and not model.noise
    assert only.value >= 6 and not only.noise


def test_ui_polish_and_copy_tweaks_stay_filtered() -> None:
    ui = score_change(
        title="fix(ui): side-view robot runs in place on every loading screen",
        body="",
        files=("src/components/Robot.tsx",),
        is_pr=False,
    )
    copy = score_change(
        title="feat(notifications): richer popup copy for email-detected reject/offer",
        body="",
        files=("src/notifications/copy.ts",),
        is_pr=False,
    )
    navbar = score_change(
        title="feat(landing): show Pricing in navbar after Features",
        body="",
        files=("src/landing/nav.tsx",),
        is_pr=False,
    )
    assert ui.value < 6 or ui.noise
    assert copy.value < 6 or copy.noise
    assert navbar.value < 6 or navbar.noise


def test_file_move_migrate_is_not_a_decision() -> None:
    score = score_change(
        title="refactor: migrate utils into lib/",
        body="move helpers",
        files=("src/utils/helpers.py", "src/lib/helpers.py"),
        is_pr=True,
    )
    assert score.noise or score.value < 6


def test_stack_migrate_still_scores() -> None:
    score = score_change(
        title="feat(db): migrate to PostgreSQL",
        body="We decided to use PostgreSQL because we need transactions.",
        files=("src/db/engine.py", "alembic/versions/0001.py"),
        is_pr=True,
    )
    assert score.value >= 6
    assert not score.noise
    assert score.category == "database"


def test_session_word_is_not_auth() -> None:
    score = score_change(
        title="feat(logging): persist request session id",
        body="store the session id on the request log line",
        files=("src/log/writer.py",),
        is_pr=True,
    )
    assert score.category != "auth"


def test_extract_product_titles() -> None:
    dropped = extract_title(
        "feat(product): drop user analytics pages, restore four-agent landing",
        "product",
    )
    renamed = extract_title(
        "feat(debrief): rename Rejection Debrief to Interview Debrief end-to-end",
        "product",
    )
    assert dropped.lower().startswith("do not keep")
    assert "interview debrief" in renamed.lower()


def test_extract_body_keeps_later_paragraphs() -> None:
    raw = (
        "We are moving voice to Chirp 3.\n\n"
        "Language detection is automatic. Timeouts stay at 8s.\n\n"
        "Do not fall back to the old vendor."
    )
    body = extract_body(raw, "PR #2942")
    assert "Chirp 3" in body
    assert "Do not fall back" in body
