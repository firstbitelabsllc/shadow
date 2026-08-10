# Native hosts

Shadow's sealed host runner supports `codex`, `claude-code`, and `cursor`. You
choose the host directly: `shadow host run --host <name>` is the complete
sealed path. There is no roster, route, or seat layer in front of it, and
Shadow cannot verify or guarantee the provider model or billing tier inside a
host.

Cold directive activation is a narrower surface. Shadow manages a marker block
in Claude Code's `CLAUDE.md` and Codex's `AGENTS.md`. Cursor cold activation is
an explicit projection into global User Rules through Cursor's own application
surface. Shadow emits the exact block and derived hash, but does not invent a
file path, write private application settings, or claim it inspected them.

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

## Supported cold-activation targets

Activation is distinct from delegation. Any supported host can RUN a sealed
task; activation is the standing-goal block that lets a fresh chat open the
board without being asked. This table lists file-backed targets. When machine
configuration declares a canonical source, both targets must already resolve
to it; otherwise these built-in paths remain the default.

| Host selector | Activation file |
| --- | --- |
| claude | `~/.claude/CLAUDE.md` |
| codex | `~/.codex/AGENTS.md` |

**Cursor uses a projection, not a file target.** Declare
`directives.projections.cursor: user_rules` in the installed Shadow checkout's
ignored machine config. `shadow goal --install` prints the exact standing-goal
block and SHA-256 for a one-time Cursor-native User Rules action; `shadow
doctor` reports that expectation as manual and unobserved. A fresh uncoached
Cursor chat is the activation proof. Writing `~/.cursor/rules/shadow.md` or
`~/.cursor/AGENTS.md` would still be a false green because neither is a
documented user-level activation file.
