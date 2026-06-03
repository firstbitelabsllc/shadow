# T2a Missing File And Markdown Guard

Date: 2026-06-03
Plan: `projects/vidux-browser/PLAN.md`
Task: `T2a Discovery upgrades - handle missing files gracefully, surface broken markdown`

## Change

- Added `/api/file` missing-target classification in `browser/server.py`: allowed targets such as `PLAN.md`, sibling plan files, evidence/investigation markdown, and browser artifacts now return `404 file missing: <name>` when absent.
- Kept forbidden missing targets forbidden: a missing `.env` under the dev root still returns `403 forbidden`.
- Wrapped markdown rendering in `browser/static/app.js` so parser failures show `markdown render failed` plus a bounded escaped source fallback instead of losing the pane.
- Added `.markdown-source-fallback` styling in `browser/static/style.css`.
- Added focused contracts in `tests/test_browser_server.py`.

## Proof

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS.
- `node --check browser/static/app.js` PASS.
- Focused unittest PASS: `BrowserWriteEndpointHTTPTests.test_api_file_returns_404_for_allowed_missing_file`, `BrowserWriteEndpointHTTPTests.test_api_file_still_rejects_forbidden_missing_file`, and `BrowserViduxTruthTests.test_vidux_truth_static_contract` ran 3/3 OK.
- Browser server suite PASS: `python3 -m unittest tests.test_browser_server` ran 47/47 OK.
- JS unit suite PASS: `npm run test:js` ran Vitest 7/7 OK.
- Scoped whitespace gate PASS: `git diff --check -- browser/server.py browser/static/app.js browser/static/style.css tests/test_browser_server.py`.
- Publish scrutiny PASS: `ready=true` for ledger `evt_codex_20260603_vb_t2a_missing_file_markdown_guard`.
- Publish ledger verified at `/Users/leokwan/.agent-ledger/activity.jsonl:6103`.

## Live 7191 Smoke

- Existing live server PID `31495` was correctly rejected by `bin/vidux-browse --no-open` after `browser/server.py` changed because health advertised old `server_mtime_ns=1780472614203589519`.
- Restarted live server; fresh PID `88551` now listens on `http://127.0.0.1:7191`.
- Fresh `/api/health` returned `repo_root=/Users/leokwan/Development/vidux`, `dev_root=/Users/leokwan/Development`, `port=7191`, `server_path=/Users/leokwan/Development/vidux/browser/server.py`, `server_mtime_ns=1780473436299633343`.
- Live allowed missing file smoke: `/api/file?path=/Users/leokwan/Development/vidux/projects/vidux-browser/__missing__/PLAN.md` returned `404` with `file missing: PLAN.md`.
- Live forbidden missing file smoke: `/api/file?path=/Users/leokwan/Development/vidux/projects/vidux-browser/.env` returned `403` with `forbidden`.
- Live truth endpoint returned `ok=true`, config `status=ok` from example config, runtime doctor `status=warn` with warnings `orphan_automations`, `stale_in_progress`, `bimodal_runtime`, and signpost `latest_run.complete_lifecycle=true`.
- Playwright live browser smoke loaded `http://127.0.0.1:7191` with title `vidux browser`, `0` `.error` boxes, and no console errors.
- Screenshot: `projects/vidux-browser/evidence/2026-06-03-t2a-live-browser.png`.

## Non-Claims

- No stage, commit, push, PR, release, external message, destructive cleanup, artifact mutation, annotation write, or user source-file mutation beyond this T2a code/test/plan/evidence slice.
- No full `npm test` or Playwright e2e matrix was run for this slice; the post server-fingerprint packaged/e2e gates immediately before this row remain separate proof.
- Runtime doctor warnings were observed, not repaired.
