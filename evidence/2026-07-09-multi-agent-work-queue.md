# Multi-agent work queue — M4 Pro (Resplit is Studio)

**Hard rule (Leo 2026-07-09):** **Mac Studio owns Resplit.** On this M4 Pro: no `resplit-ios` / `resplit-web` probes, PRs, automations, or 5.3.1 unpark. Studio is doing that work.

**Weakest truthful claim:** M4 nurse gate = `npm run test:thin`. 5.3.1 is **Studio-owned**, not “blocked waiting for this Mac.”

## Ranked next (M4 / Vidux-only)

| Pri | ID | Slice | Status |
|-----|-----|-------|--------|
| **P0** | **V-GREEN** | `npm run test:thin` | nurse only |
| **P3** | **V-PIXEL** | Simple↔Advanced mode smoke (`npm run test:pixel`) | **shipped** — opt-in; not in `test:thin` |
| **DONE** | **V-CHROME-CUT** | Delete annotation FAB + read-aloud player (shell + engine + fixtures + voxtral scripts) | **shipped** 2026-07-09 |
| **STUDIO** | **5.3.1 / 5.3.2** | Ready-PR / Resplit-coupled automation | **Studio only — never on M4** |

### V-PIXEL / chrome-cut receipt (2026-07-09)

- Spec: `browser/tests/e2e/mode-pixel.spec.ts` via `npm run test:pixel`
- Full cut: no FAB/player in shell; deleted `readaloud.js` / kokoro / fixtures / voxtral scripts + CSS
- Comment rail + Cmd/Ctrl+Shift+C annotation capture remain (no FAB entry)
- Intentionally **outside** the ~5s thin nurse gate

## Multi-agent

- Default **1 agent**, Vidux repo only (this Mac).
- Load: `guides/thin-token.md` + this queue.
- **Never** `cd` into resplit-ios / resplit-web on M4 for this goal or the 30m loop.

```bash
npm run test:thin
```
