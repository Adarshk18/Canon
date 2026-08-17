from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from canon import __version__
from canon.cli.app import app, main

runner = CliRunner()


def test_help_and_version() -> None:
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "init" in help_result.output
    version_result = runner.invoke(app, ["--version"])
    assert version_result.exit_code == 0
    assert __version__ in version_result.output


def test_cloud_help() -> None:
    result = runner.invoke(app, ["cloud", "--help"])
    assert result.exit_code == 0
    assert "login" in result.output


def test_command_help_pages() -> None:
    for command in (
        "init",
        "status",
        "suggest",
        "approve",
        "reject",
        "list",
        "show",
        "inject-preview",
        "inject",
        "doctor",
        "config",
        "export",
        "import",
        "uninstall",
        "version",
        "cloud",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, result.output


def test_init_is_idempotent(decision_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(decision_repo)
    first = runner.invoke(app, ["init"])
    second = runner.invoke(app, ["init"])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    settings = (decision_repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert settings.count("--for-hook") == 1


def test_uninitialized_list_fails(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    code = main(["list"])
    assert code != 0


def test_main_wrapper_help() -> None:
    assert main(["--help"]) == 0
    assert main(["--version"]) == 0
