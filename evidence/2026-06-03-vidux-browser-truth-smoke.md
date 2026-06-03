# Vidux Browser Truth Surface Smoke

Date: 2026-06-03
Task: 5.3.0dd

## Scope

Fourth slice of the five-hour Vidux observability/config/app-smoke push:

- Add a read-only `GET /api/vidux/truth` browser endpoint.
- Expose config, runtime-doctor, pre-hook, and signpost state in the local browser UI.
- Keep the browser from running `vidux doctor` or runtime doctor `--fix`.
- Verify the rendered truth band on desktop and mobile viewports.

## Browser Truth Contract

- Config status comes from `vidux config check --json`.
- Runtime state comes from `scripts/vidux-doctor.sh --json`.
- Signpost state comes from `vidux signpost summary --json`.
- The browser does not run the install/readiness doctor because that path may run `npm test`.
- The browser does not expose or call runtime doctor `--fix`.

## Command Evidence

```text
python3 -m py_compile browser/server.py
PASS

python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests tests.test_browser_server.BrowserPlanBriefTests.test_plan_brief_and_steering_static_contract
Ran 3 tests in 1.014s
OK

python3 -m unittest tests.test_browser_server
Ran 42 tests in 8.149s
OK

bash -n bin/vidux-browse
PASS

npm run docs:build
build complete in 1.99s

VIDUX_BROWSER_PORT=7194 VIDUX_TRUTH_CACHE_TTL_SECONDS=5 python3 browser/server.py --port 7194
served http://127.0.0.1:7194

curl -s http://127.0.0.1:7194/api/vidux/truth
read_only=true
browser_runs_install_doctor=false
browser_runs_runtime_fix=false
config.status=ok
config.source=example
runtime_doctor.status=warn
runtime_doctor.pass=11
runtime_doctor.total=14
runtime_doctor.warnings=orphan_automations, stale_in_progress, bimodal_runtime
runtime_doctor.blockers=[]
signposts.total_events=0

Playwright desktop smoke, 1440x980
truth band rendered Local truth / config / Runtime doctor / Pre-hook / Signposts
overflowItems=[]
screenshot: evidence/2026-06-03-vidux-browser-truth-desktop.png

Playwright mobile smoke, 390x820
truth band rendered stacked without overlap
overflowItems=[]
screenshot: evidence/2026-06-03-vidux-browser-truth-mobile.png

git diff --check -- PLAN.md browser/server.py browser/static/app.js browser/static/style.css tests/test_browser_server.py docs/reference/browser.md evidence/2026-06-03-vidux-browser-truth-desktop.png evidence/2026-06-03-vidux-browser-truth-mobile.png
PASS
```

## Files In This Slice

- `PLAN.md`
- `browser/server.py`
- `browser/static/app.js`
- `browser/static/style.css`
- `tests/test_browser_server.py`
- `docs/reference/browser.md`
- `evidence/2026-06-03-vidux-browser-truth-desktop.png`
- `evidence/2026-06-03-vidux-browser-truth-mobile.png`

## Non-Claims

- No browser mutation endpoint was added for config, doctor, or signposts.
- No `vidux doctor` install/readiness run was triggered by the browser.
- No runtime doctor `--fix` cleanup was run.
- Runtime warnings were surfaced, not repaired.
- No external exposure, board mutation, GitHub mutation, stage, commit, push, or PR was performed.
- The larger five-hour objective remains active; this completes only 5.3.0dd.
