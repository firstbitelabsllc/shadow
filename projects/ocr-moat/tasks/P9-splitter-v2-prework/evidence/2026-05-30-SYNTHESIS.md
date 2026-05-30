# Splitter V2 Prework — Executive Synthesis

> Source: prework workflow `w5o5plp2k` (29 agents, adversarially verified). Companion to the full [code-state map](2026-05-30-code-state-map.md), [test audit](2026-05-30-test-audit.md), and [102-case edge catalog](2026-05-30-edge-case-catalog.md). **Planning only — no production code. Living doc; strengthens as more receipts arrive.**

## The one structural root cause

V1 models every receipt as a single additive equation and apportions everything one way:

```
resolvedTotal = itemSum + tax + tip + customExtras        // ReceiptTotalCalculator.swift:19  (UNCONDITIONALLY additive)
each person's share  = proportion-by-consumption × resolvedTotal   // ReceiptSplitEngine.swift:73  (cents-hardcoded, currency-blind)
```

Almost all 102 edge cases fall out of **four properties of that one shape**:

1. **No post-tax extra taxonomy.** There is no `.serviceCharge / .fee / .surcharge / .cover / .credit` in the splitter domain — the rich OCR enum *has* them (`ScannedReceipt.swift:121-124`) but `OCRSnapshotBridge.swift:92-98` **literally drops them with a comment**. Anything that isn't tax or tip either vanishes (group under-billed, payer eats it) or gets forced into `.custom` and spread proportionally.
2. **Everything splits proportional-by-consumption.** A flat $35/head cover, a fixed $80.83 admin fee, a mandatory auto-gratuity — all get loaded onto whoever ordered the expensive entrée. Flat charges are mis-billed by construction.
3. **Currency-blind money math.** `ReceiptSplitEngine.swift:73/78` hardcodes `×100/.../100` cents. JPY/KRW mint impossible fractional yen; BHD/KWD (3-decimal) lose precision; `Reconciler.matchThreshold = 0.01` (USD dollars) false-flags no-decimal receipts and is blind to fils errors. Root enabler: `V3ReceiptReconciler.adapt()` hardcodes `currencyCode: nil` (`V3ReceiptReconciler.swift:76`).
4. **Additive tax with no inclusive flag.** Inclusive GST/VAT (most AU/MY/EU receipts) gets **added a second time** — everyone over-billed by the full tax. And `total != balance_due` (deposits/prepayments) splits the gross, over-billing the table by the deposit.

**Implication:** V2 is not a pile of 102 patches. It's **three model changes** — (a) a typed extra taxonomy with a per-kind *apportionment mode*, (b) a currency-aware money type (minor-units + currency-scaled thresholds), (c) an inclusive-tax / balance-due aware total — plus a "verify before split" gate keyed to OCR confidence. The 102 cases are the test corpus that proves each one.

## The 4 P0s that are SILENT money errors (adversarially confirmed)

These mis-bill real money with **no error shown** — the worst kind:

