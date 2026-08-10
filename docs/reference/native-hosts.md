# Native hosts

Shadow supports `codex`, `claude-code`, and `cursor`. You choose the host
directly: `shadow host run --host <name>` is the complete sealed path. There
is no roster, route, or seat layer in front of it, and Shadow cannot verify
or guarantee the provider model or billing tier inside a host.

Every run requires an exact clean Git worktree, a frozen task file, a task
ID, and one or more exact allowed paths. Scope escape, missing receipt,
non-zero exit, timeout, or missing passing tests fails closed. The returned
claim stays `accepted_by_lead: false` until a person or lead agent reproduces
the proof. Shadow supplies the receipt contract to the host and records
the frozen task's SHA-256, not its prompt or provider output.

Shadow passes no model or account selector and records none. Which provider,
model, or account a host uses is that host CLI's own business, configured in
the host's own config (for example the Codex CLI config file, Claude Code
settings, or Cursor settings).

## A fleet map of hosts and models lives outside Shadow

If your fleet wants one human-readable map of which host runs which model, keep
it next to your other operator configuration — never in a plan, brief, status
output, or receipt. Have an agent regenerate it from the live host configs and
treat hand edits as drift.

Shadow ships no example of that file on purpose. A worked shape inside this
repository would be a template for model and account data in a product whose
boundary is that it passes no selector and records none — and the first person
to fill it in would fill it in here. The host CLI configs stay authoritative;
the map is a mirror for people, and it is yours.

## Activation surfaces — where the standing goal is written

Activation is distinct from delegation. Any supported host can RUN a sealed
task; activation is the standing-goal block `shadow goal --install` writes
into a host's own instruction file so a fresh chat opens the board without
being asked. The write targets:

| Host | Activation file |
| --- | --- |
| claude-code | `~/.claude/CLAUDE.md` |
| codex | `~/.codex/AGENTS.md` |

**Cursor is not activated, by decision (2026-08-10).** Cursor's user-level
rules live in the application's settings interface, not in a file: its own
rules documentation (cursor.com/docs/context/rules, read 2026-08-10) documents
project-scoped surfaces only — `.cursor/rules/*.mdc` and `AGENTS.md` in a
project root — and describes User Rules as configured through the Customize
interface, with no user-level file path. A local probe agrees: `~/.cursor`
holds no rules directory and no instruction file the application documents
reading. Writing `~/.cursor/rules/shadow.md` or `~/.cursor/AGENTS.md` would
invent a convention and then report success for wiring that does nothing —
the exact false-green shape this project refuses.

What a Cursor user does instead: put the standing goal block in a repository's
own `AGENTS.md`, which Cursor does read at the project root. That is a
per-repository choice made in that repository, not an install target —
Shadow's installer writes user-level files only.

This decision reverses nothing and closes silently-implied support: if Cursor
ships a documented user-level instruction file, the decision reopens with that
citation.
