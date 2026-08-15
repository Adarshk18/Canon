from __future__ import annotations

from pathlib import Path

import pytest

from canon.errors import SecurityError
from canon.security.paths import ensure_under, safe_join


def test_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        safe_join(tmp_path, "..", "etc", "passwd")


def test_accepts_child(tmp_path: Path) -> None:
    target = safe_join(tmp_path, "canon.db")
    assert target.parent == tmp_path.resolve()


def test_ensure_under_blocks_escape(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        ensure_under(tmp_path.parent / "outside.txt", tmp_path)
