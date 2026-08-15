from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import typer
from rich.prompt import Confirm, Prompt

from canon import PRODUCT_NAME, __version__
from canon.config.paths import ProjectPaths
from canon.config.settings import load_settings, merge_set, write_settings
from canon.constants import GITIGNORE_ENTRIES, HOOK_FLAG
from canon.core.models import Decision, DecisionStatus
from canon.core.timeutil import format_date
from canon.db.store import Store
from canon.errors import CanonError, NotInitializedError, UsageError
from canon.githubutil.client import GitHubClient
from canon.gitutil.repo import find_git_root
from canon.gitutil.runner import which
from canon.integrations.claude import (
    claude_status,
    detect_claude,
    install_claude,
    uninstall_claude,
)
from canon.integrations.cursor import (
    cursor_status,
    detect_cursor,
    install_cursor,
    uninstall_cursor,
)
from canon.integrations.snapshot import refresh_injection_files, select_for_injection
from canon.mining.engine import mine_candidates
from canon.output.console import Console
from canon.runtime import Runtime, configure_logging, load_runtime
from canon.security.paths import resolve_path
from canon.security.redact import redact

app = typer.Typer(
    name="canon",
    help="Canon — governed project decision memory for AI coding agents.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

state: dict[str, Any] = {"json": False, "debug": False}


def _version_option(value: bool) -> None:
    if not value:
        return
    if state.get("json"):
        Console(force_json=True).emit_json({"name": PRODUCT_NAME, "version": __version__})
    else:
        Console().print(f"{PRODUCT_NAME} {__version__}")
    raise typer.Exit(0)


def _console() -> Console:
    return Console(force_json=bool(state.get("json")))


def _json_flag() -> Any:
    return typer.Option(False, "--json", help="Machine-readable JSON output.")


def _use_json(json_output: bool) -> Console:
    if json_output:
        state["json"] = True
    return _console()


def _runtime(*, require_init: bool = True) -> Runtime:
    return load_runtime(require_init=require_init)


def _print_decision(console: Console, decision: Decision, *, verbose: bool = False) -> None:
    status = decision.status.value.upper()
    ident = f"#{decision.id}" if decision.id is not None else "#?"
    console.print(f"{ident}  {status}  {decision.title}")
    if decision.superseded_by_id:
        console.print(f"  Superseded by: #{decision.superseded_by_id}")
    if decision.supersedes_id:
        console.print(f"  Supersedes: #{decision.supersedes_id}")
    if verbose:
        console.print(f"  {decision.body}")
        for line in decision.provenance_lines():
            console.print(f"  {line}")


def _ensure_gitignore(repo_root: Path) -> bool:
    path = repo_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    missing = [entry for entry in GITIGNORE_ENTRIES if entry not in existing.splitlines()]
    if not missing:
        return False
    block = "\n".join(["", "# Canon", *missing, ""])
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + block, encoding="utf-8")
    return True


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_option,
        is_eager=True,
    ),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs and tracebacks."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Governed project decision memory for AI coding agents."""
    if os.environ.get("CANON_DEBUG") in {"1", "true", "yes"}:
        debug = True
    state["json"] = json_output
    state["debug"] = debug
    configure_logging(debug)


@app.command("version")
def version_cmd(json_output: bool = _json_flag()) -> None:
    """Show the Canon version."""
    console = _use_json(json_output)
    if console.json_mode:
        console.emit_json({"name": PRODUCT_NAME, "version": __version__})
    else:
        console.print(f"{PRODUCT_NAME} {__version__}")


@app.command("init")
def init_cmd(json_output: bool = _json_flag()) -> None:
    """Initialize Canon in the current Git repository. Safe to run repeatedly."""
    console = _use_json(json_output)
    root = find_git_root()
    repo_note = []
    paths = ProjectPaths.from_repo(root)
    paths.canon_dir.mkdir(parents=True, exist_ok=True)
    settings = load_settings(paths)
    created_config = not paths.config_file.is_file()
    if created_config:
        write_settings(paths.config_file, settings)
        repo_note.append(f"Created {paths.config_file.relative_to(root)}")
    else:
        repo_note.append("Project config already present")

    store = Store(paths.db_file)
    repo_note.append(f"SQLite schema version {store.schema_version()}")
    store.close()

    if _ensure_gitignore(root):
        repo_note.append("Updated .gitignore with Canon local files")
    else:
        repo_note.append(".gitignore already lists Canon local files")

    if settings.integrations.claude or detect_claude(root):
        repo_note.extend(install_claude(root))
    else:
        repo_note.append("Claude Code not detected; skipped hook install")

    if settings.integrations.cursor or detect_cursor(root):
        repo_note.extend(install_cursor(root))
    else:
        repo_note.append("Cursor not detected; skipped rule install")

    runtime = load_runtime(require_init=True)
    try:
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        repo_note.append("Wrote .canon/injection.md")
    finally:
        runtime.close()

    if console.json_mode:
        console.emit_json({"ok": True, "repo": str(root), "changes": repo_note})
        return
    console.print(f"Initialized {PRODUCT_NAME} in {root}")
    for line in repo_note:
        console.print(f"  • {line}")
    console.print("")
    console.print("Next:  canon suggest")


