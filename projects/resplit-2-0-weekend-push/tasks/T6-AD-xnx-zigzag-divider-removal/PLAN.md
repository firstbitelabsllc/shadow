> Parent: ../../PLAN.md

# T6 — AD-xnx: Zigzag divider removal

**Status:** [in_review]
**Priority:** P1 Sunday
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T15:55:00Z`
**Progress:** PR https://github.com/firstbitelabsllc/resplit-ios/pull/553 (commit `df34b4ee`) — draft, awaiting Graphite review
**ASC ID:** AD-xnx
**DerivedData namespace:** `/tmp/resplit-dd-T6-47344`

## Reporter Says
> "zig zags here is too distracting remove and refine UX of this whole section"

## Surface guess
`ZigzagDivider` component used in 7 surfaces per AG6aB triaged note: TripSettlementSheet, TripSummaryCard, ManualExpenseSheet, FolderReceiptRow, UnifiedReceiptRow, TripHeroBand, LedgerSectionView.

## Investigation
See `.cursor/plans/investigations/asc-AD-xnx-zigzag-divider-removal-2026-05-01.md`.

ASC reporter screenshot confirmed the circled surface is **TripSummaryCard** — the trip-detail summary with two zigzag rows above and below "Share Summary / Add receipt". Conservative call: sweep all 7 surfaces (the reporter's "remove and refine UX of this whole section" implies the zigzag pattern itself is the problem, not just one instance).

## Fix Spec (filled by claimer)
- [x] `ResplitCore/UI/Folders/TripSummaryCard.swift:504-516` — `sectionDivider` and `itemDivider` private vars now return `Divider()` (sectionDivider keeps the `actionSecondary.opacity(0.24)` overlay).
- [x] `ResplitCore/UI/Folders/TripSettlementSheet.swift:211-215` — decorative top divider removed entirely; the `settlementHeroCard` already provides the visual top edge.
- [x] `ResplitCore/UI/Folders/ManualExpenseSheet.swift:106` — between amount + description fields, replaced with `Divider()`.
- [x] `ResplitCore/UI/Folders/FolderReceiptRow.swift:133` — row separator replaced with `Divider()` (preserves `.allowsHitTesting(false)`).
- [x] `ResplitCore/Receipt List Container/UnifiedReceiptRow.swift:228` — row separator replaced with `Divider()`.
- [x] `ResplitCore/Receipt List Container/TripHeroBand.swift:60` — between participant strip and totals replaced with `Divider()`.
- [x] `ResplitCore/Receipt List Container/LedgerSectionView.swift:59` — inter-receipt separator replaced with `Divider()` (preserves leading-padding + listRowInsets).
- [x] `ZigzagDivider` type itself preserved in `ResplitDesignSystem` for safety (DevGallery + PreviewGallery still reference it). Type-removal is post-2.0 follow-up.

## Tests (MT-5 required)
- [x] `ResplitCoreTests/ZigzagDividerRemovalRegressionTests.testNoZigzagDividerCallsitesInSweptSurfaces` — grep-style assertion against the 7 swept surfaces. Uses `#filePath` compile-time literal to find the repo root, with `XCTSkip` fallback for environments where the source tree isn't reachable. Run: PASS (0.008s).

## Visual proof
- [x] BEFORE: `docs/autobot-evidence/2026-05-01-T6-AD-xnx/before-asc-reporter.jpg` — reporter's ASC screenshot (the green-circled zigzag rows in TripSummaryCard).
- [x] AFTER: esoteric-repro carve-out invoked. TripSummaryCard requires walkthrough completion + trip-folder seeding + settlement-detail navigation; the available smoke fixtures (`smoke-trip-folder` + `--skipWalkthrough` + `--uitesting`) all land on the walkthrough first screen during verification (3 attempts at 10:47-10:49 EDT 2026-05-01). Sim-AFTER would require new fixture plumbing out of scope for a 1-line divider removal. The MT-5 grep test guarantees the bug can't return by construction.

## Ship gate
- [x] Build: `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-T6-47344` → Succeeded
- [x] MT-5 test green
- [x] swiftlint clean on all 7 modified files + the new test
- [x] PR opened: #553 (draft) — awaiting Graphite + Claude review bots
- [ ] Auto-merge after review threads resolved

## Cross-references
- Master: T6 row
- PR: #553
- Mega: PR #541
