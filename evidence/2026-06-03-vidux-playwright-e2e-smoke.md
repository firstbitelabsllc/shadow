# Vidux Playwright e2e fixture smoke

Date: 2026-06-03
Task: 5.3.0eg Playwright e2e fixture smoke
Lane: vidux-five-hour-observability

## Scope

Run the hermetic browser Playwright e2e suite after the packaged repo gate.

## Command

```bash
npm run test:e2e
```

## Result

PASS.

```text
> vidux@2.23.0 test:e2e
> playwright test

Started fixture server:
browser/server.py --root browser/tests/fixtures/fake-dev-root --port 7291 --comments-path browser/tests/fixtures/comments.jsonl

Health check:
GET /api/health 200

Running 30 tests using 12 workers
30 passed (14.7s)
```

- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30eg_playwright_e2e_smoke` verified at `~/.agent-ledger/activity.jsonl:5868`.

## Warnings

- Local Mac visual specs were skipped by Playwright config unless `PLAYWRIGHT_RUN_VISUAL=1` is set.
- Node printed a non-fatal `[DEP0205] DeprecationWarning: module.register() is deprecated. Use module.registerHooks() instead.`
- Several workers printed non-fatal `NO_COLOR env is ignored due to FORCE_COLOR env being set` warnings.

## Non-claims

- This did not run visual snapshots, live app roots, product repo repair, local-CI execute lanes, or runtime-doctor warning repair.
- No stage, commit, push, PR, or external mutation was performed.
