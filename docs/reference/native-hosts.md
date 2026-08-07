# Native hosts

Shadow supports `codex`, `claude-code`, and `cursor`. You choose the host
explicitly. Shadow cannot verify or guarantee the provider model or billing
tier inside that host.

Every run requires one exact clean Git worktree, one frozen task file, one task
ID, and one or more exact allowed paths. Scope escape, missing receipt,
non-zero exit, timeout, or missing passing tests fails closed. The returned
claim stays `accepted_by_lead: false` until a person or lead agent reproduces
the proof. Shadow supplies the receipt contract to the host and records
the frozen task's SHA-256, not its prompt or provider output.

Shadow passes no model, profile, or account selector to the host; that choice
lives in the host CLI's own configuration. Shadow does not discover selector
names, inspect provider accounts or quotas, or add fallback/retry behavior.
