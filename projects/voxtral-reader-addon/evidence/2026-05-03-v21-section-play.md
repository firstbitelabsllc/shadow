# V21 Section Play Affordances — 2026-05-03

## What shipped

- Added quiet section-level `Read` controls for readable rendered blocks (`paragraph`, `list-item`, `quote`, `artifact-block`).
- Controls are generated from the existing V18 segment inventory and call the existing V19/V20 segment cache, merge, footer-player, seek, and highlight path.
- Controls are excluded from annotation capture and from segment text hashing, so the inserted `Read` buttons do not pollute cache keys or speech payloads.
- Code blocks and non-text chrome are skipped.

## Browser proof

Worktree preview: `http://127.0.0.1:7192/?plan=vidux%2Fprojects%2Fvoxtral-reader-addon%2FPLAN.md`

The browser proof stubbed `http://127.0.0.1:8765/health` and `/v1/audio/speech` in-page, returning a tiny generated WAV. No Voxtral weights were downloaded and no real synthesis ran.

Observed result:

```json
{
  "controls": 2,
  "codeHasControl": false,
  "speechPayload": "Second section unique target text should be the only payload sent to the local loopback speech endpoint for this section playback proof.",
  "firstWordSpans": 0,
  "secondWordSpans": 22,
  "playerStatus": "Playing generated audio",
  "activeWord": "Second"
}
```

Screenshot: `evidence/2026-05-03-v21-section-play.png`

## Verification

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`
- `npm test` — 182 tests OK
