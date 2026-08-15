# Privacy

Canon is local-first. You can install it and run the core loop without
creating an account.

## What stays local

- `.canon/canon.db` — decision history, including superseded and rejected records
- `.canon/injection.md` — generated snapshot for agents
- `.canon/config.toml` — project settings
- `~/.canon/config.toml` — optional user defaults
- `.canon/telemetry.jsonl` — only if you opt in

These files do not leave the machine unless you copy them, commit them, or
export them.

## What Canon accesses

Only what the current command needs:

| Action | Access |
| --- | --- |
| `init`, `list`, `status`, `inject-preview`, `approve`, `reject` | Local Git repo metadata and local SQLite |
| `suggest` | Local Git history. Optionally GitHub PR metadata if `gh` is authenticated or `GITHUB_TOKEN` is set |
| Agent hook `canon inject --for-hook` | Local SQLite only |

Canon does not scan the entire working tree for source code. File paths
from `git` / GitHub are used for scoring, not uploaded.

## Network calls

The only network call in V1 is optional GitHub access during `canon suggest`:

- `gh pr list` (GitHub CLI), or
- `https://api.github.com/repos/<owner>/<repo>/pulls` when `GITHUB_TOKEN` is set

If GitHub is unavailable, Canon falls back to local Git history and tells you.

Canon does **not** claim that zero data leaves your machine, because GitHub
calls send repository identity and receive PR metadata.

## Telemetry

Telemetry is **off** unless `CANON_TELEMETRY=1` or
`privacy.telemetry = true` in config.

Disable it:

```bash
canon config set privacy.telemetry false
# or
# unset CANON_TELEMETRY
```

When enabled in V1, events are appended locally. Event names only:

- `suggestions_generated`
- `suggestion_approved`
- `suggestion_rejected`
- `injection_performed`

Not collected: source code, decision titles/bodies, PR content, secrets,
usernames beyond what Git already stored as `confirmed_by`, file contents.

There is no PostHog, Stripe, or cloud analytics in V1.

## GitHub access

PR mining reads titles, bodies, file lists, and merge metadata. That content
is treated as untrusted and stored only if a candidate is created.

## Agent injection

Injected context is written locally and read by Claude Code or Cursor on
your machine. Canon does not send that context to a Canon server.

## What is not collected

- No account
- No device fingerprinting
- No advertising identifiers
- No automatic cloud sync
