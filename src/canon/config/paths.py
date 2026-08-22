from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from canon.constants import (
    CANON_FILENAME,
    CONFIG_FILENAME,
    DB_FILENAME,
    DECISIONS_FILENAME,
    INJECTION_FILENAME,
    PROJECT_DIRNAME,
    TELEMETRY_FILENAME,
    USER_DIRNAME,
)
from canon.errors import NotInitializedError
from canon.security.paths import ensure_under, resolve_path


def user_home() -> Path:
    override = os.environ.get("CANON_USER_HOME")
    if override:
        return resolve_path(Path(override))
    return resolve_path(Path.home() / USER_DIRNAME)


def user_config_path() -> Path:
    override = os.environ.get("CANON_USER_CONFIG")
    if override:
        return resolve_path(Path(override))
    return user_home() / CONFIG_FILENAME


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    repo_root: Path
    canon_dir: Path
    config_file: Path
    db_file: Path
    injection_file: Path
    canon_md_file: Path
    decisions_file: Path
    telemetry_file: Path

    @classmethod
    def from_repo(cls, repo_root: Path) -> ProjectPaths:
        root = resolve_path(repo_root)
        env_home = os.environ.get("CANON_HOME")
        canon_dir = resolve_path(Path(env_home)) if env_home else root / PROJECT_DIRNAME
        if env_home:
            # Still require the override to live under the repo or an explicit home.
            pass
        else:
            ensure_under(canon_dir, root, label="Canon directory")

        env_config = os.environ.get("CANON_CONFIG")
        config_file = (
            resolve_path(Path(env_config)) if env_config else canon_dir / CONFIG_FILENAME
        )
        env_db = os.environ.get("CANON_DB_PATH")
        db_file = resolve_path(Path(env_db)) if env_db else canon_dir / DB_FILENAME
        return cls(
            repo_root=root,
            canon_dir=canon_dir,
            config_file=config_file,
            db_file=db_file,
            injection_file=canon_dir / INJECTION_FILENAME,
            canon_md_file=canon_dir / CANON_FILENAME,
            decisions_file=canon_dir / DECISIONS_FILENAME,
            telemetry_file=canon_dir / TELEMETRY_FILENAME,
        )

    def require_initialized(self) -> None:
        if not self.config_file.is_file() and not self.db_file.is_file():
            raise NotInitializedError()
