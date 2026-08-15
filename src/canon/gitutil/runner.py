from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from canon.constants import DEFAULT_COMMAND_TIMEOUT
from canon.errors import GitError, SecurityError
from canon.security.redact import redact

ALLOWED_BINARIES = frozenset({"git", "gh"})


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def which(name: str) -> str | None:
    return shutil.which(name)


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = DEFAULT_COMMAND_TIMEOUT,
    env: Mapping[str, str] | None = None,
    allowed: frozenset[str] = ALLOWED_BINARIES,
    check: bool = False,
    error_cls: type[Exception] = GitError,
) -> CommandResult:
    if not args:
        raise SecurityError("Refusing to run an empty command.")
    binary = args[0]
    if Path(binary).name.split(".")[0] not in allowed and binary not in allowed:
        raise SecurityError(
            "Refusing to run an unexpected program.",
            f"Allowed: {', '.join(sorted(allowed))}",
        )
    if any(not isinstance(item, str) for item in args):
        raise SecurityError("Command arguments must be strings.")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    # Never inherit a custom GIT_EDITOR that could execute untrusted content.
    merged_env.pop("GIT_EDITOR", None)
    merged_env.pop("GIT_SEQUENCE_EDITOR", None)
    merged_env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,
            env=merged_env,
        )
    except FileNotFoundError as exc:
        raise error_cls(
            f"Canon could not find `{binary}`.",
            f"Install `{binary}` and ensure it is on PATH.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise error_cls(
            f"`{binary}` timed out after {int(timeout)} seconds.",
            "Retry when the network is available, or continue with local Git history.",
        ) from exc

    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=redact(completed.stderr or ""),
    )
    if check and not result.ok:
        raise error_cls(
            f"`{binary}` failed (exit {result.returncode}).",
            result.stderr.strip() or "No additional detail was provided.",
        )
    return result
