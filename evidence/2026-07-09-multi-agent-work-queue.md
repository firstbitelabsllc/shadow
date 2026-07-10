# Multi-agent work queue - Vidux-only host

**Historical routing snapshot (2026-07-09):** project-specific automation was owned by another host. This queue was limited to Vidux and did not authorize downstream project probes, PRs, or automation changes.

**Weakest truthful claim:** the local nurse gate was `npm run test:thin`; downstream work stayed outside this queue.

## Ranked next (Vidux-only)

| Pri | ID | Slice | Status |
|-----|-----|-------|--------|
| **P0** | **V-GREEN** | `npm run test:thin` | nurse only |
| **P3** | **V-PIXEL** | Simple↔Advanced mode smoke (`npm run test:pixel`) | **shipped** — opt-in; not in `test:thin` |
| **DONE** | **V-CHROME-CUT** | Delete annotation FAB + read-aloud player (shell + engine + fixtures + voxtral scripts) | **shipped** 2026-07-09 |
| **EXTERNAL** | **5.3.1 / 5.3.2** | Downstream ready-PR automation | outside this historical queue |

### V-PIXEL / chrome-cut receipt (2026-07-09)

- Spec: `browser/tests/e2e/mode-pixel.spec.ts` via `npm run test:pixel`
- Full cut: no FAB/player in shell; deleted `readaloud.js` / kokoro / fixtures / voxtral scripts + CSS
- Comment rail + Cmd/Ctrl+Shift+C annotation capture remain (no FAB entry)
- Fable consult (2026-07-09): full-stack delete correct; chord needs in-product name → empty-state hint + smoke; thin green
- Intentionally **outside** the ~5s thin nurse gate

## Multi-agent

- Default **1 agent**, Vidux repo only on this host.
- Load: `guides/thin-token.md` + this queue.
- Downstream repositories required their own current authority before work.

```bash
npm run test:thin
```
