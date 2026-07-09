# Vidux HTTP smoke aggregate JSON semantics

Date: 2026-06-03
Task: 5.3.0dp HTTP smoke aggregate JSON semantics
Lane: vidux-five-hour-observability

## Change

Aligned `vidux http-smoke --json` aggregate `ok` with hard-fail exit status.
Warning-only runs now return `ok: true`, `strict_ok: false`,
`warning_only: true`, and `exit_code: 0`. Per-route result `ok` remains strict:
only `pass` routes are true, while `warn_partial` routes remain false.

Updated:

- `scripts/vidux-http-smoke.py`
- `tests/test_http_smoke.py`
- `tests/test_vidux_contracts.py`
- `docs/reference/commands.md`
- `docs/reference/scripts.md`
- `README.md`
- `PLAN.md`

## Gates

- `python3 -m py_compile scripts/vidux-http-smoke.py tests/test_http_smoke.py tests/test_vidux_contracts.py` PASS.
- `python3 -m unittest tests.test_http_smoke tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces` PASS, 9/9.
- `npm run docs:build` PASS.
- `git diff --check -- README.md PLAN.md docs/reference/commands.md docs/reference/scripts.md scripts/vidux-http-smoke.py tests/test_http_smoke.py tests/test_vidux_contracts.py evidence/2026-06-03-vidux-http-smoke-json-semantics.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dp_http_smoke_json_semantics` verified at `~/.agent-ledger/activity.jsonl:5803`.

## Live JSON Smoke

Command:

```bash
bin/vidux http-smoke --json --timeout 3 --max-sample-bytes 80 \
  http://127.0.0.1:4321/api/health \
  http://127.0.0.1:4400/workers
```

Result: PASS for warning-only aggregate semantics.

Top-level JSON:

- `ok: true`
- `strict_ok: false`
- `warning_only: true`
- `warn_count: 1`
- `fail_count: 0`
- `exit_code: 0`

The Moussey health route was `pass`; Litty `/workers` remained `warn_partial`
with bytes read before timeout.

## Non-claims

- No Litty or Moussey route was repaired.
- No local-CI lane, app backend, LaunchAgent, external service, stage, commit,
  push, or PR mutation was performed.
