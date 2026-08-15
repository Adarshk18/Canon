from __future__ import annotations

import json
from pathlib import Path

from canon.integrations.claude import install_claude, uninstall_claude
from canon.integrations.cursor import install_cursor, uninstall_cursor


def test_claude_hook_is_idempotent(tmp_path: Path) -> None:
    first = install_claude(tmp_path)
    second = install_claude(tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]["SessionStart"]
    handlers = [h for group in hooks for h in group["hooks"]]
    assert sum(1 for h in handlers if "--for-hook" in h.get("args", [])) == 1
    assert any("already" in line.lower() for line in second) or first
    removed = uninstall_claude(tmp_path)
    assert removed
    leftover = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    session = leftover.get("hooks", {}).get("SessionStart", [])
    assert session == [] or all(
        "--for-hook" not in str(group) for group in session
    )


def test_cursor_rule_always_apply(tmp_path: Path) -> None:
    install_cursor(tmp_path)
    install_cursor(tmp_path)
    text = (tmp_path / ".cursor" / "rules" / "canon.mdc").read_text(encoding="utf-8")
    assert "alwaysApply: true" in text
    assert ".canon/injection.md" in text
    uninstall_cursor(tmp_path)
    assert not (tmp_path / ".cursor" / "rules" / "canon.mdc").exists()
