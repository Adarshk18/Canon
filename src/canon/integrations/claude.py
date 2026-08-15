"""Claude Code SessionStart hook integration.

Official contract (https://code.claude.com/docs/en/hooks, Aug 2026):
- SessionStart fires on startup/resume/clear/compact/fork.
- type=command with args uses exec form (no shell).
- Exit 0 + plain stdout is injected as context for SessionStart.
- hookSpecificOutput.additionalContext is also supported.
- Output is capped at 10,000 characters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from canon.constants import HOOK_FLAG, MANAGED_BEGIN, MANAGED_END
from canon.gitutil.runner import which

SETTINGS_REL = Path(".claude") / "settings.json"
RULE_REL = Path(".claude") / "rules" / "canon.md"

CLAUDE_RULE = f"""# {MANAGED_BEGIN}
# Canon — governed project decisions
#
# Treat confirmed Canon decisions as authoritative project context.
# Prefer `.canon/injection.md` and SessionStart hook output over guesswork.
# If no confirmed decision applies, say you have no confirmed decision
# rather than inventing a convention.
# {MANAGED_END}
"""


def detect_claude(repo_root: Path) -> bool:
    return (repo_root / ".claude").is_dir() or which("claude") is not None


def _canon_hook() -> dict[str, Any]:
    return {
        "type": "command",
        "command": "canon",
        "args": ["inject", HOOK_FLAG],
        "timeout": 15,
        "statusMessage": "Loading Canon project decisions",
    }


def _is_canon_hook(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    args = handler.get("args")
    command = str(handler.get("command") or "")
    if isinstance(args, list) and HOOK_FLAG in args:
        return True
    return "canon" in command and "inject" in command


def install_claude(repo_root: Path) -> list[str]:
    changes: list[str] = []
    settings_path = repo_root / SETTINGS_REL
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if settings_path.is_file():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    groups = hooks.setdefault("SessionStart", [])
    if not isinstance(groups, list):
        groups = []
        hooks["SessionStart"] = groups

    found = False
    for group in groups:
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            continue
        if any(_is_canon_hook(item) for item in handlers):
            found = True
            break
    if not found:
        groups.append(
            {
                "matcher": "startup|resume|clear|compact|fork",
                "hooks": [_canon_hook()],
            }
        )
        settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        changes.append(f"Installed Claude Code SessionStart hook in {SETTINGS_REL}")
    else:
        changes.append("Claude Code SessionStart hook already present")

    rule_path = repo_root / RULE_REL
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    if not rule_path.is_file() or MANAGED_BEGIN not in rule_path.read_text(encoding="utf-8"):
        rule_path.write_text(CLAUDE_RULE, encoding="utf-8")
        changes.append(f"Wrote {RULE_REL}")
    else:
        changes.append("Claude Code Canon rule already present")
    return changes


def uninstall_claude(repo_root: Path) -> list[str]:
    changes: list[str] = []
    settings_path = repo_root / SETTINGS_REL
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            hooks = data.get("hooks")
            if isinstance(hooks, dict) and isinstance(hooks.get("SessionStart"), list):
                new_groups = []
                for group in hooks["SessionStart"]:
                    if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                        new_groups.append(group)
                        continue
                    handlers = [h for h in group["hooks"] if not _is_canon_hook(h)]
                    if handlers:
                        group = dict(group)
                        group["hooks"] = handlers
                        new_groups.append(group)
                hooks["SessionStart"] = new_groups
                if not hooks["SessionStart"]:
                    del hooks["SessionStart"]
                if not hooks:
                    data.pop("hooks", None)
                settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                changes.append(f"Removed Canon hook from {SETTINGS_REL}")
    rule_path = repo_root / RULE_REL
    if rule_path.is_file() and MANAGED_BEGIN in rule_path.read_text(encoding="utf-8"):
        rule_path.unlink()
        changes.append(f"Removed {RULE_REL}")
    return changes


def claude_status(repo_root: Path) -> tuple[bool, str]:
    settings_path = repo_root / SETTINGS_REL
    if not settings_path.is_file():
        return False, "Claude Code settings not found"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "Claude Code settings are not valid JSON"
    hooks = data.get("hooks") if isinstance(data, dict) else None
    groups = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    if isinstance(groups, list):
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(handlers, list) and any(_is_canon_hook(item) for item in handlers):
                return True, "SessionStart hook installed"
    return False, "SessionStart hook not installed"
