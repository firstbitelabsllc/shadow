# Multi-agent work queue — 2026-07-09 (loop 6)

**Weakest truthful claim:** `runtime-proven` focused suites green on main `34c77dd`; Resplit 5.3.1 **re-blocked** with live probe (not unparked). No pixel toggle.

## Steady state (shipped)

Simple-default · thin-token · Setup/Proof · contracts · main-active mount · `scripts/vidux-thin-loop-verify.sh` (new)

## Ranked next

| Pri | ID | Slice | Status |
|-----|-----|-------|--------|
| **P0** | **V-GREEN** | Each 30m loop: `bash scripts/vidux-thin-loop-verify.sh` | **green this cycle** |
| **P2** | **5.3.1** | Ready-PR automations | **blocked** — resplit-ios dirty + behind ~2654 + multi open PRs (2026-07-09 probe) |
| **P2** | **5.3.2 / 5.4.x** | Depends 5.3.1 / Wave 3 | parked |
| **P3** | **V-PIXEL** | Playwright Simple↔Advanced pixel | optional only |

## Multi-agent rule (all boats)

- **Default: 1 agent.** Fan-out only for path-disjoint product slices.
- **Never** PE kernel / full SKILL for nurse cycles.
- Load: `guides/thin-token.md` + PLAN Current State + this queue.
- Proof: `scripts/vidux-thin-loop-verify.sh` (+ `tests.test_browser_server` when browser code changes).

## Resplit probe (5.3.1)

```
resplit-ios: main ahead 7 behind ~2654, dirty ledger/plans
open PRs: 1891, 1888, 1887, 1886, 1871, …
```

Unpark 5.3.1 only when: clean attached root (or isolated worktree), trunk not wildly diverged for the lane, and ≤1 automation PR per active lane.
