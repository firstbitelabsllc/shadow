# Host-owned execution

Vidux is not an agent scheduler. Your coding host may run one worker or many,
but it owns dispatch, authentication, provider selection, retries, and process
lifecycle.

Vidux contributes one small coordination contract:

1. Read the repository's `PLAN.md` before changing code.
2. Claim one bounded, unblocked task.
3. Avoid a surface another worker owns.
4. Verify the result with the repository's real gate.
5. Record the proof and a cold-resume next move in the plan.

## Multiple workers

Parallel work is safe only when write surfaces are disjoint. Treat worker
output as a draft until the owning agent reviews the diff and reproduces the
important proof. If a lane stops, resume from the plan, revision, and working
tree—not from a chat log.

## Worktrees

Use Git's normal worktree and branch commands. Vidux ships no worktree
garbage-collection tool and never removes a checkout. Before creating another
worktree, inspect existing work and preserve any unexplained changes.

## What does not belong in a public plan

Do not store credentials, account data, billing data, runtime identifiers, raw
conversation logs, or private machine paths. Keep only bounded facts, conflicts,
proof references, ownership, and the next move.
