# Benchmark V3 Preflight Receipt

**Date:** 2026-07-10
**Verdict:** SHIPPING the preregistration and local proof machinery only.
Vidux product advantage remains **unproven** with `0` verified net-win classes.

## Frozen Protocol

- Protocol ID: `vidux-cockpit-v3`
- Protocol digest:
  `ba5a151dde4f0b767fc438bc38cb5bfe17843ef8f303a04f2c5275e1e5418dc3`
- Provider-matched arms: native and read-only-Vidux Claude under one exact
  Anthropic profile; native and read-only-Vidux Codex under one exact OpenAI
  profile.
- One evaluator release must freeze 4 pilot fixtures and 48 full fixtures at
  once. The deterministic Cartesian schedule contains 16 pilot and 192 full
  runs.
- Every run gets a fresh frozen workspace copy. Activation overhead and all
  retry usage count toward integer elapsed, token, micro-USD, and operator-
  touch ceilings.
- Post-release run/block exclusion and fixture replacement are forbidden.
  Runner, budget, and exhausted-infrastructure failures remain scored with
  zero success. An evaluator defect invalidates the protocol instead of
  opening an analyst-controlled exclusion.

## Proof Machinery

`scripts/vidux-benchmark-v3.py` provides only local artifact operations:
validate, readiness, schedule, packet, journal initialization/event/verify,
adjudication, and decision. It contains no provider invocation command.

The validator rejects duplicate/non-finite/deep JSON, unsafe fixture aliases,
profile drift, incomplete or reordered schedules, invented attempts, torn or
tampered journals, per-run cumulative retry overruns, and stage/protocol budget
overruns. Journal events are process-locked, canonical, hash-chained,
append-only, and fsynced.

Workers cannot write an adjudication event. The adjudicator first proves that
the exact attempt, metrics, and provider/runner/transcript digests match a
journaled terminal event, binds the evaluator result to that runner result,
then appends the computed adjudication digest. The decision command requires
every adjudication in the requested stage and verifies every receipt against
the journal before applying the frozen provider-stratified paired bootstrap.

## Blocker Foldback

Five bounded read-only audits shaped the initial provider, oracle, journal,
schedule, and package contracts. Codex self-review then found and fixed two
concrete defects: retries were individually bounded but not cumulative within
a logical run, and evaluator output was not tied to the exact runner result.

A bounded Fable review exhausted its roughly `$3.17` advisor window after
surfacing three falsifiable blockers. It did not return a post-fix approval.
All three claims were accepted and closed mechanically:

1. The referenced exclusion rule did not exist. V3 now forbids all
   post-release exclusions and replacements.
2. Thresholds were not an executable decision procedure. V3 now freezes and
   implements exact resampling, seeds, statistics, confidence intervals,
   undefined ratios, terminal failures, provider-pair wins, and class wins.
3. Adjudication trusted schedule-shaped result JSON. It now requires exact
   equality with the journaled terminal attempt and appends its own receipt
   digest.

A bounded read-only Grok review surfaced no concrete falsifier, but its local
verifier could not produce a terminal verdict after an oversized reference
bundle and unavailable shell path. It is recorded as sidecar unavailable, not
as approval or a product failure.

## Mechanical Proof

| Check | Result |
|---|---|
| `python3 scripts/vidux-benchmark-v3.py validate` | PASS; frozen digest matches status |
| `python3 scripts/vidux-benchmark-v3.py readiness` | Expected exit `2`; evaluator release missing and transport disabled |
| `python3 -m unittest tests.test_benchmark_v2 tests.test_benchmark_v3` | PASS: 52 tests |
| `python3 -m unittest tests.test_vidux_contracts` | PASS: 234 tests; 4 skipped |
| `npm run verify` | PASS: 15 JavaScript tests, 876 Python tests (5 skipped), and 408-file tracked-public scan |
| `npm run test:e2e` | PASS: 129/129 cross-browser journeys |
| `npm run docs:build` | PASS |
| `npm audit --audit-level=high` | PASS: 0 vulnerabilities |
| Python compile and staged-diff gates | PASS |
| `python3 scripts/vidux-release-package.py --json` | PASS: 196 files; reproducible SHA-256 `c39cfe682ac75a0652d940dda07c8cc210d4f45eeb52d03d40420b52149a004f` |
| Synthetic complete pilot decision | PASS: 16 journal-bound runs; never claim-eligible |
| Synthetic complete full decision | PASS: 192 journal-bound runs; byte-deterministic scorer path |
| Real evaluator release / provider run | NOT RUN |

Synthetic rows test the harness only. They are generated inside unit fixtures
and are not product evidence, raw benchmark data, or a Vidux win.

## Deliberate No-Spend Boundary

`benchmarks/v3/STATUS.json` keeps `provider_transport_enabled=false`,
`pilot_executed=false`, and `verified_net_win_classes=0`. Readiness cannot
authorize provider spend without both an external release and a separately
reviewed runner slice.

The next slice must bind the private evaluator implementation/receipt and all
pilot/full public fixtures, then add persisted provider-dispatch reservation
and receipt reconciliation. Only then may the 16-run pilot execute. No full
matrix may start from a directional pilot alone.
