> Parent: ../../PLAN.md

# T3 — AO4j25: Corner radius bug

**Status:** [in_progress]
**Priority:** P0 Saturday
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T14:25:00Z`
**ASC ID:** AO4j25
**DerivedData namespace:** `/tmp/resplit-dd-T3-${RANDOM}`

## Reporter Says
> "Corner radius bug"

## Surface guess
Single-token corner-radius mismatch — likely a `.cornerRadius()` or `.clipShape(RoundedRectangle(cornerRadius:))` with wrong value. Grep `cornerRadius` in `ResplitCore/UI/Components/`.

## Investigation
See `.cursor/plans/investigations/asc-AO4j25-corner-radius-bug-2026-05-01.md`.

## Fix Spec (filled by claimer)
- [ ] Step 1
- [ ] Step 2
- [ ] file:line

## Tests (MT-5 required)
- [ ] XCTest assertion

## Visual proof
- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T3-AO4j25/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T3-AO4j25/after.jpg`

## Ship gate
Build clean, MT-5 green, visual proof, PR → review → merge.

## Cross-references
- Master: T3 row
- Mega: PR #541
