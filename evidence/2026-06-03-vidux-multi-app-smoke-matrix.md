# Vidux Multi-App Smoke Matrix

Date: 2026-06-03
Task: 5.3.0de

## Scope

Fifth slice of the five-hour Vidux observability/config/app-smoke push:

- Run observe-only checks across Vidux CLI and browser surfaces.
- Check locally available Litty and Moussey health surfaces without mutating them.
- Scan StrongYes/Resplit plan surfaces from disk without touching those repos.
- Record pass/fail/warn state plainly, including tight-budget route timeouts.

## Matrix

| Surface | Command | Result | Notes | Non-claims |
| --- | --- | --- | --- | --- |
| Repo availability | `ls -d ~/Development/{strongyes-web,strongyes,resplit-web,resplit-ios,litty,moussey}` | WARN | Found Litty, Moussey, Resplit iOS, Resplit Web, and StrongYes Web; `~/Development/strongyes` was absent. | Did not create missing roots. |
| Vidux config CLI | `bin/vidux config check --json` | PASS | `source=example`, `live_config_present=false`, `using_example=true`. | Did not create live `vidux.config.json`. |
| Vidux install/readiness doctor | `VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor` | PASS | 7/7 checks passed with npm test intentionally skipped for the smoke. | Did not run full `npm test` through doctor. |
| Vidux browser contracts | `python3 -m unittest tests.test_browser_server` | PASS | 42/42 tests passed. | Does not prove every browser route against a real DOM. |
| Vidux browser JS syntax | `node --check browser/static/app.js` and `node --check browser/static/readaloud.js` | PASS | Both browser scripts parsed. | Syntax check only. |
| Vidux browser health | `curl --max-time 3 -fsS http://127.0.0.1:7194/api/health` | PASS | Returned `ok=true`, `dev_root=~/Development`, `port=7194`. | Local-only dev server proof. |
| Vidux browser truth endpoint | `curl --max-time 3 -fsS http://127.0.0.1:7194/api/vidux/truth` | FAIL (budget) | Timed out after 3s with 0 bytes on a cold runtime-doctor path. 5.3.0dd already proved the endpoint succeeds with a longer budget and cache. | Does not claim the truth endpoint is down; only that a 3s monitor budget is too tight cold. |
| Litty health | `curl --max-time 3 -fsS http://127.0.0.1:4400/api/health` | PASS | Returned `ok=true`, `service=litty`, `runtime.ok=true`, branch `main`, head `84aba5c`, origin main `e129c55`, behind 3, dirty path count 42, Moussey reachable, FirstBite MCP ready. | Did not repair dirty or behind state. |
| Litty workers route | `curl --max-time 3 -fsS http://127.0.0.1:4400/workers` | WARN (partial) | Timed out after 3005ms after receiving 9450 bytes of Next HTML, including title/loading shell. | Did not prove the workers data finished loading. |
| Moussey health | `curl --max-time 3 -fsS http://127.0.0.1:4321/api/health` | PASS | Returned `ok=true`; agent backend `ready=false`; Codex, Hermes, and Claude Code tools ready. | Did not start or repair the agent backend. |
| Moussey coding capabilities | `curl --max-time 3 -fsS http://127.0.0.1:4321/api/coding/capabilities` | FAIL (budget) | Timed out after 3003ms with 0 bytes. | Does not prove route absence or backend correctness. |
| Moussey local-CI | `curl --max-time 3 -fsS http://127.0.0.1:4321/api/coding/local-ci` | FAIL (budget) | Timed out after 3003ms with 0 bytes. | Does not prove route absence or local-CI readiness. |
| Product plan scan | `python3 scripts/vidux-status.py --json --focus strongyes-web resplit-web resplit-ios --root ~/Development` | PASS | Compact summary: 34 tied plans, 32 StrongYes Web and 2 Resplit Web; aggregate task counts pending 302, in_progress 50, blocked 34, completed 826. | Observe-only; did not edit StrongYes or Resplit repos. |
| Resplit launch plan | Same product plan scan | PASS | Surfaced `resplit-web/resplit-2.0-launch` with pending 87, in_progress 1, blocked 3, completed 130, mtime 2026-06-02; surfaced `T-staging-readiness` with pending 5, completed 5. | Did not run Resplit web/iOS tests or fix launch blockers. |
| Resplit iOS focus | Same product plan scan | WARN | `resplit-ios` was included in `focus_repos` but did not appear in the tied set for this scan. | Not a health verdict for Resplit iOS. |
| StrongYes active plans | Same product plan scan | PASS | Surfaced `strongyes-web/game-plan`, `launch-validation`, and `blog-depth-overhaul` among other tied plans; recent mtime rows exist on 2026-06-03. | Did not mutate StrongYes plan rows or run app tests. |

