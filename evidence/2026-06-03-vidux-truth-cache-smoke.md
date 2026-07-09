# Vidux truth cache smoke

Date: 2026-06-03
Task: 5.3.0dk Browser truth cold-budget hardening
Lane: vidux-five-hour-observability

## Change

`GET /api/vidux/truth` now returns a monitor-safe cached response. On a cold cache it returns a warming payload immediately and refreshes the expensive config/runtime-doctor/signpost bundle in a background thread.

`GET /api/vidux/truth?refresh=sync` remains the explicit synchronous proof path for manual checks and tests.

The browser truth band now displays cache state (`fresh`, `stale`, or warming refresh) and retries while the cache is warming.

## Live HTTP smoke

Throwaway server:

```bash
python3 browser/server.py --host 127.0.0.1 --port 7197
```

Cold monitor-shaped request:

```bash
curl -sS -w '\nTIME:%{time_total}\n' http://127.0.0.1:7197/api/vidux/truth
```

Result: PASS. Returned `cache.status="warming"`, `cache.refreshing=true`, and `runtime_doctor.status="warming"` in `0.003259s`.

Post-refresh cached request:

```bash
curl -sS -w '\nTIME:%{time_total}\n' http://127.0.0.1:7197/api/vidux/truth
```

Result: PASS. Returned `cache.status="fresh"` in `0.001178s`. The off-thread runtime doctor reported `duration_ms=4668`, `status="warn"`, `pass=11`, `total=14`, and no blockers.

Explicit synchronous proof route:

```bash
curl -sS -w '\nTIME:%{time_total}\n' 'http://127.0.0.1:7197/api/vidux/truth?refresh=sync'
```

Result: PASS. Returned `cache.status="fresh"` in `4.652887s`, with runtime doctor `duration_ms=4544`, `status="warn"`, `pass=11`, `total=14`, and no blockers.

## Gates

- `python3 -m py_compile browser/server.py tests/test_browser_server.py` PASS.
- `node --check browser/static/app.js` PASS.
- `python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests` PASS, 3/3.
- `python3 -m unittest tests.test_browser_server` PASS, 43/43.
- `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_docs_bug_sweep_matches_current_command_setup_browser_surfaces tests.test_browser_server.BrowserViduxTruthTests` PASS, 4/4.
- `npm run docs:build` PASS.
- `git diff --check -- browser/server.py browser/static/app.js tests/test_browser_server.py docs/reference/browser.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30dk_truth_cache` verified at `~/.agent-ledger/activity.jsonl:5797`.

## Non-claims

- No runtime doctor warnings were repaired.
- No browser write or mutation endpoint was added.
- No install doctor, runtime doctor `--fix`, product-repo smoke, local-CI execute, external runtime launch, stage, commit, push, or PR was performed.
- The Moussey coding capabilities/local-CI and partial Litty `/workers` cold-budget findings from the multi-app matrix remain separate unresolved risks.
