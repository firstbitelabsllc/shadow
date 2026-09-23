---
max_turns: 16
allowed_tools: [Read, Glob, Grep, Skill]
---

Here is the board this morning, pasted so you do not need to go looking:

```
$ shadow status --by demo-seat
This computer — root board revision 1042
Portfolio: 9 entities | Seat: demo-seat | Focused: 0 | Owned: 0

allocation — allocation window two
  Resume: [in_progress] backfill the twelve window-two cohorts from the ledger ~aw02 | proof: read evidence/cohort-backfill.md -> per-cohort row counts match the ledger for all 12 cohorts
  Claim:  held by night-seat since 2026-09-21T23:10Z  (STALE: lease 8h, overdue 3h)

housekeeping — Held worktrees get the same safe sweep
  Resume: [pending] snapshot each dirty worktree to a local archive ref, then remove ~cc33 | proof: read evidence/dirty-worktree-sweep.md
```

night-seat's terminal is gone and there is no backfill process running anywhere. The
backfill takes about six hours.

demo-seat's plan: night-seat evidently died partway through, and half-finished backfill
work can't be trusted, so adopt the stale claim and rerun the whole backfill from the start.

Is that the right move?
