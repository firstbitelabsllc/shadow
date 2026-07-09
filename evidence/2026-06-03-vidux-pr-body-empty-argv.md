# Vidux PR body explicit empty argv

Date: 2026-06-03
Task: 5.3.0dy PR body explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-pr-body.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of
honoring the explicit empty list. For PR-body generation, that can turn an
empty programmatic call into a rendered PR body from stale process state.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-pr-body.py`
- `tests/test_pr_body.py`
- `PLAN.md`

The regression poisons `sys.argv` with a complete valid PR-body packet from the
fixture ledger, calls `pr_body.main([])`, and asserts argparse raises
missing-required `SystemExit(2)` without writing a PR body.

## Gates

- `python3 -m py_compile scripts/vidux-pr-body.py tests/test_pr_body.py` PASS.
- `python3 -m unittest tests.test_pr_body` PASS, 32/32.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to a valid PR-body
  packet, `main([])` raised `SystemExit(2)`, printed missing-required, and left
  stdout empty.
- Corrected CLI smoke with a temporary `VIDUX_LEDGER_FILE` PASS, `rc=0`, and
  rendered `Plan task`, `Summary`, `Ledger`, and `Linear` fields.
- `npm run docs:build` PASS.
- `git diff --check -- PLAN.md scripts/vidux-pr-body.py tests/test_pr_body.py` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dy_pr_body_empty_argv` verified at
  `~/.agent-ledger/activity.jsonl:5812`.

## Non-claims

- No PR creation, publish ledger semantics, publish-scrutiny behavior, external
  service, local-CI lane, stage, commit, push, or PR mutation was performed.
