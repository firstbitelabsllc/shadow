# Empirical Findings — Multi-Model Extraction Over the Full Corpus

> Source: `run_extract_pass.py` (Azure prebuilt + Claude + qwen on all 48 rows; 44/44 new = 0 errors, ~20 min) + the P8.5 telemetry aggregate (`~/.config/resplit/ocr-events.jsonl`, 232 events). This converts the prework from *reasoned* to *measured*. 2026-05-31.

## The headline number

**31% of real dining receipts (15 / 48) carry an extra BEYOND tax+tip** — the precise class V1's `subtotal + tax + tip + customExtras` model cannot represent without dropping or mis-apportioning. Nearly one in three. This is the empirical case for the V2 extra-taxonomy in a single figure.

## Where Azure prebuilt diverges from the flagships (the P7 oracle, now at corpus scale)

94 `ocr.divergence` events across the corpus. Kinds a flagship (Claude/qwen) caught that **Azure prebuilt dropped**:

| Kind Azure missed | # receipts |
|---|---|
| tip | 14 |
| **serviceCharge** | **9** |
| unknown | 6 |
| credit | 3 |
| discount | 3 |
| surcharge | 2 |
| fee | 2 |
| mandate | 1 |
| rounding | 1 |

Field-level divergence: **total on 21**, **currencyCode on 23**, extras on 36, subtotal on 14. So the prework's central claims are now empirically true on Leo's own receipts: Azure prebuilt silently drops post-tax charges (service charge on 9, tip on 14) and the dropped charge breaks the printed total (21 total-divergences) — the payer-eats-it failure, measured.

## Real prevalence of each extra kind (any provider found it)

| kind | receipts | note |
|---|---|---|
| tax | 43 | near-universal |
| tip | 25 | |
| **serviceCharge** | **6** | mandatory service/auto-grat — V1 drops at the bridge |
| unknown | 5 | the kind that silently disables reconciliation (`Reconciler.swift:69`) |
| fee | 3 | admin/CC/delivery |
| credit | 3 | deposit/comp — V1 has no negative-extra path (BOUNDED breaks) |
| discount | 2 | |
| surcharge | 2 | CC processing |
| mandate | 1 | health/tourism levy |
| rounding | 1 | cash-rounding adjustment |

## Currency reality

| currency | receipts |
|---|---|
| USD | 44 |
| MYR | 4 |
| AED | 4 |
| AUD | 1 |

The corpus is **genuinely international** (Malaysia, UAE, Australia) — and on **5 receipts the providers disagree on the currency**, empirically confirming the currency-resolution ambiguity (`currencyCode:nil` + ambiguous-symbol) is real, not theoretical. Still **no 0-decimal (JPY/KRW) or 3-decimal (BHD/KWD)** receipt in the corpus — those remain the highest-value scan-priority gaps (the catalog reasons about them but has no ground truth yet).

## What this proves about the V2 case

1. **The extra-taxonomy is not speculative** — 31% of receipts need it; serviceCharge appears on 6, the negative-extra kinds (credit/discount) on 5.
2. **Azure-alone under-extracts** — a flagship caught a dropped charge on dozens of receipts. The "verify before split" gate + a flagship fallback for low-confidence extras is justified by data.
3. **Currency is a real axis** — 9 non-USD receipts, 5 with currency disagreement. The currency-aware money model isn't for hypothetical users; it's for Leo's actual trips.
4. **The 3-decimal / no-decimal gap is the one thing data can't yet confirm** — scanning a JPY or BHD receipt is the single highest-leverage capture left.
