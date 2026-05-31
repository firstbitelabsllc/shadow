# P9 Splitter V2 Prework — Reading Guide

All-night prework (2026-05-30→31): map the splitter + last-mile code, audit the tests, build an adversarially-verified international/currency/tax/post-tax edge-case catalog, ground it in real receipts, and converge on a V2 design spec. **Zero production Swift touched — the dev is the talking and planning.**

## TL;DR

- **Root cause:** V1 is `total = itemSum + tax + tip + customExtras`, everything split proportional-by-gross, money hardcoded to cents. ~80% of issues fall out of that one shape.
- **V2 model (one line):** a receipt is a set of charges; each charge carries an apportionment `(mode, base)`; money is a currency-aware minor-unit type; proportion is the source of truth, equal-split is the default proportion.
- **Empirically proven:** all 48 corpus receipts multi-model extracted. **31% carry an extra beyond tax+tip.** Azure dropped serviceCharge on 9, tip on 14. 9 non-USD receipts; 5 with currency-disagreement.
- **The one decision that's YOURS:** comp/voucher apportionment (spread vs targeted). Everything else has a defensible default.

## The ONE open decision

**Comp / discount / voucher:** a table-wide promo should spread across everyone; a comp for one person's entrée should target just them. Default proposal (pending your ruling): spread proportionally unless the comp is tagged to a line item. Your call shapes the whole extra-taxonomy.

## Highest-leverage receipts to scan next (no ground truth yet)

0-decimal (JPY/KRW), 3-decimal (BHD/KWD fils), a real deposit/balance-due check, partially-inclusive tax (one inclusive + one exclusive line), an Italian coperto. Any one promotes a catalog P0 from reasoned to proven.

## Read in this order

1. **`2026-05-31-V2-DESIGN-SPEC.md`** — the capstone. Start here.
2. `2026-05-30-SYNTHESIS.md` — the root cause + the 4 silent-money P0s + the 5 apportionment calls.
3. `2026-05-31-empirical-findings.md` — the 31% + the real divergence counts (proof).
4. `2026-05-31-apportionment-decision-matrix.md` — the 5 product calls with worked dollar examples.
5. `2026-05-31-proportion-is-truth-contract.md` — your contract, verified vs shipped 1.8, + the keystone refinement (per-charge apportionment basis) + the EMPTY_ITEMS resolution.
6. `2026-05-30-edge-case-catalog.md` — the full 102 cases / 12 dimensions.
7. `2026-05-31-international-regimes.md` — 11 regimes (Quebec/GCC/India/Japan/SEA/AU-NZ…).
8. `2026-05-31-completeness-and-gaps.md` — what the 102 missed (tax-exempt P0) + 2nd-opinion corrections.
9. `2026-05-30-code-state-map.md` — how the splitter + reconciler actually work today (cited).
10. `2026-05-30-test-audit.md` — the money-math safety net + the 5 fix-first items.
11. `2026-05-31-test-specs.md` — given/when/then for the fix-first + each P0 (pre-dev).

## Status

Prework COMPLETE. Gated on: your comp/voucher ruling · more receipts (the scan gaps) · the 2.0 freeze lifting + a green `tuist test` baseline before any iOS code. See `../PLAN.md`.
