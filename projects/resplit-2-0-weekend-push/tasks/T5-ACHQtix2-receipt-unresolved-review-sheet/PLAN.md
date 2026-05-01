> Parent: ../../PLAN.md

# T5 — ACHQtix2: "Tappping doesn't dismisss and scroll to right place"

**Status:** [in_progress]
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

- [ ] Strip ASK-LEO-MANDATORY tag from existing investigation, cite c12/c13 precedent
- [ ] Cross-reference c12/c13 investigations to understand the dismiss-and-scroll handoff
- [ ] Likely fix: dismiss handler in `ReceiptUnresolvedReviewSheet` lines 557-589 + scroll target
- [ ] file:line of changes

## Tests (MT-5 required)

- [ ] XCTest UI test: tap dismiss → sheet dismissed AND scroll position lands on the expected row

## Visual proof

- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T5-ACHQtix2/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T5-ACHQtix2/after.jpg`

## Ship gate

Build clean, MT-5 green, visual proof (showing dismiss + correct scroll position), PR → review → merge.

## Cross-references

- Master: T5 row
- Mega: PR #541
- Existing investigation: `asc-ACHQtix2-unassigned-items-assign-blank-2026-04-29.md` (untracked WIP)
- Precedent siblings: `asc-c12-folder-receipt-tap-no-dismiss.md`, `asc-c13-tap-unassigned-scrolls-to-void.md`
