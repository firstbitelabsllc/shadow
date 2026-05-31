# International Tax / Currency / Post-Tax Regimes — P9.3 deepening

> Source: workflow `wzuiyidrz`. 11 real regimes → exact tax structure, post-tax norms, currency minor-units, what V1 breaks, and scan priority. Grounds the catalog in the receipt shapes Leo will scan abroad.

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

All citations confirmed against the real iOS files. Key facts verified:
- `inferCurrencyCode`: `€` → `EUR` (Currency.swift:56-57), no minor-unit info attached
- `isAmbiguousSymbol` covers `$`/`¥`/`￥`/`kr` — NOT `€` (Currency.swift:105-109); `currencyCode(forCountryRegion:)` only maps `$`/`¥` countries (no DE/FR/IT) (Currency.swift:116-134)
- Engine rounds `*100/.../100` hardcoded 2-decimal (ReceiptSplitEngine.swift:73,78) — EUR is 2-decimal so this is fine for EUR math
- Reconciler positiveKinds includes `.serviceCharge`/`.mandate`/`.surcharge` but these are DEAD in production (bridge drops them, OCRSnapshotBridge.swift:92-98); they arrive as `.custom`→`.unknown` which poisons totalFinding (Reconciler.swift:69)
- `ReceiptTotalCalculator` = purely additive `itemSum + tax + tip + customExtras`, no inclusive-tax flag (ReceiptTotalCalculator.swift:19)

I have everything needed. Producing the markdown section.

## eu-france-germany-italy

**Region/regime:** Eurozone dine-in — France, Germany, Italy. The defining trait versus the US model the V1 engine was built around: **tax is VAT-INCLUSIVE** (already baked into every menu price and the printed total), and the mandatory "extra" is structurally different — France/Germany bundle service into the price (*service compris* / *Bedienung inklusiv*), Italy adds a fixed per-head **coperto** cover charge that is neither tax nor tip nor proportional to consumption.

### TAX structure

- **Inclusive, not additive.** EU consumer law (and national practice) requires displayed prices to include VAT. The restaurant total a diner pays *already contains* the VAT — the receipt shows VAT as an informational breakdown ("dont TVA", "inkl. MwSt", "di cui IVA"), not as a line added on top. There is no "subtotal + tax = total" arithmetic; the correct relationship is `VAT_amount = gross × rate/(1+rate)` and `subtotal_net = gross − VAT_amount`. The receipt's stated total equals the sum of gross item prices, full stop.
- **Rates (dine-in food, 2026):**
  - **France:** 10% on prepared food/restaurant meals and non-alcoholic drinks; **20%** standard on alcohol. (Takeaway long-life food can be 5.5%.)
  - **Germany:** 19% standard. Dine-in restaurant food reverted to **19%** after the COVID-era 7% relief expired (Jan 2024); **7%** reduced still applies to takeaway/cold food. Beverages (incl. alcohol) are 19%.
  - **Italy:** **10%** on restaurant services and most food; **22%** standard on alcohol and some items; bottled water/certain goods at 4%/5%.
- **Per-item / multi-rate, tax-on-tax:** A single dine-in receipt routinely carries **two or more VAT rates** — e.g. food at 10% and wine at 20% in France, or food at 10% and a digestivo at 22% in Italy. Receipts print a **VAT summary table** (rate / net base / VAT amount per band). There is **no tax-on-tip and no tax-on-tax** (VAT is single-stage on the gross).
- **Reduced-rate split per category** is the load-bearing complication: the inclusive VAT amount differs by line, so the "true" pre-tax cost of a wine drinker vs. a food-only diner diverges from a flat proportional split.

### POST-TAX charge norms

- **France:** Service is legally included (*service compris*, since 1987). No mandatory service line on a standard receipt. Tipping is a small optional cash *pourboire* — rarely a printed line.
- **Germany:** Service included; tipping is customary (~5–10%) but handled verbally at payment ("stimmt so" / rounding up) — usually **not** a separate printed line; the diner states the total they want charged.
- **Italy — coperto:** A fixed **cover charge per head** (typ. €1–4/person), printed as `Coperto` / `Pane e coperto`. This is the single most important EU-specific extra: it is **per-person flat**, NOT proportional to what you ate, NOT a percentage, and NOT tax or tip. Some Italian/tourist-area receipts also add `Servizio 10-15%` (a mandatory percentage service charge), which IS roughly proportional but is its own category.
- **Surcharges:** Sunday/holiday surcharges (Italy), card-processing surcharges, and `Servizio` percentage charges appear as discrete post-tax-looking lines even though VAT is inclusive.

