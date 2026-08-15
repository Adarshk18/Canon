from __future__ import annotations

import hashlib
import re

from canon.errors import UsageError
from canon.security.sanitize import sanitize_text

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9\-_/]{0,40}$")


def normalize_title(title: str) -> str:
    cleaned = sanitize_text(title, limit=160).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        raise UsageError("A decision title is required.")
    return cleaned


def normalize_body(body: str) -> str:
    cleaned = sanitize_text(body, limit=2000).strip()
    if not cleaned:
        return "No additional rationale was provided."
    return cleaned


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in tags:
        tag = sanitize_text(raw, limit=40).strip().lower().replace(" ", "-")
        if not tag or tag in seen:
            continue
        if not _TAG_RE.match(tag):
            continue
        seen.add(tag)
        result.append(tag)
    return result[:12]


def fingerprint(
    *,
    source_type: str | None,
    source_pr: str | None,
    source_commit: str | None,
    title: str,
) -> str:
    if source_type == "pr" and source_pr:
        seed = f"pr:{source_pr}"
    elif source_type == "commit" and source_commit:
        seed = f"commit:{source_commit}"
    else:
        seed = f"title:{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