@app.command("status")
def status_cmd(json_output: bool = _json_flag()) -> None:
    """Show Canon, Git, GitHub, and agent integration status."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        counts = runtime.store.counts()
        github = GitHubClient(runtime.repo).status()
        claude_ok, claude_msg = claude_status(runtime.paths.repo_root)
        cursor_ok, cursor_msg = cursor_status(runtime.paths.repo_root)
        payload = {
            "product": PRODUCT_NAME,
            "version": __version__,
            "repo": str(runtime.paths.repo_root),
            "database": str(runtime.paths.db_file),
            "schema_version": runtime.store.schema_version(),
            "decisions": counts,
            "branch": runtime.repo.current_branch(),
            "github": {
                "available": github.available,
                "authenticated": github.authenticated,
                "method": github.method,
                "detail": github.detail,
            },
            "claude": {"ok": claude_ok, "detail": claude_msg},
            "cursor": {"ok": cursor_ok, "detail": cursor_msg},
            "telemetry": runtime.settings.privacy.telemetry,
        }
        if console.json_mode:
            console.emit_json(payload)
            return
        console.print(f"{PRODUCT_NAME} {__version__}")
        console.print(f"Repo:     {runtime.paths.repo_root}")
        console.print(f"Database: {runtime.paths.db_file}")
        console.print(
            "Decisions: "
            f"{counts['active']} active, {counts['candidate']} candidate, "
            f"{counts['superseded']} superseded, {counts['rejected']} rejected"
        )
        console.print(f"GitHub:   {github.detail}")
        console.print(f"Claude:   {claude_msg}")
        console.print(f"Cursor:   {cursor_msg}")
        console.print(
            "Telemetry: "
            + ("local opt-in log" if runtime.settings.privacy.telemetry else "off")
        )
    finally:
        runtime.close()


@app.command("suggest")
def suggest_cmd(
    review: bool = typer.Option(
        False, "--review", help="Interactively approve or reject new candidates."
    ),
    json_output: bool = _json_flag(),
) -> None:
    """Mine recent merged PRs or Git history for candidate decisions."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        result = mine_candidates(
            repo=runtime.repo, service=runtime.service, settings=runtime.settings
        )
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        candidates = runtime.service.list_decisions(statuses=[DecisionStatus.CANDIDATE])
        payload = {
            "created": result.created,
            "skipped": result.skipped,
            "inspected": result.inspected,
            "source": result.source,
            "warning": result.warning,
            "candidates": [item.to_row() for item in candidates],
        }
        if console.json_mode:
            console.emit_json(payload)
            return
        if result.warning:
            console.print(result.warning)
            console.print("")
        if result.created == 0 and not candidates:
            console.print(
                "No high-confidence decisions found. "
                "Canon prefers precision over recall."
            )
            return
        console.print(
            f"Inspected {result.inspected} sources via {result.source}. "
            f"Created {result.created} candidate(s), skipped {result.skipped}."
        )
        console.print("")
        for item in candidates:
            _print_decision(console, item, verbose=True)
            console.print("")
        if review and candidates and sys.stdin.isatty():
            _review_candidates(console, runtime, candidates)
    finally:
        runtime.close()


def _review_candidates(
    console: Console, runtime: Runtime, candidates: list[Decision]
) -> None:
    console.print(f"Canon found {len(candidates)} candidate decision(s).")
    for index, item in enumerate(candidates, start=1):
        assert item.id is not None
        console.print(f"[{index}/{len(candidates)}]")
        _print_decision(console, item, verbose=True)
        answer = Prompt.ask("Approve?", choices=["Y", "n", "s"], default="Y")
        if answer.lower() == "y":
            approved, superseded = runtime.service.approve(
                item.id, confirmed_by=runtime.repo.identity()
            )
            console.print(f"Approved #{approved.id}.")
            if superseded:
                console.print(
                    f"Decision #{superseded.id} is now SUPERSEDED by #{approved.id}."
                )
        elif answer.lower() == "n":
            runtime.service.reject(item.id)
            console.print(f"Rejected #{item.id}.")
        else:
            console.print("Skipped.")
        console.print("")
    refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)


