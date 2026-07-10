# Current Benchmark Authority: V4 Pre-Spend Integrity

Date: 2026-07-10
Owner: Codex evidence lead
Scope: Vidux only; no Resplit repository was opened or changed

## Verdict

SHIPPING for this reversible integrity slice. `vidux-cockpit-v4` is the sole current benchmark authority and is mechanically valid at manifest digest `21d6ecb6469eab654ecd932e5a27ff735518dbc19b80d3283e15848837406c81`.

The benchmark is deliberately not runnable. It has no registered external evaluator, authenticated evaluator release, provider transport, pilot result, or verified net-win class. `ready_for_provider_spend=false`, `claim_eligible=false`, and `verified_net_win_classes=0` remain the only truthful product-value state.

## What Changed

- Embedded the exact v3 outcome contract into v4: provider pairs, four arms, four scenario classes, 4-pilot/48-full fixture schedule, budgets, measurement, adjudication, exclusion, and decision rules.
- Bound authenticated evaluator releases to exact provider/runtime profiles and content-addressed fixture and runner artifacts.
- Added a deterministic 208-run schedule: 52 fixtures times 4 arms, split into 16 pilot and 192 full runs.
- Added canonical runner results and OpenSSH-signed evaluator result bundles with exact release, schedule, run, implementation, transcript, artifact, and evaluator evidence bindings.
- Added a hash-chained dispatch journal with schedule-derived run/attempt/dispatch identities, duplicate operation rejection, file and parent-directory durability, and bounded torn-tail recovery.
- Added one-shot provider reservation. An ambiguous reserved attempt must reconcile its provider receipt and cannot be invoked again automatically.
- Added cumulative provider metrics across attempts, runs, stages, and the full protocol. Retries require both the previous provider receipt and a content-addressed failure receipt.
- Added the public `vidux benchmark` front door and shell completions. It routes only to v4 readiness and integrity commands and refuses v2/v3 or legacy pilot/full/run paths.
- Clarified in README and SKILL that the old local bakeoff is historical evidence, not a current execution authority.

No provider transport, adjudication runner, or outcome-decision command was added.

## Protocol Amendment Boundary

V4 was still unregistered, unreleased, non-runnable, and unspent when this slice began. The integrity contract could therefore be amended in place only because every v3 outcome rule was embedded unchanged. The earlier v4 digest remains a truthful historical receipt in `evidence/2026-07-10-benchmark-v3-retirement-v4-integrity.md`.

After an evaluator registration or release exists, this manifest is frozen. Any future outcome-rule change requires `vidux-cockpit-v5`; transport-only implementations must bind to the registered v4 contract without changing it.

## Threat Model Closed

| Threat | Mechanical response |
|---|---|
| Digest-shaped path without artifact bytes | Every fixture, profile, runner, transcript, and result reference resolves through a content-addressed artifact root. |
| Forged or rebound evaluator result | Canonical OpenSSH signatures bind evaluator identity, release, schedule, run, and result evidence. |
| Retry cost omitted from outcome accounting | Provider receipt metrics accumulate across all attempts and fail at run, stage, and protocol ceilings. |
| Crash after dispatch but before local receipt | Reservation persists before invocation; the attempt becomes reconciliation-only and cannot auto-reinvoke. |
| Duplicate operator or replayed request | Journal operation IDs and schedule-derived attempt identities are unique and fail closed. |
| Torn or malformed journal state | Only an unterminated final fragment may be removed; a hash-chained recovery receipt is appended. Terminated invalid rows are rejected. |
| Journal creation lost after reported success | Journal bytes and the containing directory are fsynced before initialization returns. |
| Historical runner accidentally used | Public CLI refuses legacy v2/v3/run/pilot/full/decide entry points. |

## Mechanical Proof

### Focused integrity

- `python3 -m unittest -v tests.test_benchmark_v4` -> PASS, 19 tests.
- `python3 -m unittest -v tests.test_vidux_contracts.ViduxContractTests.test_vidux_fish_help_completion_includes_help_subcommand` -> PASS.
- `python3 -m py_compile scripts/vidux-benchmark-v4.py` -> PASS.
- `bash -n bin/vidux scripts/vidux-completion.sh` -> PASS.
- `git diff --check` -> PASS.

