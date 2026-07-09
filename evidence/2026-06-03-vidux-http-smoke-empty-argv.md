# Vidux HTTP smoke explicit empty argv

Date: 2026-06-03
Task: 5.3.0dt HTTP smoke explicit empty argv
Lane: vidux-five-hour-observability

## Bug

`scripts/vidux-http-smoke.py` used `argv or sys.argv[1:]`, so a programmatic
`main([])` call could fall back to ambient process arguments instead of honoring
the explicit empty list.

## Change

`main()` now distinguishes `argv is None` from an explicit empty list:

```python
args = parse_args(sys.argv[1:] if argv is None else argv)
```

Updated:

- `scripts/vidux-http-smoke.py`
- `tests/test_http_smoke.py`
- `PLAN.md`

## Gates

- `python3 -m py_compile scripts/vidux-http-smoke.py tests/test_http_smoke.py` PASS.
- `python3 -m unittest tests.test_http_smoke` PASS, 10/10.
- Direct programmatic smoke PASS: with `sys.argv` poisoned to include a URL, `main([])` returned `rc=2` and printed `vidux-http-smoke: at least one URL is required`.
- `git diff --check -- PLAN.md scripts/vidux-http-smoke.py tests/test_http_smoke.py evidence/2026-06-03-vidux-http-smoke-empty-argv.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dt_http_smoke_empty_argv` verified at `~/.agent-ledger/activity.jsonl:5807`.

## Non-claims

- No CLI user-facing behavior, route behavior, app backend, local-CI lane,
  external service, stage, commit, push, or PR mutation was performed.
