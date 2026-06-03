# Local Operator Stack Status - 2026-06-01

Parent objective: Moussey + Vidux local operator stack.

## Current Position

- Moussey `main` was clean and synced with `origin/main` at `7132196672b5` before the LCQ-5 patch; LCQ-5 is now committed locally as `5706b28` and the branch is ahead of `origin/main` by 1.
- Moussey `:4321` was rebuilt/restarted from local commit `5706b28`.
- `/api/coding/local-ci` now reports clean local source for `5706b28` (`dirty_count=0`, `freshForHead=true`) and an honest cockpit-runtime warning because `sync_status=not_origin_main`, not origin-main launch truth.
- Repo-backed FirstBite MCP status remains the authority if loaded MCP clients are stale; the live Moussey chat route itself is rebuilt and verified for LCQ-5.
- The live local-CI catalog is available on this machine: `ok=true`, `laneCatalog=43`, `latestLaneProof=43`, `recentRuns=12`.
- No local-CI lane/source reservations are active: `reservations.activeRunCount=0`.

## Completed / Evidence-Backed

1. Moussey C99 deferred React perf and submit guards are complete.
   - Plan row: `agentic-coding-workbench/PLAN.md` C99 progress entry.
   - Evidence: `evidence/2026-05-31-c99-moussey-react-perf-finalize.md`.
   - Proof already recorded there: TypeScript, focused tests, build, restart, live API, Playwright desktop/mobile screenshots for `/coding`, `/chat`, and `/consignment`.

2. Current-machine Moussey cockpit runtime was refreshed; the LCQ-5 dirty-source supersession is resolved by local commit `5706b28`.
   - Commands run in `/Users/leokwan/Development/moussey`:
     - `npm run build`
     - `bash scripts/moussey-server.sh --restart`
     - `curl -fsS http://127.0.0.1:4321/api/health`
     - `curl -fsS http://127.0.0.1:4321/api/coding/local-ci`
   - Result: build passed with the known local-CI artifact Turbopack NFT warning; health returned `ok=true`; local-CI returned current runtime proof before the LCQ-5 patch.
   - Refreshed again after HEAD moved to `7132196672b596faae9cdb3b758cd3dab6f529bb`.
   - Earlier clean proof: `/api/coding/local-ci` reported `cockpitRuntime.status=ready`, `buildStamp.freshForHead=true`, `laneCatalog=43`, `38` passing / `5` failing, `definitionDrift.hasDrift=false`, and launch trust `5/12` ready.
   - Latest local proof: after committing LCQ-5 as `5706b28`, rebuilding, and restarting, `/api/coding/local-ci` reports `dirty_count=0`, `buildStamp.freshForHead=true`, `ahead_origin_main=1`, `behind_origin_main=0`, and `sync_status=not_origin_main`.
   - Superseding note: the source-dirty warning is gone; the remaining runtime warning is only that local `main` is ahead of `origin/main`.
   - Plan update: `firstbite-local-ci-mega/PLAN.md` M4 flipped to `[completed]`.

3. Local-CI readiness has current-machine proof, with honest remaining yellow.
   - Green/ready: repo-backed FirstBite MCP catalog current, Xcode slot open, no active reservations, local KV ready, 43 catalog/proof rows available.
   - Yellow/non-green: stale loaded MCP clients, run-root latest durable report is stale, M4 peer is support-only, and some external repo Playwright caches are missing or only latest-known green.

4. Chat local front door has current route proof.
   - Focused tests passed: `node --test --import tsx lib/local-model-runtime.test.ts lib/brain-dispatcher.test.ts app/api/chat/ask/route.test.ts lib/local-tool-registry.test.ts` -> 31/31.
   - Live providers: `/api/chat/providers` reports `defaultProvider=local`, `local=gpt-oss:20b ready`, `codex=Codex CLI installed`.
   - Live two-turn memory smoke passed on the rebuilt server:
     - Session: `codex-live-smoke-1780279031317`.
     - Marker: `blue-lantern-78647`.
     - Turn 1 reply: `OK blue-lantern-78647`.
     - Turn 2 reply: `blue-lantern-78647`.
   - The local route sends role-tagged `messages[]` to Ollama and wires read-only Moussey tools through the local tool registry.
   - LCQ-5 no-thinking fast path is now closed and committed locally as `5706b28`: live `/api/chat/ask` fast smoke on `gpt-oss:20b` returned `awake` in `1305ms` precommit and `5893ms` postcommit, both with `thinking_events=0`.

