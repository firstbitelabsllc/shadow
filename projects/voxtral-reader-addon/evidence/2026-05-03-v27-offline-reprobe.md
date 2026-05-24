# V27 Offline-to-Online Auto-Reprobe — 2026-05-03

## What Shipped

- Added a bounded offline health retry loop in `browser/static/readaloud.js`.
- When the MLX server is offline, the footer keeps showing `browser/scripts/start-voxtral-mlx-server.sh` and polls `/health` every 3 seconds for up to 90 seconds.
- If the server comes online during that window, the `MLX off` source state flips back to ready without requiring another Read click.
- If the retry window expires, the footer stays explicit: `Server still offline. Run from the vidux repo root: browser/scripts/start-voxtral-mlx-server.sh`.
- Added a `server-waiting` visual fixture state and manifest entry.

## Verification

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`
- Browser proof: `evidence/2026-05-03-v27-offline-reprobe.png`

No Read click, model download, or synthesis was performed.
