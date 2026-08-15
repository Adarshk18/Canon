from __future__ import annotations

import re

from canon.decisions.validation import normalize_body, normalize_title
from canon.security.sanitize import sanitize_text, strip_dangerous_lines


def extract_title(raw_title: str, category: str | None) -> str:
    text = sanitize_text(raw_title, limit=200).strip()
    text = re.sub(r"^(feat|fix|chore|refactor|docs|perf|build|ci)(\(.+?\))?(!)?:\s*", "", text, flags=re.I)
    switch = re.search(r"(?i)switch(?:ed|ing)? to ([^,;]+?)(?:\s+(?:instead|because|for)\b|$)", text)
    if switch:
        return normalize_title(f"Use {switch.group(1).strip().rstrip('.')}")
    replace = re.search(r"(?i)replace[sd]? (.+?) with (.+)", text)
    if replace:
        return normalize_title(f"Use {replace.group(2).strip()} instead of {replace.group(1).strip()}")
    migrate = re.search(r"(?i)migrat(?:e|ed|ing) (?:from .+? )?to ([^,;]+?)(?:\s+(?:instead|because|for)\b|$)", text)
    if migrate:
        return normalize_title(f"Use {migrate.group(1).strip().rstrip('.')}")
    instead = re.search(r"(?i)use (.+?) instead of (.+)", text)
    if instead:
        return normalize_title(f"Use {instead.group(1).strip()} instead of {instead.group(2).strip()}")
    renamed = re.search(r"(?i)rename\s+(.+?)\s+to\s+(.+?)(?:\s+end-to-end)?$", text)
    if renamed:
        old = renamed.group(1).strip().rstrip(".")
        new = renamed.group(2).strip().rstrip(".")
        return normalize_title(f"Use the name {new} instead of {old}")
    dropped = re.search(r"(?i)drop(?:ped|ping)?\s+(.+?)(?:,| and |$)", text)
    if dropped:
        return normalize_title(f"Do not keep {dropped.group(1).strip().rstrip('.')}")
    only = re.search(r"(?i)show only\s+(.+)", text)
    if only:
        return normalize_title(f"Show only {only.group(1).strip().rstrip('.')}")
    if category and not text.lower().startswith("use "):
        return normalize_title(text)
    return normalize_title(text)


def extract_body(raw_body: str, evidence: str) -> str:
    text = sanitize_text(raw_body, limit=1500).strip()
    text = strip_dangerous_lines(text)
    text = re.sub(r"(?i)^co-authored-by:.*$", "", text, flags=re.M)
    text = re.sub(r"(?i)^signed-off-by:.*$", "", text, flags=re.M)
    text = re.sub(r"(?i)^\[quoted:.*$", "", text, flags=re.M)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chosen = paragraphs[0] if paragraphs else text
    sentences = re.split(r"(?<=[.!?])\s+", chosen)
    summary = " ".join(sentences[:3]).strip()
    if not summary:
        summary = f"Evidence: {evidence}. Confirm only if this reflects a real project decision."
    return normalize_body(summary)
