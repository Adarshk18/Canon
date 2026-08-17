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
_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _looks_like_sha(value: str) -> bool:
    return bool(value) and _SHA.fullmatch(value.strip()) is not None


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

    def default_ref(self) -> str:
        """Tip that has landed on the default branch. Feature HEADs are ignored."""
        symbolic = self.run(
            "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False
        )
        if symbolic.ok:
            ref = symbolic.stdout.strip()
            if ref:
                return ref
        for candidate in ("origin/main", "origin/master", "main", "master"):
            verified = self.run("rev-parse", "--verify", candidate, check=False)
            if verified.ok and verified.stdout.strip():
                return candidate
        return "HEAD"

    def commit_exists(self, sha: str) -> bool:
        if not _looks_like_sha(sha):
            return False
        result = self.run("cat-file", "-e", f"{sha}^{{commit}}", check=False)
        return result.ok

    def is_ancestor(self, maybe_ancestor: str, descendant: str | None = None) -> bool:
        if not _looks_like_sha(maybe_ancestor):
            return False
        tip = descendant or self.head_sha()
        if not tip or not _looks_like_sha(tip):
            return False
        result = self.run(
            "merge-base", "--is-ancestor", maybe_ancestor, tip, check=False
        )
        return result.ok

    def find_revert_commit(self, sha: str) -> str | None:
        """Return the revert commit if git recorded `This reverts commit <sha>`."""
        if not _looks_like_sha(sha):
            return None
        needle = sha.strip().lower()
        result = self.run(
            "log",
            "-n200",
            "--format=%H%x1f%s%x1f%b%x1e",
            check=False,
        )
        if not result.ok:
            return None
        revert_re = re.compile(r"(?i)this reverts commit ([0-9a-f]{7,40})")
        for record in result.stdout.split("\x1e"):
            record = record.strip("\n")
            if not record.strip():
                continue
            parts = record.split("\x1f")
            if len(parts) < 3:
                continue
            current, subject, body = parts[0].strip(), parts[1], parts[2]
            match = revert_re.search(f"{subject}\n{body}")
            if not match:
                continue
            found = match.group(1).lower()
            if needle.startswith(found) or found.startswith(needle[:7]):
                return current
        return None

    def recent_commits(self, limit: int = 40, *, landed: bool = True) -> list[GitCommit]:
        fmt = "%H%x1f%aI%x1f%s%x1f%P%x1f%b%x1e"
        ref = self.default_ref() if landed else "HEAD"
        result = self.run("log", ref, f"-n{int(limit)}", f"--format={fmt}", check=False)
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
                    body=sanitize_text(body.strip(), limit=4000),
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
