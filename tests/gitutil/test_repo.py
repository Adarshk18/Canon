from __future__ import annotations

from pathlib import Path

from tests.conftest import run_git

from canon.gitutil.repo import GitRepo, find_git_root


def test_find_git_root_and_commits(decision_repo: Path) -> None:
    root = find_git_root(decision_repo)
    assert root == decision_repo.resolve()
    repo = GitRepo(root)
    assert repo.is_valid()
    assert repo.identity().startswith("Dev Example")
    commits = repo.recent_commits(10)
    assert commits
    assert any("PostgreSQL" in item.subject or "OAuth" in item.subject for item in commits)
    assert all(".." not in "".join(item.files) for item in commits)


def test_github_slug_from_origin(git_repo: Path) -> None:
    run_git(git_repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    repo = GitRepo(git_repo)
    assert repo.github_slug() == "acme/demo"