@app.command("approve")
def approve_cmd(
    decision_id: int | None = typer.Argument(None, help="Decision id to approve."),
    supersedes: int | None = typer.Option(
        None, "--supersedes", help="Active decision this one replaces."
    ),
    json_output: bool = _json_flag(),
) -> None:
    """Approve a candidate. Turns it active. May supersede an older decision."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        if decision_id is None:
            candidates = runtime.service.list_decisions(statuses=[DecisionStatus.CANDIDATE])
            if not candidates:
                raise UsageError("There are no candidate decisions to approve.")
            if not sys.stdin.isatty():
                raise UsageError(
                    "Pass a decision id in non-interactive mode.",
                    "Example: canon approve 3",
                )
            _review_candidates(console, runtime, candidates)
            return
        approved, superseded = runtime.service.approve(
            decision_id,
            confirmed_by=runtime.repo.identity(),
            supersedes_id=supersedes,
        )
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        payload = {
            "approved": approved.to_row(),
            "superseded": superseded.to_row() if superseded else None,
        }
        if console.json_mode:
            console.emit_json(payload)
            return
        console.print(f"Decision #{approved.id}")
        console.print("Status: ACTIVE")
        if superseded:
            console.print(f"Supersedes: #{superseded.id}")
            console.print(f"Decision #{superseded.id}")
            console.print("Status: SUPERSEDED")
            console.print(f"Superseded by: #{approved.id}")
    finally:
        runtime.close()


@app.command("reject")
def reject_cmd(
    decision_id: int = typer.Argument(..., help="Decision id to reject."),
    reason: str | None = typer.Option(None, "--reason", help="Optional rejection note."),
    json_output: bool = _json_flag(),
) -> None:
    """Reject a candidate. The record is kept."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        rejected = runtime.service.reject(decision_id, reason=reason)
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        if console.json_mode:
            console.emit_json(rejected.to_row())
            return
        console.print(f"Decision #{rejected.id}")
        console.print("Status: REJECTED")
    finally:
        runtime.close()


@app.command("list")
def list_cmd(
    active: bool = typer.Option(False, "--active", help="Only active decisions."),
    superseded: bool = typer.Option(False, "--superseded", help="Only superseded."),
    rejected: bool = typer.Option(False, "--rejected", help="Only rejected."),
    candidate: bool = typer.Option(False, "--candidate", help="Only candidates."),
    all_rows: bool = typer.Option(False, "--all", help="Every status, including history."),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
    json_output: bool = _json_flag(),
) -> None:
    """List decisions. Default: active."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        statuses: list[DecisionStatus]
        if all_rows:
            statuses = list(DecisionStatus)
        else:
            selected: list[DecisionStatus] = []
            if active:
                selected.append(DecisionStatus.ACTIVE)
            if superseded:
                selected.append(DecisionStatus.SUPERSEDED)
            if rejected:
                selected.append(DecisionStatus.REJECTED)
            if candidate:
                selected.append(DecisionStatus.CANDIDATE)
            statuses = selected or [DecisionStatus.ACTIVE]
        rows = runtime.service.list_decisions(statuses=statuses, tag=tag)
        if console.json_mode:
            console.emit_json([item.to_row() for item in rows])
            return
        if not rows:
            console.print("No decisions match.")
            return
        table_rows = []
        for item in rows:
            table_rows.append(
                [
                    str(item.id or ""),
                    item.status.value.upper(),
                    item.title,
                    item.evidence or "—",
                    format_date(item.confirmed_at or item.source_date),
                ]
            )
        console.table(
            "Canon decisions",
            ["ID", "Status", "Title", "Source", "Date"],
            table_rows,
        )
    finally:
        runtime.close()


@app.command("show")
def show_cmd(
    decision_id: int = typer.Argument(..., help="Decision id."),
    json_output: bool = _json_flag(),
) -> None:
    """Show one decision, including provenance and history links."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        decision = runtime.service.get(decision_id)
        if console.json_mode:
            console.emit_json(decision.to_row())
            return
        console.print(f"Decision #{decision.id}")
        console.print(f"Status: {decision.status.value.upper()}")
        console.print(decision.title)
        console.print("")
        console.print(decision.body)
        console.print("")
        for line in decision.provenance_lines():
            console.print(line)
        if decision.supersedes_id:
            console.print(f"Supersedes: #{decision.supersedes_id}")
        if decision.superseded_by_id:
            console.print(f"Superseded by: #{decision.superseded_by_id}")
        if decision.tags:
            console.print("Tags: " + ", ".join(decision.tags))
    finally:
        runtime.close()