5. Captain skill/setup health has current proof.
   - Command: `bash /Users/leokwan/Development/ai/skills/captain/scripts/audit_skills.sh`.
   - Evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-captain-skill-audit.md`.
   - Result: frontmatter health OK, redirect target health OK, profile checks OK.
   - 2026-06-01 refresh result: same non-blocking warning set; shared `/ai` is ahead of upstream but no shared/private-boundary mutation was required for this operator-stack slice.
   - Non-blocking warnings remain: setup-policy first-screen warnings for `overlay:local-ci`, `shared:brand-moussey`, `shared:moussey`, `source:/Users/leokwan/Development/vidux/SKILL.md`, and the Playwright trace skill; plus `vidux/SKILL.md` description length warning.
   - No shared/private-boundary mutation was required for this operator-stack goal.

6. The next Vidux goal shape is now durable in the same project.
   - Canonical plan: `firstbite-local-ci-mega/PLAN.md` rows M17-M24.
   - Source artifacts: `firstbite-local-ci-mega/CODEX-SUPER-PLAN.md` and `firstbite-local-ci-mega/RECURSIVE-MVP-PLAN-DRAFT.md`.
   - Baseline readout: `/Users/leokwan/.agent-ledger/firstbite-operating-readout/codex-20260601-recursive-goal-baseline/summary.md`.
   - Result: the recursive execution MVP is no longer just a paste prompt; the plan now points to P4-03 retention, P1 trust-freshness, and P2 drift-ledger as the next agent-doable sequence.

7. M19/P4-03 retention dry-run proof exists, with no deletion.
   - Tests passed: `firstbite-proof-retention-plan.test.sh` and `firstbite-cache-prune-plan.test.sh`.
   - Proof-root dry-run: `/Users/leokwan/.agent-ledger/firstbite-proof-retention-plan/codex-20260601-m19-retention-dry-run/summary.md`.
   - Cache dry-run: `/Users/leokwan/.agent-ledger/firstbite-cache-prune-plan/codex-20260601-m19-cache-prune-dry-run/summary.md`.
   - Result: proof-root candidate set is 4.75 GiB approval-required, cache-prune candidate set is 7.19 GiB approval-required, and both reports say `deletion_performed=false`.
   - Review runner: `/Users/leokwan/Development/ai-leo/skills/local-ci/scripts/firstbite-retention-review-runner.sh`.
   - Runner evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m19-retention-review-runner.md`.
   - Live runner packet: `/Users/leokwan/.agent-ledger/firstbite-retention-review-runner/codex-20260601-m19-retention-review-runner/summary.md`.
   - Result: combined approval-required total is 11.94 GiB, LaunchAgent template cadence is 1800s, `deletion_performed=false`, and `install_performed=false`.

8. M20/P1 trust-freshness is implemented and live-proven.
   - Code: `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/src/server.mjs`.
   - Docs: `/Users/leokwan/Development/ai-leo/skills/resplit-watch/mcp/firstbite-local-ci/README.md`.
   - Contract added: `catalog_age_seconds` / `catalog_stale` on `list_lanes` + `status`; `source_commit`, `proof_age_hours`, and `stale_proof` on `status.latest_lane_proof[]`; host-labeled live `statfs` in `disk_guard.live_headroom`; `status.freshness_contract` with the no-green-can-lie rule.
   - Live status proof: `43/43`, `catalog_stale=false`, host `Leos-Mac-Studio-10442.local`, live disk `55.13 GiB` / `94%`, `stale_proof_count=41`, `unknown_proof_age_count=2`.
   - Red diagnosis proof: `strongyes_web_ui` is `fail/stale`, `proof_age_hours=25.92`, `stale_proof=true`, `source_commit=9488edb291b330d57470b662ca6ca42d184c8b51`, reason `command produced no output before stall timeout`.
   - Verification passed: MCP lint, live `list_lanes` JSON assertion, live `status` JSON assertion, `firstbite-disk-guard-status.test.sh`, and `firstbite-operating-readout-source-contract.test.sh`.