## Compact Product Scan Output

```text
exit 0
focus resplit-ios,resplit-web,strongyes-web
tied_count 34
by_root {'strongyes-web': 32, 'resplit-web': 2}
task_counts {'pending': 302, 'in_progress': 50, 'blocked': 34, 'completed': 826}
top strongyes-web/blog-pipeline pending 0 in_progress 1 blocked 0 mtime 2026-05-17
top strongyes-web/autobot-strongyes pending 0 in_progress 1 blocked 0 mtime 2026-05-26
top strongyes-web/content-directorate pending 2 in_progress 1 blocked 0 mtime 2026-05-17
top strongyes-web/creative-direction pending 0 in_progress 1 blocked 0 mtime 2026-05-17
top strongyes-web/content-lane/rehoboam-rd pending 2 in_progress 1 blocked 0 mtime 2026-05-17
top strongyes-web/ux-overhaul pending 4 in_progress 9 blocked 1 mtime 2026-06-01
top strongyes-web/user-memory pending 0 in_progress 0 blocked 2 mtime 2026-05-17
top strongyes-web/blog-voice-retrofit pending 5 in_progress 0 blocked 0 mtime 2026-05-17

strongyes-web/game-plan pending 19 in_progress 8 blocked 7 completed 217 mtime 2026-06-02
resplit-web/resplit-2.0-launch pending 87 in_progress 1 blocked 3 completed 130 mtime 2026-06-02
resplit-web/resplit-2.0-launch/T-staging-readiness pending 5 in_progress 0 blocked 0 completed 5 mtime 2026-06-02
strongyes-web/blog-depth-overhaul pending 4 in_progress 1 blocked 0 completed 3 mtime 2026-06-03
strongyes-web/launch-validation pending 18 in_progress 5 blocked 3 completed 13 mtime 2026-06-03
```

## Interpretation

The observe-only matrix says the core Vidux CLI/browser proof path is healthy, but app-adjacent HTTP monitors need better budgets or async/cached readiness before they can be treated as durable green checks. Litty and Moussey health routes are alive locally; deeper app routes timed out or only partially loaded within 3 seconds.

## Closeout Proof

```text
git diff --check -- PLAN.md evidence/2026-06-03-vidux-multi-app-smoke-matrix.md
PASS

ledger emit
eid=evt_codex_20260603_5e30de_multi_app_smoke_matrix
verified=~/.agent-ledger/activity.jsonl:5790

python3 scripts/vidux-publish-scrutiny.py --json ...
ready=true
task_in_plan=true
missing_fields=[]
failed_review_passes=[]
```

## Files In This Slice

- `PLAN.md`
- `evidence/2026-06-03-vidux-multi-app-smoke-matrix.md`

## Non-Claims

- No runtime doctor `--fix`, config mutation, app repair, external board mutation, GitHub mutation, stage, commit, push, or PR was performed.
- No Litty, Moussey, StrongYes, Resplit Web, or Resplit iOS repo files were edited.
- No product app tests, TestFlight/App Attest, Resplit launch proof, StrongYes signed-in browser proof, or local-CI execute proof was run.
- The browser truth endpoint is not claimed broken; the failed row is specifically a cold 3-second budget failure.
- The larger five-hour Vidux objective remains active; this completes only 5.3.0de.
