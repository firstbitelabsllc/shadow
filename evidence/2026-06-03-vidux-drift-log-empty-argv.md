# Vidux drift log explicit empty argv

Date: 2026-06-03
Task: 5.3.0eb Drift log explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-drift-log.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of
honoring the explicit empty list. Because the default command records drift,
this could mutate a plan from stale process state.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-drift-log.py`
- `tests/test_drift_log.py`
- `PLAN.md`

The regression poisons `sys.argv` with a complete valid drift-record command
pointed at a temp `PLAN.md`, calls `drift.main([])`, and asserts argparse raises
missing-required `SystemExit(2)` without stdout or any plan mutation.

## Gates

- `python3 -m py_compile scripts/vidux-drift-log.py tests/test_drift_log.py` PASS.
- `python3 -m unittest tests.test_drift_log` PASS, 10/10.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to a valid
  drift-record command, `main([])` raised `SystemExit(2)`, printed
  missing-required, left stdout empty, and left the temp plan unchanged.
- Temp CLI record smoke PASS with `rc=0`, `recorded=true`, and
  `drift_log=true`.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux-drift-log.py tests/test_drift_log.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30eb_drift_log_empty_argv` verified at
  `/Users/leokwan/.agent-ledger/activity.jsonl:5815`.

## Non-claims

- No real repo plan drift was recorded, no shared drift cache was written, no
  external service, local-CI lane, stage, commit, push, or PR mutation was
  performed.
