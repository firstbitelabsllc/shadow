# Resplit Splitter V2 — Design Spec (capstone) — Rev 2 (adversarially reviewed)

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
| `fee` (admin/CC/delivery, flat $) | **equal-per-head** (default) | per seat | 3 receipts; a fixed-$ fee is per-seat like cover. A `%` fee → proportional (see surcharge). |
| `fee` (item-attributed: CRV/corkage) | by-claim | the item's claimant | NEW: dropped/mis-spread today |
| `surcharge` (CC %, weekend %) | proportional | consumption | 2 receipts |
| `credit` / `deposit` (negative) | **context-gated** | payer OR table-wide | 3 receipts; see §below |
| `discount` / `comp` (negative) | **OPEN — Leo** | targeted OR table-wide | 2 receipts |
| `mandate` (health/tourism levy) | proportional | consumption | 1 receipt |

**Deposit/credit (context-gated):** credit-to-payer for restaurant/catering checks, table-wide (reduce everyone) for event/trip pools. The `BOUNDED_LOWER` refund branch (a credited payer going negative) is a **blocking** prerequisite, not a footnote.

> **HARD MUST (the #1 ship-bug, promoted from the decision matrix):** model a credit/deposit as a **post-split, named-participant settlement adjustment** — NOT as a signed `customExtras` term. A negative `customExtras` reconciles `ZERO_SUM` to the right *total* while moving the *wrong person's* money (the host pays the $262 deposit twice and every test stays green — `ZERO_SUM` is exactly the invariant that can't catch it). The existing `Reconciler` already subtracts `negativeKinds = [.discount, .credit]` via `abs()`, so "fold it into the total" is the path of least resistance and the path that mis-bills. The credit must apply to a *participant balance*, after the split, with its own `NEGATIVE_EXTRA_BOUNDED_LOWER` check.

**Comp/discount — THE open decision:** a table-wide promo should spread; a one-item comp should target that item. Default proposal (pending Leo): spread proportionally unless the comp is tagged to a specific line item. Leo rules.

**Apportionment is a DOLLAR LAYER, not a proportion edit.** `equal-per-head` / `by-claim` / flat-fee modes compute a **separate per-participant dollar vector** and add it on top — they MUST NOT be injected into `proportionByParticipant` (that pushes `Σ proportions` off 1.0 and breaks `PROPORTION_SUM`, `MathInvariants.swift:99`, a currently-green test). Equal-per-head is computed on **headcount** (`amount/N`), never by normalizing an all-zero proportion vector (that's a `0/0` the NaN-guard prereq exists to catch). A diner is only legitimately proportion-0 when line items exist and they claimed none; the flat layer bills them anyway.

---

## 2. Currency-aware money type

Stop hardcoding cents. `ReceiptSplitEngine.swift:73/78` does `×100/.../100`; `Reconciler.swift:34` uses `matchThreshold=0.01` USD; `V3ReceiptReconciler.swift:76` hardcodes `currencyCode:nil`.

- Money carries its **`currencyCode`** end-to-end (kill the `nil`); minor-unit scale derived from ISO 4217 (`0` JPY/KRW, `2` USD/EUR/MYR/AED/AUD, `3` BHD/KWD/OMR).
- Rounding + remainder distribution operate in **minor units**, not hardcoded cents → no fractional yen, no destroyed fils.
- **Two distinct tolerances, do NOT conflate:** internal `ZERO_SUM` (sum of shares vs the split total) stays **exact — 0 residue** (`MINOR_UNIT_NO_SUBUNIT_RESIDUE`; remainder distribution leaves nothing over). The reconciler `matchThreshold` (split total vs the *scanned* total) gets the **1-minor-unit** slack for OCR noise. Same currency scale, different jobs — using one number for both would weaken the internal exactness guarantee.
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
- **Synthesize a single `sharedEqually` item = the CONSUMPTION BASE upstream** when OCR returns no items → the engine produces `1/N` each, the contract holds, and the invariant stays as the guard for a genuinely-empty receipt (no items AND no total → correctly $0).
- **CRITICAL — synthesize from the subtotal/consumption base, NOT the raw total.** If a no-items receipt also has a service charge / tip / typed extra, synthesizing one item `= total` would fold those extras into a single equal-per-head item — splitting a *proportional* service charge equally AND contaminating the percent-tip base (violates §1 + §3). Order is fixed: **(1) extract typed extras → (2) synthesize the equal item from `balanceDue − Σ(typed extras)` → (3) apportion each typed extra by its own `(mode, base)` as a separate dollar layer.** On a no-items bill the consumption shares are all equal, so a proportional extra and equal-per-head coincide numerically — but only because the base was stripped first.
- **Cover-on-zero-items** (a flat cover, no line items): the per-head cover is a flat dollar layer (§1), applied after the synthesized consumption item, so it does not re-enter the `EMPTY_ITEMS_ALL_ZERO` engine path. Pin this reconcile path with a test (`EmptyItemsInvariantsTests` currently locks all-zero on literal-empty).

---

## 5. Verify-before-split gate (last mile)

- **Fix the silent-reconciliation hole:** a single `.unknown` extra makes the *total* check `Reconciler.totalFinding` early-return nil (`Reconciler.swift:69`). (Nuance verified in review: an `unknownExtraKindFindings` chip IS emitted separately, so the user isn't blind — but the **arithmetic total-vs-sum verification is silently skipped**, which is the actual safety hole.) V2 reconciles the known kinds (so the total check still runs) and surfaces the unknown as a *verify this extra* prompt — never skips the math.
- **Gate on OCR confidence:** low-confidence scans (already populated, `ScannedReceipt.swift:81/103`) prompt the user to verify before money is divided.
- **Flagship fallback for dropped extras:** when Azure's total doesn't reconcile, the divergence data shows a flagship often caught the missing charge — offer it as a suggested extra.

---

## 6. Payment & liability — the SECOND axis (explicitly scoped, not silently dropped)

The completeness sweep surfaced a whole second axis the apportionment model (§1) doesn't touch: **who OWES is separate from who PAID.** Multi-tender (cash + card split), one person treats/covers another, partial payment, a reimbursement already made off-app, a participant who paid but wasn't at one meal. §1 answers "what does each person owe"; this axis answers "given who fronted the money, who pays whom" — it's a **settlement** concern (`SettlementService`), and the deposit/credit `HARD MUST` above is the first toe into it (a credit is a named-participant settlement adjustment, not an apportionment).

**Decision: V2 keeps these two axes separate.** The §1 taxonomy ships first (it's the measured 31% gap). The payment/liability axis is its own follow-on spec against `SettlementService`, NOT folded into the extra-taxonomy — conflating them is how a credit becomes a signed `customExtras` and mis-bills. Flagged here so it's a known, deliberate boundary, not an omission.

## Prerequisites (fix-FIRST, before any of the above)

1. **Engine NaN/Inf guard** (`ReceiptSplitEngine.swift:26-41`).
2. **Negative-amount BOUNDED** — `SplitEngineEdgeCaseTests.swift:38-69` doesn't just omit the bound, it **actively asserts `bobOwes == -10.0` as correct** (`:30`) and only checks `ZERO_SUM` (`:31`). So the negative path is unguarded AND a green test pins the broken behavior. The fix must (a) add the engine guard, (b) wire `assertBounded` onto the path, and (c) **flip this test** to expect the guarded result — not just extend it. (Verified directly: `Reconciler.swift:71` `negativeKinds = [.discount,.credit]` subtracts via `abs()`, `MathInvariants.swift:99` PROPORTION_SUM rejects under-normalized sums.) **Must land before any negative extra (credit/discount) ships.**
3. Post-tax + custom tip end-to-end test; `ReceiptTotalCalculator` overflow guard; `MathInvariants` cross-target dedup.

## Invariant changes

- **KEEP:** `EMPTY_ITEMS_ALL_ZERO` (synthesize upstream instead), `ZERO_SUM`, `BOUNDED`, `PROPORTION_BOUNDED`, `REMAINDER_DETERMINISTIC`, all settlement/FX invariants.
- **ADD:** `TAX_ON_TAXABLE_BASE` (exempt items excluded), `FLAT_CHARGE_EQUAL_PER_HEAD` (incl. proportion-0, computed on headcount), `FLAT_LAYER_LEAVES_PROPORTIONS_UNCHANGED` (a flat/by-claim dollar layer must not move `Σ proportions` off 1.0 — protects `PROPORTION_SUM`, `MathInvariants.swift:99`), `NEGATIVE_EXTRA_BOUNDED_LOWER` (wired onto the negative path, which is currently unguarded), `INCLUSIVE_TAX_NOT_READDED`, `BALANCE_DUE_SPLIT`, `MINOR_UNIT_NO_SUBUNIT_RESIDUE`, `SYNTHESIZED_EQUAL_SPLIT_FROM_CONSUMPTION_BASE` (synthesize from `balanceDue − Σ typed extras`, not raw total).
- `ZERO_SUM` stays **exact** (0 residue); only the reconciler `matchThreshold` gets the 1-minor-unit slack. Currency-scale both to minor units.

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
