# Truthful Work Queue and Benchmark v2 Retirement

Date: 2026-07-10

Cycle verdict: SHIPPING locally. The code-bearing slice, staged release
candidate, mounted runtime, and public package boundary are green. This does
not change the product-superiority verdict, which remains unproven.

## Product Slice

Simple mode now shows three bounded cross-project queues: Next, Resume, and
Needs attention. Pending P0/P1 tasks enter Next. Task order is severity, status,
owning-plan priority, plan freshness, plan mtime, repository, then source line.
Rows preserve owner, blocker, validation, and proof metadata instead of
flattening every task into an undifferentiated label.

The server computes an exact selected-plan-excluded `simple_total` and up to
eight `simple_items` before applying the larger API category cap. A large
selected plan therefore cannot hide lower-ranked projects or produce a false
denominator. The full dashboard remains available through View all.

Related truth fixes in the same slice:

- Terminal Operator Briefs cannot claim the current goal.
- Fresh current-goal claims outrank stale claims, with deferred counts exposed.
- Outcome scorecards expose shown and total row counts instead of silently
  stopping at a parser limit.
- Ledger responses say `partial` when the older tail was not searched.
- Dated progress bullets are selected newest-first regardless of file order.

## Benchmark Decision

Five independent read-only audits found that benchmark v2 had no released
fixture corpus, provider-matched executor matrix, deterministic adjudicator,
complete schedule binding, hard run budgets, or exactly-once journal. The
legacy evaluation corpus also has unsafe path/prompt assumptions and is not a
replacement runner.

A bounded Fable advisor call selected the fail-closed option: v2 must be
declared non-runnable, and outcome-determining corrections must use a new
protocol ID. The call used `claude-fable-5`, ran for about 309 seconds, and cost
USD 2.9701585. Codex then preserved v2's frozen packet semantics as historical
evidence while adding a machine-readable administrative status and CLI refusal
gate for fixture sealing, packet issuance, and scoring.

`python3 scripts/vidux-benchmark-v2.py validate` reports the archived manifest
and status as structurally valid while `transport_ready` remains false.
`readiness` exits 2, and transport/scoring commands exit 1 with the new-protocol
gate. No fixture release or raw rows exist. Verified net-win scenario classes
remain 0; this receipt makes no superiority claim.

## Live Runtime

The updated server is mounted at `http://127.0.0.1:7192` from the staged
`browser/server.py`.

Live `/api/health` returned `ok: true`. Live `/api/plans` scanned 309 plans in
26 projects and reported exact task categories before the Simple-mode cap:

| Queue | Total | Simple shown |
|---|---:|---:|
| Next | 30 | 8 |
| Resume | 98 | 8 |
| Needs attention | 165 | 8 |

Inspected receipts:

> Round-11 privacy fix: the three screenshots for this receipt were captured
> against the maintainer's real work queue, so their rows rendered live task
> titles, repository names, and a `~/Library/LaunchAgents/...` path fragment
> from several private business projects — a leak class the text grep-gate
> cannot see (PNG pixels). The three files were removed. The truthful-queue
> behavior below is proven by the counts table above and its regression tests;
> the same queue UI is shown against synthetic fixture data in
> `2026-07-10-multi-project-onboarding-clean.png`.

The first mobile capture exposed vertically stacked repository names. The final
CSS keeps repository labels to a single-line ellipsis while preserving two-line
task labels. The focused 30-issue Playwright case passes on desktop Chromium,
iPad portrait, and iPhone portrait, including a forced 320px overflow check and
the View all route.

## Focused Proof

- `python3 -m py_compile browser/server.py scripts/vidux-benchmark-v2.py scripts/vidux-release-package.py` - PASS
- `python3 -m unittest tests.test_benchmark_v2` - PASS, 21 tests
- `python3 -m unittest tests.test_browser_server` - PASS, 136 tests, 1 skipped
- `npm run test:js` - PASS, 15 tests
- targeted 30-issue Playwright smoke - PASS, 3 projects
- `git diff --check` - PASS

## Final Release Proof

- `npm run verify` - PASS, 15 JavaScript tests and 844 Python tests, 5 skipped.
  An earlier public scan found one private absolute path in this receipt; that
  path was removed before the final clean run.
- `python3 -m unittest tests.test_vidux_contracts` - PASS, 234 tests, 4 skipped
- `npm run test:e2e` - PASS, 129/129 cross-browser journeys
- `npm run docs:build` - PASS
- `npm audit --audit-level=high` - PASS, 0 vulnerabilities
- `npm run public-ready:grep` - PASS, 402 staged/tracked files scanned
- `python3 scripts/vidux-release-package.py --json` - PASS, reproducible
  192-file package, SHA-256
  `e3b027fafdda920d199c4b73e4340eba08205f7bd1370fb47f9d40b549e047f7`
- `python3 scripts/vidux-benchmark-v2.py validate` - PASS with
  `transport_ready: false` and `protocol_status: retired_non_runnable`
- `python3 scripts/vidux-benchmark-v2.py readiness` - expected exit 2 with the
  non-runnable and missing-release gates
- live `/api/health`, `/api/plans`, desktop, and mobile smoke - PASS

## Independent Checks

GLM independently reproduced the non-runnable gate and passed 21 benchmark
tests, 22 focused dashboard tests, and 3 work-queue JavaScript tests. It did not
return a bounded final verdict before termination, so it is recorded as
non-converged rather than passing.

Grok did not return a verdict because unrelated local hooks and a missing Figma
desktop MCP endpoint repeatedly failed during startup. It is recorded as
sidecar unavailable, not as a Vidux failure or pass.

Codex self-review found and fixed three concrete issues before closeout: a
retroactive change to frozen v2 packet semantics, an incorrect Simple-mode
denominator under the API cap, and unreadable wrapped repository names.

## Scope Boundary

The local `.opencode/` state, the untracked `evaluations/` corpus, and the July
7 local verification artifacts remain intentionally unstaged and unmodified.
