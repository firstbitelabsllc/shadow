# Benchmark V2 Protocol Receipt

**Date:** 2026-07-10
**Verdict:** SHIPPING the protocol and validator slice only. Vidux product
advantage remains **unproven**.

## What This Slice Establishes

- `benchmarks/v2/manifest.json` freezes three fair arms: Vidux cockpit,
  native Claude, and native Codex. Every arm keeps ordinary filesystem access,
  uses the identical fixture workspace and tool-permission profile, and cannot
  inspect the hidden oracle.
- `benchmarks/v2/PROTOCOL.md` fixes four differentiated scenario classes:
  durable state, interruption recovery, cross-project prioritization, and
  proof inspection.
- `scripts/vidux-benchmark-v2.py` rejects unsealed transport, incomplete
  paired blocks, mismatched protocol/oracle commitments, missing runtime
  receipts, and unsupported value claims.
- The decision rule requires a class win against both native controls on
  success while staying within token-per-resolved-task, dollar-per-resolved-
  task, wall-time, operator-touch, and resume-loss guardrails. Provider costs
  include cockpit generation and routing overhead.

## Deliberate Non-Claim

No hidden oracle is sealed. No fixture release, raw result row, confidence
interval from a product run, or decision receipt exists. The score remains
`unproven`, and no one may claim that Vidux beats direct native work from this
protocol alone.

`python3 scripts/vidux-benchmark-v2.py readiness` deliberately exits `2` and
names five gates: the four unsealed oracles and the manifest transport status.
That fail-closed result is expected proof of the transport boundary, not a
product failure.

## Mechanical Proof

| Check | Result |
|---|---|
| `python3 -m unittest tests.test_benchmark_v2` | PASS: 12 tests |
| `python3 -m py_compile scripts/vidux-benchmark-v2.py` | PASS |
| `python3 scripts/vidux-benchmark-v2.py validate` | PASS: valid protocol, transport pending |
| `npm run benchmark:v2:validate` | PASS: valid protocol, transport pending |
| `bash scripts/vidux-test-all.sh --json` | PASS: 745 contract tests, 0 failures, 0 errors; doctor reported 12/15 checks with 3 warnings |
| `npm run verify` | PASS: 8 JavaScript tests; 745 Python tests, 5 skipped; public-ready scan passed on 362 staged files |
| `npm run test:e2e` | PASS: 102/102 browser journeys |
| `git diff --cached --check` | PASS: no whitespace errors in the staged candidate |
| Static proof-honesty lint | PASS: no unbacked proof claim matched; the lint does not itself validate named command execution |

## Independent Checks

- Claude advisor: two bounded read-only attempts yielded no adjudicable review,
  so no advisor approval is claimed.
- GLM delegated draft: the bounded read-only call produced no usable receipt,
  so it did not influence the protocol decision.
- Grok critique: bounded review output did not produce an adjudicable blocker,
  so it is recorded as unavailable rather than as approval.
- Skill mount audit: the named operator skills resolved. The broader mount
  audit carried pre-existing global drift advisories, so this receipt makes no
  claim that global mount hygiene is clean.

## Resume

Create a separate sealed fixture release outside every arm workspace. It must
carry the protocol digest and one SHA-256 oracle commitment per scenario class.
Only then may the validator emit arm packets and score complete paired rows.
