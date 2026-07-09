# Vidux five-hour observability closeout

Date: 2026-06-03
Task: 5.3.0dj Five-hour bug-hunt closeout
Lane: vidux-five-hour-observability

## Completed rows

| Row | Result | Evidence |
|---|---|---|
| 5.3.0da | Config CLI, doctor config check, and signpost trace shipped. | `evidence/2026-06-03-vidux-config-doctor-signpost-smoke.md`; ledger `evt_codex_20260603_5e30da_config_signpost_doctor` at line 5765. |
| 5.3.0db | Hook call-stack wrapper and lifecycle smoke shipped. | `evidence/2026-06-03-vidux-hook-trace-wrapper-smoke.md`; ledger `evt_codex_20260603_5e30db_hook_trace_wrapper` at line 5784. |
| 5.3.0dc | `vidux doctor` vs runtime doctor split hardened. | `evidence/2026-06-03-vidux-doctor-split-smoke.md`; ledger `evt_codex_20260603_5e30dc_doctor_split` at line 5786. |
| 5.3.0dd | Read-only browser truth surface shipped and visually verified. | `evidence/2026-06-03-vidux-browser-truth-smoke.md`; screenshots in `evidence/2026-06-03-vidux-browser-truth-desktop.png` and `evidence/2026-06-03-vidux-browser-truth-mobile.png`; ledger `evt_codex_20260603_5e30dd_browser_truth` at line 5788. |
| 5.3.0de | Observe-only multi-app smoke matrix recorded. | `evidence/2026-06-03-vidux-multi-app-smoke-matrix.md`; ledger `evt_codex_20260603_5e30de_multi_app_smoke_matrix` at line 5790. |
| 5.3.0df | Codex/Claude/Cursor lifecycle docs converged. | `evidence/2026-06-03-vidux-lifecycle-doc-convergence-smoke.md`; ledger `evt_codex_20260603_5e30df_lifecycle_docs` at line 5791. |
| 5.3.0dg | Config schema validation and token-file redaction guard shipped. | `evidence/2026-06-03-vidux-config-schema-redaction-smoke.md`; ledger `evt_codex_20260603_5e30dg_config_schema_redaction` at line 5792. |
| 5.3.0dh | Documentation bug sweep closed current source drift. | `evidence/2026-06-03-vidux-doc-bug-sweep-smoke.md`; ledger `evt_codex_20260603_5e30dh_docs_bug_sweep` at line 5793. |
| 5.3.0di | Spawned-subagent inherited-env attribution smoke shipped. | `evidence/2026-06-03-vidux-spawned-subagent-smoke.md`; ledger `evt_codex_20260603_5e30di_spawned_subagent_smoke` at line 5794. |

## Bugs and drift found

- Config docs described a checked-in live `vidux.config.json` shape; source truth is `vidux.config.example.json`, while live config is user-local and gitignored.
- Initial signpost attribution could be misread under ambient Codex env; `VIDUX_RUNTIME` and the spawned-subagent smoke now make Claude/Cursor worker attribution explicit.
- `vidux doctor` and `scripts/vidux-doctor.sh --json` were blurred in docs/help; they are now split as terminal install/readiness doctor versus hook-safe runtime doctor.
- Browser docs missed shipped receipt/read-aloud routes and loopback JSON-write safety.
- Command/setup/checkpoint docs carried plan-only or commit-checkpoint shortcuts; patched docs now keep owning PLAN.md plus publish ledger as the recovery packet, with git as transport.
- Lifecycle docs initially drifted on exact checkpoint wording; the contract caught it and the docs were corrected.
- A closeout publish-scrutiny packet initially omitted `--claim`; the writer failed closed and the corrected packet passed.

## Smokes run

- CLI/config: `vidux config check|show`, example fallback validation, schema-error coverage, and token-file metadata redaction.
- Doctor: skip-npm install/readiness doctor, runtime doctor JSON warning-only smoke, and help text split.
- Signposts: trace, wrap, lifecycle-smoke, and spawned-subagent-smoke with a `/tmp` fixture trace.
- Browser: server tests, read-only truth endpoint, desktop/mobile screenshots, health route, and JS syntax.
- Multi-app matrix: Vidux CLI/browser, local Litty health, local Moussey health, and observe-only StrongYes/Resplit plan scans.
- Docs/contracts: VitePress docs build and focused contracts for lifecycle, doctor split, setup/checkpoint/hooks, browser truth/read-aloud, and docs bug sweep.

## Remaining risks

- The multi-app matrix found cold 3-second budget failures: `/api/vidux/truth`, Moussey coding capabilities, Moussey local-CI, and a partial Litty `/workers` response. These are monitor-budget/readiness risks, not proof that those routes are down.
- No live `vidux.config.json` was created; config proof uses example fallback plus schema tests.
- Runtime doctor warnings were observed but not repaired.
- The signpost smokes are local fixtures; they do not prove real external Claude, Codex, or Cursor process launch.
- Hooks were documented and smokeable, but no hook installer or runner was added.
- StrongYes/Resplit product repos stayed observe-only; no product tests, TestFlight/App Attest, local-CI execute, Resplit launch proof, or external board mutation was performed.
- The wider Phase 5.3.1 automation work remains parked on the Resplit `gh pr create` overlap issue.

## Post-closeout update

- 5.3.0dk resolved the Vidux `/api/vidux/truth` cold-budget finding with a monitor-safe cached route plus an explicit synchronous proof route. Evidence: `evidence/2026-06-03-vidux-truth-cache-smoke.md`.
- The Moussey coding capabilities/local-CI and partial Litty `/workers` cold-budget findings remain separate unresolved risks.

## Next non-hot work

- Add cached/asynchronous monitor budgets for browser truth and app-adjacent health routes before treating 3-second probes as durable green/red checks.
- If real external runtimes become available, run the same signpost run id through actual Codex/Claude/Cursor parent and worker processes, then compare against the local spawned-subagent smoke.
- Decide whether live config creation should be a guided `vidux config init` onboarding step or remain explicit/manual.
- Keep product-repo proof observe-only until a current StrongYes/Resplit plan row authorizes mutation.
- Resume root Phase 5 at 5.3.1 only after the Resplit `gh pr create` overlap blocker is solved or consciously bypassed.

## Final proof

- `python3 -m unittest tests.test_signpost tests.test_vidux_contracts.ViduxContractTests.test_fleet_lifecycle_docs_share_config_doctor_signpost_contract` PASS, 7/7 after 5.3.0di.
- `npm run docs:build` PASS after 5.3.0di.
- Scoped `git diff --check` PASS after 5.3.0di.
- Closeout `npm run docs:build` PASS.
- Closeout `git diff --check -- PLAN.md evidence/2026-06-03-vidux-five-hour-closeout.md` PASS.
- Closeout publish scrutiny PASS with `ready=true`.
- Closeout publish ledger `evt_codex_20260603_5e30dj_five_hour_closeout` verified in `~/.agent-ledger/activity.jsonl:5796`.

## Non-claims

- No stage, commit, push, PR, external message, external board mutation, paid-service mutation, hook install, local-CI execute, product repo mutation, TestFlight/App Attest proof, or real external runtime launch was performed.
