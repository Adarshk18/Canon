from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import run_git
from typer.testing import CliRunner

from canon.cli.app import app
from canon.core.effective import visible_at_head
from canon.core.models import Decision, DecisionStatus, SourceType
from canon.core.timeutil import utcnow_iso
from canon.db.store import Store
from canon.decisions.service import DecisionService
from canon.gitutil.repo import GitRepo
from canon.telemetry.provider import NoOpTelemetry

runner = CliRunner()


def _active(sha: str) -> Decision:
    now = utcnow_iso()
    return Decision(
        id=1,
        title="Use PostgreSQL",
        body="Relational constraints.",
        status=DecisionStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        confirmed_at=now,
        source_commit=sha,
        effective_from=sha,
    )


def test_hidden_on_branch_forked_before_decision(git_repo: Path) -> None:
    repo = GitRepo(git_repo)
    first = repo.head_sha()
    assert first
    run_git(git_repo, "branch", "feat")
    (git_repo / "db.txt").write_text("pg\n", encoding="utf-8")
    run_git(git_repo, "add", "db.txt")
    run_git(git_repo, "commit", "-m", "feat(db): switch to PostgreSQL")
    decision_sha = repo.head_sha()
    assert decision_sha
    decision = _active(decision_sha)
    assert visible_at_head(repo, decision)

    run_git(git_repo, "checkout", "feat")
    assert not visible_at_head(repo, decision)

    run_git(git_repo, "checkout", repo.default_ref().rsplit("/", 1)[-1])
    assert visible_at_head(repo, decision)


def test_revert_hides_decision(git_repo: Path) -> None:
    (git_repo / "db.txt").write_text("pg\n", encoding="utf-8")
    run_git(git_repo, "add", "db.txt")
    run_git(git_repo, "commit", "-m", "feat(db): switch to PostgreSQL")
    repo = GitRepo(git_repo)
    sha = repo.head_sha()
    assert sha
    run_git(git_repo, "revert", "--no-edit", "HEAD")
    assert not visible_at_head(repo, _active(sha))


def test_inject_preview_skips_other_branch(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    run_git(git_repo, "branch", "feat")
    (git_repo / "policy.txt").write_text("oauth\n", encoding="utf-8")
    run_git(git_repo, "add", "policy.txt")
    run_git(git_repo, "commit", "-m", "feat(auth): switch to OAuth 2.1")
    sha = GitRepo(git_repo).head_sha()
    assert sha
    store = Store(git_repo / ".canon" / "canon.db")
    service = DecisionService(store, NoOpTelemetry())
    created = service.create_candidate(
        title="Use OAuth 2.1 instead of passwords",
        body="MFA requires OAuth.",
        source_type=SourceType.COMMIT,
        source_commit=sha,
    )
    assert created is not None
    service.approve(created.id or 0, confirmed_by="dev@example.com", at_commit=sha)
    store.close()

    on_main = runner.invoke(app, ["inject-preview"])
    assert on_main.exit_code == 0, on_main.output
    assert "OAuth" in on_main.output

    run_git(git_repo, "checkout", "feat")
    on_feat = runner.invoke(app, ["inject-preview"])
    assert on_feat.exit_code == 0, on_feat.output
    assert "OAuth" not in on_feat.output
    assert "I have no confirmed decision" in on_feat.output