@app.command("inject-preview")
def inject_preview_cmd(
    query: str | None = typer.Option(None, "--query", help="Optional relevance hint."),
    json_output: bool = _json_flag(),
) -> None:
    """Show exactly what Canon would inject into an agent session."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        selected, stats, text = select_for_injection(
            runtime.store, runtime.repo, runtime.settings, query=query
        )
        if console.json_mode:
            console.emit_json(
                {
                    "text": text,
                    "stats": stats,
                    "decision_ids": [item.id for item in selected],
                }
            )
            return
        console.print(text.rstrip())
        console.print("")
        console.print(
            f"({stats['selected']} of {stats['available']} active, "
            f"{stats['chars']} chars, ~{stats['tokens']} tokens)"
        )
    finally:
        runtime.close()


@app.command("inject")
def inject_cmd(
    for_hook: bool = typer.Option(
        False,
        HOOK_FLAG,
        help="JSON additionalContext for a Claude Code SessionStart hook.",
    ),
    query: str | None = typer.Option(None, "--query", help="Optional relevance hint."),
    json_output: bool = _json_flag(),
) -> None:
    """Emit injection text. Used by agent hooks. Safe if Canon is uninitialized."""
    console = _use_json(json_output)
    try:
        runtime = _runtime(require_init=True)
    except (NotInitializedError, CanonError):
        if for_hook:
            typer.echo(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": "",
                        }
                    }
                )
            )
            raise typer.Exit(0) from None
        raise
    try:
        selected, _stats, text = select_for_injection(
            runtime.store, runtime.repo, runtime.settings, query=query
        )
        runtime.telemetry.record("injection_performed", {"count": len(selected)})
        if for_hook:
            typer.echo(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": text,
                        }
                    }
                )
            )
            return
        if console.json_mode:
            console.emit_json({"text": text})
            return
        typer.echo(text.rstrip())
    finally:
        runtime.close()


@app.command("doctor")
def doctor_cmd(json_output: bool = _json_flag()) -> None:
    """Check Git, SQLite, GitHub, and agent integrations."""
    console = _use_json(json_output)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, warn: bool = False) -> None:
        checks.append({"name": name, "ok": ok, "warn": warn, "detail": detail})

    git_ok = which("git") is not None
    add("Git installation", git_ok, "git is on PATH" if git_ok else "git is missing")
    try:
        root = find_git_root()
        add("Git repository", True, str(root))
        paths = ProjectPaths.from_repo(root)
        initialized = paths.config_file.is_file() or paths.db_file.is_file()
        add("Canon project", initialized, str(paths.canon_dir))
        if initialized:
            store = Store(paths.db_file)
            try:
                add(
                    "SQLite database",
                    store.integrity_ok(),
                    f"schema {store.schema_version()}",
                )
                add(
                    "Decision schema",
                    store.schema_version() == store.expected_schema_version(),
                    f"{store.schema_version()} / {store.expected_schema_version()}",
                )
            finally:
                store.close()
            claude_ok, claude_msg = claude_status(root)
            add("Claude Code integration", claude_ok, claude_msg, warn=not claude_ok)
            cursor_ok, cursor_msg = cursor_status(root)
            add("Cursor integration", cursor_ok, cursor_msg, warn=not cursor_ok)
        if initialized:
            from canon.gitutil.repo import GitRepo

            github = GitHubClient(GitRepo(root))
            status = github.status()
            add(
                "GitHub CLI",
                status.available,
                status.detail,
                warn=not status.available,
            )
            add(
                "GitHub authentication",
                status.authenticated,
                status.detail,
                warn=not status.authenticated,
            )
    except CanonError as exc:
        add("Git repository", False, exc.message)

    add("Canon package", True, __version__)
    payload = {"checks": checks, "ready": all(item["ok"] or item["warn"] for item in checks)}
    if console.json_mode:
        console.emit_json(payload)
        return
    console.print("Canon Doctor")
    console.print("")
    for item in checks:
        mark = "✓" if item["ok"] else ("⚠" if item["warn"] else "✗")
        console.print(f"{mark} {item['name']}: {item['detail']}")
    console.print("")
    if payload["ready"]:
        console.print("Canon is ready.")
    else:
        console.print("Canon needs attention. See the failed checks above.")
        raise typer.Exit(1)


@app.command("config")
def config_cmd(
    action: str | None = typer.Argument(None, help="get | set | show"),
    key: str | None = typer.Argument(None),
    value: str | None = typer.Argument(None),
    json_output: bool = _json_flag(),
) -> None:
    """Show or change project configuration."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        if action in {None, "show"}:
            data = runtime.settings.as_dict()
            if console.json_mode:
                console.emit_json(data)
                return
            console.print(runtime.paths.config_file.read_text(encoding="utf-8"))
            return
        if action == "get":
            if not key:
                raise UsageError("Usage: canon config get <key>")
            found = runtime.settings.get(key)
            if console.json_mode:
                console.emit_json({"key": key, "value": found})
                return
            console.print(str(found))
            return
        if action == "set":
            if not key or value is None:
                raise UsageError("Usage: canon config set <key> <value>")
            updated = merge_set(runtime.settings, key, value)
            write_settings(runtime.paths.config_file, updated)
            if console.json_mode:
                console.emit_json({"key": key, "value": updated.get(key)})
                return
            console.print(f"Set {key} = {updated.get(key)}")
            return
        raise UsageError("Usage: canon config [show|get|set] ...")
    finally:
        runtime.close()


