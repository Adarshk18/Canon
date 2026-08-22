"""Install, refresh, and remove every agent integration Canon owns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from canon.config.settings import IntegrationSettings
from canon.integrations.adapters import (
    install_markdown_adapters,
    markdown_status,
    uninstall_markdown_adapters,
)
from canon.integrations.claude import (
    claude_status,
    install_claude,
    uninstall_claude,
)
from canon.integrations.cursor import (
    cursor_status,
    install_cursor,
    uninstall_cursor,
)

MCP_REL = Path(".mcp.json")
CURSOR_MCP_REL = Path(".cursor") / "mcp.json"
GROK_HOOK_REL = Path(".grok") / "hooks" / "canon.json"


def _mcp_server() -> dict[str, Any]:
    return {"command": "canon", "args": ["mcp"]}


def _is_canon_mcp(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    args = entry.get("args")
    command = str(entry.get("command") or "")
    if isinstance(args, list) and "mcp" in args and "canon" in command:
        return True
    return command.endswith("canon") and entry.get("args") == ["mcp"]


def merge_mcp_file(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    existing = servers.get("canon")
    desired = _mcp_server()
    if existing == desired:
        return f"Unchanged {path.as_posix()}"
    servers["canon"] = desired
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"Wrote {path.as_posix()}"


def unmerge_mcp_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers"), dict):
        return None
    servers = data["mcpServers"]
    if "canon" not in servers:
        return None
    if not _is_canon_mcp(servers.get("canon")):
        return None
    del servers["canon"]
    if servers:
        data["mcpServers"] = servers
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return f"Removed Canon MCP from {path.as_posix()}"
    path.unlink()
    return f"Removed {path.as_posix()}"


def install_grok_hook(repo_root: Path) -> str:
    path = repo_root / GROK_HOOK_REL
    payload = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "canon inject --refresh-files",
                            "timeout": 15,
                        }
                    ]
                }
            ]
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return f"Unchanged {path.as_posix()}"
    path.write_text(text, encoding="utf-8")
    return f"Wrote {path.as_posix()}"


def uninstall_grok_hook(repo_root: Path) -> str | None:
    path = repo_root / GROK_HOOK_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    blob = json.dumps(data)
    if "canon inject --refresh-files" not in blob:
        return None
    path.unlink()
    return f"Removed {path.as_posix()}"


def install_all(
    repo_root: Path,
    settings: IntegrationSettings,
    snapshot: str,
) -> list[str]:
    notes: list[str] = []
    if settings.claude:
        notes.extend(install_claude(repo_root))
    if settings.cursor:
        notes.extend(install_cursor(repo_root))
    if settings.grok:
        notes.append(install_grok_hook(repo_root))
    notes.extend(install_markdown_adapters(repo_root, settings, snapshot))
    if settings.mcp:
        notes.append(merge_mcp_file(repo_root / MCP_REL))
        if settings.cursor:
            notes.append(merge_mcp_file(repo_root / CURSOR_MCP_REL))
    return notes


def sync_all(
    repo_root: Path,
    settings: IntegrationSettings,
    snapshot: str,
) -> list[str]:
    return install_all(repo_root, settings, snapshot)


def uninstall_all(repo_root: Path) -> list[str]:
    notes: list[str] = []
    notes.extend(uninstall_claude(repo_root))
    notes.extend(uninstall_cursor(repo_root))
    hook = uninstall_grok_hook(repo_root)
    if hook:
        notes.append(hook)
    notes.extend(uninstall_markdown_adapters(repo_root))
    mcp = unmerge_mcp_file(repo_root / MCP_REL)
    if mcp:
        notes.append(mcp)
    cursor_mcp = unmerge_mcp_file(repo_root / CURSOR_MCP_REL)
    if cursor_mcp:
        notes.append(cursor_mcp)
    return notes


def status_all(repo_root: Path) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    rows.append(("Claude Code", *claude_status(repo_root)))
    rows.append(("Cursor", *cursor_status(repo_root)))
    grok_hook = repo_root / GROK_HOOK_REL
    grok_ok = grok_hook.is_file() and "canon inject" in grok_hook.read_text(encoding="utf-8")
    rows.append(
        (
            "Grok Build hook",
            grok_ok,
            "SessionStart refresh hook installed" if grok_ok else "Grok hook not installed",
        )
    )
    rows.extend(markdown_status(repo_root))
    mcp_path = repo_root / MCP_REL
    mcp_ok = False
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers") if isinstance(data, dict) else None
            mcp_ok = isinstance(servers, dict) and _is_canon_mcp(servers.get("canon"))
        except json.JSONDecodeError:
            mcp_ok = False
    rows.append(
        (
            "MCP",
            mcp_ok,
            "stdio server wired in .mcp.json" if mcp_ok else "MCP not installed",
        )
    )
    return rows