9. M21/P2 drift-ledger activation is implemented and smoke-proven.
   - Backfill rubric: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m21-drift-ledger-backfill.md`.
   - Cache: `/Users/leokwan/.vidux/drift-cache.jsonl`.
   - Seed state: 6 records, all with non-empty `evidence_refs` and `prevention_hints`, below the <=30-record cap.
   - READ wiring: `/Users/leokwan/Development/vidux/scripts/vidux-loop.sh` emits `drift_suggestions` scoped to the active task.
   - CHECKPOINT wiring: `/Users/leokwan/Development/vidux/scripts/vidux-checkpoint.sh` emits warn-only `DRIFT ADVISORY` lines when a cache-backed hint matches.
   - Quality floor: `/Users/leokwan/Development/vidux/scripts/vidux-drift-log.py` rejects `impact=blocking` records unless they include at least one `--evidence-ref`.
   - Verification passed: `python3 -m unittest tests.test_drift_log`; `bash -n scripts/vidux-loop.sh && bash -n scripts/vidux-checkpoint.sh`; `jq -s` cache validation; `vidux-drift-log.py suggest ... --task-text ... --json`; temp-plan READ smoke; temp-git checkpoint advisory smoke.

10. M22/P3 observe-only recursive bridge is complete for the no-dispatch slice.
   - Script: `/Users/leokwan/Development/vidux/scripts/vidux-firstbite-observe.py`.
   - Tests: `/Users/leokwan/Development/vidux/tests/test_firstbite_observe.py`.
   - Evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m22-observe-only-bridge.md`.
   - Fresh status snapshot evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m22-status-snapshot-drift.md`.
   - Behavior: FirstBite `report.json` / MCP text-wrapper JSON -> deterministic red/stale/missing advisories -> ready-to-run `vidux-drift-log.py` command arrays with mandatory evidence refs, plus `plan_lint` duplicate/missing-record counts and `dispatch_policy` cockpit-gate state.
   - Safety: the observe script does not write drift records, mutate PLAN.md, block rows, call MCP, or dispatch workers. It always reports `dispatch_allowed=false`, even if `BRAIN_AUTODISPATCH` is truthy.
   - Verification passed: `python3 -m unittest tests.test_firstbite_observe tests.test_drift_log`; live status-snapshot smoke returned `plan_lint.status=ready`, `already_recorded=5`, `missing_record=0`, `dispatch_policy.status=observe_only`, `dispatch_policy.blockers=[m22_observe_only_brake]`, and `dispatch_policy.cockpit_gate.allowed=false`; `BRAIN_AUTODISPATCH=on` smoke returned `dispatch_allowed=false`, `action=suppressed_observe_only`, and `dispatch_policy.requested=true`.
   - Emitted commands were run manually for `strongyes_web_ui` (`D-20260531-01`), `litty_live_moussey` (`D-20260531-06`), `resplit_currency_api_trust_preflight` (`D-20260601-01`), `moussey_snowcubes_invoice` (`D-20260531-09`), and `moussey_snowcubes_readiness` (`D-20260531-11`) in `firstbite-local-ci-mega/PLAN.md` plus `/Users/leokwan/.vidux/drift-cache.jsonl`; no task was blocked.

11. M23/P4 verified-alive is complete for agent-doable work as a self-refreshing, review-only heartbeat packet.
   - Script: `/Users/leokwan/Development/vidux/scripts/vidux-firstbite-verified-alive.py`.
   - Runner: `/Users/leokwan/Development/vidux/scripts/vidux-firstbite-verified-alive-runner.sh`.
   - Tests: `/Users/leokwan/Development/vidux/tests/test_firstbite_verified_alive.py`.
   - Runner test: `/Users/leokwan/Development/vidux/tests/test_firstbite_verified_alive_runner.sh`.
   - Evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-verified-alive.md`.
   - Live rollup JSON: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-verified-alive.json`.
   - Live runner packet: `/Users/leokwan/.agent-ledger/vidux-firstbite-verified-alive-runner/codex-20260601-m23-verified-alive-runner/summary.md`.
   - Live runner report: `/Users/leokwan/.agent-ledger/vidux-firstbite-verified-alive-runner/codex-20260601-m23-verified-alive-runner/report.json`.
   - LaunchAgent template: `/Users/leokwan/.agent-ledger/vidux-firstbite-verified-alive-runner/codex-20260601-m23-verified-alive-runner/com.leokwan.vidux-firstbite-verified-alive.template.plist`.
   - Refresh mode: `--refresh-dir` now gathers FirstBite MCP status, re-runs M22 observe-policy, fetches live Moussey `/api/health`, `/api/chat/providers`, and `/api/coding/local-ci`, and writes exact input snapshots before emitting the rollup.
   - Input snapshots: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-firstbite-status.json`, `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-observe-policy.json`, `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-moussey-health.json`, `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-chat-providers.json`, and `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m23-refresh-moussey-local-ci.json`.
   - Result: current rollup is `warning`, not blocked: `3 ready / 5 warning / 0 blocked`.
   - Ready checks: repo-backed catalog is fresh (`43` lanes across `6` repos), drift tile is reconciled (`already_recorded=8`, `dispatch_allowed=false`), and Moussey health is green.
   - Yellow checks: stale/unknown proof remains `41` / `2`; disk guard reports warning at `37.47 GiB` and `96%`; retention LaunchAgent template exists but was not installed; Claude remains credential-gated; Moussey local-CI endpoint responds but still reports launch/readiness warnings.
   - Safety: the verified-alive script and runner do not run CI lanes, install crons, delete files, write drift records, dispatch workers, mutate repos, or restart services.
   - Live runner flags: `readonly=true`, `local_ci_lanes_executed=false`, `install_performed=false`, `deletion_performed=false`, `drift_records_written=false`, and `workers_dispatched=false`.
   - Verification passed: `python3 -m unittest tests.test_firstbite_verified_alive tests.test_firstbite_observe tests.test_drift_log` -> `19/19 OK`; `bash tests/test_firstbite_verified_alive_runner.sh`; `bash -n scripts/vidux-firstbite-verified-alive-runner.sh tests/test_firstbite_verified_alive_runner.sh`; `python3 -m py_compile scripts/vidux-firstbite-verified-alive.py`; live refresh smoke returned `warning: 3 ready, 5 warning, 0 blocked`; live runner packet returned the same summary; `plutil -lint` on the template returned `OK`.
   - Row status: `firstbite-local-ci-mega/PLAN.md` marks M23 `[completed 2026-06-01]`; installing or bootstrapping the LaunchAgent is still a separate operator-approved operation.

