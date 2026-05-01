> Parent: ../../PLAN.md

# T6 — AD-xnx: Zigzag divider removal

**Status:** [pending]
**Priority:** P1 Sunday
**Claim:** `claimed_by: <agent_id>` `claimed_at: <iso>`
**ASC ID:** AD-xnx
**DerivedData namespace:** `/tmp/resplit-dd-T6-${RANDOM}`

## Reporter Says
> "zig zags here is too distracting remove and refine UX of this whole section"

## Surface guess
`ZigzagDivider` component used in 7 surfaces per AG6aB triaged note: TripSettlementSheet, TripSummaryCard, ManualExpenseSheet, FolderReceiptRow, UnifiedReceiptRow, TripHeroBand, LedgerSectionView.

## Investigation
See `.cursor/plans/investigations/asc-AD-xnx-zigzag-divider-removal-2026-05-01.md`.

## Fix Spec (filled by claimer)
- [ ] Step 1
- [ ] Step 2
- [ ] file:line

## Tests (MT-5 required)
- [ ] XCTest assertion

## Visual proof
- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T6-AD-xnx/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T6-AD-xnx/after.jpg`

## Ship gate
Build clean, MT-5 green, visual proof, PR → review → merge.

## Cross-references
- Master: T6 row
- Mega: PR #541
