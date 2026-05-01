> Parent: ../../PLAN.md

# T3 — AO4j25: Corner radius bug

**Status:** [completed] (MERGED 2026-05-01 via PR #549 squash `b24f72da`)
**Priority:** P0 Saturday
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T14:25:00Z`
**ASC ID:** AO4j25
**DerivedData namespace:** `/tmp/resplit-dd-T3-${RANDOM}`
**PR:** https://github.com/firstbitelabsllc/resplit-ios/pull/549

## Reporter Says
> "Corner radius bug"

Reporter screenshot at `docs/asc-screenshots/AO4j25U-7o7PlCeys5Cp9X0/01.jpg` — circled the TOP-LEFT corner of the **Settlement hero card** (TripSettlementSheet) with an arrow pointing INSIDE the rounded stroke border.

## Surface
**`ResplitCore/UI/Folders/TripSettlementSheet.swift` `settlementHeroCard` (lines 287–322).** Inner gradient overlay (`.background(RoundedRectangle.fill.overlay { LinearGradient })`) renders with hard SQUARE corners while the outer stroke renders with the rounded shape — visible "double-corner" / "rim-leak" leak. Missing `.clipShape(RoundedRectangle)` between the background and the stroke overlay.

## Investigation
See `.cursor/plans/investigations/asc-AO4j25-corner-radius-bug-2026-05-01.md` (filled).

## Fix Spec
- [x] Insert `.clipShape(RoundedRectangle(cornerRadius: designSystem.radii.lg, style: .continuous))` at TripSettlementSheet.swift:316 between the `.background` closure and the stroke `.overlay`
- [x] 1 line added — production code change

## Tests (MT-5 required)
- [x] `ResplitCoreTests/TripSettlementHeroCardCornerRadiusTests.swift` — 2 tests, both pass
  - Positive: with .clipShape, top-left corner pixel is near-white (clipped)
  - Negative contrapositive: without .clipShape, top-left corner pixel is NOT near-white (leaks gradient) — proves the positive test would catch a regression

## Visual proof
- [x] BEFORE: `docs/autobot-evidence/2026-05-01-T3-AO4j25/before-asc-reporter-screenshot.jpg` (ASC reporter screenshot, copied)
- [x] AFTER (esoteric-repro carve-out): `docs/autobot-evidence/2026-05-01-T3-AO4j25/before-after-test-transcript.md` — pixel-sample MT-5 contrapositive proves the fix mathematically. Same carve-out pattern T1 PR #547 + T2 PR #548 used.

## Ship gate
- [x] Build clean (`tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-T3-1194`)
- [x] MT-5 green (2/2)
- [x] Visual proof (BEFORE = reporter screenshot; AFTER = pixel-sample test transcript)
- [x] PR #549 opened, draft, Graphite review fired
- [ ] Review threads resolved → merge

## Progress
- 2026-05-01 — T3 shipped: PR #549 (`fix(settlement-sheet): clip inner gradient to rounded shape`). Identified surface from reporter screenshot (downloaded via `ruby scripts/asc_beta_feedback.rb download-screenshots --id AO4j25U-7o7PlCeys5Cp9X0`). Fix is 1 line. MT-5 contrapositive pair (positive + negative) proves the assertion catches regressions.

## Cross-references
- Master: T3 row
- Mega: PR #541
- PR: #549
