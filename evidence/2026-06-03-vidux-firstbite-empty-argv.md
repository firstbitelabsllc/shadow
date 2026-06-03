# Vidux FirstBite helpers explicit empty argv

Date: 2026-06-03
Task: 5.3.0ec FirstBite helper explicit empty argv sweep
Lane: vidux-five-hour-observability

## Bug

The FirstBite local-CI helper CLIs used `argv or sys.argv[1:]`, so a
programmatic `main([])` call could fall back to ambient process arguments
instead of honoring the explicit empty list.

Affected helpers:

- `scripts/vidux-firstbite-observe.py`
- `scripts/vidux-firstbite-diagnose.py`
- `scripts/vidux-firstbite-verified-alive.py`

For observe this could emit a report from stale process state. For diagnose and
verified-alive it could also write JSON/Markdown outputs from stale process
state.

## Change

Each `main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-firstbite-observe.py`
- `scripts/vidux-firstbite-diagnose.py`
- `scripts/vidux-firstbite-verified-alive.py`
- `tests/test_firstbite_observe.py`
- `tests/test_firstbite_diagnose.py`
- `tests/test_firstbite_verified_alive.py`
- `PLAN.md`

The regressions poison `sys.argv` with complete valid helper commands, call
`main([])`, and assert the helpers raise the empty-input `SystemExit(2)` without
stdout or output-file writes.

## Gates

- `python3 -m py_compile scripts/vidux-firstbite-observe.py scripts/vidux-firstbite-diagnose.py scripts/vidux-firstbite-verified-alive.py tests/test_firstbite_observe.py tests/test_firstbite_diagnose.py tests/test_firstbite_verified_alive.py` PASS.
- `python3 -m unittest tests.test_firstbite_observe tests.test_firstbite_diagnose tests.test_firstbite_verified_alive` PASS, 20/20.
- Direct poisoned-argv smokes PASS:
  - observe: `rc=2`, stdout empty.
  - diagnose: `rc=2`, stdout empty, no diagnosis file written.
  - verified-alive: `rc=2`, stdout empty, no rollup file written.
- Exact bad-pattern grep PASS with no hits for `argv or sys.argv[1:]`.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux-firstbite-observe.py scripts/vidux-firstbite-diagnose.py scripts/vidux-firstbite-verified-alive.py tests/test_firstbite_observe.py tests/test_firstbite_diagnose.py tests/test_firstbite_verified_alive.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ec_firstbite_empty_argv` verified at
  `/Users/leokwan/.agent-ledger/activity.jsonl:5816`.

## Non-claims

- No local-CI lane was executed or rerun, no dispatch/autodispatch was enabled,
  no real FirstBite evidence was mutated, no external service, stage, commit,
  push, or PR mutation was performed.
