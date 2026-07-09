# Vidux config checked-path dedupe

Date: 2026-06-03
Task: 5.3.0du Config checked-path dedupe
Lane: vidux-five-hour-observability

## Bug

When the command cwd was also the Vidux root, `vidux config check --json`
reported the same `vidux.config.json` candidate twice in `checked`: once for
`cwd` and once for `root`.

## Change

`resolve_config()` now deduplicates resolved candidate paths while preserving
the original candidate order.

Updated:

- `scripts/vidux-config.py`
- `tests/test_vidux_config_cli.py`
- `PLAN.md`

## Gates

- `python3 -m py_compile scripts/vidux-config.py tests/test_vidux_config_cli.py` PASS.
- `python3 -m unittest tests.test_vidux_config_cli` PASS, 9/9.
- `git diff --check -- PLAN.md scripts/vidux-config.py tests/test_vidux_config_cli.py evidence/2026-06-03-vidux-config-checked-dedupe.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30du_config_checked_dedupe` verified at `~/.agent-ledger/activity.jsonl:5808`.

## Live Config Smoke

Command:

```bash
bin/vidux config check --json --strict
```

Result:

- `rc=1`
- `status=fail`
- `source=example`
- `checked_count=2`
- checked paths:
  - `~/Development/vidux/vidux.config.json`
  - `~/Development/vidux/vidux.config.example.json`

The strict failure is expected because no live `vidux.config.json` exists; the
proof is that `vidux.config.json` appears once instead of twice.

## Non-claims

- No live config file was created or modified.
- No token file was read or printed.
- No adapter sync, local-CI lane, external service, stage, commit, push, or PR
  mutation was performed.
