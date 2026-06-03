# T2c Session Panel

Date: 2026-06-03
Plan: `projects/vidux-browser/PLAN.md`
Task: `T2c Session panel - read latest JSONL per repo from ~/.claude/projects/, parse summary`

## Change

- Added repo-mapped Claude session discovery in `browser/server.py`.
- For each discovered repo, the browser maps `DEV_ROOT / repo` to the Claude project folder slug, picks the newest `*.jsonl` by mtime, scans a bounded tail, and exposes the last five user/assistant text turns as compact excerpts in `/api/plans`.
- Missing/unreadable/empty session folders return an explicit `available=false` session payload instead of breaking plan discovery.
- Added a `Sessions` pane tab in `browser/static/app.js` with source metadata, count/status, and compact turn cards.
- Hid investigation/evidence strips on `Sessions` and `Decision Log` tabs so derived panels are not buried below file-navigation chips.
- Added session-panel CSS in `browser/static/style.css`.
- Added deterministic tests using fixture JSONL, not live transcript text.

## Proof

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS.
- `node --check browser/static/app.js` PASS.
- Focused unittest PASS: `BrowserPlanDiscoveryTests.test_plan_payload_includes_latest_claude_session_summary`, `BrowserPlanDiscoveryTests.test_plan_payload_reports_missing_claude_session`, and `BrowserViduxTruthTests.test_vidux_truth_static_contract` ran 3/3 OK.
- Browser server suite PASS: `python3 -m unittest tests.test_browser_server` ran 49/49 OK.
- JS unit suite PASS: `npm run test:js` ran Vitest 7/7 OK.
- Scoped whitespace gate PASS: `git diff --check -- browser/server.py browser/static/app.js browser/static/style.css tests/test_browser_server.py`.
- Publish scrutiny PASS: `ready=true` for ledger `evt_codex_20260603_vb_t2c_session_panel`.
- Publish ledger verified at `/Users/leokwan/.agent-ledger/activity.jsonl:6104`.

## Live 7191 Smoke

- Existing live server PID `88551` was correctly rejected by `bin/vidux-browse --no-open` after `browser/server.py` changed because health advertised an old server fingerprint.
- Restarted live server; fresh PID `99433` now listens on `http://127.0.0.1:7191`.
- Fresh `/api/health` returned `repo_root=/Users/leokwan/Development/vidux`, `dev_root=/Users/leokwan/Development`, `port=7191`, and `server_mtime_ns=1780473862109192679`.
- Live `/api/plans` for `vidux/PLAN.md` returned session `available=true`, `status=ok`, 5 displayed turns, 98 text turns seen, and `tail_truncated=true`.
- Playwright smoke loaded `http://127.0.0.1:7191/?plan=vidux%2FPLAN.md&tab=Sessions`; active tab was `Sessions`, file strip count was 0, session turn count was 5, `.error` count was 0, and console errors were 0.
- Screenshot: `projects/vidux-browser/evidence/2026-06-03-t2c-session-tab.png`.

## Non-Claims

- No raw transcript text is copied into this evidence file or the plan row.
- No stage, commit, push, PR, release, external message, destructive cleanup, Claude session mutation, comments write, or source-file mutation beyond this T2c code/test/plan/evidence slice.
- No full `npm test` or Playwright e2e matrix was run for this slice.
