# Multi-agent work queue — 2026-07-09 (loop 5)

**Weakest truthful claim:** `runtime-proven` for browser health + static Simple wiring; `unit-proven` for Simple-default contract. No Playwright pixel toggle screenshot.

## Steady state on main

| Item | Status |
|------|--------|
| Simple-default cockpit | shipped #191 |
| Thin-token + Recipe 13 | shipped #191 |
| Setup/Proof thin | shipped #195 |
| Thin-token contracts | shipped #193 |
| `/auto` off farm | archived ai-leo |
| **vidux-main-active** | → `Development/vidux@main` (live tip tracked) |
| **Tests** | loop5: test:js **8/8**, focused py **46 PASS**, health **200** |

## Ranked next

| Pri | ID | Slice | Notes |
|-----|-----|-------|-------|
| **P1** | **V-PIXEL** | Optional Playwright Simple↔Advanced pixel smoke | only if visual regression risk rises |
| **P2** | **5.3.1** | Ready-PR automations | blocked on Resplit overlap |
| **P2** | **5.4.x** | Branch protection for automation actors | depends Wave 3 |
| **P2** | Farm OCCUPIED | Skillbox doctor noise | document-only |

## Multi-agent posture (steady state)

- **Do not** fan out kernel/PE sidecars.
- Default load: `guides/thin-token.md` + PLAN Current State + one Open work row.
- Max 2–3 workers only when a **new** path-disjoint product slice appears.
- Rising-tide default: keep tests green; prefer docs/test contracts over SKILL bloat.

## Proof this cycle

```bash
npm run test:js   # 8 tests incl. Simple/Advanced default contract
# live: python3 browser/server.py --port 7193 → GET /api/health 200; app.js serves isAdvancedMode
```
