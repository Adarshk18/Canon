from __future__ import annotations

import json
from pathlib import Path

from canon.config.settings import IntegrationSettings
from canon.integrations.adapters import install_markdown_adapters, uninstall_markdown_adapters
from canon.integrations.claude import install_claude, uninstall_claude
from canon.integrations.cursor import install_cursor, uninstall_cursor
from canon.integrations.managed import upsert_html_block
from canon.integrations.wire import install_all, uninstall_all


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


def test_agents_md_block_does_not_clobber_user_text(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text("# Agent instructions\n\nUse pytest.\n", encoding="utf-8")
    upsert_html_block(path, "Use PostgreSQL.\n", stub="# Agent instructions\n\n")
    upsert_html_block(path, "Use PostgreSQL.\n", stub="# Agent instructions\n\n")
    text = path.read_text(encoding="utf-8")
    assert text.count("BEGIN-CANON-MANAGED") == 1
    assert "Use pytest." in text
    assert "Use PostgreSQL." in text


def test_markdown_adapters_and_uninstall(tmp_path: Path) -> None:
    settings = IntegrationSettings()
    notes = install_markdown_adapters(tmp_path, settings, "Use PostgreSQL instead of MongoDB.")
    assert notes
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "BEGIN-CANON-MANAGED" in agents
    assert "PostgreSQL" in agents
    grok = tmp_path / ".grok" / "rules" / "canon.md"
    assert grok.is_file()
    assert "PostgreSQL" in grok.read_text(encoding="utf-8")
    removed = uninstall_markdown_adapters(tmp_path)
    assert removed
    assert not grok.exists()


def test_install_all_is_idempotent_and_wires_mcp(tmp_path: Path) -> None:
    settings = IntegrationSettings()
    first = install_all(tmp_path, settings, "I have no confirmed decision on this.")
    second = install_all(tmp_path, settings, "I have no confirmed decision on this.")
    assert first
    assert second
    mcp = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["canon"]["args"] == ["mcp"]
    settings_json = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    handlers = [
        h for group in settings_json["hooks"]["SessionStart"] for h in group["hooks"]
    ]
    assert sum(1 for h in handlers if "--for-hook" in h.get("args", [])) == 1
    uninstall_all(tmp_path)
    leftover = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    session = leftover.get("hooks", {}).get("SessionStart", [])
    assert session == [] or all("--for-hook" not in str(group) for group in session)
