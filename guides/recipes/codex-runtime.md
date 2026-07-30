# Recipe: Vidux on Codex

Use Codex as the coding host while the repository remains the authority. Codex
may run the work; Vidux does not depend on private Codex account, session,
database, cache, or model details.

## When to use

- The current Codex surface can read the named repository and `PLAN.md`.
- The task fits a supported Chat, Local, Worktree, scheduled, or subagent mode.
- The required verification can run in that mode.
- The lane has an exact write boundary and retirement condition.

Check current official Codex documentation for available modes and controls.
Do not rely on historical UI behavior or undocumented local storage.

## Runtime contract

A Codex-run cycle:

1. reads the owning `PLAN.md` and current revision;
2. claims one unblocked row;
3. changes only authorized paths;
4. runs the row's verification;
5. records outcome, proof, risk, and one resume action.

Codex configuration, conversation history, and automation state are diagnostic
runtime data. They are not plan or completion proof.

## Choose an execution mode

| Need | Preferred mode |
|---|---|
| Research, review, or status | Chat or read-only |
| Repository implementation | Isolated Worktree |
| Host-specific UI or local tool | Local |
| Independent bounded slice | Subagent |
| Repeatable maintenance | Supported automation surface |

Use the least-powerful mode that can complete the proof. Do not grant external
publication, deployment, destructive changes, secrets, or unrelated filesystem
access as part of a normal implementation lane.

## Automation setup

Register recurring work through Codex's supported product controls. The
automation prompt should point to a stable, repo-owned plan and include:

- mission and retirement condition;
- authority plan and allowed paths;
- deterministic task selection;
- verification requirements;
- blocker and checkpoint format.

Do not edit undocumented Codex databases, caches, session stores, or account
records. Do not copy their contents into a public repository.

Test one run before relying on a schedule. Verify that missed, failed, and
cancelled runs remain visible and that disabling the automation works through
the same supported control.

## Subagents

Give each child a working directory, revision, allowed paths, acceptance
checks, and output format. Keep writable paths disjoint. The lead reviews the
diff and reproduces important checks before accepting the work.

See `subagent-delegation.md` for the full handoff contract.

## Safety rules

1. Never bypass repository hooks to make a lane appear green.
2. Never force-push or delete branches, worktrees, or user files by default.
3. Never treat a child response or scheduled-run receipt as completion.
4. Never store credentials, account details, session identifiers, usage, cost,
   or private paths in public plan state.
5. Stop on an authority conflict and record the relation that must change
   before work can resume.

## See also

- `guides/automation.md` — runtime-neutral automation doctrine
- `guides/recipes/subagent-delegation.md` — bounded child-agent work
- `docs/fleet/platforms.md` — runtime selection questions
