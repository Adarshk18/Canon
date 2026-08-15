# Architecture

Canon V1 is a local Python CLI. There is no required server.

## Loop

```text
Git / merged PR history
        ↓
deterministic candidate extraction
        ↓
human approve / reject
        ↓
SQLite (active / rejected / superseded)
        ↓
relevance + token budget
        ↓
Claude SessionStart hook / Cursor always-apply rule
        ↓
coding agent
```

## Storage

SQLite at `.canon/canon.db` with numbered migrations from version 1.
WAL mode, foreign keys, parameterized SQL, integrity check on `doctor`.

The `Decision` dataclass is the domain object. Persistence is isolated in
`canon.db.store.Store` so a future cloud store can implement the same
methods without leaking SQL into the CLI.

## Mining

No LLM. Scoring looks for explicit engineering intent (switch/migrate/
instead of/breaking) plus category path hints, and subtracts lockfile,
typo, format, and test-only noise. Threshold is conservative (`min_score=6`).

GitHub is preferred when `gh auth status` succeeds. Otherwise Canon uses
`git log`. Provenance fields that cannot be known stay `unavailable`.

## Injection

Only `active` decisions. Ranked by directory/tag overlap, optional query
text, and recency. Hard caps: count, characters, estimated tokens.

Claude Code: official SessionStart command hook, exec form, JSON
`additionalContext`.

Cursor: official `.cursor/rules/*.mdc` with `alwaysApply: true` referencing
`.canon/injection.md`. Cursor has no hook; the snapshot is refreshed when
decisions change.

## Security boundaries

- subprocess allowlist
- path containment
- untrusted-text sanitizer
- secret redaction in errors
- no dynamic SQL
- no evaluation of repository content

## Telemetry

`TelemetryProvider` with `NoOpTelemetry` default. Opt-in writes a local
JSONL file. No remote implementation ships in V1.

## Key decisions

Recorded in `docs/DECISIONS.md`.
