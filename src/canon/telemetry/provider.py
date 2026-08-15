from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from canon.core.timeutil import utcnow_iso


class TelemetryProvider(Protocol):
    def record(self, event: str, payload: dict[str, Any] | None = None) -> None: ...


class NoOpTelemetry:
    def record(self, event: str, payload: dict[str, Any] | None = None) -> None:
        return None


class LocalFileTelemetry:
    """Opt-in local event log. Never sends data off-machine."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, event: str, payload: dict[str, Any] | None = None) -> None:
        safe = payload or {}
        blocked = {"body", "title", "token", "secret", "authorization", "code", "pr"}
        cleaned = {key: value for key, value in safe.items() if key not in blocked}
        line = json.dumps(
            {"event": event, "at": utcnow_iso(), **cleaned},
            sort_keys=True,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def build_telemetry(*, enabled: bool, path: Path) -> TelemetryProvider:
    if enabled:
        return LocalFileTelemetry(path)
    return NoOpTelemetry()
