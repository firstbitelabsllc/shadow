# Vidux publish scrutiny explicit empty argv

Date: 2026-06-03
Task: 5.3.0dx Publish scrutiny explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-publish-scrutiny.py` used `argv or sys.argv[1:]`, so a
programmatic `main([])` call could fall back to ambient process arguments
instead of honoring the explicit empty list. This is especially risky for a
publish preflight because an ambient valid packet could make an empty
programmatic call return a readiness verdict.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-publish-scrutiny.py`
- `tests/test_publish_scrutiny.py`
- `PLAN.md`

The regression poisons `sys.argv` with a complete valid publish packet, calls
`publish_scrutiny.main([])`, and asserts the explicit empty list raises the
normal argparse missing-required `SystemExit(2)` instead of reading the ambient
packet.

## Gates

- `python3 -m py_compile scripts/vidux-publish-scrutiny.py tests/test_publish_scrutiny.py` PASS.
- `python3 -m unittest tests.test_publish_scrutiny` PASS, 19/19.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to a valid publish
  packet, `main([])` raised `SystemExit(2)` and printed the missing-required
  argparse error.
- Live publish-scrutiny CLI smoke PASS against task `5.3.0dx`, reporting
  `ready=True task_in_plan=True`.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux-publish-scrutiny.py tests/test_publish_scrutiny.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dx_publish_scrutiny_empty_argv`
  verified at `~/.agent-ledger/activity.jsonl:5811`.

## Non-claims

- No publish readiness semantics, ledger writer behavior, PR body behavior,
  external service, local-CI lane, stage, commit, push, or PR mutation was
  performed.