12. M24/P5 honest deferrals firewall is complete.
   - Script: `/Users/leokwan/Development/vidux/scripts/vidux-local-operator-deferrals.py`.
   - Tests: `/Users/leokwan/Development/vidux/tests/test_local_operator_deferrals.py`.
   - Evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m24-honest-deferrals-firewall.md`.
   - Live firewall JSON: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m24-honest-deferrals-firewall.json`.
   - Result: current firewall is `ready`: `6 deferred surface group(s) have canonical owners and re-entry gates`.
   - Deferred groups: Moussey mobile PWA, Tailscale remote LAN, Nicole device handoffs, fleet-state/secret rotation, voice streaming/router, and worker-pool/embeddings/autodispatch.
   - Canonical owners: `connect-the-fleet/PLAN.md` rows C-3/C-4/C-7/C-11/C-14/C-16/C-17..C-20/C-21/C-22/C-24/C-25/C-30..C-35, `moussey-mobile-operator/PLAN.md` rows M-R6/M-R66/M-R68/M-R74, and `firstbite-local-ci-mega/PLAN.md` rows M22/M23/M24.
   - Safety: the firewall does not edit Moussey app code, touch Nicole-owned devices, send human messages, expose services over Tailscale/public networking, execute local-CI lanes, dispatch workers, write embeddings, or mark deferred rows product-complete.
   - Verification passed: `python3 -m unittest tests.test_local_operator_deferrals tests.test_firstbite_verified_alive tests.test_firstbite_observe tests.test_drift_log` -> `22/22 OK`; `python3 -m py_compile scripts/vidux-local-operator-deferrals.py scripts/vidux-firstbite-verified-alive.py scripts/vidux-firstbite-observe.py scripts/vidux-drift-log.py`; live firewall JSON returned `status=ready`.
   - Row status: `firstbite-local-ci-mega/PLAN.md` marks M24 `[completed 2026-06-01]`; any future dispatch/worker promotion still needs a separate operator-approved plan row.

## Still Not Done

