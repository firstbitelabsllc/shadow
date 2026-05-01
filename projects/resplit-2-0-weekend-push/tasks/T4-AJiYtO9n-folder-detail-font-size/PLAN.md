> Parent: ../../PLAN.md

# T4 — AJiYtO9n: "Why the fuck are numbers still not same font size"

**Status:** [completed] (MERGED 2026-05-01 via PR #550 squash `04f684ed`)
**Priority:** P0 (Saturday parallel-dispatchable)
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T14:55:00Z`
**Progress:** PR https://github.com/firstbitelabsllc/resplit-ios/pull/550 (`claude/T4-AJiYtO9n-folder-detail-font-size`) — Build Succeeded, MT-5 green, Graphite review fired, ready for merge.
**ASC ID:** AJiYtO9n
**DerivedData namespace:** `/tmp/resplit-dd-T4-16486`

## Reporter Says

> "Why the fuck are numbers still not same font size"

The word **STILL** indicates a prior fix exists. First step: find the prior fix.

## Surface

FolderDetail right-column amount column. Existing investigation: `.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` (Fix Spec NOT filled — claimer must fill).

## Investigation

`.cursor/plans/investigations/asc-AJiYtO9nX1Ty-folder-detail-right-column-chrome-2026-04-29.md` (existing, partial — H1/H2/H3 hypotheses listed, no Root Cause selected, no Fix Spec)

## Fix Spec (filled by claimer)

- [x] Read the existing investigation file's H1/H2/H3 hypotheses → all rejected; selected H_NEW (typography scale mismatch). Reporter circled the rollup-card-vs-receipt-row size cliff (22pt `moneyMedium` vs 16pt `bodyEmphasis`), not in-row pairing.
- [x] Found prior fix `8357cad1` (2026-04-10) for ASC `AOKFNAJoDp9` — promoted row amount labelEmphasis(14pt) → bodyEmphasis(16pt) to match merchant-name. Gap: never compared to rollup card / footer (both `moneyMedium` 22pt).
- [x] Promoted FolderReceiptRow + UnifiedReceiptRow folder-row amount Text from `bodyEmphasis.monospacedDigit()` → `moneyMedium.weight(.semibold).monospacedDigit()`; minimumScaleFactor 0.8 → 0.7.
- [x] Files changed:
  - `ResplitCore/UI/Folders/FolderReceiptRow.swift:152-176`
  - `ResplitCore/Receipt List Container/UnifiedReceiptRow.swift:177-204`

## Tests (MT-5 required)

- [x] `ResplitCoreTests/FolderReceiptRowAmountFontTests.swift` — 2 invariants:
  - `testMoneyMediumTokenRendersAt22Points` — pins design-system metric.
  - `testFolderReceiptRowAmountRendersAtMoneyMediumSize` — UIHostingController.sizeThatFits asserts row amount glyph height equals rollup-card participant-amount height (±0.5pt) AND is strictly larger than `bodyEmphasis` height. Catches both directions of regression.
  - Run result: 2/2 passed in 0.027s, 2026-05-01T10:19Z.

## Visual proof

§Visual Proof Merge Gate **esoteric-repro carve-out** applied. The regression is a typography-scale cliff that's pixel-exactly assertable via XCTest (the new test does this). Same-token fix means amounts cannot diverge by construction. ASC reporter screenshot at `docs/asc-screenshots/AJiYtO9nX1Ty9_Kc0MICO2o/01.jpg` shows the bug.

## Ship gate

Build clean, MT-5 green, visual proof, PR → review → merge.

## Cross-references

- Master: T4 row
- Mega: PR #541
- Existing investigation has 3 hypotheses (H1/H2/H3) — claimer commits to one in Fix Spec
