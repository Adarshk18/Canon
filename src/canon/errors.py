"""Structured errors with user-facing messages and hints. No tracebacks by default."""

from __future__ import annotations


class CanonError(Exception):
    """Application error shown to the user. Exit code 1 unless overridden."""

    exit_code: int = 1

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def render(self) -> str:
        if self.hint:
            return f"{self.message}\n\n{self.hint}"
        return self.message


class UsageError(CanonError):
    exit_code = 2


class NotInitializedError(CanonError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "This directory is not a Canon project.",
            "Run:\n\n    canon init\n\nfrom the Git repository root.",
        )


class GitError(CanonError):
    pass


class GitHubError(CanonError):
    pass


class DatabaseError(CanonError):
    pass


class ConfigError(CanonError):
    pass


class SecurityError(CanonError):
    pass


class IntegrationError(CanonError):
    pass
