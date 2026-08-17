# Canon

[![CI](https://github.com/Adarshk18/Canon/actions/workflows/ci.yml/badge.svg)](https://github.com/Adarshk18/Canon/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/canon-memory.svg)](https://pypi.org/project/canon-memory/)
[![Python Version](https://img.shields.io/pypi/pyversions/canon-memory.svg)](https://pypi.org/project/canon-memory/)
[![License: MIT](https://img.shields.io/pypi/l/canon-memory.svg)](https://github.com/Adarshk18/Canon/blob/main/LICENSE)

**Canon remembers the decisions your repo already made — and makes Claude Code and Cursor follow them automatically.**

Governed project decision memory for AI coding agents.

Canon is a local-first CLI that sits between coding agents (Claude Code and Cursor first) and a project's institutional knowledge. It stops agents and new teammates from re-adopting rejected approaches, inventing conventions, or re-asking questions that were already settled.

It is not a chatbot, not another coding agent, not generic RAG, and not a website-first knowledge base. It is the living, agent-native layer for project decisions. It complements `CLAUDE.md`, `AGENTS.md`, and ADRs — it does not replace them.

```text
start coding agent
        ↓
Canon automatically loads relevant active decisions
        ↓
agent receives them
```

## Why it exists

Static files go stale. Agents forget last month's review thread. Asking people to stop mid-sprint and write an ADR does not survive week three.

Canon mines recent merged PRs (or Git history) and proposes candidate decisions. A human only approves or rejects. Confirmed decisions are injected automatically at the start of the next agent session. Old decisions are superseded, never silently deleted.

## How it works

1. `canon init` wires local storage and agent integrations.
2. `canon suggest` reads recent merged PRs or commits and proposes conservative candidates.
3. You approve or reject. That interaction should take seconds, not a writing session.
4. On the next Claude Code session, a SessionStart hook injects relevant active decisions.
5. Cursor reads an always-apply project rule that points at the generated snapshot.

## Installation

Requires Python 3.11 or newer and Git.

```bash
pip install canon-memory
```

Isolated CLI install (recommended):

```bash
pipx install canon-memory
# or
uv tool install canon-memory
```

The product and CLI are **Canon**. The PyPI name is `canon-memory` because `canon` is taken by an unrelated package.

```bash
canon --help
canon --version
```

If `canon` is not recognized (common on Windows user installs):

```bash
python -m canon --version
```

Add your Python `Scripts` folder to PATH, or keep using `python -m canon`.

## Quickstart

```bash
cd my-project
canon init
canon suggest
canon approve 1
canon inject-preview
```

Then start **Claude Code** or a **new Cursor Agent chat** in the same repository. The agent should see the confirmed decision without you running `canon query`.

V1 does not auto-inject into ChatGPT or standalone Grok. Those tools can only see Canon if you attach `.canon/injection.md`.

## Claude Code integration

`canon init` installs an official [SessionStart](https://code.claude.com/docs/en/hooks) command hook in `.claude/settings.json` (exec form, no shell):

```json
{
  "type": "command",
  "command": "canon",
  "args": ["inject", "--for-hook"],
  "timeout": 15
}
```

Claude Code injects the hook's `additionalContext` at session start, resume, clear, compact, and fork. Output stays under the 10,000 character hook cap.

`canon init` also writes a small managed rule at `.claude/rules/canon.md`. It does not rewrite your `CLAUDE.md`.

Inspect: `canon doctor`  
Disable: `canon uninstall`  
Troubleshoot: confirm `canon` is on `PATH` inside the Claude Code environment.

## Cursor integration

Cursor has no session-start hook. Canon uses the officially supported [project rules](https://cursor.com/docs/rules) mechanism:

- `.cursor/rules/canon.mdc` with `alwaysApply: true`
- `@.canon/injection.md` referenced from that rule
- `.canon/injection.md` regenerated on `init`, `approve`, `reject`, and `suggest`

Limitation: Cursor will not re-read a changed snapshot until a new Agent session (or a rule reload). Approve a decision, then start a new chat. This is a Cursor platform limitation, not a missing Canon command.

## CLI commands

| Command | Purpose |
| --- | --- |
| `canon init` | Create local storage, schema, and agent wiring. Idempotent. |
| `canon status` | Project, database, GitHub, and integration status. |
| `canon suggest` | Mine recent PRs/commits for conservative candidates. |
| `canon approve [id]` | Candidate → active. May supersede an older decision. |
| `canon reject <id>` | Candidate → rejected. Record is kept. |
| `canon list` | List decisions. `--active`, `--superseded`, `--rejected`, `--all`, `--tag`. |
| `canon show <id>` | Full body and provenance. |
| `canon inject-preview` | Exactly what an agent would receive. |
| `canon doctor` | Environment and integration checks. |
| `canon config` | Show or set project configuration. |
| `canon export` | Portable JSON of stored decisions. |
| `canon import` | Validated import. |
| `canon uninstall` | Remove managed integrations. History is kept unless `--purge-data`. |
| `canon version` | Print the version. |

Most commands accept `--json`. Debug with `--debug` or `CANON_DEBUG=1`.

Exit codes: `0` success, `1` application error, `2` invalid usage.

## Decision lifecycle

```text
candidate  →  active
candidate  →  rejected
active     →  superseded
```

Rejected and superseded records stay in SQLite. Injection uses **active** decisions only.

```text
Decision #42
Status: SUPERSEDED
Superseded by: #57
```

## Provenance

Every suggested and approved decision records what Canon actually knows:

- source PR or commit
- source repository
- source date
- confirmation date and confirmer

If a field is unavailable, Canon says so. It never invents PR numbers, hashes, authors, dates, or URLs.

## Privacy

The default is local and private. No account is required.

- SQLite, decision history, and injected context stay on disk.
- Network is used only for optional GitHub PR metadata.
- Telemetry is **off** unless you set `CANON_TELEMETRY=1`, and even then V1 only appends local events to `.canon/telemetry.jsonl`.

See [PRIVACY.md](https://github.com/Adarshk18/Canon/blob/main/PRIVACY.md).

## Security

Canon treats commit messages, PR titles, PR bodies, filenames, and API responses as untrusted data. They are never executed and never treated as instructions. Git and `gh` run with argument lists, not a shell. SQL is parameterized.

See [SECURITY.md](https://github.com/Adarshk18/Canon/blob/main/SECURITY.md).

## Configuration

Precedence:

```text
CLI arguments
    ↓
environment variables
    ↓
project config (.canon/config.toml)
    ↓
user config (~/.canon/config.toml)
    ↓
defaults
```

Defaults:

| Setting | Default | Meaning |
| --- | --- | --- |
| `injection.max_decisions` | 12 | Hard cap on injected decisions |
| `injection.max_chars` | 4000 | Hard cap on injection characters |
| `injection.max_tokens` | 1000 | Estimated token cap (`chars / 4`) |
| `mining.lookback_prs` | 20 | Merged PRs to inspect |
| `mining.lookback_commits` | 80 | Commits to inspect when GitHub is unavailable |
| `mining.min_score` | 6 | Conservative suggestion threshold |
| `privacy.telemetry` | false | Local event log only, off by default |

Copy [`.env.example`](https://github.com/Adarshk18/Canon/blob/main/.env.example) if you need environment overrides. Never commit `.env`.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `not a Canon project` | Run `canon init` inside a Git repository. |
| `GitHub CLI is installed, but you are not authenticated` | Run `gh auth login`, then `canon suggest`. |
| `canon` is not recognized | Use `python -m canon ...` or add Python `Scripts` to PATH. |
| No candidates | Expected on mechanical/UI-only history. Product/policy and stack choices should appear. |
| Claude session has no decisions | Run `canon doctor`. Confirm `canon` is on `PATH`. Start a new session. |
| Cursor ignores a new decision | Start a new Agent chat after `canon approve`. |
| Offline | `list`, `status`, and `inject-preview` work without a network. `suggest` falls back to Git history. |

## Development

See [CONTRIBUTING.md](https://github.com/Adarshk18/Canon/blob/main/CONTRIBUTING.md).

```bash
git clone https://github.com/Adarshk18/Canon.git
cd Canon
python -m pip install -e ".[dev]"
pytest
ruff check src tests
mypy
python -m build
```

Install unreleased `main` without a checkout:

```bash
pip install git+https://github.com/Adarshk18/Canon.git
```

## Testing

`pytest` covers decision lifecycle, supersession, mining filters, injection budget, CLI commands, path traversal, SQL injection, command injection, and prompt-injection-style repository content.

## Canon Cloud (optional)

Local use needs no account. Cloud is sync + team seats + billing.

```bash
export CANON_CLOUD_URL=https://your-canon-host
canon cloud login
canon cloud push
canon cloud pull
canon cloud upgrade pro
```

Billing is **Polar.sh**, not Stripe (Stripe India is invite-only). See [docs/SAAS.md](https://github.com/Adarshk18/Canon/blob/main/docs/SAAS.md).

## Roadmap / deferred features

Intentionally **not** in V1, matching the source product plan:

- Slack or Notion connectors
- Daily multi-project drift engine
- Rich team dashboard
- Deep MCP query interface
- Enterprise self-host packaging
- Organization management and SSO

The domain model is isolated from SQLite so those can be added later without rewriting the local core.

## Historical name

An earlier plan used the working name DecisionVault. The product is Canon.

## License

MIT. See [LICENSE](https://github.com/Adarshk18/Canon/blob/main/LICENSE).
