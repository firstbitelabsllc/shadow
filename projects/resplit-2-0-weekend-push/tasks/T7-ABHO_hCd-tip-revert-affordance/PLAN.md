> Parent: ../../PLAN.md

# T7 — ABHO_hCd: Tip revert affordance

**Status:** [in_progress]
**Priority:** P1 Sunday
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T15:55:00Z`
**ASC ID:** ABHO_hCd
**DerivedData namespace:** `/tmp/resplit-dd-T7-${RANDOM}`

## Reporter Says
> "Why does tip have a revert to scanned UX as well?"

## Surface guess
`ReceiptSummaryViewModel.resetSummaryAmount()` for tip row (cite: line 1136 of master plan, feature shipped in `165cb2bf` build 1084).

## Investigation
See `.cursor/plans/investigations/asc-ABHO_hCd-tip-revert-affordance-2026-05-01.md`.

## Fix Spec (filled by claimer)
- [ ] Step 1
- [ ] Step 2
- [ ] file:line

## Tests (MT-5 required)
- [ ] XCTest assertion

## Visual proof
- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T7-ABHO_hCd/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T7-ABHO_hCd/after.jpg`

## Ship gate
Build clean, MT-5 green, visual proof, PR → review → merge.

## Cross-references
- Master: T7 row
- Mega: PR #541
