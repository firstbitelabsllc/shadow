# Vidux Browser Stale Listener Guard

Date: 2026-06-03
Task: 5.3.0fe Browser stale-listener launch guard

## Finding

`bin/vidux-browse` treated any process listening on port 7191 as the current
Vidux browser. During live proof, the old listener answered `/api/health` but
served pre-patch API shape without `repo_root`, so `vidux browse` could open a
stale surface while the checkout on disk had newer `/api/vidux/truth` code.

## Change

- Added `repo_root` to the browser `/api/health` payload.
- Made `bin/vidux-browse` reuse an existing listener only when health reports
  matching `repo_root`, `dev_root`, and `port`.
- Made foreground/background launches pass resolved `VIDUX_ROOT` and
  `VIDUX_BROWSER_PORT` into the server process.
- Updated browser reference docs and focused tests for the launcher health
  contract.

## Proof

```text
bash -n bin/vidux-browse
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_reuses_only_matching_health
PASS; matching fake health reused, stale fake health without repo_root rejected.

python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests.test_health_payload_identifies_repo_root_for_launcher_reuse
PASS

python3 -m py_compile browser/server.py tests/test_browser_server.py tests/test_vidux_contracts.py
PASS

python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_reuses_only_matching_health tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces
PASS; 6 tests.

npm run docs:build
PASS; VitePress build completed in 1.91s.

Live stale-listener refusal:
curl -fsS http://127.0.0.1:7191/api/health
PASS before restart; health had ok/dev_root/port/artifacts_dir but no repo_root.

bin/vidux-browse --no-open
PASS expected refusal; exit=1 with:
port 7191 is already in use, but http://127.0.0.1:7191/api/health does not match this Vidux checkout/root
expected repo_root=~/Development/vidux dev_root=~/Development

kill 12559
PASS; stopped the stale 7191 listener only.

bin/vidux-browse --no-open
PASS; fresh/current listener available at http://127.0.0.1:7191.

lsof -nP -iTCP:7191 -sTCP:LISTEN
PASS; fresh listener PID 71935.

curl -fsS http://127.0.0.1:7191/api/health
PASS; includes repo_root=~/Development/vidux,
dev_root=~/Development, port=7191.

curl -fsS 'http://127.0.0.1:7191/api/vidux/truth?refresh=sync' | python3 -c '...compact projection...'
PASS; ok=True, repo_root=~/Development/vidux,
config source=example, runtime=warn 11/14,
warnings=orphan_automations,stale_in_progress,bimodal_runtime,
blockers=[], signposts=24,
call_stack="codex > claude > cursor > codex", complete_lifecycle=True.

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fe ...
PASS; ready=true with invariant, regression, and adversarial review passes.

~/<private-skill-root>/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fe_browser_stale_listener_guard ...
PASS; verified in ~/.agent-ledger/activity.jsonl at line 6030.
```

## Non-Claims

- No runtime-doctor warnings were cleaned up.
- No runtime doctor `--fix` ran.
- No install doctor ran from the browser.
- No Playwright e2e rerun after this narrow launcher fix.
- No full packaged `npm test` rerun after this narrow launcher fix yet.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
