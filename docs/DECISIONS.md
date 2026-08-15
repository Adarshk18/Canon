# Technical decisions

These are implementation decisions for Canon V1, not project decisions
that Canon itself would mine.

## Product name vs package name

`canon` is taken on PyPI (unrelated 2018 Club Penguin compression tool).
Distribution name is `canon-memory`. Import package and CLI stay `canon`.
The product is not silently renamed.

## No LLM in the miner

The source plan asked for the simplest explainable miner. An LLM would
need credentials, would expand the prompt-injection surface, and would
make suggestions harder to trust. V1 scoring is deterministic.

## subprocess over GitPython

Fewer dependencies, no shell interpolation, explicit timeouts, and an
allowlist (`git`, `gh`) are easier to reason about than a Git library
that shells out internally.

## gh first, API second

GitHub CLI uses the user's existing login and avoids storing a token in
the project. `GITHUB_TOKEN` is a documented optional fallback with
read-only use.

## Isolated SQLite + migrations from day one

The source plan requires upgrade handling. A `schema_migrations` table
starts at version 1 so later columns do not become ad-hoc `CREATE TABLE IF
NOT EXISTS` drift.

## Injection budget is a hard cap

The source plan's top risk is context flooding. Defaults (12 decisions,
4000 chars, 1000 estimated tokens) are conservative and configurable.

## Claude hook + Cursor file

Different official contracts. One dynamic hook, one always-apply rule
plus generated snapshot. Same rendered text.

## Telemetry is a no-op

The source plan allows optional anonymous telemetry. Shipping a network
client without a real endpoint would be fake telemetry. V1 records locally
only when opted in.

## Nested git repository

The workspace `E:\Canon` previously sat inside an unrelated parent Git
tree. Canon initializes its own `.git` so product history is not mixed
with that parent.