1. **Ambiguous currency symbol → wrong FX pair.** `¥` → CNY not JPY (~20× error); bare `$` collapses CAD/AUD/SGD/MXN → USD. The rate fetch *succeeds* (CNY→USD is a valid pair), freshness reads `.live`, nothing warns. `Currency.swift:52-98` resolves ambiguous symbols unconditionally.
2. **CC/processing surcharge dropped by Azure.** The printed total no longer reconciles; `resolvedTotalAmount` prefers the computed (pre-fee) total, so **the payer silently eats the whole surcharge** (P7's canonical Marathon Cafe $1.77).
3. **Inclusive GST/VAT double-added.** `ReceiptTotalCalculator.swift:19` re-adds a tax already baked into the printed total — everyone over-billed by the full tax amount.
4. **Deposit credited to ONE payer, not the table.** Even if a −$262 deposit were captured, it flows proportionally, so the host who prepaid only gets ~1/N of their own deposit back.

## The 5 calls that are YOURS to make (dangerous apportionment decisions)

The adversarial pass flagged these `needs-revision` because the *engineering* is clear but the *product rule* is a judgment call — and getting it wrong mis-bills a real person at a real dinner:

| # | The charge | Proportional-by-consumption | Equal-per-head | The trap |
|---|---|---|---|---|
| 1 | **Mandatory % service charge (10/18%)** | ✅ scales with consumption like tax | — | Probably proportional — but is it taxable? tippable-on-top? |
| 2 | **Flat cover / table minimum ($35/head)** | ❌ heavy eater overpays | ✅ likely correct | **A 0-consumption person (non-drinker at AYCE) still owes the cover** — per-head must handle proportion=0, which today's engine can't. |
| 3 | **Deposit / prepayment (total ≠ balance_due)** | — | — | Is the deposit *one person's money returned* (credit to payer) or *a table-wide prepayment* (reduce everyone)? Different math, different people. |
| 4 | **Comp / discount / voucher** | depends | depends | The one credit that *should* spread — but proportional vs per-head changes who benefits. A comp for one person's entrée ≠ a table-wide promo. |
| 5 | **Weighted per-lb/kg item** | item-level | — | Fractional quantity coerced to integer 1 today; rare in dining. |

**These five are the heart of "dangerous territory." I am NOT proposing to resolve them unilaterally — they need your ruling.** Everything else (currency model, inclusive flag, extra taxonomy plumbing, reconciler thresholds) is mechanical once the apportionment rules are decided.

## Fix-FIRST tests (your explicit ask — before any V2 code)

The engine is well-protected (property-based 10k-receipt invariants, no disabled money tests), but the new receipts expose edges with no coverage:

1. **Engine has no NaN/Inf guard** (`ReceiptSplitEngine.swift:26-41`) — a garbage OCR amount propagates into everyone's share. *High.*
2. **Negative amounts break BOUNDED** — `SplitEngineEdgeCaseTests.swift:38-69` already *proves* the engine returns proportion 1.25 / −0.25 for a negative item. This is the exact failure a deposit-credit (negative extra) would hit. **Fix this before adding any negative extra kind.** *High.*
3. **Post-tax + custom tip never driven end-to-end** through engine→settlement (only the pure tip helper is tested). *Medium.*
4. **`ReceiptTotalCalculator` total-overflow guard** missing. *Medium.*
5. **`MathInvariants` duplicated across targets** (`UITestDataCorpusInvariantTests` re-implements it inline) — consolidate so one source of truth guards both. *Low/hygiene.*

## Recommended sequencing (when you say go — not now)

1. **Harden the existing engine** (fix-first #1, #2) — NaN/Inf + negative-amount BOUNDED. Pure safety, no behavior change, unblocks negative extras.
2. **Currency-aware money model** — minor-units from `currencyCode`, currency-scaled `matchThreshold`, stop hardcoding `currencyCode: nil`. Mechanical; guarded by `SettlementServiceMultiCurrencyTests` + `CurrencyResolutionInvariantsTests`.
3. **Disambiguate currency symbols** (P0 #1) — require CountryRegion or prompt; never silently pick CNY/USD.
4. **Inclusive-tax flag + balance_due** (P0 #3, #4) — the additive-total fix.
5. **Typed extra taxonomy + apportionment modes** — *gated on your 5 rulings above.* This is the big one.
6. **"Verify before split" confidence gate** (last-mile) — surface low-confidence scans before money is divided.

## What more receipts would strengthen

You said more are coming. The catalog is thin on **real scanned evidence** for: 3-decimal currencies (no BHD/KWD/OMR receipt yet), cross-currency *settlement* (a trip mixing currencies), an actual deposit/balance-due receipt (the $2180/$1918 case is from the P8 story, only ~4 of 48 rows are scanned), and partially-inclusive tax (one inclusive + one exclusive line). Scanning any of those promotes its catalog entry from "reasoned" to "grounded." Drop them and the loop folds them in.
