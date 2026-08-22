from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from canon.cli.app import app
from canon.integrations.mcp import handle_request

runner = CliRunner()


def test_add_approve_writes_team_snapshot(
    decision_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "add",
            "Use SQLite for local Canon state",
            "--body",
            "Keep the default store on disk, not a required server.",
            "--tag",
            "storage",
            "--approve",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["decision"]["status"] == "active"
    canon_md = (decision_repo / ".canon" / "CANON.md").read_text(encoding="utf-8")
    assert "SQLite" in canon_md
    agents = (decision_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "BEGIN-CANON-MANAGED" in agents
    assert "SQLite" in agents
    query = runner.invoke(app, ["query", "sqlite", "--json"])
    assert query.exit_code == 0, query.output
    assert "SQLite" in json.loads(query.output)["text"]


def test_check_fails_on_rejected_overlap(
    decision_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    suggest = json.loads(runner.invoke(app, ["suggest", "--json"]).output)
    ident = suggest["candidates"][0]["id"]
    title = suggest["candidates"][0]["title"]
    assert runner.invoke(app, ["reject", str(ident)]).exit_code == 0
    failed = runner.invoke(app, ["check", "--text", title, "--json"])
    assert failed.exit_code == 1
    payload = json.loads(failed.output)
    assert payload["ok"] is False
    assert payload["findings"]
    clean = runner.invoke(app, ["check", "--text", "change button padding", "--json"])
    assert clean.exit_code == 0, clean.output


def test_init_hydrates_committed_export(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(
        app, ["add", "Never store secrets in Canon snapshots", "--approve"]
    ).exit_code == 0
    export = (git_repo / ".canon" / "decisions.json").read_text(encoding="utf-8")

    other = tmp_path / "clone"
    other.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Dev Example",
            "GIT_AUTHOR_EMAIL": "dev@example.com",
            "GIT_COMMITTER_NAME": "Dev Example",
            "GIT_COMMITTER_EMAIL": "dev@example.com",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=other,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    git("init")
    git("config", "user.name", "Dev Example")
    git("config", "user.email", "dev@example.com")
    git("config", "commit.gpgsign", "false")
    (other / "README.md").write_text("# clone\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "chore: initial import")
    (other / ".canon").mkdir()
    (other / ".canon" / "decisions.json").write_text(export, encoding="utf-8")
    monkeypatch.chdir(other)
    assert runner.invoke(app, ["init"]).exit_code == 0
    listed = json.loads(runner.invoke(app, ["list", "--active", "--json"]).output)
    assert any("secrets" in item["title"].lower() for item in listed)


def test_mcp_initialize_and_tools_list() -> None:
    init = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == "canon"
    listed = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    names = {item["name"] for item in listed["result"]["tools"]}
    assert names == {"canon_list", "canon_show", "canon_query", "canon_inject"}
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