The adversarial suite covers exact v3 outcome equality, schedule completeness and tamper, signed evaluator results and identity rebound, missing and aliased artifacts, duplicate dispatch, ambiguous no-reinvoke behavior, receipt reconciliation, retry authorization, cumulative metrics, crash recovery, directory durability, and public CLI/completion authority.

### Full product floor

- `npm run verify` -> PASS: 15 JavaScript tests; 897 Python tests, 5 skipped; 415 tracked files passed the public-ready scan.
- Final staged `python3 scripts/vidux-public-ready-grep-gate.py --tracked-only` -> PASS across 416 files, including this receipt.
- `npm run test:e2e` -> PASS: 129 Playwright journeys across desktop Chromium and phone portrait.
- `npm run docs:build` -> PASS.
- `npm audit --audit-level=high` -> PASS, 0 vulnerabilities.
- `npm run release:verify` -> PASS: version `2.23.0`, 201 files, 2,089,572 unpacked bytes, package SHA-256 `a0e015a29cc1f537dd352d25df5c6efab82db6e490757b716da124390597805d`.

### Authority and readiness

- `npm run benchmark:v2:validate` -> valid historical artifact, `retired_non_runnable`.
- `npm run benchmark:v2:readiness` -> expected exit 2, not ready.
- `npm run benchmark:v3:validate` -> valid historical artifact, `retired_non_runnable`.
- `npm run benchmark:v3:readiness` -> expected exit 2, not ready.
- `npm run benchmark:v4:validate` -> PASS, digest `21d6ecb6469eab654ecd932e5a27ff735518dbc19b80d3283e15848837406c81`.
- `npm run benchmark:v4:readiness` -> expected exit 2 with four explicit gates: authenticated external evaluator release, non-runnable status, absent provider transport, and unfrozen evaluator registration.
- `bin/vidux benchmark` -> same fail-closed v4 readiness receipt.
- `bin/vidux benchmark v3` -> expected refusal; legacy execution is unavailable.

### Mount and remote currentness

- `skillbox doctor --json` -> exit 0, blocking 0; normal source-shadow rows only.
- `python3 ~/Development/ai/scripts/validate-skill-sources.py` -> identical sources and win order.
- Vidux mounts in `~/.ai/skills-active`, `~/.agents/skills`, and `~/.claude/skills` all point to the current Vidux checkout.
- `git fetch origin main codex/vidux-mission-control-20260709` -> PASS.
- `git rev-list --left-right --count origin/main...HEAD` -> `0 14` before this commit: no missing main commit.
- `git pull --ff-only` -> already up to date.
- PR #8 was OPEN, non-draft, CLEAN, with secret scan and mergeability checks green before this commit.

## Independent Review

- GLM read-only review identified concrete preservation, result-authentication, and dispatch-persistence gaps. The final implementation closes them with exact contract checks and adversarial tests.
- Claude/Fable delivered the bounded protocol decision: amending unregistered v4 is valid only while v3 outcome rules stay exact; any outcome change requires v5. The advisor session then reached its hard budget, so it is recorded as a useful decision, not a clean sidecar completion.
- Grok was invoked read-only with a bounded blocker prompt, but global hook/bootstrap noise consumed the window and no verdict was produced. It is recorded as unavailable, not as approval and not as a product failure.
- Codex adjudicated every concrete claim against disk and runtime evidence, fixed the completion drift and the two final journal durability gaps, and accepted no broad risk statement without a falsifiable command or artifact.

## Resume Point

1. Obtain one independent evaluator registration and signed real-evidence release for all 52 fixtures and exact provider profiles.
2. Validate it with `vidux benchmark release-check`, then generate and freeze the deterministic schedule.
3. Implement provider transport as a separately reviewed consumer of the reservation/reconciliation journal. Do not add a browser action endpoint.
4. Run the 16-run pilot only when `vidux benchmark readiness` reports `ready_for_provider_spend=true`.
5. Keep every superiority claim at zero until authenticated real-evidence result bundles pass the frozen decision procedure.
