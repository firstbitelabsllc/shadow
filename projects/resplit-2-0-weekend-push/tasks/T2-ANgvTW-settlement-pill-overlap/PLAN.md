> Parent: ../../PLAN.md

# T2 — ANgvTW: "Still overlapping" (settlement pill / participant chip)

**Status:** [in_review]
**Priority:** P0 (Saturday parallel-dispatchable)
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T13:36:30Z`
**PR:** [#548](https://github.com/firstbitelabsllc/resplit-ios/pull/548) — opened 2026-05-01, all 9 MT-5 tests passing, awaiting Graphite review
**ASC ID:** ANgvTW
**DerivedData namespace:** `/tmp/resplit-dd-T2-${RANDOM}`
**Special concern:** Reporter said "STILL overlapping" → a prior fix exists and didn't work. **First step: find the prior fix commit** before writing new code.

## Reporter Says

> "Still overlapping"

## Surface guess

Settlement pill OR participant chip overlap. Sibling investigation: `.cursor/plans/investigations/asc-settlement-pill-overlap.md` (NOT YET CREATED — stub via sibling agent).

## Investigation

See `.cursor/plans/investigations/asc-ANgvTW-settlement-pill-still-overlapping-2026-05-01.md`.

## Fix Spec (filled by claimer)

- [x] **FIRST:** prior fix is PR #49 (`7780905d` — `fix: resolve settlement pill overlap with layout priority`), merged 2026-04-13. Subsequent hardening: `1403b047`, `a0fc511b`, `3b57cbab`, `b53f9b3e`.
- [x] Identify why prior fix didn't stick: H1 (modifier-removal regression) **falsified** — all 5 PR #49 modifiers verified present in trunk. H2 confirmed: `.fixedSize(horizontal: true)` on amount refuses ALL compression, so under FX-amount/locale/narrow-width/Dynamic-Type stress the pill visually overlaps the amount.
- [x] Fix applied: extracted `transactionRow` to `internal struct TripSettlementTransactionRow` (testability) + added `.minimumScaleFactor(0.85) + .allowsTightening(true)` to amount, names, and pill text on both `TripSettlementSheet` and `CompletedSettlementFooter` surfaces.
- [x] Files changed:
  - `ResplitCore/UI/Folders/TripSettlementTransactionRow.swift` (new, 88 lines)
  - `ResplitCore/UI/Folders/TripSettlementSheet.swift:526-551` — `transactionRow` now wraps the extracted view
  - `ResplitCore/UI/Folders/FolderDetailView.swift:1462-1483` — same modifiers added to `CompletedSettlementFooter` row

## Tests (MT-5 required, ESPECIALLY this one)

- [x] `ResplitCoreTests/TripSettlementTransactionRowLayoutTests.swift` — 9 contrapositive tests via `UIHostingController.sizeThatFits()`, one per stress dimension (long English, FX `¥1,234,567`, MYR `RM 12,345.67` @ iPhone SE, German compound, CJK chain, narrow width, compound stress, Accessibility 3, Accessibility 5)
- [x] All 9 pass with the fix applied (verified 2026-05-01 22:1X EDT). Tests 2-5 and 7-8 would fail without the gap fix because `.fixedSize(horizontal: true)` alone refuses compression — that's exactly the contrapositive PR #49's manual visual check could not codify.

## Visual proof

- [x] Esoteric-repro carve-out used (per CLAUDE.md §Visual Proof Merge Gate). The bug surface is combinatorial (4 stress dimensions x device variants); pixel-exact `UIHostingController.sizeThatFits` measurements cover the entire space deterministically. AFTER proof: [`docs/autobot-evidence/2026-05-01-T2-ANgvTW/before-after-test-transcript.md`](../../../resplit-ios/docs/autobot-evidence/2026-05-01-T2-ANgvTW/before-after-test-transcript.md)

## Ship gate

- Build clean, MT-5 green, visual proof committed, PR draft → @graphite review → ready → auto-merge

## Cross-references

- Master plan: T2 row
- Multi-platform mega plan: PR #541
- Likely sibling investigation: `asc-settlement-pill-overlap.md` (stub being created)
