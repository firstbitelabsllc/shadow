> Parent: ../../PLAN.md

# T5 — ACHQtix2: "Tappping doesn't dismisss and scroll to right place"

**Status:** [in_review]
**PR:** https://github.com/firstbitelabsllc/resplit-ios/pull/551
**Priority:** P1 (Sunday morning, ~3hr)
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T15:25:00Z`
**ASC ID:** ACHQtix2
**DerivedData namespace:** `/tmp/resplit-dd-T5-${RANDOM}`

## Reporter Says

> "Tappping doesn't dismisss and scroll to right place"

## Surface

`ReceiptUnresolvedReviewSheet` at `ResplitCore/ReceiptDetail/ReceiptDetailView.swift:557-589`.

## Investigation

`.cursor/plans/investigations/asc-ACHQtix2-unassigned-items-assign-blank-2026-04-29.md`.

**⚠ ASK-LEO-MANDATORY tag is suspect.** Per master plan Decision Log 2026-05-01: siblings c12 (`asc-c12-folder-receipt-tap-no-dismiss.md`) and c13 (`asc-c13-tap-unassigned-scrolls-to-void.md`) describe the same nav bug class and were both shipped without Leo escalation. T5 follows the same precedent. **First step: STRIP the ASK-LEO-MANDATORY tag**, citing this PLAN row + the c12/c13 precedent in the investigation Decision Log.

## Fix Spec (filled by claimer)

- [x] Strip ASK-LEO-MANDATORY tag from existing investigation, cite c12/c13 precedent
- [x] Cross-reference c12/c13 investigations to understand the dismiss-and-scroll handoff
- [x] Bug 1 fix (dismiss): `.contentShape(Rectangle())` on `unresolvedItemButton` at `ReceiptDetailView.swift:622` — same pattern as PR #530
- [x] Bug 2 fix (scroll): `pendingJumpToItemAnchor = .center` instead of `nil` at `ReceiptDetailView.swift:176` — feeds c13's `effectiveScrollAnchor` near-end clamp

## Tests (MT-5 required)

- [x] 2 new MT-5 contrapositives in `ReceiptDetailViewModelTests.swift`:
  - `test_unresolvedReviewHandoff_lastItem_withCenterAnchor_returnsBottom` (fix shape)
  - `test_unresolvedReviewHandoff_lastItem_withNilAnchor_shortCircuits` (bug shape)
- [x] All 23 ReceiptDetailViewModelTests passing

## Visual proof

- [x] BEFORE: `docs/autobot-evidence/2026-05-01-T5-ACHQtix2/before.jpg` (ASC reporter screenshot)
- [x] AFTER: `docs/autobot-evidence/2026-05-01-T5-ACHQtix2/after.md` — esoteric-repro carve-out (hit-test fix invisible at pixel level, MT-5 contrapositive transcript + sibling c12/c13 precedent)

## Ship gate

- [x] Build clean (`tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-T5-...`)
- [x] MT-5 green (23/23 ReceiptDetailViewModelTests including 2 new T5 contrapositives)
- [x] Visual proof (BEFORE + esoteric-repro AFTER with code reasoning)
- [x] PR #551 drafted + Graphite review triggered
- [ ] Greptile/Graphite verdict, threads resolved, merge

## Cross-references

- Master: T5 row
- Mega: PR #541
- Existing investigation: `asc-ACHQtix2-unassigned-items-assign-blank-2026-04-29.md` (untracked WIP)
- Precedent siblings: `asc-c12-folder-receipt-tap-no-dismiss.md`, `asc-c13-tap-unassigned-scrolls-to-void.md`
