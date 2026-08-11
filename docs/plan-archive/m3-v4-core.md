<!-- shadow:archive:v1:m3-v4-core:sha256:c3de76e0f5eb235331c4a255bce55339d51c6c37a27f32bfa6a1d74d615cf1c1:cas:26447780540ee0c0526d277c322548b1b69d5da4661470c0f62f3d3cbe286a49:head:b719ea4418bb23272aeefc9d69eb50ad57efb166:blob:2e1a8c8853fc67c84b795bb56cf8caf23f728e29:successor:~disc -->
# Archived milestone: m3-v4-core

Source: `PLAN.md`

## Exact milestone block

### M3 — v4 core
- [completed] the Method reduced to eight concepts, lint the enforcer ~h4v1 | proof: cmd npm run test:py | needs: ~r9c3
- [completed] four tagged plans on grammar v2: shadow, moussey #145, snowcubes #2113, resplit #2236 ~g4mv | proof: read shadow lint -> 0 blocking on all four | needs: ~h4v1
- [completed] v4.0.0 released, installed, doctor green ~z7e5 (DoD) | proof: read shadow doctor -> 11/11 on installed v4.0.0 | needs: ~h4v1

## Exact Progress receipts

- 2026-08-07T04:55:00Z SHIP report — mega goal (Shadow v4) closes agent-side: M3 DoD ~z7e5 proven (doctor 11/11 on installed 4.0.0); step 4 proven (~g4mv, four plans lint-clean); the 19-agent challenge fixed 12 confirmed defects pre-tag; standard vocabulary shipped per operator ruling. LESSON folded: invented vocabulary is product surface an operator must veto — standard words survive; the highest-yield adversarial target is the enforcers themselves. SUCCESSOR: the chain hands to product goals — first: trysnowcubes-web's open storefront milestone runs start-to-ship on Shadow as substrate; ASC resubmission stays gate leo. In-flight background: vocab-resweep workflow over moussey #145 / snowcubes #2113 / resplit #2236 (complete when all three report pushed + worktrees pruned). Deferred ~ob1c (one-chat brief surface) wake HAS fired; it re-parks with wake: the first product cycle names cold-start cost as friction — product goals own the chain first.
- 2026-08-07T04:35:00Z ~z7e5 PROOF shadow doctor on installed v4.0.0 -> 11/11, 0 warnings; tarball sha256 9b617fe0..3d53f matches the release; version 4.0.0 (read, re-observed post-install)
- 2026-08-07T04:35:00Z ~z7e5 DoD flips: M3 complete — the mega goal's Shadow-side work is done; the chain hands to product goals per the completion condition
- 2026-08-07T04:05:00Z ~g4mv PROOF shadow-lint over the four migrated plans -> 0 blocking (moussey fdb2f223 on #145; snowcubes draft #2113 + graphite; resplit 897801527 on #2236; worktrees torn down) (read)
- 2026-08-06T16:35:00Z PARK seat=chief — v4 (PR #254) is green locally
  (Python 131, JS 4, Playwright 10, docs, privacy, 4.0.0 package) and pushed,
  but merge is blocked by a GitHub Actions outage: every job fails at "Set up
  job" with "Failed to resolve action download info: Service Unavailable" —
  GitHub cannot fetch actions/checkout etc. Not our code; two re-triggers hit
  the same infra failure. Not retry-looping. RESUME: when Actions recovers,
  `gh run rerun` the failed workflows (or push an empty commit), and on green
  merge #254, cut v4.0.0, reinstall on the operator machine (flips DOD d2
  ~z7e5 Unknown->Verified), tear down the worktree.


- 2026-08-06T15:30:00Z ~h4v1 PROOF npm run test:py -> 124 pass, lint 0 blocking (accept)
- DOD d1 Method reduced to eight concepts, lint-enforced | C: ~h4v1 | proof: cmd npm run test:py -> pass, shadow lint 0 blocking | status: Verified
- DOD d2 v4.0.0 released, installed, doctor green | C: ~z7e5 | proof: read shadow doctor -> pending reinstall on the operator machine | status: Unknown
- 2026-08-05T23:05:00Z ~h4v1 PROOF seat=chief out=/api/plans readback shows four
  entity lanes (pilot-puppy, moussey, resplit, snowcubes) each with mode,
  milestone, checkpoint counts; desktop+phone board screenshots reviewed by
  eye (which caught and fixed the shell-hide defect in v2.3.2). Tagging PRs:
  moussey #145, trysnowcubes-web #2057 (first root PLAN.md), resplit-ios
  #2236 (additive; authority remains vidux/north-star).
- 2026-08-05T23:05:00Z ~h4v1 DONE seat=chief
- 2026-08-05T23:05:00Z ~z7e5 PROOF seat=chief out=this commit's own diff: mode
  Close declared in the Operator Brief, checkpoint rows flipped only with
  these paired PROOF lines, one re-portioning line with its trigger, and the
  Close matrix below — the cycle ran by the released grammar it shipped.
- 2026-08-05T23:05:00Z ~z7e5 DONE seat=chief

### Close

- DOD d3 Real plans render as entity lanes | C: ~h4v1 | proof: /api/plans readback + reviewed screenshots (scratchpad board-desktop/phone.png) | status: Verified
- DOD d4 One Method-style cycle ran in a tagged repo | C: ~z7e5 | proof: this commit's PLAN.md diff | status: Verified
