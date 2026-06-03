# Vidux HTTP smoke numeric option validation

Date: 2026-06-03
Task: 5.3.0dr HTTP smoke numeric option validation
Lane: vidux-five-hour-observability

## Bug

`vidux http-smoke --timeout -1` crashed with a Python `ValueError` traceback.
`--timeout 0` also produced an opaque transport failure instead of explaining
that the monitor budget was invalid.

## Change

`scripts/vidux-http-smoke.py` now rejects invalid numeric options during
argument parsing, before any HTTP request is attempted:

- `--timeout` must be greater than 0.
- `--max-sample-bytes` must be 0 or greater.

Updated terminal help and reference docs to describe those limits.

Updated:

- `scripts/vidux-http-smoke.py`
- `tests/test_http_smoke.py`
- `bin/vidux`
- `docs/reference/commands.md`
- `docs/reference/scripts.md`
- `PLAN.md`

## Gates

- `bash -n bin/vidux` PASS.
- `python3 -m py_compile scripts/vidux-http-smoke.py tests/test_http_smoke.py` PASS.
- `python3 -m unittest tests.test_http_smoke` PASS, 9/9.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md bin/vidux docs/reference/commands.md docs/reference/scripts.md scripts/vidux-http-smoke.py tests/test_http_smoke.py evidence/2026-06-03-vidux-http-smoke-option-validation.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dr_http_smoke_option_validation` verified at `/Users/leokwan/.agent-ledger/activity.jsonl:5805`.

## Live Invalid-Option Smokes

- `bin/vidux http-smoke --json --timeout -1 ...` returned `rc=2`, printed `--timeout must be greater than 0`, and had `traceback=no`.
- `bin/vidux http-smoke --json --timeout 0 ...` returned `rc=2`, printed `--timeout must be greater than 0`, and had `traceback=no`.
- `bin/vidux http-smoke --json --max-sample-bytes -1 ...` returned `rc=2`, printed `--max-sample-bytes must be 0 or greater`, and had `traceback=no`.

## Non-claims

- No route behavior, app backend, local-CI lane, external service, stage, commit,
  push, or PR mutation was performed.
