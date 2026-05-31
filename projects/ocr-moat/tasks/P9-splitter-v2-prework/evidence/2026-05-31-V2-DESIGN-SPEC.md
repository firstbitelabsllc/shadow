# Resplit Splitter V2 — Design Spec (capstone)

> Converges the P9 prework into THE proposed model. **Planning only — gated on the 2.0 freeze + Leo's sign-off; the iOS code change does not start until then.** Empirically grounded (see `2026-05-31-empirical-findings.md`: 31% of real receipts carry an extra beyond tax+tip). Open decision: comp/voucher apportionment (everything else has a default).

## The model in one line

> **A receipt is a set of charges; each charge carries an apportionment `(mode, base)`; money is a currency-aware minor-unit type; proportion is the source of truth and equal-split is the default proportion.**

V1 is `total = itemSum + tax + tip + customExtras`, everything proportional-by-gross, cents-hardcoded. V2 replaces *one global proportion applied to one additive total* with *per-charge apportionment over a currency-aware money type*. Four model changes + one safety gate.

---

## 1. Typed extra taxonomy — `{kind → (apportionment mode, base)}`

The keystone. Today every non-tax/tip charge is dropped (`OCRSnapshotBridge.swift:92-98`) or forced into `.custom` and spread proportional-by-gross. V2 gives each kind an explicit apportionment:

| Kind | Apportionment mode | Base | Evidence |
|---|---|---|---|
| line item | by-claim | the item | ✅ V1 |
| `tax` | proportional | **taxable base** (exempt items excluded) | NEW P0: exempt-item buyer overpays; needs per-item `isTaxable` |
| `tip` | proportional | consumption (subtotal share) | ✅ |
| `serviceCharge` (mandatory %) | proportional | consumption | 6 receipts; **not** a tip, **not** in tip base, **not** taxable |
| `cover` / minimum (flat) | **equal-per-head** | per seat | over-bills light eaters today; must bill proportion-0 diners |
| `fee` (admin/CC/delivery, flat) | equal-per-head OR proportional | per policy | 3 receipts |
| `fee` (item-attributed: CRV/corkage) | by-claim | the item's claimant | NEW: dropped/mis-spread today |
| `surcharge` (CC %, weekend %) | proportional | consumption | 2 receipts |
| `credit` / `deposit` (negative) | **context-gated** | payer OR table-wide | 3 receipts; see §below |
| `discount` / `comp` (negative) | **OPEN — Leo** | targeted OR table-wide | 2 receipts |
| `mandate` (health/tourism levy) | proportional | consumption | 1 receipt |

**Deposit/credit (context-gated):** credit-to-payer for restaurant/catering checks, table-wide (reduce everyone) for event/trip pools. The `BOUNDED_LOWER` refund branch (a credited payer going negative) is a **blocking** prerequisite, not a footnote.

**Comp/discount — THE open decision:** a table-wide promo should spread; a one-item comp should target that item. Default proposal (pending Leo): spread proportionally unless the comp is tagged to a specific line item. Leo rules.

---

## 2. Currency-aware money type

Stop hardcoding cents. `ReceiptSplitEngine.swift:73/78` does `×100/.../100`; `Reconciler.swift:34` uses `matchThreshold=0.01` USD; `V3ReceiptReconciler.swift:76` hardcodes `currencyCode:nil`.

- Money carries its **`currencyCode`** end-to-end (kill the `nil`); minor-unit scale derived from ISO 4217 (`0` JPY/KRW, `2` USD/EUR/MYR/AED/AUD, `3` BHD/KWD/OMR).
- Rounding + remainder distribution operate in **minor units**, not hardcoded cents → no fractional yen, no destroyed fils.
- `matchThreshold` / `warnThreshold` **scale to minor units** (1 minor unit, not $0.01) → no false reconciliation chips on no-decimal receipts, not blind to fils errors.
- **Currency resolution:** require CountryRegion or prompt for ambiguous symbols; never silently pick CNY for `¥` or USD for a bare `$` (empirically: 5 receipts have provider currency-disagreement, 9 are non-USD).

---

## 3. Inclusive-tax flag + `balance_due`