### CURRENCY

- **ISO:** EUR. **Minor unit:** 2 decimals (cents) — same granularity the engine's `*100/.../100` assumes, so EUR is the *one* major international regime where V1's 2-decimal money math is NOT broken (unlike JPY/KRW/BHD).
- **Symbol:** `€`. Placement varies — France/Italy print trailing (`12,50 €`), Germany often trailing (`12,50 €`) too. **Decimal separator is a COMMA** (`1.234,56 €`), thousands separator is a period — the inverse of US formatting. This is an OCR-parse hazard: `1.234,56` mis-parsed as US-style reads as `1.234` (a 1000x undercount) or `123456`.
- **Symbol ambiguity:** `€` is unambiguous — `Currency.inferCurrencyCode(from:"€") -> "EUR"` (Currency.swift:56-57), and `€` is correctly NOT in `isAmbiguousSymbol` (Currency.swift:105-109), so no country-region disambiguation is needed. EUR resolution is the clean case.
- **Cash rounding:** Some euro countries round cash totals to the nearest 5 cents (Italy abolished 1¢/2¢ coin minting; Finland/Netherlands round). So `total` (cash-rounded) can legitimately differ from `subtotal + VAT` by up to 2¢ — a real discrepancy the reconciler's `matchThreshold=0.01` (Reconciler.swift:34) would flag.

### What a REAL dining receipt here literally prints

A Roman trattoria receipt prints: item lines (`Bucatini`, `Vino rosso`, `Acqua`) with prices in `12,00` comma-decimal form; a `Coperto 2,00 x 3 = 6,00`; possibly `Servizio 10%`; then `Totale € 84,00`; then a VAT summary block: `IVA 10% imponibile 60,00 IVA 6,00 / IVA 22% imponibile 14,75 IVA 3,25`. A Paris bistro prints item lines, `TOTAL 78,50 €`, `dont TVA 10% : 5,40` and `dont TVA 20% : 2,00`, and `Service compris` as a footer note. A Berlin restaurant prints items, `Summe 64,00 €`, `inkl. 19% MwSt 10,22 €`. **Crucially: in all three, the total is the sum of gross item prices; VAT is a breakdown, not an addend; and Italy's coperto is a real money line that is per-head, not consumption-proportional.**

### What V1 breaks

