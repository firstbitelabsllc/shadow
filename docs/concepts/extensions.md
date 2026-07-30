# No external integrations

Vidux authority is repository files + Git. The core ships no external-board or
issue-tracker sync.

`PLAN.md` in git is the only queue/planning authority. You read it, update it, and
checkpoint it in the repository. If your team lives on a kanban board, mirror the plan
state there by hand — vidux will not round-trip to one.

Why plan-native: the store *is* the discipline. A second synced surface is a second
source of truth, and the failure mode of every board integration is silent drift
between the board and the plan. Keeping `PLAN.md` as the sole authority removes that
drift by construction.

## FAQ

### What if my team already works from a board?

Keep using it for human communication if you want, but treat it as a mirror.
Vidux will not sync tasks, statuses, comments, or ownership back and forth. The
agent-readable source of truth stays `PLAN.md`, linked proof, and the Git
revision.

### Can I build my own bridge?

Yes, outside the core contract. Keep it as a private overlay or downstream tool
that reads `PLAN.md` and writes its own projection. Do not make Vidux depend on
that projection, and do not teach agents that the projection is authoritative.

The same rule applies to the optional local ledger used by `vidux checkpoint`:
it may receive a checkpoint row, but it does not become authority or a
publication gate.
