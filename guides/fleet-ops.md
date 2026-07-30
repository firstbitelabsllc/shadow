# Multiple workers without a second scheduler

Vidux does not dispatch or supervise workers. The coding host owns execution;
the repository plan owns durable coordination.

## Before work

1. Read `PLAN.md`, the current revision, and the working tree.
2. Resume an active row before taking new work.
3. Inspect existing branches, worktrees, and pull requests.
4. Claim one bounded surface and name its verification gate.

## During work

- Keep writable surfaces disjoint.
- Treat delegated output as a draft.
- Preserve unexplained local changes.
- Record material decisions in the plan, not in chat history.

## Handoff

Leave:

- the exact outcome state;
- changed paths;
- proof reproduced at the current revision;
- open risks or blockers;
- one cold-resume next move.

Use Git's normal worktree commands. Vidux ships no worktree cleanup tool and
never removes another worker's checkout.