1. Chat/operator routing is green for local memory/tool-loop/no-think basics, but not fully green across every brain and data source.
   - Claude route is credential-gated on this Mac: `/api/chat/providers` reports `Claude CLI auth failed recently on this Mac; sign in again with \`claude\`.`
   - Receipts-backed tool answers still depend on `vidux-browse :7191`; consignment tool answers depend on the tracker CSV being configured.
   - Current auth surface audit: `/Users/leokwan/Development/vidux/projects/connect-the-fleet/evidence/2026-06-01-current-auth-surface-audit.md`.
   - Initial audit found LAN trigger HMAC auth present, but `/api/chat/ask` was not guarded by the M-R6/RA-2 Bearer-passcode path. RA-2 proof exists in PR #26 commit `b20e7e8`, but that commit is not an ancestor of current HEAD `5706b28`.
   - Integration probe result: `git cherry-pick --no-commit b20e7e8 7a7257e 9b65993` conflicted on drifted `/api/chat/ask` and missing current `/api/voice` route tree, then was cleanly aborted. Use a clean worktree for the RA-2 current-source merge.
   - 2026-06-01 update: current-source `/api/chat/ask` server auth guard is now ported and live-rebuilt. Evidence: `/Users/leokwan/Development/vidux/projects/connect-the-fleet/evidence/2026-06-01-current-chat-auth-port.md`.
   - Remaining non-claims: no live `MOUSSEY_CHAT_AUTH=enforce` flip, no real passcode set/read, no current-source `/voice` route/auth parity, no RA-2b client prompt, and no RA-2c STT WebSocket gate.

2. Moussey mobile operator rows are still mostly plan-gated or owner-gated.
   - C-9/M-R3b is no longer an active blocker: the physical merge is deferred post-launch, and `moussey-mobile-operator/PLAN.md` remains the canonical mobile overlay while `agentic-text-chat/PLAN.md` owns the desktop/SSE foundation.
   - `moussey-mobile-operator/PLAN.md` still carries pending implementation rows such as M-R66/M-R68/M-R74, M-R75/M-R76, M-R84, M-R87/M-R88/M-R89, M-A1..M-A4, and Phase 1 mobile shell rows.
   - `connect-the-fleet/PLAN.md` keeps those implementation rows sequenced behind M1 Pro Claude ownership, Tailscale/auth gates, and Leo/Nicole keyboard gates.
   - M24 now records this as an explicit firewall instead of an implicit loose end; see `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m24-honest-deferrals-firewall.md`.

3. Litty boundary is clear, but runtime handoff remains gated.
   - Boundary: Moussey is the LAN/data/API hub; Litty is the standalone coding cockpit.
   - Completed proof: FirstBite M4 Moussey rebuild is done now, historical Litty lane proof exists, and Litty C233's Ollama 32768-context LaunchAgent row is now completed from live plist proof.
   - Plan-spine cleanup completed: `connect-the-fleet/PLAN.md` C-8 migrated legacy workbench UX-01..UX-42 into Litty; workbench now keeps those rows as a historical mirror only.
   - Evidence: `/Users/leokwan/Development/vidux/projects/connect-the-fleet/evidence/2026-06-01-c8-coding-ux-migration.md`.
   - Remaining runtime gate: `firstbite-local-ci-mega/PLAN.md` M3 LaunchAgent handoff for `:4400` is still `[blocked]` on operator handoff; M2 host-app MCP convergence is still blocked on restarting stale Codex/Cursor MCP clients; Litty C234 still needs the `:4400` production/LaunchAgent watchdog half.

4. Captain skill/setup audit is non-blocking, not fully clean.
   - Current audit passed redirect/profile checks.
   - Evidence: `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-captain-skill-audit.md`.
   - Remaining warnings are setup-policy/description warnings in existing skill docs and are documented as non-blocking unless Leo asks for a shared-skill cleanup pass.

5. M23/P4 verified-alive is install-ready for review, but not installed as a heartbeat.
   - The self-refreshing digest and review-only runner exist and are tested.
   - A LaunchAgent template exists in the live runner packet and passed `plutil -lint`.
   - No LaunchAgent or recurring scheduler was installed.
   - Next decision: keep it as an explicit operator-run digest or approve the exact LaunchAgent install/bootstrap operation.

6. M24/P5 closes deferral tracking, not the deferred products.
   - Mobile PWA, Tailscale, Nicole device handoffs, fleet-state/secret rotation, voice streaming/router, and worker-pool/embeddings/autodispatch are all tracked with canonical owners and re-entry conditions.
   - None of those surfaces are claimed complete by the FirstBite trust/drift slice.
   - Worker/autodispatch promotion remains closed until a future operator-approved plan row names authority, budget, rollback, and proof.

## Exact Resume Path

Recommended next agent-doable slice:

