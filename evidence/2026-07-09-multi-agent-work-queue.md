# Multi-agent work queue — M4 Pro (Resplit is Studio)

**Hard rule (Leo 2026-07-09):** **Mac Studio owns Resplit.** On this M4 Pro: no `resplit-ios` / `resplit-web` probes, PRs, automations, or 5.3.1 unpark. Studio is doing that work.

**Weakest truthful claim:** M4 nurse gate = `npm run test:thin`. 5.3.1 is **Studio-owned**, not “blocked waiting for this Mac.”

## Ranked next (M4 / Vidux-only)

| Pri | ID | Slice | Status |
|-----|-----|-------|--------|
| **P0** | **V-GREEN** | `npm run test:thin` | nurse only |
| **P3** | **V-PIXEL** | Optional Simple↔Advanced pixel smoke | optional, Vidux UI only |
| **STUDIO** | **5.3.1 / 5.3.2** | Ready-PR / Resplit-coupled automation | **Studio only — never on M4** |

## Multi-agent

- Default **1 agent**, Vidux repo only (this Mac).
- Load: `guides/thin-token.md` + this queue.
- **Never** `cd` into resplit-ios / resplit-web on M4 for this goal or the 30m loop.

```bash
npm run test:thin
```
