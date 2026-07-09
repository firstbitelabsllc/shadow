# Multi-agent work queue — 2026-07-09 (Resplit freeze)

**Hard rule (Leo 2026-07-09):** **Do not work on Resplit.** No `resplit-ios` probes, PRs, automations, or 5.3.1 unpark.

**Weakest truthful claim:** Nurse gate remains `npm run test:thin`. 5.3.1 is policy-blocked, not “waiting for clean Resplit.”

## Ranked next (Vidux-only)

| Pri | ID | Slice | Status |
|-----|-----|-------|--------|
| **P0** | **V-GREEN** | `npm run test:thin` | nurse only |
| **P3** | **V-PIXEL** | Optional Simple↔Advanced pixel smoke | optional, Vidux UI only |
| **FROZEN** | **5.3.1 / 5.3.2** | Ready-PR automations (were Resplit-coupled) | **do not touch** |

## Multi-agent

- Default **1 agent**, Vidux repo only.
- Load: `guides/thin-token.md` + this queue.
- **Never** `cd` into resplit-ios / resplit-web for this goal or the 30m loop.

```bash
npm run test:thin
```