1. Start in `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega`.
2. Read `PLAN.md` rows M17-M24, `CODEX-SUPER-PLAN.md`, `RECURSIVE-MVP-PLAN-DRAFT.md`, and the baseline readout summary above.
3. M19/P4-03 is complete for agent-doable work:
   - review-only runner exists at `/Users/leokwan/Development/ai-leo/skills/local-ci/scripts/firstbite-retention-review-runner.sh`,
   - live packet is `/Users/leokwan/.agent-ledger/firstbite-retention-review-runner/codex-20260601-m19-retention-review-runner/summary.md`,
   - LaunchAgent template exists in that packet but was not installed,
   - exact cleanup-class approval is still required before deleting anything.
4. M22/P3 observe-only recursive bridge is complete for the no-dispatch slice:
   - first safe slice is `/Users/leokwan/Development/vidux/scripts/vidux-firstbite-observe.py`,
   - real emitted drift records include `D-20260531-01` for `strongyes_web_ui`, `D-20260531-06` for `litty_live_moussey`, `D-20260601-01` for `resplit_currency_api_trust_preflight`, `D-20260531-09` for `moussey_snowcubes_invoice`, and `D-20260531-11` for `moussey_snowcubes_readiness`,
   - keep `BRAIN_AUTODISPATCH=off`; if set truthy, the observer still reports `suppressed_observe_only`,
   - treat advisories as sort inputs, not autonomous authority,
   - next code slice should be a separate operator-approved promotion row if real dispatch is ever desired.
5. M23/P4 verified-alive is completed for agent-doable work:
   - refresh the digest with `python3 scripts/vidux-firstbite-verified-alive.py --refresh-dir projects/firstbite-local-ci-mega/evidence --prefix <date-or-run-id> --write-json <rollup.json> --write-markdown <rollup.md>`,
   - run the review-only heartbeat packet with `VIDUX_VERIFIED_ALIVE_RUN_ID=<run-id> bash scripts/vidux-firstbite-verified-alive-runner.sh`,
   - latest live packet is `/Users/leokwan/.agent-ledger/vidux-firstbite-verified-alive-runner/codex-20260601-m23-verified-alive-runner/summary.md`,
   - do not install LaunchAgents, delete retention candidates, dispatch workers, write drift records, or run CI lanes without explicit operator approval.
6. M24/P5 honest deferrals firewall is completed for agent-doable work:
   - refresh the firewall with `python3 scripts/vidux-local-operator-deferrals.py --repo-root /Users/leokwan/Development/vidux --write-json projects/firstbite-local-ci-mega/evidence/<run-id>-m24-firewall.json --write-markdown projects/firstbite-local-ci-mega/evidence/<run-id>-m24-firewall.md`,
   - current proof is `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/evidence/2026-06-01-m24-honest-deferrals-firewall.md`,
   - do not convert deferred rows into build work inside the FirstBite trust/drift slice; resume them from `connect-the-fleet/PLAN.md` or `moussey-mobile-operator/PLAN.md` under their named owner gates.
7. If returning to Moussey chat instead, start in `/Users/leokwan/Development/moussey`, read `AGENTS.md`, `/Users/leokwan/Development/vidux/projects/firstbite-local-ci-mega/PLAN.md`, and the Local Chat Quality Track in that plan.
8. Continue chat front-door hardening from the remaining yellow:
   - Re-auth Claude CLI if Claude routing needs to be green on this Mac.
   - Run a live read-only tool smoke once `vidux-browse :7191` and the relevant data source are up.
   - Watch fast local latency for regressions; LCQ-5 itself is closed by `firstbite-local-ci-mega/evidence/2026-06-01-lcq5-no-think-fast-path.md`.
9. Preserve boundaries:
   - Do not expand old Moussey `/coding` product UI.
   - Do not mutate mobile/PWA code rows owned by M1 Pro Claude unless Leo redirects ownership.
   - Keep Litty cockpit work in the Litty plan.
   - Treat C-8 as closed: workbench UX-01..UX-42 are now historical mirrors, and active follow-up belongs in `litty/PLAN.md` Phase 12.

Operator-gated resume:

- M2: restart host apps so loaded MCP clients converge.
- M3: hand off `:4400` from manual dev server to LaunchAgent.
- M9: provide webhook secrets.
- M16: approve/run M4 parity execute.
- Mobile/PWA: Leo/Nicole keyboard gates for Tailscale, device install, and Nicole iOS version.
