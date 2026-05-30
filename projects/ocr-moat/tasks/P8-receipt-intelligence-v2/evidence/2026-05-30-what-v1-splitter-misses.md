# What Resplit's V1 receipt splitter misses — the story, from 44 real receipts

**Source:** workflow `wg5yo9au4` (8 vision agents read all 44 real restaurant receipts harvested from Leo's Photos) + P7 multi-model benchmark. 2026-05-30.

## The one-sentence story

Resplit V1 models a restaurant bill as **`subtotal + tax + tip = total`** — but real receipts routinely carry a **third class of money between subtotal and total** (service charges, admin fees, cover charges, surcharges, deposits, inclusive taxes) that V1's `extras = [tax, tip]`-only schema **silently drops**, so the split is wrong before anyone picks an item.

## The evidence (real receipts, real amounts)

V1's `OCRSnapshotMapper` only ever fills `extras` from Azure's `TotalTax` (→ `.tax`) and `Tip` (→ `.tip`). Everything below — pulled from Leo's actual receipts — is dropped:

| What V1 drops | Real example (in the corpus) | `ScannedExtraKind` it should be |
|---|---|---|
| **Auto-gratuity** (printed, mandatory) | catering check, **gratuity $339.47** | `.serviceCharge` (NOT `.tip` — it's not discretionary) |
| **Admin / service fee** | **admin fee $80.83**; service charge **10% = RM26 / $29.93 / 6.40** | `.serviceCharge` / `.fee` |
| **Service tax (separate from sales tax)** | **service tax 6% = 3.84** alongside sales tax | `.tax` (a SECOND tax line) |
| **Cover / minimum charge** | **2× $35 cover = $70**; **AYCE "2 adult" $49.90**; **drink minimum $10** | `.fee` / `.surcharge` |
| **CC processing surcharge** | Marathon Cafe **3% CC fee $1.77** (P7 finding) | `.surcharge` |
| **Deposit credit (NEGATIVE)** | **tripleseat deposit redeem −$262.00** | `.credit` (reduces total) |
| **Inclusive tax** | **"GST included in total $90.68"** (tax already in the number) | needs an `inclusive` flag, not an additive `.tax` |
| **Rounding adjustment** | **rounding adj $0.01** | `.fee` (or a dedicated rounding field) |
| **Comped items ($0.00)** | ice water ×2, comped mushroom/pancake | $0.00 line items the splitter must keep visible |

**Net effect:** on the catering check, V1 sees `subtotal + tax + tip`, but the real bill has `subtotal + sales tax + admin fee + auto-gratuity − deposit`. **`total ($2180.26) != balance due ($1918.26)`** because of the deposit — V1 has no concept of either the admin fee, the gratuity-as-service-charge, or the deposit credit, so it cannot reconcile, and whoever it splits among pays the wrong share.

## Split-impact edge cases (beyond the extras schema)

These break the *split*, not just the total:

1. **Shared appetizers** (chowder fries, salads "among the table") — V1 has no shared-item concept; they get assigned to one person.
2. **Handwritten tip** ($25 in pen, $6 on a signed Amex slip) — not a printed `Tip` field, so Azure/V1 miss it; the tipper's share is understated.
3. **Total ≠ balance due** (deposit/prepayment applied) — V1 splits the wrong number.
4. **Modifiers / add-ons** ("caesar salad / add chicken") as sub-items — price attribution is ambiguous.
5. **Dual-language / non-English items** ("Sm Guacamole con T…", Chinese/Malay/Arabic) — `locale=en` is hardcoded; names garble.
6. **No-decimal & foreign currency** (RM, AED, AUD) — `V3ReceiptReconciler` hardcodes `currencyCode: nil` and `matchThreshold = 0.01`, both wrong off-USD.
7. **Quantity-embedded-in-description / wrapped multi-line item names** — qty×price validation fails.
8. **Duplicate tax lines** ("sales tax $7.34" + "tax $…") — Azure's `TotalTax` may grab the wrong one.

## Root cause is two-layer

1. **Azure-call layer** — we send a bare `prebuilt-receipt` analyze with no `features`, and decode only `MerchantName/Address/Total/Subtotal/Items[Desc,Qty,TotalPrice]/TotalTax/Tip`. Azure already returns **`TaxDetails[]`, `Payments[]`, unit `Price`, `CountryRegion`** for free — we drop them. The arbitrary "Service Charge: $X" lines need **`features=queryFields`** (the v4-supported answer — see the Azure gap report).
2. **Domain/reconciler layer** — even when a fee is present, `extras` only knows `.tax`/`.tip`, the reconciler discards currency, and the match threshold is USD-only.

→ See `2026-05-30-azure-v4-gap-report.md` (config changes) and the V2 spec in the P8 PLAN.
