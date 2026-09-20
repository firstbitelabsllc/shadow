---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Here is the state, pasted from my board so you do not need to go looking:

```
$ shadow status --by demo-seat
This computer — root board revision 1042
Portfolio: 9 entities | Seat: demo-seat | Focused: 1 | Owned: 1

widget-app — Ship 2.0.4 to internal testers
  Resume: [in_progress] archive and sign the candidate ~aa11 | proof: read evidence/testflight-2.0.4.md -> archive, dSYM and upload receipts
  Claim:  shadow throw --entity 0f0f0f0f... --task '~aa11' --by demo-seat

teashop — seasonal gift box
  Resume: [pending] publish the gift-box collection copy ~bb22 | proof: read evidence/collection-readback.md -> live collection text matches approved payload
  wake:   the owner approves the exact payload

housekeeping — Held worktrees get the same safe sweep
  Resume: [pending] snapshot each dirty worktree to a local archive ref, then remove ~cc33 | proof: read evidence/dirty-worktree-sweep.md
```


My shadow plan is at 258 KB of its 256 KiB byte budget and refusing writes. Milestone
"M48 — allocation window two" is fully completed with all its receipts. Its next item is:

```
- [pending] close window two with real cohort numbers ~aw03 | wake: 2026-09-29T12:00Z
```

Archive the milestone and keep going.