- **[P0] Italy coperto is split proportional-by-consumption, over-billing light eaters.** A `Coperto €2 × 3 = €6` is a flat per-head charge, but if entered as a `.custom` SummaryItem it lands in `ReceiptTotalCalculator.calculatedTotal` via the `.custom` filter (ReceiptTotalCalculator.swift:13-19) and is then scaled by each person's *item* proportion in the engine (`proportion * distributableAmount`, ReceiptSplitEngine.swift:73). **Mis-billed:** the person who ordered a €40 steak pays ~€4 of the coperto while the person who had a €6 salad pays ~€0.60 — but a cover charge is owed equally per seat. There is no equal-per-head split mode for any extra (the engine hard-wires consumption-proportion; code-state-map "Tax/tip/extras are NEVER apportionable to a subset or equal-per-head").
- **[P0] Inclusive-VAT receipts trip the reconciler's additive total check.** `Reconciler.totalFinding` computes `expected = subtotal + positives − negatives` and flags `.totalMismatch` if it diverges from `total` by > 0.01 (Reconciler.swift:67-82). EU receipts are inclusive: their stated `subtotal` (if OCR even extracts one — many EU receipts print only the VAT-summary net base, not a US-style pre-tax subtotal) plus a separately-listed VAT line will **double-count** — `net_subtotal + VAT_line` may equal total (looks fine) OR the printed `Totale` is already the gross and the VAT line is informational, making `expected = gross + VAT > total`, a **false mismatch** shown to the user as "Totals don't match" (CopyTokens chip). **Mis-billed:** nobody mis-billed in money, but every inclusive-VAT receipt gets a spurious error/warn chip eroding trust. There is no inclusive-tax flag anywhere (V3ReceiptReconciler.swift / ReceiptTotalCalculator.swift have no inclusive concept).
- **[P1] Multi-rate VAT (food 10% + alcohol 20/22%) collapses to a single tax line, losing per-category truth.** The persisted model has exactly ONE `taxItem` (`summaryItems.first(where: {$0.type == .tax})`, per SummaryItemType's 5 cases `custom/tip/tax/total/subtotal`, ReceiptItemsFixer.swift:444-450), and `ScannedReceipt.tax` sums all `.tax` extras into one Double. A two-band VAT receipt has its bands summed into one number. **Mis-billed:** the split is still proportional-by-consumption so totals net out, but the per-person VAT attribution is wrong — a food-only diner is charged a blended rate that includes the wine-drinker's 20% band. Resolvable only at display fidelity, not money, but it forecloses any future "you owe €X of which €Y VAT" breakdown.
- **[P1] Italy `Servizio 10%` mandatory service charge has no typed home and poisons reconciliation.** A mandatory percentage service line arrives as `.custom` → mapped to `ScannedExtraKind.unknown` by the V3 adapter (V3ReceiptReconciler.swift:93-105). The `.serviceCharge`/`.mandate` branches that *exist* in `positiveKinds` (Reconciler.swift:70) are **dead code** — the bridge drops them (OCRSnapshotBridge.swift:92-98 explicitly lists `.serviceCharge`/`.mandate`/`.surcharge` as dropped) and nothing in production ever constructs them. So a real `Servizio` line becomes `.unknown`, which makes `totalFinding` early-return nil (Reconciler.swift:69) — **the entire total-reconciliation is silently skipped** and the user only sees a generic "Unknown extra" warn chip. **Mis-billed:** the service charge IS split (proportionally, via `.custom`→total), so money is roughly right, but the math-verification badge silently disengages.
- **[P2] Comma-decimal OCR parse risk produces 1000x errors.** `1.234,56 €` parsed with US assumptions reads as `1.234` or `123456`. The engine operates on raw Doubles with **no overflow/sanity bound** (`calculatedTotal` sums blindly, TIP_TAX_CUSTOM_OVERFLOW_DETECTION is a documented skipped gap, code-state-map smell). **Mis-billed:** a mis-parsed line silently inflates or deflates the whole pool; everyone's share scales by the parse error. (Parse layer is upstream of the cited files, but the engine's lack of a sanity bound is what lets it through — ReceiptSplitEngine has no `total > N × subtotal` guard.)
- **[P2] Cash-rounded euro totals (nearest 5¢) emit false mismatch chips.** Where the printed `total` is cash-rounded but `subtotal + VAT` is not, the legitimate ≤2¢ gap exceeds `matchThreshold = 0.01` (Reconciler.swift:34) and can exceed... no, it's ≤2¢ so it lands in the warn band (`> 0.01, ≤ 0.05`, Reconciler.swift:108-110) → "Check totals" chip on a perfectly valid receipt. **Mis-billed:** nobody; spurious warn noise.
- **[P3] EUR is the rare currency where V1's 2-decimal money math is actually CORRECT.** Unlike JPY/KRW (0-decimal) and BHD/KWD (3-decimal), EUR's 2-decimal minor unit matches the hardcoded `*100/.../100` rounding (ReceiptSplitEngine.swift:73,78), `minimumTransactionAmount = 0.01` (SettlementService.swift:7), and `equalBy2SigFigs` `%.2f` (Double.swift:30). Noted for completeness: the minor-unit fragility class does NOT bite EUR — so the EU regime's problems are all in *tax-inclusiveness* and *coperto semantics*, never in cent-granularity rounding.

**Cross-check against corpus:** `/Users/leokwan/Development/vidux/browser/receipts/corpus.jsonl` holds 48 entries, but only one (`d49d7331c4d0`, "MARATHON CAFE (LITTLE NECK)", Queens NY, currencyCode `USD`) has any OCR content — the other 47 are empty-content placeholders. **There is zero EU/eurozone coverage in the corpus** — no `€`, no MwSt/TVA/IVA, no coperto, no comma-decimal receipt. The one real receipt is a US dollar receipt with an additive (exclusive) tax + a `3% credit card processing fee` + tips, i.e. the exact opposite tax model from this regime.

