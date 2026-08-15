# Agent integrations

Research date: August 2026. Product requirements come from the source plan.
Technical contracts come from official docs.

## Claude Code (primary)

Official references:

- Hooks: https://code.claude.com/docs/en/hooks
- Memory / CLAUDE.md: https://code.claude.com/docs/en/memory

Chosen mechanism: **SessionStart command hook** in `.claude/settings.json`.

Why this one:

1. Officially supported.
2. Runs automatically on startup, resume, clear, compact, and fork.
3. Stdout / `additionalContext` becomes model context without the user
   remembering to query Canon.
4. Exec form (`command` + `args`) avoids a shell.
5. Can be installed and removed without rewriting `CLAUDE.md`.

Hook output:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "# Canon — Active Project Decisions\n..."
  }
}
```

Plain stdout would also work for SessionStart. JSON is used so the payload
is structured and stays within the 10,000 character hook output cap.

Complementary: `.claude/rules/canon.md` reminds Claude to treat confirmed
decisions as authoritative. Canon does not own `CLAUDE.md`.

Uninstall removes only the Canon hook and the managed rule file.

## Cursor (secondary)

Official reference: https://cursor.com/docs/rules

Cursor project rules are `.cursor/rules/*.mdc` with frontmatter.
`alwaysApply: true` includes the rule in every Agent session.
Rules may `@`-reference files.

Chosen mechanism:

- `.cursor/rules/canon.mdc` (`alwaysApply: true`)
- `@.canon/injection.md`

Why not a hook: Cursor does not document a SessionStart hook comparable to
Claude Code. Inventing an unsupported hook would violate the V1 rule
“do not invent unsupported hooks”.

Limitation: the snapshot is a file. Cursor picks it up on the next Agent
session after Canon rewrites `.canon/injection.md`. Users should start a
new chat after approving a decision.

`.cursorrules` is legacy and is not written.

## Shared snapshot

`.canon/injection.md` is the portable injection document. Claude's hook
builds the same text dynamically from SQLite (fresher). Cursor reads the
file. `canon inject-preview` prints that text.

## Detection

`canon init` installs Claude and Cursor integrations by default (config
flags `integrations.claude` / `integrations.cursor`). `canon doctor`
reports whether the managed files are present.
