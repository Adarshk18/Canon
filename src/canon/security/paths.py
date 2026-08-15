from __future__ import annotations

from pathlib import Path

from canon.errors import SecurityError


def resolve_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def ensure_under(path: Path, root: Path, *, label: str = "path") -> Path:
    """Reject path traversal and unexpected symlink escapes."""
    resolved = resolve_path(path)
    root_resolved = resolve_path(root)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SecurityError(
            f"Refusing to use {label} outside the allowed directory.",
            f"Path: {resolved}\nAllowed root: {root_resolved}",
        ) from exc
    return resolved


def safe_join(root: Path, *parts: str) -> Path:
    for part in parts:
        if part in ("", ".", "..") or "/" in part or "\\" in part:
            if part in {".", ""}:
                continue
            if any(seg in ("..", "") for seg in Path(part).parts):
                raise SecurityError(
                    "Refusing a path that contains traversal segments.",
                    f"Rejected: {part!r}",
                )
    candidate = root.joinpath(*parts)
    return ensure_under(candidate, root)


def is_probably_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False
