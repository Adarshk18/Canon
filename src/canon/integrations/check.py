"""Deterministic drift check: catch PRs that re-introduce a rejected decision."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from canon.core.models import Decision
from canon.gitutil.repo import GitRepo
from canon.security.sanitize import sanitize_text

_TOKEN = re.compile(r"[a-z0-9]{4,}")
_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "instead",
        "because",
        "using",
        "decision",
        "should",
        "would",
        "could",
        "about",
        "after",
        "before",
        "into",
        "just",
        "have",
        "been",
        "were",
        "will",
        "your",
        "their",
        "them",
        "then",
        "than",
        "also",
        "only",
        "when",
        "what",
        "which",
        "make",
        "made",
        "need",
        "needs",
        "used",
        "uses",
        "over",
        "under",
        "project",
        "application",
        "persistent",
        "relational",
        "custom",
    }
)


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if token not in _STOP}


@dataclass(slots=True)
class Finding:
    kind: str
    decision_id: int | None
    title: str
    detail: str
    severity: str  # "error" | "warning"

    def to_row(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "decision_id": self.decision_id,
            "title": self.title,
            "detail": self.detail,
            "severity": self.severity,
        }


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def github_event_text() -> str:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        return ""
    event_path = Path(path)
    if not event_path.is_file():
        return ""
    try:
        payload = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    parts: list[str] = []
    pr = payload.get("pull_request")
    if isinstance(pr, dict):
        parts.append(str(pr.get("title") or ""))
        parts.append(str(pr.get("body") or ""))
    parts.append(str(payload.get("head_commit", {}).get("message") or ""))
    return "\n".join(parts)


def repo_text(repo: GitRepo) -> str:
    parts: list[str] = [github_event_text()]
    log = repo.run("log", "-1", "--pretty=%s%n%n%b", check=False)
    if log.ok:
        parts.append(log.stdout)
    names = repo.run("diff", "--name-only", "HEAD", check=False)
    if names.ok:
        parts.append(names.stdout)
    cached = repo.run("diff", "--cached", "--name-only", check=False)
    if cached.ok:
        parts.append(cached.stdout)
    parts.extend(repo.changed_files())
    return "\n".join(parts)


def check_decisions(
    *,
    rejected: list[Decision],
    text: str,
) -> list[Finding]:
    haystack = _tokens(sanitize_text(text, limit=20_000))
    findings: list[Finding] = []
    for item in rejected:
        title_tokens = _tokens(item.title)
        body_tokens = _tokens(item.body)
        title_ratio = overlap_ratio(title_tokens, haystack)
        body_ratio = overlap_ratio(body_tokens, haystack)
        if title_ratio >= 0.6 or (title_ratio >= 0.4 and body_ratio >= 0.3):
            findings.append(
                Finding(
                    kind="rejected_reintroduced",
                    decision_id=item.id,
                    title=item.title,
                    detail=(
                        f"This change looks like rejected decision #{item.id}. "
                        "Do not re-adopt a rejected approach."
                    ),
                    severity="error",
                )
            )
    return findings


def github_annotations(findings: list[Finding]) -> list[str]:
    lines: list[str] = []
    for item in findings:
        level = "error" if item.severity == "error" else "warning"
        lines.append(f"::{level} title=Canon::{item.detail}")
    return lines
