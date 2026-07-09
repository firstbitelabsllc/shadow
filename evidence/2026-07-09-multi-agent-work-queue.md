# Multi-agent work queue — 2026-07-09 (updated loop 2)

**Weakest truthful claim (this cycle):** `source-proven` — thin-token guide + Recipe 13 landed; `test:js` + browser_server + focused plan tests green. Simple UI still uncommitted WIP (implemented in tree, not yet PR-smoked as a package). No live browser toggle screenshot this cycle.

**Token burden:** PE bakeoff refuted kernel handoff. Remaining waste = full SKILL load. Mitigation shipped: `guides/thin-token.md` + Recipe 13.

## Ranked slices (dispatch next)

| Pri | ID | Slice | Status | Next agent |
|-----|-----|-------|--------|------------|
| **P0** | V-TEST-1 | Keep facelift focused tests green | **green this cycle** | re-run on every edit |
| **P0** | V-SIMPLE-1 | Simple-default cockpit package | **in tree, uncommitted** | commit + toggle smoke → PR |
| **P0** | V-TOKEN-1 | Thin-token recipe | **done** (`guides/thin-token.md`) | use only |
| **P1** | V-MULTI-1 | Multi-agent product fan-out | **done** (Recipe 13) | use only |
| **P1** | V-FACELIFT-1 | Commit Simple package + open/ready PR | **next** | nurse agent |
| **P1** | V-AUTO-1 | `/auto` contract env honesty | open | farm agent |
| **P2** | V-5.3.1 | Ready-PR automations | blocked (Resplit) | leave parked |
| **P2** | FARM-1/2 | OCCUPIED / chezmoi | deferred | leave |

## Fan-out now (if 3 agents available)

1. **Lead:** stage Simple UI + tests budget + guides; run full focused suite; commit on `facelift/insights-driven-hardening`
2. **Worker A (optional):** Playwright/Chrome toggle smoke Simple↔Advanced on `:7192`
3. **Worker B (optional):** draft PR body from thin-token + facelift hardening commits

## Testing cadence

```bash
cd ~/Development/vidux
npm run test:js
python3 -m unittest tests.test_plan_guard tests.test_write_verify \
  tests.test_step_journal tests.test_browser_server -q
```

## Do not do

- Reopen PE kernel as default control plane
- Load full SKILL for routine PLAN rows (use thin-token guide)
- `git reset --hard` Simple-mode WIP
- Mass-delete Skillbox OCCUPIED mounts
