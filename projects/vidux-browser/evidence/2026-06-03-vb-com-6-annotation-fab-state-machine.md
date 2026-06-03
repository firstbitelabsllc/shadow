# VB-COM-6 Annotation FAB State Machine

Task: `VB-COM-6 Annotation FAB state machine`.

## Changed

- Added `browser/static/annotation-state.js`, loaded before `app.js`, as the named state/view contract for the floating Annotate FAB.
- The FAB now exposes `data-annotation-state` and aria/button text for `unavailable`, `idle`, `capture-active`, `target-picked`, `composer-open`, `saving`, `saved`, and `error`.
- Comment submit now visibly enters `saving`, briefly confirms `saved`, stays in `error` on failed save, and preserves `Cmd/Ctrl+Shift+C`, Escape, outside-click, and textarea shortcut immunity.
- Tightened popover action layout so the error status truncates and `Add comment` does not wrap.

## Proof

- `node --check browser/static/app.js && node --check browser/static/annotation-state.js` PASS.
- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests.test_annotation_fab_state_machine_contract_is_named` PASS.
- `python3 -m py_compile browser/server.py` PASS.
- `python3 -m unittest tests.test_browser_server` PASS, 61/61.
- `npm run test:js` PASS, 7/7.
- `npm run docs:build` PASS.
- `npx playwright test browser/tests/e2e/smoke.spec.ts --grep "annotation FAB exposes" --project=desktop-chromium` PASS, 1/1.
- `npx playwright test browser/tests/e2e/smoke.spec.ts` PASS, 45/45 after the final CSS adjustment.
- Scoped `git diff --check` PASS.
- Size check: `browser/static/app.js` is 99,973 bytes; new helper is 2,318 bytes.

## Live 7191 Proof

Live target: `http://127.0.0.1:7191/`, health OK on port 7191 with server mtime `1780476429578827627`.

Live proof JSON:
- `projects/vidux-browser/evidence/2026-06-03-vb-com-6-annotation-fab-state-machine-live-proof.json`

Observed states:
- `idle -> capture-active -> composer-open -> composer-open textarea shortcut immune -> saving -> saved -> idle -> error`

Live browser proof:
- desktop console errors: `[]`
- desktop page errors: `[]`
- mobile console errors: `[]`
- mobile page errors: `[]`
- mobile viewport: `390/390`, `sidebarOffscreen=true`, `fabClearsFooter=true`
- comments mutated: `false`; `/api/comments` was intercepted in proof to exercise UI transitions without writing real app data.

Screenshots:
- `projects/vidux-browser/evidence/2026-06-03-vb-com-6-annotation-fab-state-machine-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-com-6-annotation-fab-state-machine-saving.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-com-6-annotation-fab-state-machine-error.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-com-6-annotation-fab-state-machine-mobile-final.png`

## Non-Claims

- No real comments, plans, artifacts, LaunchAgents, local-CI lanes, external services, stage, commit, push, PR, or release were mutated.
- No annotation review drawer, anchor markers, thread lifecycle model, visual-state harness, or Storybook work shipped in this slice.
