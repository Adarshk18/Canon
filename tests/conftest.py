from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Dev Example"
    env["GIT_AUTHOR_EMAIL"] = "dev@example.com"
    env["GIT_COMMITTER_NAME"] = "Dev Example"
    env["GIT_COMMITTER_EMAIL"] = "dev@example.com"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Iterator[Path]:
    repo = tmp_path / "project"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.name", "Dev Example")
    run_git(repo, "config", "user.email", "dev@example.com")
    run_git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "chore: initial import")
    yield repo


@pytest.fixture
def decision_repo(git_repo: Path) -> Path:
    auth = git_repo / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "oauth.py").write_text("PROVIDER = 'oauth'\n", encoding="utf-8")
    run_git(git_repo, "add", "src/auth/oauth.py")
    run_git(
        git_repo,
        "commit",
        "-m",
        "feat(auth): switch to OAuth 2.1 instead of custom passwords\n\n"
        "We decided to use OAuth 2.1 because custom password auth cannot meet MFA requirements.",
    )
    db = git_repo / "src" / "db"
    db.mkdir()
    (db / "engine.py").write_text("ENGINE = 'postgres'\n", encoding="utf-8")
    run_git(git_repo, "add", "src/db/engine.py")
    run_git(
        git_repo,
        "commit",
        "-m",
        "feat(db): migrate to PostgreSQL for persistent application data\n\n"
        "Use PostgreSQL instead of MongoDB because we need relational constraints "
        "and transactional consistency.",
    )
    (git_repo / "typo.txt").write_text("fix\n", encoding="utf-8")
    run_git(git_repo, "add", "typo.txt")
    run_git(git_repo, "commit", "-m", "fix: typo in readme wording")
    return git_repo