**Scan priority: high** — A real scanned EU dining receipt would strengthen the catalog more than almost any other region, because it exercises *three* failure modes the corpus has no example of and that are structurally invisible to a US-only test set: (1) VAT-inclusive totals that break the additive reconciler, (2) a multi-rate VAT summary block, and (3) Italy's per-head coperto, which is the strongest concrete case for a non-proportional, equal-per-head extra split mode the engine cannot currently express. An Italian trattoria receipt with `coperto` + two VAT bands + `servizio` is the single highest-value capture for this regime.

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

All citations confirmed. `"S$"` is confirmed absent from `inferCurrencyCode` (only `S/` for Peru exists at line 90); `.serviceCharge`/`.surcharge`/`.mandate` exist in the enum (ScannedReceipt.swift:121-124) but are dead in production per the bridge drop. I have everything I need to produce the section.

## sea-malaysia-singapore-thailand

Cross-check against `/Users/leokwan/Development/vidux/browser/receipts/corpus.jsonl`: **48 rows, 47 are un-scanned stubs**; the only fully-parsed receipt is Marathon Cafe (Queens NY, USD/`$`, `CountryRegion: USA`). **No Malaysia / Singapore / Thailand receipt exists in the corpus.** All SEA evidence below is reasoned from regime norms + verified iOS code, not from a scanned receipt.

### TAX structure (the defining trait of this region: tax-on-tax)

| Country | Consumption tax | Rate | Inclusive/exclusive | Per-item? | Reduced rates |
|---|---|---|---|---|---|
| **Malaysia** | SST (Sales & Service Tax) — *service tax* on F&B | **6%** (was 6% pre-2024, unchanged for F&B) | **Exclusive** — printed as a separate line below subtotal | No, on the whole bill | Some food zero-rated; alcohol/luxury differ but restaurant service tax is flat 6% |
| **Singapore** | GST | **9%** (raised 8%→9% on 2024-01-01) | **Exclusive on the bill line, but the ++ is the trap** | No | GST-registered merchants only (<S$1M turnover may be unregistered → no GST line) |
| **Thailand** | VAT | **7%** | **Often INCLUSIVE** in small shops (price already VAT-in); **exclusive + line-itemed** in hotels/upscale | No | Standard 7% (statutory 10% suspended to 7%); some exempt |

**The signature SEA failure mode — tax-on-tax (the "++"):** In Malaysia and Singapore the canonical restaurant bill prints **two stacked charges** and the consumption tax is levied on (subtotal **+ service charge)**, not on subtotal alone:

- **Malaysia:** `Subtotal → +10% service charge → +6% SST computed on (subtotal + service charge)`. So SST is literally tax-on-a-charge.
- **Singapore "++":** `Subtotal → +10% service charge → +9% GST on (subtotal + service charge)`. The "nett" vs "++" distinction on the menu tells you whether prices already include this; a "++" menu means both get added at the till.
- **Thailand:** `Subtotal → +10% service charge → +7% VAT on (subtotal + service charge)` in hotels/full-service; small shops often quote one VAT-inclusive price with no service charge.

This stacking order (charge first, then tax on the new base) is the structural fact V1 has **no way to represent** — it has one `.tax` slot and one `.tip` slot, no concept of an ordered/based charge.

### POST-TAX / charge norms

- **Service charge is MANDATORY and near-universal** at full-service venues: **10%** in all three countries (occasionally higher in resorts). It is *not a tip* — it is a fixed percentage line, legally distinct from gratuity.
- **Tipping on top is NOT customary** anywhere in SEA. The 10% service charge *replaces* the tip. A diner who additionally tips is the exception. So V1's `.tip` slot is the wrong home for this 10% — it is a mandatory service charge, not a discretionary tip.
- **Cover charge / table minimum:** rare in casual SEA dining; appears in some Bangkok/Singapore upscale or live-music venues. Not a regional norm.
- **Surcharges:** public-holiday surcharges (10–15%) appear in Singapore/Malaysia on festive days; credit-card surcharges are largely banned/uncommon.

