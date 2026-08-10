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
