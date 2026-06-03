# T4b Ledger Entries

## Goal

Surface recent publish/checkpoint ledger proof for the selected plan in `vidux-browse` without mutating plan files or the activity ledger.

## What Changed

- Added `GET /api/ledger?path=<PLAN.md>` in `browser/server.py`.
- The endpoint scans `${VIDUX_LEDGER_FILE:-~/.agent-ledger/activity.jsonl}` tail-first, bounded by `VIDUX_LEDGER_SCAN_LIMIT` and `VIDUX_LEDGER_ITEM_LIMIT`.
- Ledger matching is plan-first by `plan_path`, `files`, and `files_claimed`, with a repo guard so same relative paths in other repos do not bleed into the selected plan.
- Added a read-only `Ledger` tab in `browser/static/app.js` with compact proof, handoff status, resume hints, file-claim counts, ledger line numbers, and same-repo fallback rows.
- Added responsive ledger styles in `browser/static/style.css`.
- Updated README and browser reference docs.

## Live API Proof

Fresh server:

- URL: `http://127.0.0.1:7191`
- `server_mtime_ns`: `1780475734610555878`
- `repo_root`: `/Users/leokwan/Development/vidux`
- `dev_root`: `/Users/leokwan/Development`

Live `GET /api/ledger?path=/Users/leokwan/Development/vidux/projects/vidux-browser/PLAN.md`:

- `available=true`
- `status=ok`
- `repo=vidux`
- `scanned_rows=5000`
- `invalid_rows=0`
- `plan_total=5`
- `repo_total=202`
- `returned=20`
- `truncated=true`
- newest plan item: `evt_codex_20260603_vb_t4b_ledger_entries` at ledger line `6109`
- note: the T4b ledger row's proof string records the pre-append API sample (`plan_total=4`); after the append, the final live API sample is `plan_total=5` because the T4b row is now included.

## Browser Proof

URL: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md&tab=Ledger`

- In-app Browser DOM proof: active tab `Ledger`, `20` ledger entries, `0` `.error` boxes, `0` console errors, comments panel hidden, `scrollWidth=1280`, `clientWidth=1280`.
- Playwright desktop screenshot: `projects/vidux-browser/evidence/2026-06-03-t4b-ledger-tab-desktop.png`
- Playwright mobile screenshot: `projects/vidux-browser/evidence/2026-06-03-t4b-ledger-tab-mobile.png`
- Desktop screenshot proof: active tab `Ledger`, `20` entries, first visible row `evt_codex_20260603_vb_t4b_ledger_entries`, `0` console errors, `0` `.error` boxes, no horizontal overflow (`1280/1280`).
- Mobile screenshot proof: active tab `Ledger`, `20` entries, first visible row `evt_codex_20260603_vb_t4b_ledger_entries`, `0` console errors, `0` `.error` boxes, no horizontal overflow (`390/390`).

## Gates

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS
- `node --check browser/static/app.js` PASS
- `python3 -m unittest tests.test_browser_server.BrowserLedgerTests` PASS (3/3)
- `python3 -m unittest tests.test_browser_server` PASS (56/56)
- `npm run test:js` PASS (7/7)
- `npm run docs:build` PASS
- `npm run test:e2e` PASS (30/30)
- Publish scrutiny PASS (`ready=true`)
- Publish ledger PASS: `evt_codex_20260603_vb_t4b_ledger_entries` at `/Users/leokwan/.agent-ledger/activity.jsonl:6109`

## Non-Claims

- No browser mutation of `PLAN.md`, `INBOX.md`, comments, artifacts, repo code, or activity ledger data.
- No raw transcript copied into evidence or plans.
- No local-CI execute proof, stage, commit, push, PR, release, or runtime-doctor warning repair.
