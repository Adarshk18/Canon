# Contributing

## Setup

```bash
git clone https://github.com/Adarshk18/Canon.git
cd Canon
python -m pip install -e ".[dev]"
```

Python 3.11+ is required. Use a virtual environment.

## Test commands

```bash
pytest
pytest tests/security
pytest -k journey
```

## Lint

```bash
ruff check src tests
ruff format src tests
```

## Type checking

```bash
mypy
```

## Architecture

```text
src/canon/
    cli/            Typer commands
    core/           Decision model and lifecycle
    db/             SQLite store and migrations
    decisions/      Approve / reject / supersede
    mining/         Deterministic PR/commit extraction
    integrations/   Injection, budget, Claude, Cursor
    gitutil/        Safe git subprocess
    githubutil/     Read-only gh / API client
    config/         Settings precedence
    security/       Path, redact, untrusted-text
    output/         Terminal / JSON
    telemetry/      No-op by default
```

Keep cloud ideas behind interfaces. Do not add a mandatory backend.

## Contribution workflow

1. Open an issue or describe the change.
2. Keep the V1 product constraints: local-first, passive capture, conservative suggestions, no silent deletes.
3. Add tests, including a regression test for any bug.
4. Run `pytest`, `ruff check`, and `mypy`.
5. Do not commit secrets, `.env`, or `.canon/canon.db`.
6. Do not commit product plans, SaaS plans, strategy docs, or internal
   build briefs (PDF/TXT/DOCX). Those stay local and are gitignored.

## Product name

The product and CLI are **Canon**. Do not reintroduce the historical working
name in UI, CLI, package metadata, or user-facing copy.

## Releasing

Version is read from `src/canon/__init__.py` (`__version__`).

1. Bump `__version__` and update `CHANGELOG.md`.
2. Push to `main` and wait for CI.
3. Create a GitHub release named `vX.Y.Z` (for example `v1.0.1`).
4. `.github/workflows/publish.yml` builds the sdist/wheel and uploads to PyPI
   as `canon-memory` using trusted publishing.

First-time PyPI setup (once):

1. Create a PyPI account and enable 2FA.
2. Add a pending trusted publisher:
   - PyPI project name: `canon-memory`
   - Owner: `Adarshk18`
   - Repository: `Canon`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. Confirm the GitHub Actions environment `pypi` exists on this repository.
