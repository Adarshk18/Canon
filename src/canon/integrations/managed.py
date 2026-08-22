"""Insert or replace Canon-managed blocks without rewriting user files."""

from __future__ import annotations

import re
from pathlib import Path

from canon.constants import MANAGED_BEGIN, MANAGED_END

_HTML_BLOCK = re.compile(
    rf"<!--\s*{re.escape(MANAGED_BEGIN)}\s*-->.*?<!--\s*{re.escape(MANAGED_END)}\s*-->\n?",
    re.DOTALL,
)
_HASH_BLOCK = re.compile(
    rf"# {re.escape(MANAGED_BEGIN)}.*?# {re.escape(MANAGED_END)}\n?",
    re.DOTALL,
)


def html_block(inner: str) -> str:
    body = inner.strip("\n")
    return f"<!-- {MANAGED_BEGIN} -->\n{body}\n<!-- {MANAGED_END} -->\n"


def hash_block(inner: str) -> str:
    body = inner.strip("\n")
    return f"# {MANAGED_BEGIN}\n{body}\n# {MANAGED_END}\n"


def upsert_html_block(path: Path, inner: str, *, stub: str = "") -> str:
    """Write or replace an HTML-comment managed block. Returns a short change note."""
    block = html_block(inner)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text((stub + block) if stub else block, encoding="utf-8")
        return f"Wrote {path.as_posix()}"
    existing = path.read_text(encoding="utf-8")
    if _HTML_BLOCK.search(existing):
        updated = _HTML_BLOCK.sub(block, existing, count=1)
    else:
        prefix = existing if existing.endswith("\n") else existing + "\n"
        updated = prefix + "\n" + block
    if updated == existing:
        return f"Unchanged {path.as_posix()}"
    path.write_text(updated, encoding="utf-8")
    return f"Updated {path.as_posix()}"


def remove_html_block(path: Path, *, delete_if_empty: bool = True) -> str | None:
    if not path.is_file():
        return None
    existing = path.read_text(encoding="utf-8")
    if MANAGED_BEGIN not in existing:
        return None
    updated = _HTML_BLOCK.sub("", existing)
    updated = _HASH_BLOCK.sub("", updated)
    leftover = updated.strip()
    if delete_if_empty and len(leftover) < 80:
        path.unlink()
        return f"Removed {path.as_posix()}"
    if updated != existing:
        path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
        return f"Removed Canon block from {path.as_posix()}"
    return None


def write_managed_file(path: Path, inner: str) -> str:
    """A file that Canon owns entirely (HTML-comment wrapped)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = html_block(inner)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return f"Unchanged {path.as_posix()}"
    path.write_text(text, encoding="utf-8")
    return f"Wrote {path.as_posix()}"


def remove_managed_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if MANAGED_BEGIN not in text:
        return None
    path.unlink()
    return f"Removed {path.as_posix()}"
