# VB-NEW-2 ETA Fleet Total

## Goal

Append a server-calculated remaining-hours total to the Vidux Browser topbar summary:

`X plans · Y repos · Z artifacts · W/V tasks (P%) · Nh remaining`

## Changes

- Added `/api/plans.summary` via `build_fleet_summary(plans)` in `browser/server.py`.
- Summed plan counts, repo counts, completed/total tasks, completion percentage, active-task ETA hours, ETA-tagged count, and ETA-eligible count server-side.
- Kept ETA semantics aligned with `task_stats`: only `pending`, `in_progress`, and `in_review` ETA tags count as remaining; completed and blocked ETA tags are ignored.
- Updated the topbar to prefer `plansData.summary` while preserving a local fallback shape for older payloads.
- Updated browser docs, README status/config note, and this plan row.

## Live API Proof

Server health after restart:

- URL: `http://127.0.0.1:7191/api/health`
- `server_mtime_ns`: `1780476429578827627`
- `dev_root`: `/Users/leokwan/Development`

`/api/plans.summary` returned:

```json
{
  "plans": 1101,
  "repos": 35,
  "tasks_completed": 12266,
  "tasks_total": 17187,
  "completion_pct": 71,
  "eta_remaining_hours": 2076.2,
  "eta_remaining_label": "2076.2h remaining",
  "eta_tagged": 844,
  "eta_eligible": 4456
}
```

## Browser Proof

Playwright checked the live page at `http://127.0.0.1:7191/`.

- Desktop topbar text: `1101 plans · 35 repos · 19 artifacts · 12266/17187 tasks (71%) · 2076.2h remaining`
- Mobile topbar DOM text: `1101 plans · 35 repos · 19 artifacts · 12266/17187 tasks (71%) · 2076.2h remaining`
- Console errors: `0`
- Page errors: `0`
- `.error` boxes: `0`
- Desktop document overflow: `1440/1440`
- Mobile document overflow: `390/390`
- Mobile note: long meta text is contained by topbar ellipsis; document does not horizontally overflow.

Screenshots:

- `projects/vidux-browser/evidence/2026-06-03-vb-new-2-eta-topbar-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-2-eta-topbar-mobile.png`

## Verification

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS
- `node --check browser/static/app.js` PASS
- `python3 -m unittest tests.test_browser_server.BrowserPlanDiscoveryTests.test_build_fleet_summary_sums_completion_and_active_eta tests.test_browser_server.BrowserDashboardTests.test_dashboard_static_contract` PASS, 2/2
- `python3 -m unittest tests.test_browser_server` PASS, 57/57
- `npm run test:js` PASS, 7/7
- `npm run docs:build` PASS
- `npm run test:e2e` PASS, 30/30

## Non-Claims

- Did not change sort/filter behavior.
- Did not add the manual dark/light toggle.
- Did not change ETA tagging coverage; `eta_eligible` still shows many active rows without ETA tags.
- Did not stage, commit, push, or open a PR.
