from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from canon.constants import DEFAULT_GITHUB_TIMEOUT
from canon.errors import GitHubError
from canon.gitutil.repo import GitRepo
from canon.gitutil.runner import run_command, which
from canon.security.redact import redact
from canon.security.sanitize import sanitize_text


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str
    url: str
    merged_at: str | None
    author: str | None
    merge_commit: str | None
    files: tuple[str, ...]
    repository: str


@dataclass(frozen=True, slots=True)
class GitHubStatus:
    available: bool
    authenticated: bool
    method: str
    detail: str


class GitHubClient:
    """Read-only GitHub access. Prefer `gh`. Fall back to API token if present."""

    def __init__(self, repo: GitRepo, timeout: float = DEFAULT_GITHUB_TIMEOUT) -> None:
        self.repo = repo
        self.timeout = timeout
        self.slug = repo.github_slug()

    def status(self) -> GitHubStatus:
        if which("gh") is not None:
            result = run_command(
                ["gh", "auth", "status"],
                cwd=self.repo.root,
                timeout=self.timeout,
                check=False,
                error_cls=GitHubError,
            )
            if result.ok:
                return GitHubStatus(True, True, "gh", "GitHub CLI is authenticated.")
            return GitHubStatus(
                True,
                False,
                "gh",
                "GitHub CLI is installed, but you are not authenticated.",
            )
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return GitHubStatus(
                True, True, "api", "Using GITHUB_TOKEN for read-only API access."
            )
        return GitHubStatus(
            False,
            False,
            "none",
            "GitHub CLI is not installed and GITHUB_TOKEN is not set.",
        )

    def recent_merged_prs(self, limit: int = 20) -> list[PullRequest]:
        status = self.status()
        if not status.authenticated:
            raise GitHubError(
                "Canon could not access GitHub.",
                (
                    "GitHub CLI is installed, but you are not authenticated.\n\n"
                    "Run:\n\n    gh auth login\n\n"
                    "Then retry:\n\n    canon suggest"
                    if status.method == "gh"
                    else "Install GitHub CLI and run `gh auth login`, or set GITHUB_TOKEN "
                    "for read-only PR metadata. Canon will fall back to local Git history."
                ),
            )
        if status.method == "gh":
            return self._from_gh(limit)
        return self._from_api(limit)

    def _from_gh(self, limit: int) -> list[PullRequest]:
        args = [
            "gh",
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(int(limit)),
            "--json",
            "number,title,body,url,mergedAt,author,mergeCommit,files",
        ]
        result = run_command(
            args,
            cwd=self.repo.root,
            timeout=self.timeout,
            check=False,
            error_cls=GitHubError,
        )
        if not result.ok:
            raise GitHubError(
                "GitHub CLI could not list merged pull requests.",
                result.stderr.strip() or "No additional detail was provided.",
            )
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise GitHubError("GitHub CLI returned malformed JSON.") from exc
        if not isinstance(payload, list):
            raise GitHubError("GitHub CLI returned an unexpected payload.")
        return [item for item in (self._parse_pr(raw) for raw in payload) if item]

    def _from_api(self, limit: int) -> list[PullRequest]:
        if not self.slug:
            raise GitHubError(
                "Canon could not determine the GitHub repository.",
                "Set a GitHub `origin` remote, or use `gh` inside the repository.",
            )
        token = os.environ.get("GITHUB_TOKEN", "")
        query = urllib.parse.urlencode(
            {"state": "closed", "sort": "updated", "direction": "desc", "per_page": str(limit)}
        )
        url = f"https://api.github.com/repos/{self.slug}/pulls?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "canon-memory/1.0",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise GitHubError(
                "GitHub API request failed.",
                f"HTTP {exc.code}. Check that GITHUB_TOKEN has read-only access.",
            ) from exc
        except urllib.error.URLError as exc:
            raise GitHubError(
                "Canon could not reach the GitHub API.",
                "Check your network, or continue with local Git history.",
            ) from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GitHubError("GitHub API returned malformed JSON.") from exc
        if not isinstance(payload, list):
            raise GitHubError("GitHub API returned an unexpected payload.")
        parsed: list[PullRequest] = []
        for item in payload:
            pr = self._parse_pr(item)
            if pr and pr.merged_at:
                parsed.append(pr)
        return parsed[:limit]

    def _parse_pr(self, raw: Any) -> PullRequest | None:
        if not isinstance(raw, dict):
            return None
        number = raw.get("number")
        if not isinstance(number, int):
            return None
        title = sanitize_text(str(raw.get("title") or ""), limit=300)
        body = sanitize_text(str(raw.get("body") or ""), limit=4000)
        url = str(raw.get("url") or raw.get("html_url") or "")
        if url and not (url.startswith("https://github.com/") or url.startswith("http://github.com/")):
            # Keep only GitHub http(s) URLs. Never invent one.
            if "github.com" not in url:
                url = ""
        merged_at = raw.get("mergedAt") or raw.get("merged_at")
        merged_at_text = str(merged_at) if merged_at else None
        author_raw = raw.get("author") or raw.get("user") or {}
        author = None
        if isinstance(author_raw, dict):
            login = author_raw.get("login")
            if isinstance(login, str):
                author = sanitize_text(login, limit=80)
        merge_commit_raw = raw.get("mergeCommit") or raw.get("merge_commit_sha")
        merge_commit = None
        if isinstance(merge_commit_raw, dict):
            oid = merge_commit_raw.get("oid")
            if isinstance(oid, str):
                merge_commit = oid
        elif isinstance(merge_commit_raw, str):
            merge_commit = merge_commit_raw
        files_raw = raw.get("files") or []
        files: list[str] = []
        if isinstance(files_raw, list):
            for item in files_raw[:200]:
                if isinstance(item, dict):
                    path = item.get("path") or item.get("filename")
                    if isinstance(path, str):
                        files.append(path)
                elif isinstance(item, str):
                    files.append(item)
        return PullRequest(
            number=number,
            title=title,
            body=body,
            url=url,
            merged_at=merged_at_text,
            author=author,
            merge_commit=merge_commit,
            files=tuple(files),
            repository=self.slug or "unavailable",
        )


def github_error_hint(status: GitHubStatus) -> str:
    return redact(status.detail)
