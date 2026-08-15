"""Shared product constants. Keep user-facing strings on the Canon brand."""

from __future__ import annotations

PRODUCT_NAME = "Canon"
PACKAGE_NAME = "canon-memory"
CLI_NAME = "canon"
SCHEMA_VERSION = 1

PROJECT_DIRNAME = ".canon"
CONFIG_FILENAME = "config.toml"
DB_FILENAME = "canon.db"
INJECTION_FILENAME = "injection.md"
TELEMETRY_FILENAME = "telemetry.jsonl"
LOCK_FILENAME = "canon.lock"

USER_DIRNAME = ".canon"

MANAGED_BEGIN = "BEGIN-CANON-MANAGED"
MANAGED_END = "END-CANON-MANAGED"
HOOK_FLAG = "--for-hook"

DEFAULT_MAX_DECISIONS = 12
DEFAULT_MAX_CHARS = 4000
DEFAULT_MAX_TOKENS = 1000
DEFAULT_LOOKBACK_PRS = 20
DEFAULT_LOOKBACK_COMMITS = 80
DEFAULT_MIN_SCORE = 6
DEFAULT_COMMAND_TIMEOUT = 20.0
DEFAULT_GITHUB_TIMEOUT = 20.0

# Claude Code SessionStart stdout / additionalContext is capped at 10_000 chars.
HOOK_OUTPUT_CAP = 9000

UNTRUSTED_BEGIN = "<<<CANON_UNTRUSTED_REPOSITORY_CONTENT>>>"
UNTRUSTED_END = "<<<END_CANON_UNTRUSTED_REPOSITORY_CONTENT>>>"

GITIGNORE_ENTRIES = (
    ".canon/canon.db",
    ".canon/canon.db-wal",
    ".canon/canon.db-shm",
    ".canon/injection.md",
    ".canon/telemetry.jsonl",
    ".canon/*.log",
    ".env",
)

VALID_STATUSES = ("candidate", "active", "rejected", "superseded")
VALID_SOURCE_TYPES = ("pr", "commit", "manual")
VALID_CONFIDENCE = ("high", "medium", "low")
