# Public Authority Hygiene Receipt

Date: 2026-07-10

## Verdict

PASS. Vidux public authority now scans current plan doctrine without erasing legitimate append-only history, and private host-routing assignments fail the release boundary. This is release hygiene, not benchmark evidence: verified net-win classes remain 0.

## Concrete Red State

1. A retired-doctrine phrase inserted in a live `PLAN.md` section passed because the entire file was classified as historical.
2. A private machine-routing assignment in a public document passed because no bounded ownership pattern existed.
3. The current root plan and a historical queue still encoded stale host-specific project ownership.

The first two regression tests failed before the implementation and passed afterward.

## Implementation

- `scripts/vidux-public-ready-grep-gate.py` now treats only Decision, Decisions, Drift Log, and Progress sections as append-only plan history.
- ATX headings, setext headings, nested historical headings, and fenced code blocks have explicit parsing coverage.
- Privacy patterns still run inside append-only history.
- A bounded bidirectional detector rejects private machine ownership, assignment, and no-touch routing while allowing benign phrases such as a machine having its own cache.
- `PLAN.md` now delegates downstream work to each project's current authority instead of publishing local host assignments.
- The historical multi-agent queue is anonymized without changing its recorded project boundary.

## Independent Review

Fable reviewed the bounded diff in read-only plan mode and returned three concrete blockers:

1. Reversed and adjectival ownership forms were not covered.
2. Heading-shaped text inside fenced code could alter section state.
3. A broad ownership matcher could reject benign uses of `own`.

Each objection was reproduced as a regression test and fixed. Fable also questioned terminal blocked rows; that objection was rejected because Vidux's state machine defines `blocked` as terminal and the rows now say they are closed rather than resumable.

## Mechanical Proof

```text
python3 -m unittest tests.test_public_ready_grep_gate
PASS - 29 tests

npm run verify
PASS - 15 JavaScript tests
PASS - 903 Python tests, 5 skipped
PASS - 417 tracked files through the public-ready scan

python3 scripts/vidux-public-ready-grep-gate.py --tracked-only --json
PASS - 417 tracked files, 0 matches

npm run docs:build
PASS

npm audit --audit-level=high
PASS - 0 vulnerabilities

npm run release:verify
PASS - version 2.23.0
PASS - 201 files, 2,092,483 unpacked bytes
PASS - sha256 2469569dc3de3d3c465ff485135d4f3c98038aa8e3ab42eac2b5353b5a3bb1bc

git diff --cached --check
PASS
```

No browser code changed. The prior 129/129 cross-browser result remains the current UI proof and was deliberately not rerun for this scanner-and-authority-only slice.

## Scope Boundary

The intentionally untracked `.opencode/`, `evaluations/`, final-verification screenshot, and local final-verification receipt were not staged, deleted, normalized, or used as release proof.
