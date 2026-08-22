# Configuration

## Files

| File | Role | Commit? |
| --- | --- | --- |
| `.canon/config.toml` | Project settings | Yes, if you want shared defaults |
| `~/.canon/config.toml` | User defaults | No |
| `.canon/canon.db` | Decision store | No |
| `.canon/injection.md` | Checkout-local snapshot (HEAD-filtered) | No (gitignored) |
| `.canon/CANON.md` | Team snapshot of active decisions | Yes |
| `.canon/decisions.json` | Portable export for clones and CI | Yes |
| `.env` | Secrets | Never |

## Precedence

CLI → environment → project config → user config → defaults.

## Environment variables

See `.env.example`.

| Name | Required | Secret |
| --- | --- | --- |
| `CANON_DEBUG` | No | No |
| `CANON_HOME` | No | No |
| `CANON_DB_PATH` | No | No |
| `CANON_CONFIG` | No | No |
| `GITHUB_TOKEN` | No (prefer `gh auth login`) | Yes |
| `CANON_NO_COLOR` | No | No |
| `CANON_MAX_DECISIONS` | No | No |
| `CANON_MAX_CHARS` | No | No |
| `CANON_MAX_TOKENS` | No | No |
| `CANON_TELEMETRY` | No | No |

## Commands

```bash
canon config show
canon config get injection.max_decisions
canon config set injection.max_decisions 8
```
