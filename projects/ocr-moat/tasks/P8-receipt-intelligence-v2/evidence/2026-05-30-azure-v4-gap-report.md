# Azure DI v4 `prebuilt-receipt` — what we're not using

**Source:** workflow `wg5yo9au4` azure-audit agent (read `ocr.py` + `ReceiptScanner.swift`, researched the v4 GA schema). 2026-05-30.

## Current usage (the bare minimum)

`POST {endpoint}/documentintelligence/documentModels/prebuilt-receipt:analyze?api-version=2024-11-30&locale=en` — **no `features=`, no `queryFields=`**. Decoder (`ReceiptResultV4.swift` iOS / `ocr.py` harness) reads only `MerchantName, MerchantAddress, Total, Subtotal, Items[Description, Quantity, TotalPrice], TotalTax, Tip`.

## Leo's idea, corrected

> *"arbitrary key value support post subtotal"*

- **`features=keyValuePairs` does NOT work on `prebuilt-receipt`** — the per-model feature matrix leaves Key/Value-Pairs blank for the receipt model. It only works on `prebuilt-layout`/`prebuilt-document`.
- **The right answer is `features=queryFields`** — supported on `prebuilt-receipt`, lets you name the exact extra fields to extract: `&features=queryFields&queryFields=ServiceCharge,Gratuity,DeliveryFee,Surcharge,Fee,Deposit`. This is the v4-native way to capture the "Service Charge: $X" lines below subtotal. (Premium/billed.)
- If truly *arbitrary* (unknown) keys are needed, add a **second `prebuilt-layout:analyze?...&features=keyValuePairs`** pass on the same image and merge — but `queryFields` covers the known fee taxonomy at lower cost.

## Gap table

| Pri | Capability | Gives | Status | Cost |
|---|---|---|---|---|
| **P1** | **`TaxDetails[]`** (Amount, Rate, NetAmount, Description) | Per-tax breakdown — every distinct tax line (state/city/VAT/service-tax), not one collapsed `TotalTax`. **This IS Leo's "per-tax breakdown."** | NOT PARSED (only `TotalTax`) | **FREE — already returned** |
| **P1** | **`features=queryFields`** | The arbitrary-extras mechanism: ServiceCharge / Gratuity / Surcharge / Fee / Deposit as named fields | NOT USED (no `features` sent) | Premium (billed) |
| **P2** | **`Payments[]`** (Method, Amount) | Card vs cash vs split-tender — "who paid" reconciliation | NOT PARSED | FREE |
| **P2** | **`Items.Price`** (unit price), `QuantityUnit`, `ProductCode` | Unit price → detect/repair `qty×price ≠ line total`; unit (lb/kg/ea); SKU | PARTIAL (only `TotalPrice`) | FREE |
| **P2** | `prebuilt-layout` + `keyValuePairs` (2nd pass) | Truly arbitrary unlabeled key:value capture | NOT USED (needs 2nd request) | FREE-ish (extra request) |
| **P3** | `CountryRegion`, `MerchantPhoneNumber`, `ReceiptType`, `MerchantAliases` | **CountryRegion → currency inference** (fixes the `currencyCode: nil` reconciler bug); phone for folder auto-name | NOT PARSED | FREE |
| **P3** | `features=languages,barcodes` | Per-line locale (replace hardcoded `locale=en`); QR/UPC | NOT USED | FREE |
| **P3** | `features=ocrHighResolution` | Small-text recall on dense/long receipts | NOT USED | Premium |

## Recommended order (validate each against the 44-receipt corpus)

1. **Decode the FREE fields first — no Azure spend, data already returned:** `TaxDetails[]`, `Payments[]`, `Items.Price/QuantityUnit/ProductCode`, `CountryRegion`. Extend `FieldsV4`/`ItemObjectV4` (iOS) + `azure_to_scanned` (`extract.py`) + the `ScannedReceipt` mapping. Confirm against the corpus rows.
2. **Stop hardcoding `locale=en`** — add `features=languages` (free) for the non-English receipts (Chinese/Malay/Arabic in the corpus).
3. **Prototype `features=queryFields=ServiceCharge,Gratuity,Surcharge,Fee,Deposit`** in `ocr.py` against the captured corpus; measure how many of the dropped extras it recovers vs the cost.
4. **Gate premium add-ons** (`queryFields`, `ocrHighResolution`) behind a cost decision; consider applying `ocrHighResolution` only on retry when item count looks truncated.
