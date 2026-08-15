# Changelog

## 1.0.1 — 2026-08-15

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
