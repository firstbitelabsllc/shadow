# V22 Player Visual-State Harness — 2026-05-03

## What shipped

- Added `browser/static/readaloud-fixture.html`, a static no-JS visual harness for read-aloud footer states.
- The harness reuses the production read-aloud player classes with a `readaloud-player-fixture` override, so style regressions are visible before any React / Storybook decision.
- Covered states: `server-offline`, `first-load`, `synth-queue`, `cache-hit`, `playing`, `paused`, `seek-hover`, `segment-failure`, `long-title`, `mobile-width`, and `annotation-fab-coexistence`.

## Browser proof

Opened:

`http://127.0.0.1:7192/static/readaloud-fixture.html`

Captured full-page screenshot:

`evidence/2026-05-03-v22-player-fixture.png`

This proof did not click Read, download model weights, or synthesize audio.

## Verification

- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `npm test` — 183 tests OK
- `git diff --check`
