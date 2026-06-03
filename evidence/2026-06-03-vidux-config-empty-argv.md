# Vidux config explicit empty argv

Date: 2026-06-03
Task: 5.3.0dv Config explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-config.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of honoring
the explicit empty list.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-config.py`
- `tests/test_vidux_config_cli.py`
- `PLAN.md`

## Gates

- `python3 -m py_compile scripts/vidux-config.py tests/test_vidux_config_cli.py` PASS.
- `python3 -m unittest tests.test_vidux_config_cli` PASS, 10/10.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to `["probe", "path"]`, `main([])` raised `SystemExit(2)` and printed `the following arguments are required: command`.
- `git diff --check -- PLAN.md scripts/vidux-config.py tests/test_vidux_config_cli.py evidence/2026-06-03-vidux-config-empty-argv.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dv_config_empty_argv` verified at `/Users/leokwan/.agent-ledger/activity.jsonl:5809`.

## Non-claims

- No CLI user-facing behavior, live config, token file, adapter sync, local-CI
  lane, external service, stage, commit, push, or PR mutation was performed.
