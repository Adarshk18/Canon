from __future__ import annotations

from pathlib import Path

import pytest

from canon.config.paths import ProjectPaths
from canon.config.settings import load_settings, merge_set, write_settings


def test_env_overrides_project_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    paths = ProjectPaths.from_repo(repo)
    settings = load_settings(paths)
    settings.injection.max_decisions = 4
    write_settings(paths.config_file, settings)
    monkeypatch.setenv("CANON_MAX_DECISIONS", "9")
    loaded = load_settings(paths)
    assert loaded.injection.max_decisions == 9


def test_merge_set_and_get(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    paths = ProjectPaths.from_repo(repo)
    settings = load_settings(paths)
    updated = merge_set(settings, "injection.max_tokens", "500")
    assert updated.get("injection.max_tokens") == 500
    assert settings.injection.max_tokens != 500