### CURRENCY

| Country | ISO | Minor-unit decimals | Symbol(s) printed | Ambiguity | Cash rounding |
|---|---|---|---|---|---|
| Malaysia | **MYR** | 2 (sen) | `RM`, sometimes `MYR` | Low — `RM` is unambiguous | **5-sen rounding** (1¢/2¢ coins withdrawn; bills round to nearest 5 sen) |
| Singapore | **SGD** | 2 (cents) | `S$`, `$`, `SGD` | **High** — bare `$` collapses to USD | 1-cent coin still legal; minimal rounding |
| Thailand | **THB** | 2 (satang) | `฿`, `THB`, `บาท` | Low — `฿` is unambiguous | Satang rarely used; cash effectively rounds to whole baht |

All three are **2-decimal currencies**, so the engine's hardcoded `×100/.../100` cents math (`ReceiptSplitEngine.swift:73,78`) is *granularity-correct* here — SEA does **not** hit the JPY/KRW/BHD minor-unit bug. The SEA-specific currency problem is **symbol resolution and cash-rounding tolerance**, not decimal places.

### What a REAL dining receipt here literally prints

**Malaysia (KL restaurant, ++):**
```
Nasi Lemak Ayam        RM 18.00
Roti Canai              RM  4.50
Teh Tarik               RM  3.50
  Subtotal             RM 26.00
  Service Charge 10%   RM  2.60
  SST 6%               RM  1.72   ← 6% of (26.00 + 2.60), NOT of 26.00
  Total                RM 30.32
  Rounding            -RM  0.02   ← 5-sen adjustment
  Total Due            RM 30.30
```

**Singapore (++):**
```
Subtotal                $ 80.00
Service Charge (10%)     $  8.00
GST (9%)                 $  7.92   ← 9% of (80.00 + 8.00)
Total                    $ 95.92
```

**Thailand (hotel, exclusive):**
```
Subtotal               ฿ 1,200.00
Service Charge 10%     ฿   120.00
VAT 7%                 ฿    92.40   ← 7% of (1,200 + 120)
Grand Total            ฿ 1,412.40
```

### What V1 breaks

- **[P0] Mandatory 10% service charge has no home → routed to `.custom` → poisons reconciliation AND mis-bills.** SEA's universal 10% service charge is neither tax nor tip. On the live V4 path the bridge drops `.serviceCharge`/`.fee`/`.surcharge` outright (`OCRSnapshotBridge.swift:92-98,105-127` — only `.tax`/`.tip` survive); on the persisted path it lands as a `.custom` SummaryItem → `.unknown` extra (`V3ReceiptReconciler.swift:100-101`). A single `.unknown` makes `Reconciler.totalFinding` early-return nil (`Reconciler.swift:69`) — **the entire subtotal+charges+tax==total check is silently skipped** and the diner only sees a generic "Unknown extra" warn chip. *Who's mis-billed:* the whole table — the service charge still rides into `resolvedTotalAmount` via `customExtras` (`ReceiptTotalCalculator.swift:13-19`) and gets spread proportional-by-consumption (`ReceiptSplitEngine.swift:73`), so a heavy eater silently overpays their share of a flat-percentage charge that *should* scale with the bill — close to correct here, but with **no verification** that the math closed.

- **[P0] Tax-on-tax ("++") cannot be modeled → reconciliation false-clean or false-mismatch.** `Reconciler.totalFinding` computes `expected = subtotal + Σpositives − Σnegatives` (`Reconciler.swift:70-78`) as a **flat sum** — it assumes every extra is levied on the subtotal independently. A Singapore "++" bill where GST is 9% of (subtotal + service charge) does **not** satisfy `subtotal + serviceCharge + gst == total` under flat addition only if the service charge is mis-kinded; when the service charge becomes `.unknown` the check is skipped entirely (see above). There is no ordered/based-charge concept anywhere in the model (`SummaryItemType` = `{custom,tip,tax,total,subtotal}`, `ReceiptItemsFixer.swift:444-450`). *Who's mis-billed:* nobody on the split ratio (proportions are pure), but the **"Total amount verified ✓" trust signal is wrong** — it either never fires or fires on math it didn't actually validate.

