# V23 React + Storybook Decision — 2026-05-03

## Decision

Keep PR #87 on vanilla JavaScript with static fixture snapshots.

Do not introduce React or Storybook for the read-aloud player in this PR.

## Why

- `browser/` is a Python `http.server` app with static HTML, CSS, and JavaScript.
- `package.json` has VitePress/Vue dev dependencies for docs, but no React, Storybook, Vite app bundle, webpack, Rollup, or esbuild app pipeline.
- The `/storybook` skill is useful in Leo's React repos, but this repo has no existing Storybook surface or story index to extend.
- V22 already produced the low-cost thing Storybook would provide here: a state harness covering offline, first load, synth queue, cache hit, playing, paused, seek hover, segment failure, long title, mobile width, and annotation-FAB coexistence.

## What shipped

- Added `browser/static/readaloud-fixture-manifest.json`, a machine-readable fixture contract.
- Linked that manifest from `browser/static/readaloud-fixture.html`.
- Made the decision visible in the fixture header: `vanilla fixture snapshots - no React/Storybook for PR #87`.
- Added static tests that assert the manifest decision, state coverage, and absence of React/Storybook browser-app dependencies.

## Browser proof

Opened:

`http://127.0.0.1:7192/static/readaloud-fixture.html`

Captured screenshot:

`evidence/2026-05-03-v23-storybook-decision.png`

No Read click, model download, or synthesis.

## Verification

- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests`
- `npm test` — 184 tests OK
- `git diff --check`
