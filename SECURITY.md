# Security Policy

## Reporting vulnerabilities

Report privately through
[GitHub Security Advisories](https://github.com/Adarshk18/Canon/security/advisories/new).
Do not open a public issue for a previously undisclosed vulnerability. Include
reproduction steps, impact, and whether repository content, GitHub credentials,
or local files are involved.

There is no bug bounty. We will acknowledge valid reports and fix them in a
patch release when possible.

This document does not claim that Canon is free of vulnerabilities.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |

## Secret handling

- Never commit `.env`, tokens, or credentials.
- Prefer `gh auth login` over a long-lived `GITHUB_TOKEN`.
- Environment variables are used for secrets. Source code contains placeholders only.
- Secrets are not stored in SQLite.
- Logs and error messages run through a redactor. Tokens matching common prefixes are replaced with `[redacted]`.
- Debug mode still must not print tokens, PR bodies, or decision text.

## GitHub permissions

Canon only needs **read** access to repository metadata for PR mining:

- merged PR number, title, body, URL, merge commit, files, merged-at
- no repository write
- no org admin
- no webhook administration

If you set `GITHUB_TOKEN`, grant the minimum read scope (`public_repo` or
`repo` contents read). Canon never requests extra scopes.

## Local data

The database lives at `.canon/canon.db` (or `CANON_DB_PATH`). It contains
decision titles, bodies, and provenance. Protect the project directory the
same way you protect the source tree.

`canon uninstall` removes managed integration files. It does **not** delete
history unless you pass `--purge-data`.

## Telemetry

Off by default. If `CANON_TELEMETRY=1`, V1 writes event names and numeric
ids to `.canon/telemetry.jsonl` on the local disk. It does not open a
network socket. Decision bodies, source code, and PR content are not written.

## Untrusted repository content

Commit messages, PR titles, PR bodies, filenames, diffs, and GitHub JSON are
untrusted input. Canon:

- never executes them
- never interpolates them into a shell
- never treats them as Canon system instructions
- sanitizes control characters
- quotes common prompt-injection phrases
- wraps leftover repository text in explicit untrusted delimiters when needed

A PR that says `IGNORE ALL PREVIOUS INSTRUCTIONS` is repository data.

## Prompt injection

If a future version calls a model, system instructions and repository data
must stay separated, model output must be schema-validated, and the model
must never receive secrets or the ability to run shell commands. V1 mining
is deterministic and does not call an LLM.

Injected agent context is labeled as confirmed project decisions and tells
the agent that repository-derived text is data, not instructions.

## Command execution

`git` and `gh` are spawned with an argument list (`shell=False`). Timeouts
are enforced. The first argument must be an allowed binary. Untrusted text
is never used as a program name or switch.

## Filesystem

Path joins reject `..` and refuse to write outside the project or configured
Canon directory.

## Dependency security

CI runs `pip-audit`. Review new dependencies before adding them. Prefer the
standard library.

## No fake guarantees

Canon implements the controls above. It does not provide “enterprise-grade”,
“military-grade”, or “zero vulnerability” security.
