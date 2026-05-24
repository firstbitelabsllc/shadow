# V24 reader accessibility + keyboard hardening - 2026-05-03

## What changed

- `browser/static/index.html`: read-aloud footer is now a named `role="region"` with `aria-describedby` pointing at a live status line.
- `browser/static/readaloud.js`: read/play/speed/source controls update ARIA labels as state changes; loading state sets `aria-busy`; seek control reports `aria-valuetext`; section Read buttons expose section-specific labels and busy state; highlighted words are keyboard-focusable `role="button"` spans with Enter/Space jump support.
- `browser/static/style.css`: focus-visible rings added for word jumps, footer controls, speed, seek, and section Read controls; section Read remains visible during keyboard focus.
- `browser/static/readaloud-fixture.html`: fixture controls mirror production ARIA so future visual proof covers the accessibility contract.
- `tests/test_browser_server.py`: static contracts now assert the new ARIA and keyboard affordances.

## Browser proof

- Screenshot: `evidence/2026-05-03-v24-accessibility-keyboard.png`
- URL: `http://127.0.0.1:7192/static/readaloud-fixture.html`
- Command:

```bash
browse env local >/dev/null
browse viewport 1220 1179 >/dev/null
browse goto http://127.0.0.1:7192/static/readaloud-fixture.html >/dev/null
browse wait load >/dev/null
browse screenshot projects/voxtral-reader-addon/evidence/2026-05-03-v24-accessibility-keyboard.png
```

## Verification

```bash
node --check browser/static/readaloud.js
python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests
git diff --check
npm test
```

Result: all passed. Full `npm test` ran 184 tests.

## Model / synthesis note

No Read click, model download, or audio synthesis happened in this cycle. Verification used static contracts and the visual fixture only.
