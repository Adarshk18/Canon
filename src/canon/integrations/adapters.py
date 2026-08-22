"""Markdown/rule adapters for agents that load files, not SessionStart hooks.

Vendor memory (Claude auto-memory, Cursor/Codex/Grok memories) is agent-written
and local. These files carry human-confirmed Canon decisions instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from canon.config.settings import IntegrationSettings
from canon.gitutil.runner import which
from canon.integrations.managed import (
    remove_html_block,
    remove_managed_file,
    upsert_html_block,
    write_managed_file,
)


def adapter_inner(snapshot: str) -> str:
    return snapshot.strip() + "\n"


@dataclass(frozen=True, slots=True)
class MarkdownAdapter:
    name: str
    setting: str
    relative: Path
    mode: str  # "file" owns the whole file; "block" patches a managed section
    stub: str = ""
    detect_dirs: tuple[str, ...] = ()
    detect_bins: tuple[str, ...] = ()


ADAPTERS: tuple[MarkdownAdapter, ...] = (
    MarkdownAdapter(
        name="Grok Build",
        setting="grok",
        relative=Path(".grok") / "rules" / "canon.md",
        mode="file",
        detect_dirs=(".grok",),
        detect_bins=("grok",),
    ),
    MarkdownAdapter(
        name="AGENTS.md",
        setting="agents_md",
        relative=Path("AGENTS.md"),
        mode="block",
        stub="# Agent instructions\n\n",
    ),
    MarkdownAdapter(
        name="GitHub Copilot",
        setting="copilot",
        relative=Path(".github") / "copilot-instructions.md",
        mode="block",
        stub="# GitHub Copilot instructions\n\n",
        detect_dirs=(".github",),
        detect_bins=("gh",),
    ),
    MarkdownAdapter(
        name="Gemini CLI",
        setting="gemini",
        relative=Path("GEMINI.md"),
        mode="block",
        stub="# Gemini CLI instructions\n\n",
        detect_bins=("gemini",),
    ),
    MarkdownAdapter(
        name="Windsurf",
        setting="windsurf",
        relative=Path(".windsurf") / "rules" / "canon.md",
        mode="file",
        detect_dirs=(".windsurf",),
        detect_bins=("windsurf",),
    ),
    MarkdownAdapter(
        name="Cline",
        setting="cline",
        relative=Path(".clinerules") / "canon.md",
        mode="file",
        detect_dirs=(".clinerules", ".cline"),
        detect_bins=("cline",),
    ),
    MarkdownAdapter(
        name="Continue",
        setting="continue_ide",
        relative=Path(".continue") / "rules" / "canon.md",
        mode="file",
        detect_dirs=(".continue",),
    ),
)


def _enabled(settings: IntegrationSettings, name: str) -> bool:
    return bool(getattr(settings, name, True))


def detect_adapter(adapter: MarkdownAdapter, repo_root: Path) -> bool:
    if any((repo_root / directory).exists() for directory in adapter.detect_dirs):
        return True
    return any(which(binary) is not None for binary in adapter.detect_bins)


def sync_markdown_adapters(
    repo_root: Path,
    settings: IntegrationSettings,
    snapshot: str,
) -> list[str]:
    notes: list[str] = []
    inner = adapter_inner(snapshot)
    for adapter in ADAPTERS:
        if not _enabled(settings, adapter.setting):
            continue
        path = repo_root / adapter.relative
        if adapter.mode == "file":
            notes.append(write_managed_file(path, inner))
        else:
            notes.append(upsert_html_block(path, inner, stub=adapter.stub))
    return notes


def install_markdown_adapters(
    repo_root: Path,
    settings: IntegrationSettings,
    snapshot: str,
) -> list[str]:
    return sync_markdown_adapters(repo_root, settings, snapshot)


def uninstall_markdown_adapters(repo_root: Path) -> list[str]:
    notes: list[str] = []
    for adapter in ADAPTERS:
        path = repo_root / adapter.relative
        if adapter.mode == "file":
            note = remove_managed_file(path)
        else:
            note = remove_html_block(path)
        if note:
            notes.append(note)
    grok_hook = repo_root / ".grok" / "hooks" / "canon.json"
    note = remove_managed_file(grok_hook)
    if note:
        notes.append(note)
    return notes


def markdown_status(repo_root: Path) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    for adapter in ADAPTERS:
        path = repo_root / adapter.relative
        ok = path.is_file() and "BEGIN-CANON-MANAGED" in path.read_text(encoding="utf-8")
        detail = str(adapter.relative).replace("\\", "/")
        if ok:
            rows.append((adapter.name, True, f"Installed ({detail})"))
        elif detect_adapter(adapter, repo_root):
            rows.append((adapter.name, False, f"Detected, not wired ({detail})"))
        else:
            rows.append((adapter.name, False, f"Not installed ({detail})"))
    return rows
