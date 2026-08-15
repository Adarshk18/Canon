from __future__ import annotations

import json
import os
import sys
from typing import Any

from rich.console import Console as RichConsole
from rich.table import Table

from canon.errors import CanonError


class Console:
    def __init__(self, *, force_json: bool = False, no_color: bool | None = None) -> None:
        if no_color is None:
            no_color = os.environ.get("CANON_NO_COLOR") in {"1", "true", "yes"}
        self.force_json = force_json
        self.rich = RichConsole(
            no_color=no_color,
            highlight=False,
            soft_wrap=True,
            stderr=False,
        )
        self.err = RichConsole(no_color=no_color, highlight=False, stderr=True)

    @property
    def json_mode(self) -> bool:
        return self.force_json

    def print(self, message: str = "") -> None:
        if not self.force_json:
            self.rich.print(message)

    def error(self, error: CanonError | str) -> None:
        text = error.render() if isinstance(error, CanonError) else str(error)
        if self.force_json:
            sys.stderr.write(json.dumps({"error": text}) + "\n")
            return
        self.err.print(f"[red]{text}[/red]")

    def emit_json(self, payload: Any) -> None:
        self.rich.print_json(data=payload)

    def table(self, title: str, columns: list[str], rows: list[list[str]]) -> None:
        if self.force_json:
            return
        table = Table(title=title, show_lines=False, header_style="bold")
        for column in columns:
            table.add_column(column)
        for row in rows:
            table.add_row(*row)
        self.rich.print(table)


def get_console(*, force_json: bool = False) -> Console:
    return Console(force_json=force_json)
