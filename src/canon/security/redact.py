from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)(\S+)"),
    re.compile(r"(?i)(token[=:\s]+)([A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(?i)(secret[=:\s]+)(\S+)"),
    re.compile(r"(?i)(password[=:\s]+)(\S+)"),
    re.compile(r"(?i)(api[_-]?key[=:\s]+)(\S+)"),
    re.compile(r"(?i)(ghp_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"(?i)(gho_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(sk-[A-Za-z0-9]{16,})"),
)


def redact(text: str) -> str:
    """Remove secret-shaped values from log/error strings."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1[redacted]", redacted)
        else:
            redacted = pattern.sub("[redacted]", redacted)
    return redacted
