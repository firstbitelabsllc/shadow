# VB-ACT-1 App-Action Zoning Proof

Date: 2026-06-03

## Change

Formalized the vidux-browse app chrome zones:

- Header/status zone stays for global status, filters, theme, and refresh controls.
- Footer zone stays for the read-aloud player.
- Floating action zone owns page-mode entry points such as Annotate.
- Mode detail/popover zones own annotation drawer and composer surfaces.

The UI now exposes `data-vidux-zone` markers for the header, app shell, sidebar, pane, floating action, footer player, annotation detail panel, and annotation popover. Shared CSS tokens define the app chrome z-index and footer reserve contract so the read-aloud footer, annotation FAB, comments panel, popover, and mobile layout do not collide.

Also repaired the existing auto-refresh mobile smoke after the broad Playwright run showed it selected an artifact while the mobile sidebar still covered the pane. The product path was unchanged; the spec now closes the drawer before asserting the artifact iframe.

## Files

- `browser/static/style.css`
- `browser/static/index.html`
- `browser/static/app.js`
- `browser/tests/e2e/smoke.spec.ts`
- `tests/test_browser_server.py`
- `projects/vidux-browser/PLAN.md`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-live-proof.json`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-playwright-proof.json`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-mobile.png`

## Verification

- `python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests.test_app_action_zoning_contract_names_chrome_layers` PASS
- `node --check browser/static/app.js` PASS
- `npm run test:e2e -- --grep "app-action zones"` PASS, 3 tests
- `python3 -m unittest tests.test_browser_server` PASS, 60 tests
- `npm run test:js` PASS, 7 tests
- `npm run docs:build` PASS
- `npm run test:e2e -- --grep "auto-refresh polling"` PASS, 3 tests
- `npm run test:e2e` PASS, 42 tests
- Scoped `git diff --check` PASS
- Publish scrutiny PASS, `ready=true`
- Publish ledger PASS: `evt_vidux_publish_vb_act_1_app_action_zoning` at `/Users/leokwan/.agent-ledger/activity.jsonl:6114`

## Live Browser Proof

Live app: `http://127.0.0.1:7191/`

In-app browser proof wrote:

- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-live-proof.json`

Summary:

- URL: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md&tab=Ledger`
- Zones present: `status-header`, `app-shell`, `navigation-sidebar`, `content-pane`, `floating-action`, `footer-player`
- z-index token order: header `20`, footer `30`, action `40`, popover `50`
- `fabClearsFooter`: true
- `horizontalOverflow`: false
- Viewport: `1280x720`

The in-app screenshot capture timed out after the DOM proof was written, so visual proof was captured with Playwright against the same live server and plan URL:

- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-playwright-proof.json`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-act-1-app-action-zoning-mobile.png`

Desktop proof:

- URL: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md&tab=PLAN.md`
- Viewport: `1280x720`
- Zones present: `status-header`, `app-shell`, `navigation-sidebar`, `content-pane`, `mode-detail`, `floating-action`, `footer-player`, `mode-popover`
- z-index token order: header `20`, footer `30`, action `40`, popover `50`
- `fabClearsFooter`: true
- `popoverAboveAction`: true
- `horizontalOverflow`: false

Mobile proof:

- URL: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md&tab=PLAN.md`
- Viewport: `390x844`
- Zones present: `status-header`, `app-shell`, `navigation-sidebar`, `content-pane`, `mode-detail`, `floating-action`, `footer-player`, `mode-popover`
- z-index token order: header `20`, footer `30`, action `40`, popover `50`
- `fabClearsFooter`: true
- `popoverAboveAction`: true
- `horizontalOverflow`: false

## Non-Claims

- This does not ship the full annotation FAB state machine; `VB-COM-6` remains pending.
- This does not ship review drawer/marker work; `VB-COM-7`, `VB-COM-8`, and `VB-COM-9` remain pending.
- This does not introduce React or Storybook; `VB-COM-10` remains pending.
- This does not mutate comments, plans, artifacts, LaunchAgents, external services, or local-CI lanes.
- No stage, commit, push, PR, or release was created.

## Resume

Next agent can resume at `VB-COM-6 Annotation FAB state machine` in `projects/vidux-browser/PLAN.md`.
