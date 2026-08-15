# V1 scope traceability

Source: the original product plan (Aug 2026). The shipping product is Canon.

| Requirement | Implementation | Tests | Status |
| --- | --- | --- | --- |
| One-command setup | `canon/cli/app.py` `init` | `tests/cli/test_cli.py` | Complete |
| Claude Code integration | `canon/integrations/claude.py` | `tests/integrations/test_agent_files.py` | Complete |
| Cursor integration | `canon/integrations/cursor.py` | `tests/integrations/test_agent_files.py` | Complete (file-based; no Cursor hook exists) |
| `init` | `cli/app.py` | `tests/cli/test_cli.py` | Complete |
| `status` | `cli/app.py` | `tests/cli/test_cli.py` | Complete |
| `suggest` | `cli/app.py`, `mining/engine.py` | `tests/cli/test_core_journey.py` | Complete |
| `approve` | `decisions/service.py` | `tests/decisions/test_service.py`, journey | Complete |
| `reject` | `decisions/service.py` | `tests/cli/test_core_journey.py` | Complete |
| `list` | `cli/app.py` | journey tests | Complete |
| `inject-preview` | `integrations/snapshot.py` | journey tests | Complete |
| Local SQLite | `db/store.py` | `tests/db/test_store.py` | Complete |
| Decision lifecycle | `core/lifecycle.py` | `tests/core/test_lifecycle.py` | Complete |
| Supersession | `decisions/service.py` | `tests/decisions/test_service.py` | Complete |
| Provenance | `core/models.py` | journey / show command | Complete |
| Passive PR/commit mining | `mining/` + `githubutil/` | `tests/mining/test_scoring.py`, journey | Complete |
| Automatic injection | Claude hook + Cursor rule | `tests/integrations/test_agent_files.py` | Complete |
| Relevance filtering | `integrations/relevance.py` | `tests/integrations/test_budget_and_relevance.py` | Complete |
| Token/context budget | `integrations/budget.py` | same | Complete |
| Secure local storage | parameterized SQL, WAL, no secrets | `tests/security/test_sql_and_shell.py` | Complete |
| Git / GitHub | `gitutil/`, `githubutil/` | `tests/gitutil/test_repo.py` | Complete |
| Comprehensive tests | `tests/` | this file | Complete |
| CLI help | Typer `--help` | `tests/cli/test_cli.py` | Complete |
| README | `README.md` | review | Complete |
| Install instructions | README | review | Complete |
| Configuration docs | `docs/CONFIGURATION.md` | `tests/config/test_settings.py` | Complete |
| Security docs | `SECURITY.md` | review | Complete |
| Privacy docs | `PRIVACY.md` | review | Complete |
| `.env.example` | `.env.example` | review | Complete |
| CI | `.github/workflows/ci.yml` | review | Complete |
| Packaging | `pyproject.toml` | build step | Complete |
| Lint / typecheck / tests | ruff, mypy, pytest | CI | Complete |
| Safe failure | `errors.py`, `main()` | CLI tests | Complete |
| Migrations | `db/migrations.py` | `tests/db/test_migrations.py` | Complete |
| Useful errors | `CanonError.render` | CLI tests | Complete |
| Reproducible local setup | CONTRIBUTING + pyproject | review | Complete |
| Doctor | `canon doctor` | help test | Complete |
| Export / import | `cli/app.py` | `tests/cli/test_export_import.py` | Complete |
| Uninstall | `cli/app.py` | integration uninstall tests | Complete |
| Offline local commands | no network in list/status/inject | design | Complete |
| Prompt-injection defense | `security/sanitize.py` | `tests/security/test_sanitize.py`, adversarial | Complete |
| Path traversal | `security/paths.py` | `tests/security/test_paths.py` | Complete |
| Command injection | `gitutil/runner.py` | `tests/security/test_sql_and_shell.py` | Complete |

## Explicitly deferred

- Slack / Notion connectors
- Daily multi-project drift engine
- Rich team dashboard
- Deep MCP query interface
- Enterprise self-host packaging
- Organization management / SSO
- Stripe billing / cloud sync / accounts
- PostHog or remote telemetry
