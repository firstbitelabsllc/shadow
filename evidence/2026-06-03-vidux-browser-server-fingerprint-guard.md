# Vidux Browser Server Fingerprint Guard

Date: 2026-06-03
Task: 5.3.0fk Browser same-root server fingerprint guard

## Finding

The stale-listener guard from 5.3.0fe correctly rejected foreign listeners and
old listeners that lacked `repo_root`, but a same-checkout listener could still
be stale after `browser/server.py` changed. The live `7191` process was PID
`71935`; its `/api/health` matched `repo_root`, `dev_root`, and `port`, but did
not include a server-file freshness fingerprint.

## Change

- Added `server_path` and `server_mtime_ns` to `GET /api/health`.
- Made `bin/vidux-browse` compare the listener's `server_mtime_ns` against the
  current checkout's `browser/server.py` mtime before reusing a busy port.
- Updated launcher tests so matching fake health payloads must carry the
  current server mtime fingerprint.
- Updated browser-health tests and reference docs to name the new reuse
  contract.

## Proof

```text
bash -n bin/vidux-browse bin/vidux
PASS

python3 -m py_compile browser/server.py tests/test_browser_server.py tests/test_vidux_contracts.py
PASS

python3 -m unittest \
  tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_reuses_only_matching_health \
  tests.test_vidux_contracts.ViduxContractTests.test_vidux_browse_launcher_parses_flags_instead_of_silently_ignoring \
  tests.test_browser_server.BrowserViduxTruthTests.test_health_payload_identifies_repo_root_for_launcher_reuse
PASS; 3 tests in 1.543s.

npm run docs:build
PASS; VitePress build complete in 1.91s.

bin/vidux-browse --no-open
PASS as a stale-listener rejection: existing PID 71935 on port 7191 exited 1
because /api/health did not match expected server_mtime_ns=1780472614203589519.

kill 71935
PASS; replacement listener PID 31495 on 7191.

curl -fsS http://127.0.0.1:7191/api/health
PASS; payload included repo_root=/Users/leokwan/Development/vidux,
dev_root=/Users/leokwan/Development, port=7191,
server_path=/Users/leokwan/Development/vidux/browser/server.py, and
server_mtime_ns=1780472614203589519.

curl -fsS 'http://127.0.0.1:7191/api/vidux/truth?refresh=sync'
PASS; ok=true, config ok=true from example config, runtime doctor status=warn
with known warnings orphan_automations/stale_in_progress/bimodal_runtime,
and signpost latest_run complete_lifecycle=true.

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fk ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fk_browser_server_fingerprint_guard ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6082.
```

## Non-Claims

- No full packaged `npm test` rerun after this narrow fingerprint guard yet.
- No Playwright e2e rerun after this slice.
- No runtime-doctor warning cleanup.
- No runtime doctor `--fix`.
- No install doctor from browser.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
