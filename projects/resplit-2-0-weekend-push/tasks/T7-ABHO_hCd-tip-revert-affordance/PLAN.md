> Parent: ../../PLAN.md

# T7 — ABHO_hCd: Tip revert affordance

**Status:** [completed] (MERGED 2026-05-01 via PR #552 squash `476b3905`)
**Priority:** P1 Sunday
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T15:55:00Z`
**Progress:** PR #552 — https://github.com/firstbitelabsllc/resplit-ios/pull/552
**ASC ID:** ABHO_hCd
**DerivedData namespace:** `/tmp/resplit-dd-T7-${RANDOM}`

## Reporter Says
> "Why does tip have a revert to scanned UX as well?"

## Surface guess
`ReceiptSummaryViewModel.resetSummaryAmount()` for tip row (cite: line 1136 of master plan, feature shipped in `165cb2bf` build 1084).

## Investigation
See `.cursor/plans/investigations/asc-ABHO_hCd-tip-revert-affordance-2026-05-01.md`.

## Fix Spec (filled by claimer)
- [x] `ResplitCore/ReceiptDetail/Summary/ReceiptSummaryDetailState.swift:453` — gate `resetToScanned` action emission on `context.kind != .tip`
- [x] No changes to `ReceiptSummaryViewModel.resetSummaryAmount()` (the function stays — just no longer reachable for tip rows)
- [x] `ReceiptSummaryDetailContext.Kind.tip` already exists at `ReceiptSummaryDetailSheet.swift:6-12` — no model plumbing required

## Tests (MT-5 required)
- [x] Modified `testEditedCustomTipUsesPencilDisclosureAndShowsDifferenceFromScan` — was asserting the bug
- [x] MT-5 contrapositive `testEditedTipWithScannedAmount_doesNotExposeResetToScanned` — uses exact reporter values ($5.00 scanned, $10.10 custom)
- [x] MT-5 positive `testEditedTotalWithScannedAmount_stillExposesResetToScanned` — prevents over-fix

## Visual proof
- [x] BEFORE: `docs/autobot-evidence/2026-05-01-T7-ABHO_hCd/before-asc-reporter.jpg` (ASC reporter screenshot)
- [x] AFTER: §Visual Proof esoteric-repro carve-out — 3-line guard, fix correct by construction, MT-5 contrapositive uses exact reporter values

## Ship gate
- [x] `tuist generate --no-open` clean
- [x] `tuist xcodebuild build -scheme 'Resplit Debug'` Build Succeeded
- [x] All 3 ABHO_hCd tests green (pre-existing `testAllFlagsReturnsDefinedFlags` failure unrelated, on origin/main)
- [x] PR #552 draft + Graphite review fired
- [ ] Review threads resolved → ready → merge

## Cross-references
- Master: T7 row
- Mega: PR #541
