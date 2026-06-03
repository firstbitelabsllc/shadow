# VB-NEW-4 Filter Chips Proof

Date: 2026-06-03

## Change

Added persisted sidebar quick-filter chips for:

- `hot`: only freshness-hot plans.
- `tasks`: only plans with task totals.
- `ETA`: only plans with active remaining ETA.

The chip filters apply after the text filter and before grouping/sorting. Artifact rows and artifact recents are hidden while chip filters are active because the chip predicates are plan-only. Plan recents are also constrained to the filtered plan set, so recent rows do not bypass the selected chip.

Also tightened sidebar progress-row flex layout after live proof showed labels could force horizontal overflow in narrow rows. The clamp is scoped to `.progress-row .progress-bar`, so pane progress bars keep their existing full-width behavior.

`browser/static/sidebar-filters.js` holds storage, matching, toggle, and button-sync helpers so `browser/static/app.js` stays below the 100 KB source-size smoke limit.

## Files

- `browser/static/index.html`
- `browser/static/sidebar-filters.js`
- `browser/static/app.js`
- `browser/static/style.css`
- `browser/tests/e2e/smoke.spec.ts`
- `browser/tests/fixtures/fake-dev-root/proj-gamma/PLAN.md`
- `tests/test_browser_server.py`
- `README.md`
- `docs/reference/browser.md`
- `projects/vidux-browser/PLAN.md`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-live-proof.json`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-mobile-open.png`

## Verification

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS
- `node --check browser/static/sidebar-filters.js` PASS
- `node --check browser/static/app.js` PASS
- `wc -c browser/static/app.js browser/static/sidebar-filters.js` PASS: `app.js` 99085 bytes, helper 2402 bytes
- `python3 -m unittest tests.test_browser_server.BrowserDashboardTests.test_dashboard_static_contract` PASS
- `python3 -m unittest tests.test_browser_server` PASS, 57 tests
- `npm run test:js` PASS, 7 tests
- `npm run docs:build` PASS
- `npm run test:e2e -- --grep "filter chips"` PASS, 3 tests
- `npm run test:e2e` PASS, 36 tests
- Scoped `git diff --check` PASS
- Publish scrutiny PASS, `ready=true`
- Publish ledger PASS: `evt_vidux_publish_vb_new_4_filter_chips` at `/Users/leokwan/.agent-ledger/activity.jsonl:6112`

Note: the first focused Playwright run caught the iPhone spec clicking the chip while the mobile drawer was closed. The product path was correct; the spec now opens the drawer before interacting on narrow viewports.

## Live UI Proof

Live app: `http://127.0.0.1:7191/`

Health:

```json
{
  "ok": true,
  "dev_root": "/Users/leokwan/Development",
  "port": 7191,
  "repo_root": "/Users/leokwan/Development/vidux",
  "server_path": "/Users/leokwan/Development/vidux/browser/server.py",
  "server_mtime_ns": 1780476429578827627,
  "artifacts_dir": "/Users/leokwan/Development/vidux/browser/artifacts"
}
```

Desktop and mobile live proof:

- ETA chip clicked and `aria-pressed="true"`
- persisted `localStorage["vidux:sidebar-filter-chips"] = ["eta"]`
- plan rows narrowed from 1181 to 93
- persisted after reload with 93 rows still visible
- first visible plan titles after filtering: `vidux-browser`, `moussey-mobile-operator`, `firstbite-local-ci-mega`, `litty`, `connect-the-fleet`
- console errors: 0
- page errors: 0
- `.error` boxes: 0
- horizontal overflow: page false, sidebar false, controls false
- live proof JSON: `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-live-proof.json`
- screenshots:
  - `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-desktop.png`
  - `projects/vidux-browser/evidence/2026-06-03-vb-new-4-filter-chips-mobile-open.png`

## Non-Claims

- No root automation row was unblocked.
- No Resplit `gh pr create` overlap issue was solved.
- No live config, token, adapter, LaunchAgent, or external service was mutated.
- No local-CI execute lane was run.
- No stage, commit, push, or PR was created.
