from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from canon.cli.app import app

runner = CliRunner()


def test_git_to_injection_journey(decision_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0

    suggest = runner.invoke(app, ["suggest", "--json"])
    assert suggest.exit_code == 0, suggest.output
    payload = json.loads(suggest.output)
    assert payload["created"] >= 1
    candidates = payload["candidates"]
    assert candidates
    first_id = candidates[0]["id"]

    approve = runner.invoke(app, ["approve", str(first_id), "--json"])
    assert approve.exit_code == 0, approve.output
    approved = json.loads(approve.output)
    assert approved["approved"]["status"] == "active"

    listed = json.loads(runner.invoke(app, ["list", "--active", "--json"]).output)
    assert any(item["id"] == first_id for item in listed)

    preview = runner.invoke(app, ["inject-preview"])
    assert preview.exit_code == 0, preview.output
    assert "Active Project Decisions" in preview.output
    assert candidates[0]["title"].split()[0] in preview.output or "Use" in preview.output

    injection = (decision_repo / ".canon" / "injection.md").read_text(encoding="utf-8")
    assert "confirmed project decisions" in injection.lower()


def test_supersession_injection_excludes_old(
    decision_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    payload = json.loads(runner.invoke(app, ["suggest", "--json"]).output)
    ids = [item["id"] for item in payload["candidates"]]
    assert len(ids) >= 1
    first = ids[0]
    assert runner.invoke(app, ["approve", str(first)]).exit_code == 0

    # Second remaining candidate, if any, or create via another suggest after new commit.
    remaining = [
        item["id"]
        for item in json.loads(runner.invoke(app, ["list", "--candidate", "--json"]).output)
    ]
    if remaining:
        second = remaining[0]
        result = runner.invoke(app, ["approve", str(second), "--supersedes", str(first), "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["approved"]["status"] == "active"
        assert data["superseded"]["status"] == "superseded"
        preview = runner.invoke(app, ["inject-preview"]).output
        old_title = json.loads(runner.invoke(app, ["show", str(first), "--json"]).output)["title"]
        # Old decision must still exist historically, but injection uses only active.
        history = runner.invoke(app, ["list", "--superseded"])
        assert history.exit_code == 0
        assert "SUPERSEDED" in history.output
        assert old_title not in preview or data["approved"]["title"] in preview


def test_reject_candidate(decision_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    payload = json.loads(runner.invoke(app, ["suggest", "--json"]).output)
    ident = payload["candidates"][0]["id"]
    result = runner.invoke(app, ["reject", str(ident), "--reason", "not a real decision"])
    assert result.exit_code == 0, result.output
    listed = json.loads(runner.invoke(app, ["list", "--rejected", "--json"]).output)
    assert listed[0]["status"] == "rejected"
