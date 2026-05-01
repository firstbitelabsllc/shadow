> Parent: ../../PLAN.md

# T4 — AJiYtO9n: "Why the fuck are numbers still not same font size"

**Status:** [pending]
**Priority:** P0 (Saturday parallel-dispatchable)
**Claim:** `claimed_by: <agent_id>` `claimed_at: <iso>`
**ASC ID:** AJiYtO9n
**DerivedData namespace:** `/tmp/resplit-dd-T4-${RANDOM}`

## Reporter Says

> "Why the fuck are numbers still not same font size"

The word **STILL** indicates a prior fix exists. First step: find the prior fix.

## Surface

FolderDetail right-column amount column. Existing investigation: `.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` (Fix Spec NOT filled — claimer must fill).

## Investigation

`.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` (existing, partial — H1/H2/H3 hypotheses listed, no Root Cause selected, no Fix Spec)

## Fix Spec (filled by claimer)

- [ ] Read the existing investigation file's H1/H2/H3 hypotheses
- [ ] Pick the one supported by evidence (likely missing `.monospacedDigit()` modifier OR `Font.fixed-size` mismatch on amount strings)
- [ ] Audit ALL amount-rendering Text views in FolderDetail right-column for the same modifier
- [ ] file:line of changes

## Tests (MT-5 required)

- [ ] XCTest assertion: amount Text renders with consistent `.font` modifier across all rows

## Visual proof

- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T4-AJiYtO9n/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T4-AJiYtO9n/after.jpg`

## Ship gate

Build clean, MT-5 green, visual proof, PR → review → merge.

## Cross-references

- Master: T4 row
- Mega: PR #541
- Existing investigation has 3 hypotheses (H1/H2/H3) — claimer commits to one in Fix Spec
