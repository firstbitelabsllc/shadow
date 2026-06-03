# VB-NEW-3 Sidebar Sort Proof

Date: 2026-06-03

## Change

Added a persisted sidebar sort menu for plan groups and rows:

- `mtime` keeps the existing recency-first default.
- `ETA` sorts by remaining active ETA descending.
- `status` sorts by freshness status (`hot`, `stale`, `cold`).

The ordering applies after sidebar filtering, at both repo-group and child-plan row levels. The sort helper lives in `browser/static/sidebar-sort.js` so `browser/static/app.js` stays under the source-size smoke limit.

Also fixed the mobile sidebar drawer top offset so the filter/sort row clears the taller mobile topbar.

## Files

- `browser/static/index.html`
- `browser/static/sidebar-sort.js`
- `browser/static/app.js`
- `browser/static/style.css`
- `browser/tests/e2e/smoke.spec.ts`
- `browser/tests/fixtures/fake-dev-root/proj-alpha/PLAN.md`
- `browser/tests/fixtures/fake-dev-root/proj-beta/PLAN.md`
- `tests/test_browser_server.py`
- `docs/reference/browser.md`
- `README.md`
- `projects/vidux-browser/PLAN.md`

## Verification

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS
- `node --check browser/static/sidebar-sort.js` PASS
- `node --check browser/static/app.js` PASS
- `python3 -m unittest tests.test_browser_server.BrowserDashboardTests.test_dashboard_static_contract` PASS
- `python3 -m unittest tests.test_browser_server` PASS, 57 tests
- `npm run test:js` PASS, 7 tests
- `npm run docs:build` PASS
- `npm run test:e2e -- --grep "sidebar sort"` PASS, 3 tests
- `npm run test:e2e` PASS, 33 tests
- Publish scrutiny PASS, `ready=true`
- Publish ledger PASS: `evt_vidux_publish_c10bab99a429`

Note: the first `npm run test:js` run caught `app.js` crossing the 100 KB source-size guard. The helper split into `sidebar-sort.js` fixed that without weakening the guard.

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

Plan summary from `/api/plans`:

```json
{
  "plans": 1101,
  "repos": 35,
  "tasks_completed": 12267,
  "tasks_total": 17187,
  "completion_pct": 71,
  "eta_remaining_hours": 2075.7,
  "eta_remaining_label": "2075.7h remaining",
  "eta_tagged": 843,
  "eta_eligible": 4455
}
```

Desktop live proof:

- selected `ETA`
- first visible plan titles: `ai-substrate-1000x`, `firstbite-local-ci-mega`, `litty`, `firstbite-slack-ops`, `moussey-bug-opt-sweep`
- selected `status`
- first visible plan titles: `vidux-browser`, `vidux/PLAN.md`, `moussey-mobile-operator`, `firstbite-local-ci-mega`, `litty`
- persisted `localStorage["vidux:sidebar-sort"] = "eta"`
- console errors: 0
- page errors: 0
- `.error` boxes: 0
- horizontal overflow: false
- screenshot: `projects/vidux-browser/evidence/2026-06-03-vb-new-3-sidebar-sort-desktop.png`

Mobile live proof:

- selected `ETA`
- sidebar drawer opened
- sort visible: true
- `controlsClearTopbar`: true
- first visible plan titles: `ai-substrate-1000x`, `firstbite-local-ci-mega`, `litty`, `firstbite-slack-ops`, `moussey-bug-opt-sweep`
- console errors: 0
- page errors: 0
- `.error` boxes: 0
- horizontal overflow: false
- screenshots:
  - `projects/vidux-browser/evidence/2026-06-03-vb-new-3-sidebar-sort-mobile.png`
  - `projects/vidux-browser/evidence/2026-06-03-vb-new-3-sidebar-sort-mobile-open.png`
