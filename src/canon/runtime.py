from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from canon.config.paths import ProjectPaths
from canon.config.settings import Settings, load_settings
from canon.db.store import Store
from canon.decisions.service import DecisionService
from canon.gitutil.repo import GitRepo, find_git_root
from canon.telemetry.provider import TelemetryProvider, build_telemetry


def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level, format="canon: %(levelname)s: %(message)s")
    if os.environ.get("CANON_DEBUG") in {"1", "true", "yes"}:
        logging.getLogger().setLevel(logging.DEBUG)


@dataclass(slots=True)
class Runtime:
    repo: GitRepo
    paths: ProjectPaths
    settings: Settings
    store: Store
    service: DecisionService
    telemetry: TelemetryProvider

    def close(self) -> None:
        self.store.close()


def load_runtime(start: Path | None = None, *, require_init: bool = True) -> Runtime:
    root = find_git_root(start)
    repo = GitRepo(root)
    paths = ProjectPaths.from_repo(root)
    if require_init:
        paths.require_initialized()
    settings = load_settings(paths)
    configure_logging(settings.debug)
    store = Store(paths.db_file)
    telemetry = build_telemetry(enabled=settings.privacy.telemetry, path=paths.telemetry_file)
    service = DecisionService(store, telemetry)
    return Runtime(
        repo=repo,
        paths=paths,
        settings=settings,
        store=store,
        service=service,
        telemetry=telemetry,
    )