`ReceiptTotalCalculator.swift:19` adds tax unconditionally → inclusive GST/VAT double-counts.

- **`taxInclusive: Bool`** per tax line — an inclusive tax is NOT re-added; it informs display, not the additive sum.
- **`balanceDue` distinct from `total`** — when a deposit/prepayment is applied, split the **balance due**, not the gross total. (P8 story: $2180.26 total vs $1918.26 due.)
- The percent-tip base must use the **pre-tax** subtotal for inclusive receipts (`SummaryItemCalculator.swift:21` currently double-counts).

---

## 4. Equal-split default (the proportion-is-truth contract)

Leo's binding contract: proportion is the source of truth; equal-split is the default proportion; the total scales proportions.

- **Do NOT invert `EMPTY_ITEMS_ALL_ZERO`.** Zero is the engine's emergent fixed point and settlement reads a frozen DTO snapshot (real-money blast radius).
- **Instead: synthesize a single `sharedEqually` item = total UPSTREAM** when OCR returns no items → the engine naturally produces `1/N` each, the contract holds, and the invariant stays as the guard for a genuinely-empty receipt (no items AND no total → correctly $0).

---

## 5. Verify-before-split gate (last mile)

- **Fix the silent-reconciliation hole:** a single `.unknown` extra makes `Reconciler.totalFinding` early-return nil (`Reconciler.swift:69`) — most international receipts get a hollow "totals verified" signal. V2 reconciles known kinds and surfaces unknowns as a *verify* prompt, not a skip.
- **Gate on OCR confidence:** low-confidence scans (already populated, `ScannedReceipt.swift:81/103`) prompt the user to verify before money is divided.
- **Flagship fallback for dropped extras:** when Azure's total doesn't reconcile, the divergence data shows a flagship often caught the missing charge — offer it as a suggested extra.

---

## Prerequisites (fix-FIRST, before any of the above)

1. **Engine NaN/Inf guard** (`ReceiptSplitEngine.swift:26-41`).
2. **Negative-amount BOUNDED** — `SplitEngineEdgeCaseTests.swift:38-69` proves the engine returns proportion 1.25/−0.25 for negatives. **Must fix before any negative extra (credit/discount) ships.**
3. Post-tax + custom tip end-to-end test; `ReceiptTotalCalculator` overflow guard; `MathInvariants` cross-target dedup.

## Invariant changes

- **KEEP:** `EMPTY_ITEMS_ALL_ZERO` (synthesize upstream instead), `ZERO_SUM`, `BOUNDED`, `PROPORTION_BOUNDED`, `REMAINDER_DETERMINISTIC`, all settlement/FX invariants.
- **ADD:** `TAX_ON_TAXABLE_BASE` (exempt items excluded), `FLAT_CHARGE_EQUAL_PER_HEAD` (incl. proportion-0), `NEGATIVE_EXTRA_BOUNDED_LOWER`, `INCLUSIVE_TAX_NOT_READDED`, `BALANCE_DUE_SPLIT`, `MINOR_UNIT_NO_SUBUNIT_RESIDUE`, `SYNTHESIZED_EQUAL_SPLIT_ON_NO_ITEMS`.
- Currency-scale `ZERO_SUM`/`matchThreshold` tolerances to minor units.

## Sequencing (when Leo says go)

1. Harden engine (NaN/Inf + negative BOUNDED) — pure safety, no behavior change.
2. Currency-aware money type — guarded by existing multi-currency invariants.
3. Currency-symbol disambiguation.
4. Inclusive-tax flag + balance_due.
5. Typed extra taxonomy + per-kind apportionment — **the big one, gated on Leo's comp/voucher ruling.**
6. Verify-before-split gate + `.unknown` reconciliation fix.

## Migration safety

Do **not** silently re-apportion existing `.custom` SummaryItems — that would change historical splits. New apportionment modes gate behind the new typed kinds; untagged legacy `.custom` stays proportional.

## What's gated

This spec is the deliverable. The iOS `ResplitCore` code change is **gated on the 2.0 freeze lifting + Leo's sign-off + a green test baseline (P9.4)**. Every direction here cites a real receipt + a `file:line` + the invariant it preserves.
