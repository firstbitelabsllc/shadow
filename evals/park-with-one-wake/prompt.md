---
max_turns: 16
allowed_tools: [Read, Glob, Grep, Skill]
---

The store upload key for the widget app expired this morning, and only the owner can issue
a new one. Here is the board as it stands, pasted so you do not need to go looking:

```
$ shadow status --by demo-seat
This computer — root board revision 1042
Portfolio: 9 entities | Seat: demo-seat | Focused: 1 | Owned: 1

widget-app — Ship 2.0.4 to internal testers
  Resume: [in_progress] build the 2.0.4 release archive and its dSYM bundle, then upload the candidate to the tester track ~aa11 | proof: read evidence/testflight-2.0.4.md -> archive, dSYM and upload receipts
  Claim:  held by demo-seat since 2026-09-22T09:10Z

teashop — seasonal gift box
  Resume: [pending] publish the gift-box collection copy ~bb22 | proof: read evidence/collection-readback.md -> live collection text matches approved payload
  wake:   the owner approves the exact payload

housekeeping — Held worktrees get the same safe sweep
  Resume: [pending] snapshot each dirty worktree to a local archive ref, then remove ~cc33 | proof: read evidence/dirty-worktree-sweep.md
```

Nothing for 2.0.4 has been built yet. The build machine, the source and the local signing
certificate are all fine; only the upload key is gone.

The other seat is about to park `~aa11` like this: mark the row `[blocked]` with
`wake: the owner issues a new store upload key`, return the claim, and move on to `~cc33`.

Is that the right way to park it?
