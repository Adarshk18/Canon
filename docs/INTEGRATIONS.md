# Agent integrations

Research date: August 2026. Official contracts come from vendor docs.
Canon does **not** duplicate vendor memory. It fills the gap those
products document themselves: agent-written notes are not team law.

## What vendors already do (not Canon)

| Tool | Native memory / rules | Who writes it | Shared with the team? | Rejected approaches |
| --- | --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` + auto-memory (`MEMORY.md`) | You write CLAUDE.md. Claude writes auto-memory. | CLAUDE.md can be git. Auto-memory is machine-local. | No lifecycle |
| Cursor | `.cursor/rules`, `AGENTS.md`, Team Rules | You (or the agent, if you ask) | Rules can be git. Memories are not this. | No lifecycle |
| Grok Build | `AGENTS.md` / `.grok/rules` + experimental memory | You write rules. Grok writes `~/.grok/memory/` | Rules can be git. Memory is local and off by default. | No lifecycle |
| Codex / ChatGPT | `AGENTS.md` + local memories | You write AGENTS.md. Codex extracts chat memories. | Docs say: keep required team guidance in AGENTS.md. Memories are a recall layer. | No lifecycle |

Claude's own memory docs: auto-memory is notes Claude writes; it is not
enforced; it skips what it thinks git already shows. Grok SessionStart
hooks **ignore stdout**, so a Claude-style `additionalContext` hook cannot
inject decisions into Grok. Codex memories are generated from chats and
stored under `~/.codex/memories/`.

None of that is: mine git → human yes/no → active/rejected/superseded →
inject only what is currently in force, with provenance.

## Claude Code

Official: https://code.claude.com/docs/en/hooks
https://code.claude.com/docs/en/memory

Mechanism: **SessionStart command hook** in `.claude/settings.json`
(exec form, no shell). JSON `additionalContext`. Does not rewrite
`CLAUDE.md`. Complementary `.claude/rules/canon.md`.

## Cursor

Official: https://cursor.com/docs/rules

Mechanism: `.cursor/rules/canon.mdc` with `alwaysApply: true`, pointing at
`.canon/CANON.md` (team) and `.canon/injection.md` (checkout-local).
Cursor has no SessionStart hook comparable to Claude Code.

Start a new Agent chat after `canon approve`.

## Grok Build

Official (TUI user guide): project rules load `AGENTS.md` and
`.grok/rules/*.md`. SessionStart stdout is ignored.

Mechanism:

- `.grok/rules/canon.md` contains the snapshot (Grok loads the file)
- `.grok/hooks/canon.json` runs `canon inject --refresh-files` so the
  snapshot is current at session start
- `AGENTS.md` managed block (Grok also reads AGENTS.md)

## Codex, Copilot, Gemini, Windsurf, Cline, Continue

`AGENTS.md` is the portable standard (Codex, Cursor, Copilot agent,
Gemini, Jules, Factory, Windsurf, and others). Canon writes a managed
block and does not delete user content outside the markers.

Also:

| Tool | File |
| --- | --- |
| GitHub Copilot | `.github/copilot-instructions.md` managed block |
| Gemini CLI | `GEMINI.md` managed block |
| Windsurf | `.windsurf/rules/canon.md` |
| Cline | `.clinerules/canon.md` |
| Continue | `.continue/rules/canon.md` |
| Any MCP client | `.mcp.json` → `canon mcp` |

ChatGPT web cannot auto-inject. Attach `.canon/CANON.md`.

## Team snapshot

| File | Git | Role |
| --- | --- | --- |
| `.canon/CANON.md` | commit | Active decisions for every agent that reads files |
| `.canon/decisions.json` | commit | Clone hydrate + CI |
| `.canon/injection.md` | gitignore | HEAD-filtered local snapshot |
| `.canon/canon.db` | gitignore | Working store |

`canon init` on a clone imports `decisions.json` when the database is empty.

## MCP

`canon mcp` is a local stdio server: `canon_list`, `canon_show`,
`canon_query`, `canon_inject`. No network. Agents use it when the
injected budget is too small.

## GitHub Action

```yaml
- uses: Adarshk18/Canon/.github/actions/check@main
```

Runs `canon check --strict` so a PR that re-adopts a rejected decision fails.

## Detection

`canon init` installs every integration that is enabled in
`[integrations]` (all on by default). `canon doctor` reports each one.
`canon uninstall` removes only Canon-managed blocks and files.
