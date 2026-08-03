# Native hosts

Pilot Puppy supports `codex`, `claude-code`, and `cursor`. You choose the host.

Every run requires one exact clean Git worktree, one frozen task file, one task
ID, and one or more exact allowed paths. Scope escape, missing receipt,
non-zero exit, timeout, or missing passing tests fails closed. The returned
claim stays `accepted_by_lead: false` until a person or lead agent reproduces
the proof. Pilot Puppy supplies the receipt contract to the host and records
the frozen task's SHA-256, not its prompt or provider output.

Pre-existing ignored files must be inside an allowed path or the bounded local
evidence directory. This keeps ignored files inside the same scope audit.
