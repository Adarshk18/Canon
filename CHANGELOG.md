# Changelog

## 1.2.0 — 2026-08-17

- Optional Canon Cloud: `canon cloud login|push|pull|invite|upgrade`
- Team workspaces keyed by the GitHub repo slug
- Billing via Polar.sh (not Stripe — India is invite-only)
- Local CLI still works with no account and no server

## 1.1.0 — 2026-08-17

- Inject only decisions whose source commit is already on this checkout
- Hide a decision after a git revert or an explicit supersede
- Mine local git from the default branch, not the current feature branch
- Do not treat `migrate utils into lib/` as a decision
- Stop tagging unrelated commits as `auth` (`session`, `security/`)
- Keep the full commit/PR explanation on suggest/show (injection stays short)

## 1.0.1 — 2026-08-16

- First PyPI release: `pip install canon-memory`
- Mine product/policy decisions (drop a surface, rename A→B, model fallback, show-only constraints)
- Do not treat every `rename` or `fix(ui)` as a decision
- Inspect 80 recent commits by default (was 40)

## 1.0.0 — 2026-08-15

First shippable Canon V1.

- Local-first CLI with SQLite decision store
- `init`, `status`, `suggest`, `approve`, `reject`, `list`, `show`, `inject-preview`, `inject`, `doctor`, `config`, `export`, `import`, `uninstall`
- Deterministic PR/commit mining without an LLM
- Supersession and provenance
- Claude Code SessionStart hook injection
- Cursor always-apply project rule plus generated snapshot
- Conservative injection budget
- Opt-in local telemetry only
- Tests, lint, typecheck, and GitHub Actions CI
