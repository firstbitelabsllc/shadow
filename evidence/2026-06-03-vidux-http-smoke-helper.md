# Vidux HTTP smoke helper

Date: 2026-06-03
Task: 5.3.0dl HTTP monitor classification helper
Lane: vidux-five-hour-observability

## Change

Added `scripts/vidux-http-smoke.py`, a stdlib-only observe helper for local HTTP monitor budgets.

The helper classifies:

- `pass`: response completed inside the budget.
- `warn_partial`: response streamed bytes before the timeout budget expired.
- `fail_budget`: no response bytes arrived before the timeout budget expired.

It stores only a bounded response sample, so app-route smokes do not dump full HTML streams or multi-megabyte JSON into evidence.

## Focused Tests

- `python3 -m py_compile scripts/vidux-http-smoke.py tests/test_http_smoke.py` PASS.
- `python3 -m unittest tests.test_http_smoke` PASS, 4/4.
- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces` PASS, 1/1.
- `npm run docs:build` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dl_http_smoke_helper` verified at `/Users/leokwan/.agent-ledger/activity.jsonl:5799`.

## Live Local Smoke

Command:

```bash
python3 scripts/vidux-http-smoke.py --json --timeout 3 --max-sample-bytes 160 \
  http://127.0.0.1:4400/api/health \
  http://127.0.0.1:4400/workers \
  http://127.0.0.1:4321/api/health \
  http://127.0.0.1:4321/api/coding/capabilities \
  http://127.0.0.1:4321/api/coding/local-ci
```

Result: PASS for the helper run, with one warning and zero failures:

| URL | Verdict | Duration | Bytes |
|---|---:|---:|---:|
| `http://127.0.0.1:4400/api/health` | pass | 132ms | 951 |
| `http://127.0.0.1:4400/workers` | warn_partial | 3002ms | 73728 |
| `http://127.0.0.1:4321/api/health` | pass | 2ms | 309 |
| `http://127.0.0.1:4321/api/coding/capabilities` | pass | 2565ms | 46645 |
| `http://127.0.0.1:4321/api/coding/local-ci` | pass | 1325ms | 1252873 |

The warmed Moussey capabilities/local-CI routes passed in this run. That does not erase the earlier cold-budget timeout evidence; it means future smokes should use this helper to distinguish cold failure, warmed pass, and partial-byte route behavior without massive output.

## Non-claims

- No Litty or Moussey files were edited.
- No app route, cache, backend, local-CI, worker, or LaunchAgent was repaired.
- No local-CI lane was executed.
- No external service, product repo, stage, commit, push, or PR mutation was performed.
