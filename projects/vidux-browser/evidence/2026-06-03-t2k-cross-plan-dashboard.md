# T2k Cross-Plan Dashboard

Date: 2026-06-03
Lane: vidux-browser
Task: T2k Cross-plan dashboard

## Result

Shipped the read-only fleet dashboard as the default Vidux browser pane.

- `/api/plans` now returns a bounded `dashboard` payload with categories for `in_progress`, `blocked`, open `ASK-LEO.md`, and `INBOX.md` entries.
- Dashboard extraction happens server-side from existing plan and sibling files; the client does not fan out across every plan file.
- Ordinary plan-list rows strip the private extractor scratch fields before returning to the browser.
- The sidebar now has a top-level `Fleet dashboard` row, and dashboard items click through to the source plan/sibling tab.
- The dashboard is bounded by `VIDUX_DASHBOARD_ITEM_LIMIT` with a default of 200 items per category and `truncated=true` when totals exceed the returned sample.

## Live Fleet Proof

Fresh browser server:

```json
{
  "ok": true,
  "dev_root": "/Users/leokwan/Development",
  "port": 7191,
  "repo_root": "/Users/leokwan/Development/vidux",
  "server_path": "/Users/leokwan/Development/vidux/browser/server.py",
  "server_mtime_ns": 1780474960002676275,
  "artifacts_dir": "/Users/leokwan/Development/vidux/browser/artifacts"
}
```

Live `/api/plans` dashboard sample:

```json
{
  "plans": 1101,
  "plans_scanned": 1101,
  "repos": 35,
  "limit": 200,
  "in_progress_total": 658,
  "in_progress_items": 200,
  "in_progress_truncated": true,
  "blocked_total": 465,
  "blocked_items": 200,
  "blocked_truncated": true,
  "ask_leo_total": 0,
  "ask_leo_items": 0,
  "ask_leo_truncated": false,
  "inbox_total": 9621,
  "inbox_items": 200,
  "inbox_truncated": true,
  "has_private_plan_fields": false
}
```

ASK-LEO note: the only `ASK-LEO.md` sibling found on this machine is resolved-only, so the open ASK count is correctly 0. A unit test covers legacy `## Q...` ASK blocks and excludes resolved entries.

## UI Smoke

Playwright against the real `http://127.0.0.1:7191/` surface:

- Desktop dashboard rendered 658 in-progress, 465 blocked, 0 ASK-LEO, and 9621 INBOX totals.
- Visible bounded rows: 200 in-progress, 200 blocked, 0 ASK-LEO, 200 INBOX.
- Click-through from the first in-progress dashboard row opened `strongyes-web/vidux/blog-depth-overhaul/PLAN.md` with `PLAN.md` active and 8435 markdown characters rendered.
- Console errors: 0 desktop, 0 mobile.
- Error boxes: 0 dashboard, 0 click-through, 0 mobile.
- Mobile viewport `390x844` had `scrollWidth=390`, so no horizontal overflow.

Screenshots:

- `projects/vidux-browser/evidence/2026-06-03-t2k-dashboard-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-t2k-dashboard-mobile.png`

## Gates

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS
- `node --check browser/static/app.js` PASS
- `python3 -m unittest tests.test_browser_server.BrowserDashboardTests` PASS, 4/4
- `python3 -m unittest tests.test_browser_server` PASS, 53/53
- `npm run test:js` PASS, Vitest 7/7
- `npm run docs:build` PASS
- `npm run test:e2e` PASS, Playwright 30/30
- `git diff --check -- browser/server.py browser/static/app.js browser/static/style.css tests/test_browser_server.py README.md docs/reference/browser.md projects/vidux-browser/PLAN.md projects/vidux-browser/evidence/2026-06-03-t2k-cross-plan-dashboard-preflight.md` PASS

## Publish

- Publish scrutiny: `ready=true`
- Publish ledger: `evt_codex_20260603_vb_t2k_cross_plan_dashboard` at `/Users/leokwan/.agent-ledger/activity.jsonl:6108`

## Non-Claims

- No plan, INBOX, ASK-LEO, comment, or artifact mutation from the browser UI.
- No stage, commit, push, PR, or release.
- No local-CI execute proof.
- No change to browser write endpoints.
