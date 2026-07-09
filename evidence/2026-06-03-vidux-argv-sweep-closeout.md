# Vidux argv sweep closeout

Date: 2026-06-03
Task: 5.3.0ed Argv sweep regression proof
Lane: vidux-five-hour-observability

## Scope

This proof closes the explicit-empty-argv bug family found during the
five-hour Vidux pass. The risky pattern was:

```python
parse_args(argv or sys.argv[1:])
```

That pattern treats an explicit empty list as falsey and reads ambient process
arguments. The sweep fixed it across the helpers touched in rows 5.3.0dt,
5.3.0dv, 5.3.0dx, 5.3.0dy, 5.3.0dz, 5.3.0ea, 5.3.0eb, and 5.3.0ec.

## Combined Proof

- Combined regression suite PASS, 114/114:
  `python3 -m unittest tests.test_http_smoke tests.test_vidux_config_cli tests.test_publish_scrutiny tests.test_pr_body tests.test_signpost tests.test_vidux_claims tests.test_drift_log tests.test_firstbite_observe tests.test_firstbite_diagnose tests.test_firstbite_verified_alive`
- Exact bad-pattern grep PASS with no product hits:
  `rg -n "argv or sys\\.argv|parse_args\\(argv or|main\\(\\[\\]\\).*ambient|poison" scripts tests`.
  The only remaining hits are guard-test docstrings describing the ambient
  `sys.argv` regressions.
- `npm run docs:build` PASS.
- `git diff --check` PASS for the FirstBite closeout surface after the final
  row.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ed_argv_sweep_closeout` verified at
  `~/.agent-ledger/activity.jsonl:5817`.

## Fixed Helpers In This Sweep

- `scripts/vidux-http-smoke.py`
- `scripts/vidux-config.py`
- `scripts/vidux-publish-scrutiny.py`
- `scripts/vidux-pr-body.py`
- `scripts/vidux_signpost.py`
- `scripts/vidux-claims.py`
- `scripts/vidux-drift-log.py`
- `scripts/vidux-firstbite-observe.py`
- `scripts/vidux-firstbite-diagnose.py`
- `scripts/vidux-firstbite-verified-alive.py`

## Non-claims

- No stage, commit, push, PR, local-CI execute, app-route repair, external
  service mutation, or product repo mutation was performed.
