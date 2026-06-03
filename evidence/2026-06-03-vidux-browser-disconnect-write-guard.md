# Vidux Browser Disconnect Write Guard

Date: 2026-06-03
Task: 5.3.0fi Browser disconnect write guard

## Finding

The post-launcher Playwright e2e gate passed, but its web-server output showed a
`BrokenPipeError` traceback from `_json()` when a browser client closed an
`/api/artifacts` request before the server finished writing the response.
That is normal browser churn, but the server printed an exception stack trace
that made passing e2e output look noisy and failure-like.

## Change

- Added a shared guarded response writer in `browser/server.py`.
- Routed static, JSON, typed, markdown, and plain-text response helpers through
  the guarded writer.
- Swallowed `BrokenPipeError` and `ConnectionResetError` for response body
  writes after headers are already committed.
- Added a direct regression that simulates a client disconnect while every
  response helper writes.

## Proof

```text
python3 -m unittest tests.test_browser_server.BrowserResponseWriteTests.test_response_helpers_swallow_client_disconnect_writes
PASS

python3 -m py_compile browser/server.py tests/test_browser_server.py
PASS

python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests tests.test_browser_server.BrowserResponseWriteTests
PASS; 5 tests.

npm run test:e2e
PASS; Playwright 30/30 in 7.5s across desktop, iPad portrait, and iPhone portrait.
Observed output no longer included the earlier `BrokenPipeError` or
"Exception occurred during processing of request" traceback.

Remaining observed e2e warnings:
- Node `DEP0205` deprecation warning for `module.register()`.
- Node `NO_COLOR` ignored because `FORCE_COLOR` is set.

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fi ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fi_browser_disconnect_write_guard ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6066.
```

## Non-Claims

- No Playwright trace artifact was exported.
- No full packaged `npm test` rerun after this disconnect-write guard yet.
- No change to the Node warning sources.
- No runtime-doctor warning cleanup.
- No runtime doctor `--fix`.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.
