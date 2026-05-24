# V25 Cache Hygiene + Controls — 2026-05-03

## What changed

- Added `#readaloud-cache-clear` to the fixed footer player.
- The cache pill now shows current playback source: `Fresh`, `Cached`, `Mixed`, `Cleared`, or disabled `Cache`.
- Clicking the pill deletes the current playback's per-segment IndexedDB cache keys and clears `currentCacheKey`, so the next `Read` regenerates the document instead of replaying the stale in-memory/cache path.
- Added cache-control styling, annotation-capture exclusion, ARIA labels, static fixture states, and contract tests.

## Proof

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`
- `npm test` → 184 tests OK
- Browser fixture screenshot: `evidence/2026-05-03-v25-cache-controls.png`

No model weights were downloaded. No Voxtral synthesis was run. Verification used static fixture/browser proof only.
