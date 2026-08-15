from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from canon.errors import GitError
from canon.gitutil.runner import CommandResult, run_command, which
from canon.security.sanitize import sanitize_text

_GITHUB_REMOTE = re.compile(
    r"(?:git@github\.com:|https://github\.com/|ssh://git@github\.com/)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)


@dataclass(frozen=True, slots=True)
class GitCommit:
    sha: str
    authored_at: str
    subject: str
    body: str
    files: tuple[str, ...]
    is_merge: bool


def find_git_root(start: Path | None = None) -> Path:
    if which("git") is None:
        raise GitError(
            "Git is not installed (or not on PATH).",
            "Install Git, then retry from inside a repository.",
        )
    cwd = (start or Path.cwd()).resolve()
    result = run_command(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
    )
    if not result.ok:
        raise GitError(
            "This directory is not a Git repository.",
            "Canon works inside a Git project. `cd` into the repository and run `canon init`.",
        )
    return Path(result.stdout.strip()).resolve()


class GitRepo:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, *args: str, check: bool = True, timeout: float = 20.0) -> CommandResult:
        return run_command(["git", *args], cwd=self.root, check=check, timeout=timeout)

    def is_valid(self) -> bool:
        result = self.run("rev-parse", "--is-inside-work-tree", check=False)
        return result.ok and result.stdout.strip() == "true"

    def current_branch(self) -> str | None:
        result = self.run("rev-parse", "--abbrev-ref", "HEAD", check=False)
        if not result.ok:
            return None
        value = result.stdout.strip()
        return value or None

    def head_sha(self) -> str | None:
        result = self.run("rev-parse", "HEAD", check=False)
        if not result.ok:
            return None
        return result.stdout.strip() or None

    def identity(self) -> str:
        name = self.run("config", "--get", "user.name", check=False).stdout.strip()
        email = self.run("config", "--get", "user.email", check=False).stdout.strip()
        if name and email:
            return f"{name} <{email}>"
        return name or email or "local-user"

    def remote_url(self, name: str = "origin") -> str | None:
        result = self.run("remote", "get-url", name, check=False)
        if not result.ok:
            return None
        return result.stdout.strip() or None

    def github_slug(self) -> str | None:
        url = self.remote_url()
        if not url:
            return None
        match = _GITHUB_REMOTE.search(url.strip())
        if not match:
            return None
        return f"{match.group('owner')}/{match.group('repo').removesuffix('.git')}"

    def changed_files(self) -> list[str]:
        result = self.run("status", "--porcelain", check=False)
        files: list[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.append(path)
        return files

    def recent_commits(self, limit: int = 40) -> list[GitCommit]:
        fmt = "%H%x1f%aI%x1f%s%x1f%P%x1f%b%x1e"
        result = self.run("log", f"-n{int(limit)}", f"--format={fmt}", check=False)
        if not result.ok:
            return []
        commits: list[GitCommit] = []
        for record in result.stdout.split("\x1e"):
            record = record.strip("\n")
            if not record.strip():
                continue
            parts = record.split("\x1f")
            if len(parts) < 4:
                continue
            sha, authored_at, subject, parents = parts[:4]
            body = parts[4] if len(parts) > 4 else ""
            files = self._commit_files(sha)
            commits.append(
                GitCommit(
                    sha=sha.strip(),
                    authored_at=authored_at.strip(),
                    subject=sanitize_text(subject.strip(), limit=300),
                    body=sanitize_text(body.strip(), limit=2000),
                    files=tuple(files),
                    is_merge=len(parents.split()) > 1,
                )
            )
        return commits

    def _commit_files(self, sha: str) -> list[str]:
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
            return []
        result = self.run(
            "diff-tree", "--no-commit-id", "--name-only", "-r", sha, check=False
        )
        if not result.ok:
            return []
        files: list[str] = []
        for line in result.stdout.splitlines():
            text = line.strip()
            if text and ".." not in Path(text).parts:
                files.append(text)
        return files[:200]
