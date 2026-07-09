# Vidux HTTP smoke fixture disconnect noise

Date: 2026-06-03
Task: 5.3.0do HTTP smoke fixture disconnect noise
Lane: vidux-five-hour-observability

## Change

Suppressed expected disconnect write errors in the local HTTP smoke test fixture.
The timeout tests intentionally let the client give up before the server writes a
late body; the fixture now treats that `BrokenPipeError` or connection reset as
normal fixture behavior instead of printing a traceback during otherwise green
proof.

Updated:

- `tests/test_http_smoke.py`
- `PLAN.md`

## Gates

- `python3 -m py_compile tests/test_http_smoke.py` PASS.
- `python3 -m unittest tests.test_http_smoke` PASS, 7/7, with no fixture traceback.
- `git diff --check -- PLAN.md tests/test_http_smoke.py evidence/2026-06-03-vidux-http-smoke-fixture-noise.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30do_http_smoke_fixture_noise` verified at `~/.agent-ledger/activity.jsonl:5802`.

## Non-claims

- No `scripts/vidux-http-smoke.py` helper behavior changed.
- No CLI, completion, docs, product app, local-CI lane, external service, stage,
  commit, push, or PR mutation was performed.