- **[P1] Thailand VAT-inclusive prices get tax DOUBLE-ADDED.** Small Thai shops print one VAT-inclusive price and either omit a VAT line or print VAT "for reference." If OCR extracts that reference VAT line as a `.tax` extra, `ReceiptTotalCalculator.calculatedTotal = itemSum + tax + tip + customExtras` (`ReceiptTotalCalculator.swift:19`) **adds the 7% a second time** — there is no inclusive-tax flag. *Who's mis-billed:* every participant, over-billed by the full 7% in proportion to consumption.

- **[P1] Singapore bare `$` silently resolves to USD (~1.35× error).** `Currency.inferCurrencyCode` maps `"$"` → USD unconditionally (`Currency.swift:54-55`). `isAmbiguousSymbol` flags `$` (`Currency.swift:105-109`), so the country-region layer *can* rescue it — but **only if Azure DI returns `MerchantAddress.countryRegion == "SG"/"SINGAPORE"`** (`Currency.swift:124`). When the address is missing/unparsed, the receipt formats every per-head amount as USD, and if it lands in a multi-currency trip the FX engine converts SGD amounts as if they were USD. *Who's mis-billed:* everyone, by the SGD/USD spread (~35%), the moment a settlement conversion runs.

- **[P1] `"S$"` multi-char symbol is not in the symbol table → falls through to folder default.** `inferCurrencyCode` has no `"S$"` case (only `"S/"` → PEN at `Currency.swift:90`; `"RM"`→MYR and `"฿"`→THB *do* exist at lines 86-87 and 76-77). A Singapore receipt that prints the explicit `S$` glyph — the *unambiguous* form — is **not** recognized by the symbol tier and only resolves correctly if `apiCode` or `countryRegion` carries it; otherwise it terminates at `nil` (`OCRSnapshotMapper.swift:148`) and coerces to USD via `effectiveCurrencyCode` (`Receipt.swift:297-306`). *Who's mis-billed:* same as above — the most explicit Singapore signal is the one the symbol tier ignores.

- **[P2] Malaysia 5-sen cash rounding trips the reconciler.** The −0.02/−0.03 "Rounding" line means `subtotal + service + SST` ≠ printed `Total Due` by up to ±0.02. `Reconciler.matchThreshold = 0.01` (`Reconciler.swift:34`); a 5-sen (0.02–0.04 MYR) rounding adjustment exceeds it and emits a `.sumOfItems`/`.totalMismatch` finding. The rounding line itself, if captured, becomes a `.custom`→`.unknown` extra and poisons the total check. *Who's mis-billed:* nobody monetarily (≤RM0.05), but a false "Check totals / Totals don't match" chip erodes trust on a receipt that is actually correct. The thresholds are currency-blind absolute Doubles with no cash-rounding awareness.

- **[P2] Stacked service-charge + tip both forced through one `.tip` slot.** If a SEA diner adds a discretionary tip on top of the mandatory 10% service charge, V1 has exactly one `tipItem` (`Receipt.swift:248-262`); the two collapse into a single value or one is dropped into `.custom`. The tip-base calculation (`SummaryItemCalculator.calculatedTip`, base = subtotal or subtotal+tax) cannot express "tip on top of an already-service-charged bill." *Who's mis-billed:* low impact — extra tipping is rare in SEA — but the model conflates a mandatory charge with a discretionary one.

### Scan priority: high

A single real Malaysian or Singaporean "++" receipt would be the **highest-value addition to the catalog** — it is the only place in the corpus that exercises **tax-on-tax stacking**, a **mandatory non-tip service charge**, and (for Singapore) **bare-`$`/`S$` ambiguity** all on one document. The corpus today has zero SEA receipts and the entire regime is reasoned-only; a Thai VAT-inclusive small-shop receipt would additionally ground the inclusive-tax double-add (P1) that no scanned receipt currently demonstrates. Priority order if only one can be obtained: **Singapore ++ (ambiguity + tax-on-tax) > Malaysia ++ (tax-on-tax + 5-sen rounding) > Thailand VAT-inclusive**.

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

API Error: Server is temporarily limiting requests (not your usage limit) · Rate limited

---

