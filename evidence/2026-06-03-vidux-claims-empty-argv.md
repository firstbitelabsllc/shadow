# Vidux claims explicit empty argv

Date: 2026-06-03
Task: 5.3.0ea Claims explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-claims.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of
honoring the explicit empty list. For the claims helper, that could append a
claim or release row from stale process state.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-claims.py`
- `tests/test_vidux_claims.py`
- `PLAN.md`

The regression poisons `sys.argv` with a complete valid `claim` command pointed
at a temp JSONL file, calls `claims.main([])`, and asserts argparse raises
missing-required `SystemExit(2)` without stdout or a created claims file.

## Gates

- `python3 -m py_compile scripts/vidux-claims.py tests/test_vidux_claims.py` PASS.
- `python3 -m unittest tests.test_vidux_claims` PASS, 6/6.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to a valid claim
  command, `main([])` raised `SystemExit(2)`, printed missing-required, left
  stdout empty, and did not create the JSONL claims file.
- Temp claim/release CLI round trip PASS with `claim=claimed release=released`.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux-claims.py tests/test_vidux_claims.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ea_claims_empty_argv` verified at
  `/Users/leokwan/.agent-ledger/activity.jsonl:5814`.

## Non-claims

- No real shared claims ledger, publish ledger semantics, external service,
  local-CI lane, stage, commit, push, or PR mutation was performed.
