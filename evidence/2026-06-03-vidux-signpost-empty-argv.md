# Vidux signpost explicit empty argv

Date: 2026-06-03
Task: 5.3.0dz Signpost explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux_signpost.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of
honoring the explicit empty list. For signposts, that could accidentally emit
or summarize the wrong trace from stale process state.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux_signpost.py`
- `tests/test_signpost.py`
- `PLAN.md`

The regression poisons `sys.argv` with a complete valid `emit` command pointed
at a temp JSONL file, calls `signpost.main([])`, and asserts argparse raises
missing-required `SystemExit(2)` without stdout or a created signpost log.

## Gates

- `python3 -m py_compile scripts/vidux_signpost.py tests/test_signpost.py` PASS.
- `python3 -m unittest tests.test_signpost` PASS, 7/7.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to a valid signpost
  `emit` command, `main([])` raised `SystemExit(2)`, printed missing-required,
  left stdout empty, and did not create the JSONL log.
- Lifecycle smoke PASS with 4 events and runtimes `codex,claude,cursor,codex`.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux_signpost.py tests/test_signpost.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dz_signpost_empty_argv` verified at
  `/Users/leokwan/.agent-ledger/activity.jsonl:5813`.

## Non-claims

- No real external Claude/Codex/Cursor launch, hook installer/runner, product
  analytics event, external service, local-CI lane, stage, commit, push, or PR
  mutation was performed.
