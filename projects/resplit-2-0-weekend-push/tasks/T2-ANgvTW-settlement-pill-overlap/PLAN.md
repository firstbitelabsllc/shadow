> Parent: ../../PLAN.md

# T2 — ANgvTW: "Still overlapping" (settlement pill / participant chip)

**Status:** [in_progress]
**Priority:** P0 (Saturday parallel-dispatchable)
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T13:36:30Z`
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

- [ ] **FIRST:** `git log --all --oneline | grep -iE 'pill|chip|overlap|settlement'` to find prior fix commit
- [ ] Identify why prior fix didn't stick (race condition? wrong surface? incomplete?)
- [ ] Write fix that addresses root cause, not just symptoms
- [ ] file:line of the change

## Tests (MT-5 required, ESPECIALLY this one)

- [ ] XCTest assertion that pill/chip do NOT overlap at the geometry where reporter saw it
- [ ] Document why this assertion would have caught the prior fix's incompleteness

## Visual proof

- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T2-ANgvTW/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T2-ANgvTW/after.jpg`

## Ship gate

- Build clean, MT-5 green, visual proof committed, PR draft → @graphite review → ready → auto-merge

## Cross-references

- Master plan: T2 row
- Multi-platform mega plan: PR #541
- Likely sibling investigation: `asc-settlement-pill-overlap.md` (stub being created)
