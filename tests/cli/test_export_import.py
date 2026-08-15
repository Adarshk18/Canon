from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from canon.cli.app import app

runner = CliRunner()


def test_export_and_import(decision_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(decision_repo)
    assert runner.invoke(app, ["init"]).exit_code == 0
    payload = json.loads(runner.invoke(app, ["suggest", "--json"]).output)
    ident = payload["candidates"][0]["id"]
    assert runner.invoke(app, ["approve", str(ident)]).exit_code == 0
    export_path = tmp_path / "decisions.json"
    result = runner.invoke(app, ["export", "-o", str(export_path)])
    assert result.exit_code == 0, result.output
    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert data["format"] == "canon-export"
    assert data["decisions"]

    other = tmp_path / "other"
    other.mkdir()
    # Reuse same git repo for import overwrite path
    imported = runner.invoke(app, ["import", str(export_path)])
    assert imported.exit_code == 0
