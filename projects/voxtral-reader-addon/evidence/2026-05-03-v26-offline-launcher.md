# V26 Offline Launcher Guidance — 2026-05-03

## What changed

- The `MLX` source chip is now a button. Clicking it copies the local server command:

```sh
browser/scripts/start-voxtral-mlx-server.sh
```

- When the loopback health probe reports offline while the player is idle, the footer status now says:

```text
Server offline. Run from the vidux repo root: browser/scripts/start-voxtral-mlx-server.sh
```

- The offline/error state reveals a compact command pill under the status line. The pill is keyboard-focusable, annotation-safe, and also copies the command.
- The static fixture now covers both `server-offline` and `server-command-copied` states.

## Verification

- `node --check browser/static/readaloud.js`
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `git diff --check`
- Browser proof: `evidence/2026-05-03-v26-offline-launcher.png`

No Read click, model download, or synthesis was run.
