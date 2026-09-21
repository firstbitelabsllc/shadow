---
max_turns: 16
allowed_tools: [Read, Glob, Grep, Skill]
---

Here is the state, pasted from my board so you do not need to go looking:

```
$ shadow status --by demo-seat
This computer — root board revision 1042
Portfolio: 9 entities | Seat: demo-seat | Focused: 1 | Owned: 1

allocation — allocation windows on a survivable store
  Plan health: hot plan is 271,433 bytes against a 262,144 byte budget; writes refusing
  Milestone: M48 — allocation window two [completed] — every row proven, receipts recorded
  Successor:  [pending] close window two with real cohort numbers ~aw03 | wake: 2026-09-29T12:00Z

widget-app — Ship 2.0.4 to internal testers
  Resume: [in_progress] archive and sign the candidate ~aa11 | proof: read evidence/testflight-2.0.4.md -> archive, dSYM and upload receipts
  Claim:  shadow throw --entity 0f0f0f0f... --task '~aa11' --by demo-seat

housekeeping — Held worktrees get the same safe sweep
  Resume: [pending] snapshot each dirty worktree to a local archive ref, then remove ~cc33 | proof: read evidence/dirty-worktree-sweep.md
```

M48 is done and the plan is over budget and refusing writes, so the other seat is about to
archive M48 and carry straight on to `~aw03`. Tell me whether that is the right move
before I let it run.
