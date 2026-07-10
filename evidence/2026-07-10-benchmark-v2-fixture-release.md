# Benchmark v2 Fixture Release Receipt

**Date:** 2026-07-10
**Verdict:** SHIPPING the evaluator-release boundary only. Vidux value remains
**unproven**.

## What Changed

The frozen source manifest no longer has a self-seal path. It stays in
`protocol_frozen_pending_fixture_seal` with no oracle commitment. An independent
evaluator now creates a separate release from a public fixture root, a separate
evaluator-only oracle root, and a compact evaluator index.

The release binds the exact source-manifest digest, hashes every public fixture,
and records only fixture paths, fixture hashes, and oracle commitments. It does
not record oracle paths or oracle bytes. Packet generation verifies the release
and public fixture hashes, then binds both the source-manifest digest and the
fixture-release digest into the arm packet and raw-row contract.

Final browser verification also exposed a cockpit regression: auto-refresh
could replace an anchored target before its 2.2-second comment-jump highlight
expired. Highlight state now follows the active comment target and expiry, so a
rendered replacement receives the remaining highlight without carrying it to a
different plan.

The same inspection found that Playwright's fixture `--root` did not isolate the
receipt corpus. The server fell back to a contributor-local corpus, so a
fixture run could render real local receipt rows. The server and launcher now
take an explicit receipt-corpus path, report it in `/api/health`, and refuse
reuse when that path differs. The E2E fixture passes an empty corpus and asserts
both the reported path and `loaded 0` before exercising receipt controls.

## Security Boundary

- Source manifests cannot self-seal or expose an oracle commitment.
- Fixture and oracle roots must be separate and non-overlapping.
- Relative path escape and symlink traversal are rejected.
- A changed fixture blocks readiness.
- Release output is immutable and cannot be written under either input root.
- The release command does not run a model, dispatch work, make a network
  request, copy an arm workspace, or score results.

## Mechanical Proof

| Check | Result |
|---|---|
| `python3 -m py_compile scripts/vidux-benchmark-v2.py tests/test_benchmark_v2.py` | PASS |
| `python3 -m unittest tests.test_benchmark_v2` | PASS: 20 tests |
| `npm run benchmark:v2:validate` | PASS: source protocol valid; transport intentionally requires an external release |
| `node --check browser/static/comment-markers.js && node --check browser/static/app.js` | PASS |
| iPhone auto-refresh comment-jump regression (`--repeat-each=3 --workers=1`) | PASS: 3/3, including a fresh jump after the original highlight deadline |
| `python3 -m unittest tests.test_browser_server` | PASS: 88 tests, 1 skipped |
| `python3 -m unittest tests.test_vidux_contracts` | PASS: 225 tests, 4 skipped |
| `npm run verify` | PASS: 8 JavaScript tests; 755 Python tests, 5 skipped; public-ready scan of 364 tracked files |
| `npm run test:e2e` | PASS: 102/102 browser journeys |
| `git diff --check` | PASS before final staging |

## Independent Review

- Fable advisor: the configured read-only command returned no adjudicable review
  because connector/auth bootstrap took precedence. No approval is claimed.
- Grok critique: bounded read-only review returned `NO_CONCRETE_BLOCKER` after
  independent symlink, path-escape, tamper, immutability, empty-corpus, and
  health-path probes. Its global bootstrap emitted unrelated warnings, and its
  later upload/bootstrap phase was stopped after the verdict; the result is
  corroboration, not approval.
- GLM advisory: returned no concrete blocker but explicitly had no filesystem
  or tool access. It is unavailable as evidence, not approval.
- Skillbox mount proof: relevant requested skill hashes were consistent; an
  unrelated global runtime doctor drift remains out of this repo's scope.
- Codex lead review: found and fixed a diagnostic gap where a source manifest
  that both self-sealed and exposed a commitment reported only the first fault,
  then found and fixed the hermetic receipt-corpus gap above.

## Follow-Up

An isolated iPhone receipt-lab smoke rendered an empty fixture corpus as
expected, but exposed header/model-badge crowding in the existing mobile
receipt lab. That is a visible 6.0.3 onboarding/UX follow-up, not a reason to
weaken the fixture-isolation or benchmark boundary claim.

## Non-Claim And Resume

No external fixture release has been created. No hidden oracle body, model run,
provider receipt, raw row, confidence interval, or decision receipt exists.
Verified net-win scenario classes remain **0**.

Next, an independent evaluator creates at least 12 fixtures for each frozen
scenario class, runs `seal-release`, verifies `readiness`, materializes the
same public fixture in each arm workspace, and only then runs the paired native
Claude and Codex baselines. The operating contract is
`benchmarks/v2/FIXTURE-RELEASE.md`.