@app.command("export")
def export_cmd(
    output: Path | None = typer.Option(None, "--output", "-o", help="Write to this file."),
    json_output: bool = _json_flag(),
) -> None:
    """Export decisions to a portable JSON file. No secrets included."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        payload = runtime.store.export_payload()
        if output is None:
            if console.json_mode or not sys.stdout.isatty():
                typer.echo(json.dumps(payload, indent=2))
                return
            target = runtime.paths.canon_dir / "export.json"
        else:
            target = resolve_path(output)
            if target.exists() and target.is_dir():
                raise UsageError("Export path must be a file.")
        runtime.service.write_export(target)
        if console.json_mode:
            console.emit_json({"path": str(target), "count": len(payload["decisions"])})
            return
        console.print(f"Wrote {len(payload['decisions'])} decision(s) to {target}")
    finally:
        runtime.close()


@app.command("import")
def import_cmd(
    path: Path = typer.Argument(..., help="Canon export JSON file."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace matching fingerprints."),
    json_output: bool = _json_flag(),
) -> None:
    """Import a Canon export. Validates schema. Never executes imported content."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        source = resolve_path(path)
        if not source.is_file():
            raise UsageError(f"File not found: {source}")
        if source.stat().st_size > 10_000_000:
            raise UsageError("Import file is larger than 10 MB.")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise UsageError("Import file must be a JSON object.")
        count = runtime.service.import_decisions(payload, overwrite=overwrite)
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        if console.json_mode:
            console.emit_json({"imported": count})
            return
        console.print(f"Imported {count} decision(s).")
    finally:
        runtime.close()


@app.command("uninstall")
def uninstall_cmd(
    purge_data: bool = typer.Option(
        False, "--purge-data", help="Also delete the local SQLite history."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not prompt."),
    json_output: bool = _json_flag(),
) -> None:
    """Remove Canon-managed agent integrations. Decision history is kept unless --purge-data."""
    console = _use_json(json_output)
    root = find_git_root()
    if purge_data and not yes:
        if sys.stdin.isatty() and not Confirm.ask(
            "Delete local Canon decision history?", default=False
        ):
            raise typer.Exit(1)
        if not sys.stdin.isatty() and not yes:
            raise UsageError("Pass --yes to delete decision history in non-interactive mode.")
    changes = []
    changes.extend(uninstall_claude(root))
    changes.extend(uninstall_cursor(root))
    if purge_data:
        paths = ProjectPaths.from_repo(root)
        for candidate in (paths.db_file, Path(str(paths.db_file) + "-wal"), Path(str(paths.db_file) + "-shm")):
            if candidate.is_file():
                candidate.unlink()
                changes.append(f"Removed {candidate.name}")
        if paths.injection_file.is_file():
            paths.injection_file.unlink()
            changes.append("Removed injection snapshot")
    if console.json_mode:
        console.emit_json({"changes": changes})
        return
    if not changes:
        console.print("Nothing Canon-managed to remove.")
        return
    console.print("Removed Canon-managed configuration:")
    for line in changes:
        console.print(f"  • {line}")
    if not purge_data:
        console.print("Decision history was preserved.")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    debug = "--debug" in args or os.environ.get("CANON_DEBUG") in {"1", "true", "yes"}
    try:
        app(args=args, standalone_mode=False)
        return 0
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    except CanonError as exc:
        Console(force_json="--json" in args).error(exc)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        if debug:
            traceback.print_exc()
        Console(force_json="--json" in args).error(
            CanonError(
                "Canon hit an unexpected error.",
                redact(str(exc)) + "\nRe-run with --debug for a traceback.",
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
