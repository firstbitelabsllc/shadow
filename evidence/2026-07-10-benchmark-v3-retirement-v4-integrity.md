# Benchmark v3 Retirement and v4 Integrity Preflight

Date: 2026-07-10

Verdict: **SHIPPING** for the v3 retirement and v4 integrity-preflight slice. **UNPROVEN** for Vidux product value. No provider run occurred, provider spend remains unauthorized, and verified net-win scenario classes remain 0.

## Why v3 Was Retired

Four adversarial falsifiers could change the benchmark outcome rather than merely improve implementation quality:

1. Readiness accepted arbitrary fixture JSON plus digest-shaped references without proving the fixture bytes belonged to the release.
2. Synthetic evaluator rows could reach a claim-eligible verified-win decision.
3. Retry usage counted against budgets while only the terminal attempt reached decision statistics.
4. A crash-torn final journal row could permanently wedge the protocol with no bounded authenticated recovery path.

V3 therefore remains available only as an inspectable negative artifact. `validate` proves its frozen identity, `readiness` returns the retirement gate, and every schedule, packet, journal, adjudication, and decision command refuses to run.

## V4 Integrity Boundary

`vidux-cockpit-v4` has protocol digest `dfbe8444fc60580615f75eeb3749383c13e2d8e25f055acf272e684269976edb` and status `draft_integrity_preflight`.

- The manifest requires exactly 52 fixtures, bounded task prompts, scenario cross-checks, content-addressed workspace sources, and byte-verified flat artifact storage.
- Provider profiles resolve and bind the runner binary, arguments, permission mode, tool policy, base prompt, system prompt, and developer prompt artifacts.
- Evaluator preregistration uses an OpenSSH Ed25519 `sshsig` under namespace `vidux-benchmark-v4`; the signature binds the canonical release core.
- Symlinks, hard links, non-regular files, digest mismatches, release tampering, registration substitution, and package-private runtime/evaluator files fail closed.
- Synthetic evidence is authenticated for machinery tests but permanently claim-ineligible. Claim eligibility also revalidates the manifest and status, so a forged permissive status cannot bypass the current non-runnable state.
- Retry accounting is cumulative across attempts in both budgets and eventual decision statistics.
- Journal recovery accepts only an unterminated final fragment after a valid committed prefix, holds an exclusive sidecar lock, writes a content-addressed recovery event, atomically replaces the file, and leaves terminated corruption fatal.
- Ambiguous provider dispatch is frozen to receipt reconciliation with no automatic reinvocation.
- V4 intentionally exposes no schedule, provider, adjudication, or decision command.

## Threat Model

Protected assets are benchmark-claim integrity, external-evaluator provenance, provider-profile identity, fixture/workspace bytes, cumulative cost evidence, and the append-only journal.

The tested failure and attacker paths are digest-shaped fake references, synthetic evidence presented as real, evaluator-key substitution, release-signature tampering, symlink/hard-link aliases, crash-partial appends, forged status state, retry undercounting, and ambiguous dispatch duplication. The controls above fail closed at release validation, filesystem resolution, claim eligibility, recovery, and package construction.

Residual gates are explicit: no evaluator is registered, no signed external release exists, evaluator result authentication and cumulative runner receipts are not implemented, provider dispatch is absent, and no pilot has run. Those are readiness failures, not product-test failures.

## Mechanical Proof

- `python3 -m unittest -v tests.test_benchmark_v3 tests.test_benchmark_v4`: PASS, 43 tests.
- `python3 -m unittest -v tests.test_benchmark_v4`: PASS, 11 tests after the forged-status regression.
- `npm run verify`: PASS, 15 JavaScript tests and 889 Python tests with 5 skipped; public-ready scan PASS.
- `npm run test:e2e`: PASS, 129 Playwright journeys across Chromium desktop, desktop dark, and iPhone portrait.
- `npm run docs:build`: PASS.
- `npm audit --audit-level=high`: PASS, 0 vulnerabilities.
- `python3 scripts/vidux-benchmark-v3.py validate`: PASS with `runnable: false`; `readiness`: expected exit 2 with the retirement gate.
- `python3 scripts/vidux-benchmark-v4.py validate`: PASS with `runnable: false`; `readiness`: expected exit 2 with four explicit spend gates and `claim_eligible: false`.
- `python3 scripts/vidux-release-package.py --json`: PASS, reproducible 201-file package, 600,428 packed bytes, 2,031,606 unpacked bytes, SHA-256 `77dcda515ee80a73edb1743e633dd43f0a25c8d88a1b70360d7edd3a83a3602c`.
- `git diff --check`: PASS.

## Independent Review

- Two bounded independent reviews found the crash-torn-tail, synthetic-claim, and retry-statistics blockers. They were accepted as concrete and drove the v3 retirement/v4 design.
- GLM independently recomputed the v4 manifest digest, ran 52 focused pytest cases plus 10 subtests, probed deep JSON handling, and returned `NO_BLOCKER_FOUND`.
- Grok identified a falsifiable forged-status claim-eligibility path; Codex reproduced and fixed it with a regression. Grok's follow-up verifier exceeded its turn bound and returned no terminal verdict, so the sidecar is recorded unavailable rather than passing.
- Fable consumed a bounded `$2.305553` review attempt but returned no terminal decision; it is recorded unavailable rather than approval.
- Three additional reviewers returned no usable result after safety-classifier exits. Their absence did not waive any mechanical gate.

Codex adjudication: no concrete unfixed blocker remains in the v3 retirement or v4 integrity-preflight slice. This does not authorize a benchmark run or a Vidux superiority claim.
