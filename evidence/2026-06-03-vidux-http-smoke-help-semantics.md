# Vidux HTTP smoke CLI help JSON semantics

Date: 2026-06-03
Task: 5.3.0dq HTTP smoke CLI help JSON semantics
Lane: vidux-five-hour-observability

## Change

Updated `vidux help http-smoke` so terminal help explains the aggregate JSON
semantics introduced in 5.3.0dp:

- top-level `ok` follows hard-fail exit status
- `strict_ok` is false when any warning is present
- `warning_only` identifies warning-only exit 0 runs

Updated:

- `bin/vidux`
- `tests/test_http_smoke.py`
- `PLAN.md`

## Gates

- `bash -n bin/vidux` PASS.
- `python3 -m unittest tests.test_http_smoke` PASS, 8/8.
- `bin/vidux help http-smoke | rg 'top-level ok|strict_ok|warning_only|warn_partial|fail_budget'` PASS.
- `git diff --check -- PLAN.md bin/vidux tests/test_http_smoke.py evidence/2026-06-03-vidux-http-smoke-help-semantics.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dq_http_smoke_help_semantics` verified at `~/.agent-ledger/activity.jsonl:5804`.

## Non-claims

- No HTTP helper behavior changed.
- No docs/reference, product app, local-CI lane, external service, stage,
  commit, push, or PR mutation was performed.
