# Completeness Critic — What the 102 Cases + 11 Regimes Missed (P9 pass 3)

> Source: workflow `wj9n3in15`. 8 critics, each hunting a distinct blind spot. PLANNING ONLY.

Confirmed: `calculatedTotal = itemSum + tax + tip + customExtras` — purely additive, single tax bucket, no exemption logic, no negative/credit handling in the tax slot. This is the additive-total root cause the grounding already names, but it also confirms there's no path for tax-exempt items, deposits as credits, or refundable fees.

Let me do one final check on whether `customExtras` can be negative (credits/deposits) and whether the `discount`/`credit` extra kinds are dropped at the bridge (already confirmed dropped at OCRSnapshotBridge.swift:96-98). I have enough verified evidence. Writing the critique.

## tax-modalities-missed

Scope note: I verified all citations against the canonical repo at `/Users/leokwan/Development/resplit-ios` (not worktrees). The structural truth behind every case below: V1 carries exactly **one** tax scalar (`Receipt.taxItem`, a single `MultiSourceAmount` — `SummaryItem.swift:167-187`), there is **no per-item taxable/exempt/zero-rated field** anywhere in `OCRLineItem` or `ScannedLineItem` (grep returned zero `taxable`/`exempt`/`zeroRated`/`taxRate` matches), and the total is **purely additive** — `ReceiptTotalCalculator.calculatedTotal = itemSum + tax + tip + customExtras` (`ReceiptTotalCalculator.swift:5-19`). The split engine then apportions that total by item-amount proportion (`ReceiptSplitEngine.swift:43-76`). Tax-typed line items the OCR sees get summed into the one tax bucket at the bridge (`OCRSnapshotBridge.swift:94-95`); everything that isn't `.tax`/`.tip` is **dropped** (`OCRSnapshotBridge.swift:96-98`). That single fact is what makes most of the cases below either silently mis-billed or invisible.

The grounding already covers: additive-total, proportional apportionment, cents-hardcoded money, `currencyCode:nil`, dropped post-tax extras, inclusive-tax double-add, multi-tax/tax-on-tax, service-charge/surcharge/cover/deposit-credit as *dimensions*. So below I only surface **tax-type-specific modalities** the prework's region/dimension grid does not name, and I flag honestly where my assigned blind-spot list overlaps something already cataloged.

---

### 1. Multi-jurisdiction stacked sales tax (state + county + city + special-district), all on the same receipt — P1, scales by proportion

**Receipt:** A Chicago restaurant prints `Sales Tax 6.25% (IL state)`, `County 1.75%`, `City 1.25%`, `Special MPEA Restaurant Tax 1.00%` as four separate lines = ~10.25% combined. This is the US single-receipt analog the grounding's "multi-tax" dimension gestures at but does not name as a *domestic US local-stack* (the grounding frames multi-tax around GCC/India/EU regimes).

**What V1 does today:** The OCR provider may emit four `ScannedExtra(kind: .tax)` rows. At `OCRSnapshotBridge.swift:94-95` all `.tax` extras are **summed into one** `OCRSnapshot.tax` scalar. Net math is *correct* here — the four sum cleanly into one bucket and apportion by proportion.

**Who's mis-billed:** Nobody, money-wise. **The broken trust signal is auditability**: the user sees `Tax $4.10` where the paper receipt shows four distinct lines. When a friend disputes ("why is tax so high?"), the app cannot reproduce the receipt. **Severity P1** for trust, P3 for money. **Scales by proportion** — no new mode needed; needs a display/breakdown affordance, not new math.

---

### 2. Tax-exempt vs zero-rated items on a mixed receipt (grocery/pharmacy/some restaurants) — P0, CANNOT scale by proportion, needs new mode

This is the single most damaging case in my blind-spot list and it is **genuinely not covered** by the grounding (the grounding's dimensions are about *extra* lines, not about *which items the tax applies to*).

**Receipt:** A US convenience-store/grocery split: `Sandwich $8.00` (taxable, prepared food), `Bottled water $2.00` (tax-exempt grocery in many states), `OTC Tylenol $6.00` (exempt in NY/NJ), `Beer $10.00` (taxable + alcohol surtax). Subtotal $26.00, but tax of, say, $1.44 applies only to the $18 taxable base.

**What V1 does today:** Tax is one scalar with no item linkage (`SummaryItem.swift:167`; no `taxable` field exists). The split engine apportions the *whole* total by *each item's gross amount* (`ReceiptSplitEngine.swift:73`). So the person who ordered only the exempt water + Tylenol ($8 of items) is charged `8/26 × $1.44 = $0.44 of tax they legally never incurred`. The beer-and-sandwich person is **under**-charged the tax they did incur.

**Who's mis-billed:** The exempt-item buyer overpays; the taxable-item buyer underpays. Real money, every grocery/pharmacy split. **Severity P0** — this is silent and systematic, exactly the "additive total hides a per-item truth" failure class.

**Scaling:** **Proportion-by-gross-amount is the wrong proportion.** The contract says "proportion is truth, equal-split is the default proportion" — and that's right — but the *correct* proportion for tax here is **proportion-of-the-taxable-base**, not proportion-of-total. V1 has no taxable flag to compute that base. This needs a **new mode / new field** (`isTaxable` per item), or at minimum a per-item tax-apportionment that excludes flagged-exempt lines. Cannot be fixed by reusing equal-split.

---

### 3. Bottle deposit (CRV / state container deposit) and bag fee — P1, partially a *credit-sign* problem, needs handling decision

**Receipt:** California: `Sparkling water 6pk $5.99`, `CA Redemption Value $0.30` (CRV deposit), `Bag Fee $0.10`. New York / NJ bag fee `$0.05`. These are **not tax** — CRV is a refundable deposit, the bag fee is a flat regulatory fee.

**What V1 does today:** If the OCR tags CRV/bag as `.fee` (the natural mapping), `OCRSnapshotBridge.swift:96-98` **drops it entirely** — it never reaches `OCRSnapshot`. The receipt total then won't reconcile (`total != itemSum + tax + tip`), tripping the `total != balance_due` mismatch the grounding already flags. If instead the user manually adds CRV as a custom extra, it's apportioned by proportion across *all* participants (`ReceiptTotalCalculator.swift:14-16` folds `customExtras` into total), even though only the water-buyer incurred the deposit.

**Who's mis-billed:** Either the deposit vanishes (total mismatch, trust break) or it's spread to people who didn't buy the deposit-bearing item. **Severity P1.** Bag fee is trivial money but CRV on a case of drinks ($1.20–$2.40) is real.

**Scaling:** CRV scales by proportion *if and only if* it's attributed to the deposit-bearing item, not the whole bill — same defect as exempt items (case 2). The `.fee` kind already exists in `ScannedExtraKind` (`ScannedReceipt.swift:121`) but is dropped at the bridge. Needs the Reconciler (P3) the bridge comment promises, plus an item-attribution decision. **New mode-ish** (item-attributed fee), not pure proportion.

---

### 4. Tourism / occupancy / health-mandate levies — SF Healthy-SF surcharge, hotel occupancy tax, resort/tourism fee — P1, scales by proportion but mislabeled

**Receipt:** A San Francisco restaurant: `SF Mandate 5%` (Healthy SF employer health surcharge) printed as a separate line; or a hotel folio with `Occupancy Tax 14%` + `Tourism Assessment 1.5%` + `Resort Fee $35`.

**What V1 does today:** The `.mandate` kind exists in the enum (`ScannedReceipt.swift:123`) specifically for this — and it is **explicitly dropped at the bridge** (`OCRSnapshotBridge.swift:96-98` lists `.mandate` among the dropped kinds). So the SF health surcharge silently disappears, the total won't reconcile. If the OCR instead lumps it into `.tax`, it's summed correctly (case 1 behavior) and apportions fine.

**Who's mis-billed:** When dropped: total mismatch, the surcharge is eaten by nobody and the math breaks. When mis-tagged as tax: math is fine but the label is wrong. **Severity P1** — SF surcharges are 5% of the bill, not rounding noise; for a hotel the resort fee is flat-per-room and arguably shouldn't be split by food proportion at all.

**Scaling:** A *percentage* mandate (SF 5%) scales cleanly by proportion. A *flat* resort/tourism fee (`$35/night`) does **not** — it should be equal-split (everyone benefits equally), which is exactly the contract's "equal-split is the default proportion." So this splits into two sub-cases: percentage-mandate = scales by gross proportion; flat-mandate = equal-split. V1 currently does neither because `.mandate` is dropped.

---

### 5. Sin / alcohol / soda surtax (item-specific excise) — P1, CANNOT scale by gross proportion

**Receipt:** `Beer $10.00`, `Liquor $14.00`, `Soda $3.00`, `Burger $12.00`, then `Alcohol Surtax 10% $2.40`, `Philadelphia Soda Tax $0.06` (often built into the soda price but sometimes a line), plus base sales tax. Several states/cities (Chicago, Philly, Seattle, WA spirits) apply excise *only* to alcohol or sweetened beverages.

**What V1 does today:** If line-itemized as `.surcharge` → **dropped** (`OCRSnapshotBridge.swift:96-98`). If folded into the one tax scalar → apportioned across *all* diners by gross proportion (`ReceiptSplitEngine.swift:73`), so the teetotaler subsidizes the drinkers' alcohol surtax.

**Who's mis-billed:** The non-drinker overpays the alcohol surtax; the soda-abstainer overpays the soda tax. Real money, common at group dinners. **Severity P1** (P0 if alcohol is a large fraction of the bill — at a bar tab the excise can be $5–15).

**Scaling:** Same shape as exempt items (case 2) — this is an **item-restricted tax** and the correct proportion is "proportion of the alcohol/soda subset," not proportion of total. **Needs item-attribution mode**, cannot reuse gross-proportion.

---

### 6. Duty-free / airport / tribal-land / Indian-reservation receipts — tax-absent regime — P2, scales by proportion (degenerate), but breaks reconciliation heuristics

**Receipt:** Duty-free shop (no tax line at all), an airport restaurant in a no-sales-tax airport authority, or a smoke-shop/casino on tribal land where state sales tax does not apply. Subtotal == Total, `tax` is genuinely absent/zero.

**What V1 does today:** `tax` is `nil` → no extra is created (`OCRSnapshotBridge.swift:39`, "Nil tax produces no extras"), `calculatedTotal = itemSum + 0 + tip` reconciles, the split apportions cleanly. **Math is actually correct here.**

**Who's mis-billed:** Nobody. **The risk is in V2's planned validators**: any "total != subtotal ⇒ flag missing tax" or "expected-tax-rate" heuristic the splitter-v2 prework introduces will **false-positive** on these legitimately tax-free receipts and nag the user to "fix" a correct scan. **Severity P2** — a future-trust-erosion landmine, not a current money bug.

**Scaling:** Degenerate — proportion works because tax is zero. The catalog action item is "**don't treat tax-absence as an error**," i.e., a guard the v2 validator must carry, not a math change.

---

### Cross-cutting honest note (what's already covered, don't re-litigate)

- **Generic "service charge," "cover charge," "surcharge," "deposit/credit" as dimensions** — already in the grounding's 12-dimension grid. I did **not** re-list those; cases 3/4/5 above are the *specific tax/levy instances* that differ in sign (refundable deposit), attribution (item-restricted excise), or flat-vs-percentage behavior, which the dimension labels alone don't resolve.
- **The drop at `OCRSnapshotBridge.swift:92-98`** is already named in the grounding. I cite it repeatedly only to show *which named tax-types* fall through it (`.fee` CRV/bag, `.mandate` SF-health, `.surcharge` sin-tax) — the bridge drop is the mechanism, these are the casualties.
- **Multi-tax / tax-on-tax** is in the grounding; case 1 (US domestic state/county/city/district stack) is the specifically-American instance that the grounding's GCC/India/EU framing misses, and its failure mode is **auditability, not math**.

### The one structural verdict

Cases 2, 3, 5 share a single missing primitive: **per-item tax attribution**. V1 has no `isTaxable` / `taxCategory` field on `OCRLineItem` or `ScannedLineItem` (verified — zero matches). Until that field exists, "proportion is truth" silently means "proportion of *gross total* is truth," which is the wrong proportion for any item-restricted tax. This is a **new-mode** requirement, not something equal-split or the existing proportional engine can satisfy. It is the tax-side twin of the additive-total root cause — and it is **P0** because exempt-grocery and alcohol-surtax splits are everyday US scenarios that mis-bill real money with zero visible warning.

---

Confirmed. HUF, ISK, CLP are all user-selectable in the picker (and CLF, a 4-decimal unit, plus 3-decimal Gulf currencies BHD/KWD/OMR/TND-class). UGX/PYG are not in the catalog but FX-reachable. All of these flow through the unconditional `* 100` cents math. I have everything I need.

## currency-modalities-missed

Scope note: I confirmed against the real iOS files. Money math is **unconditionally cents** (`ReceiptSplitEngine.swift:73` `(proportion * distributableAmount * 100).rounded() / 100`; remainder at `:78`). `matchThreshold = 0.01` lives at `Reconciler.swift:34`. There is **no `amountPaid` / `tender` / `balanceDue` / `changeDue` field anywhere** — `OCRSnapshot` (`OCRSnapshot.swift:23-64`) and `ScannedReceipt` carry only subtotal/tax/tip/total/extras. `discount`/`credit` extras are **dropped at the bridge** (`OCRSnapshotBridge.swift:96-97`) and never reach the split. The currency picker (`CurrencyPickerCatalog.swift`) exposes **HUF, ISK, CLP, CLF, BHD, KWD, OMR, QAR, SAR, AED** to users today. These facts drive every case below.

---

### 1. Zero-decimal currencies beyond JPY/KRW — the cents-math poisons them (P0)
**Not in grounding.** Grounding's "cents-hardcoded money" line cites the bug generically; the prework never enumerated which *user-reachable* currencies trip it beyond the JPY/KRW it names. **HUF, ISK, CLP are literally in the picker** (`CurrencyPickerCatalog.swift:46-64` region + the AED/ARS/…HUF/ISK enumeration). VND too. UGX/PYG aren't in the picker but are FX-reachable.

**Scenario:** Budapest dinner, total 12,500 HUF, 3 people. Engine does `(0.3333… * 12500 * 100).rounded() / 100` → each owes `4166.67 HUF`. HUF has **no fillér**; "4166.67 Ft" is a nonsense amount no Hungarian can pay or Venmo-equivalent. ISK (1850 ISK / 3 = 616.67 ISK) and CLP (15000 / 3 = 5000.00 — happens to land clean, but 16000/3 = 5333.33 CLP, also unpayable) behave the same.

**V1 today:** `:73`/`:78` round to 1/100 of a unit regardless of currency. Display formatter (`CurrencyAmountFormatter` / `Double.formatCurrency`, `Extensions/Double.swift:3-52`) uses ISO minor-unit digits so the **screen shows `4 167 Ft`** (NumberFormatter snaps to 0 digits) **while the stored owed-amount is `4166.67`** and the remainder-distribution math at `:78-81` balanced on the *wrong* grid.

**Who's mis-billed:** the remainder fix-up adds a sub-unit remainder (e.g. `0.01 HUF`) to the first sorted participant — a phantom that can't exist. Settlement display rounds it away, so **Σ(displayed) ≠ stored total** by up to (n−1) sub-units; trust signal "the splits add up" silently breaks for every zero-decimal table.

**Contract:** Proportion is still truth — this is **not** a new mode. The fix is making the `100` a per-currency `minorUnitScale` (1 for HUF/ISK/CLP/JPY/KRW/VND, 100 for USD, 1000 for BHD/KWD/OMR). Equal-split default unaffected.

### 2. Three-decimal (and CLF four-decimal) currencies round *too coarse* (P1)
**Not in grounding.** The 12-dimension list names "no/3-decimal" as a *dimension* but the apportionment decision matrix and contract doc assume the cents grid is merely "wrong for zero-decimal." The **opposite-direction** error is uncovered: **BHD, KWD, OMR, TND** are 1000-minor-unit. **CLF (Chilean UF) is 4-decimal** and is in the picker.

**Scenario:** Kuwait City group bill, 7.535 KWD, 2 people. Engine rounds each to `(0.5 * 7.535 * 100).rounded()/100 = 3.77` → **3.77 + 3.77 = 7.54 ≠ 7.535**. The remainder logic at `:78` computes `(7.535 - 7.54)*100 rounded /100 = -0.01`, subtracts a fake fils. Real grid is 7.535 → 3.768 / 3.767.

**Who's mis-billed:** payer is short 5 fils every time the third decimal is non-zero; over a GCC trip these accumulate and the trip-settlement footer won't reconcile to the bank statement.

**Contract:** scale-by-proportion holds; needs the same `minorUnitScale` fix as #1, just scale=1000. No new mode.

### 3. Gift card / voucher / store-credit as TENDER (P0 — silent over-billing)
**Not in grounding.** This is the biggest blind spot. The catalog/regimes docs treat the receipt as **subtotal + extras = total**, and the contract says "proportion is truth." But a **partial gift-card tender is not an extra and not a discount** — it's money *already paid* that reduces the **balance the table actually owes**, while the receipt's `total` still prints the full pre-redemption amount.

**Scenario:** $120 dinner, 4 people, but the host redeems a $50 Starbucks/restaurant gift card at the register. The printed receipt shows `Total $120.00`, then a separate line `Gift Card −$50.00`, `Balance Due $70.00`. Resplit's OCR captures `total = 120`. The split bills 4 × $30. **The host fronted $50 of stored value and is owed it back — they should net pay $20, the table owes the host $50 for the card plus their own $50 cash.** V1 has no concept of this.

**V1 today:** `OCRSnapshot` has no tender/balance field at all (`OCRSnapshot.swift:23-64`). Even if Azure tags the gift-card line, the **bridge drops it** — it maps only `.tax`/`.tip` into snapshot fields and explicitly discards `.discount`/`.credit`/`.fee` etc. (`OCRSnapshotBridge.swift:96-97`). The `total = 120` flows straight to `ReceiptSplitEngine.calculateSplit(totalAmount:)` and gets proportioned.

**Who's mis-billed:** the gift-card holder eats the $50 — they paid stored value AND get billed their full proportional share as if cash. Direct financial harm; this is exactly the "who pays whom" trust the app sells.

**Contract:** **CANNOT scale by proportion.** Proportion governs *consumption* (who ate what); tender governs *who already paid*. These are orthogonal axes. Needs a **new tender/settlement layer**: split the `subtotal+extras` proportionally as today, then subtract pre-paid tender from the payer's owed-to-table balance. A `balanceDue` field + a "who tendered the card" attribution is required.

### 4. Multi-tender / split payment at register (P1)
**Not in grounding.** Distinct from #3: two cards, or cash + card, tendered by **two different diners** at checkout. Receipt prints `VISA …4321 $60.00` and `CASH $60.00` under a `$120` total.

**Scenario:** Two friends each tap a card for half at the terminal because the place won't split the bill, but the *consumption* was 70/30. Resplit proportions 70/30 against `total=120` and tells them to Venmo-settle — but they **already settled 50/50 at the register**, so the correct residual transfer is only the 20-point gap, not the full 30/70.

**V1 today:** no tender capture; the app assumes one payer fronts the whole `total`. The single-payer assumption is baked into SettlementService and the "who fronted it" model.

**Who's mis-billed:** double-counting — diners pay at register, then the app tells them to pay *again* for their full share, ignoring what each tendered.

**Contract:** needs the same tender layer as #3 (per-tender attribution), **new mode**. Proportion still computes the consumption truth; tender reconciliation is the new step.

### 5. Points / miles / loyalty redemption as partial payment (P2)
**Not in grounding.** A loyalty/points redemption line (`Points −2,500 = −$25.00`, or "Rewards $25 OFF") behaves like a gift card economically but is often **attributable to one person's loyalty account**.

**Scenario:** One diner's Chase/airline/cafe points knock $25 off a $100 bill. Receipt total prints $75 (redemption applied as discount) OR $100 with a redemption line. If it prints as a **discount** baked into total → the whole table benefits from one person's points (they get under-credited). If it prints as a separate redemption line → bridge drops it (`:96-97`) and total stays $100.

**V1 today:** if Azure classifies it `.discount`/`.credit`, the bridge drops it and the Reconciler's `negativeKinds` math (`Reconciler.swift:71,77`) would have used it for *validation only* — never for attribution. Either way the points-holder isn't credited.

**Who's mis-billed:** the loyalty-account owner subsidizes the table with personal points and gets nothing back.

**Contract:** **attribution is the gap, not proportion.** If the redemption lowers the shared subtotal, proportional split is *arguably* fair (the deal applied to the order). The real failure is the **dropped line** + no "this credit belongs to person X" attribution. Borderline new-mode; minimum fix is stop dropping `.credit`/`.discount` and let UI attribute.

### 6. Thousands-separator-as-decimal locale: `1.234,56` mis-parsed (P0 if app-side, P1 if provider-side)
**Not in grounding.** The international-regimes doc covers EU/Brazil *regions* but not the **numeric-format collision**: in de-DE, es-ES, pt-BR, id-ID, much of EU, `1.234,56` means one-thousand-two-hundred-thirty-four point five-six, and `1.234` can mean **1234**, not 1.234.

**Scenario:** German receipt `Summe 1.234,56 €`. If any path parses this with a US/invariant `Double()` or a `.` decimal assumption, `1.234` → **1.234** (a ~1000x under-read) or `1.234,56` fails to parse → `total = nil`.

**V1 today:** I confirmed the app does **not** string-parse line-item/total amounts itself — it trusts Azure DI's typed `valueCurrency.amount` (no in-app `Double(string)` for amounts; the only `Double(...)` in OCR is `Reconciler.swift:59` on quantity). **So the risk is provider-side**, and the one app-side parser, `Currency.isMoney` (`Currency.swift:27-50`), hardcodes `\\d*\\.\\d{2}` — **only a `.` decimal with exactly two trailing digits**. A `1.234,56` or zero-decimal `1234` string fails `isMoney` entirely → any heuristic gated on `isMoney` (manual-entry validation, OCR fallback text scan) rejects valid European/zero-decimal amounts.

**Who's mis-billed:** `isMoney` false-negatives block legit amounts in comma-decimal locales and **all zero-decimal currencies** (no `.\d{2}` ever present in `1850 ISK`). Trust signal: manual-entry validation and any text-fallback parsing silently reject correct money.

**Contract:** parsing fidelity, not apportionment — orthogonal to proportion. Fix `isMoney` to be locale-aware (or delete it if dead). No new split mode.

### 7. CHF / AUD / NZD cash-rounding (Swedish/nickel rounding) (P2)
**Not in grounding.** CHF is in the picker; AUD/NZD are FX-reachable. These have **cash-rounding to 0.05** (CHF Rappen; AUD/NZD nickel rounding) — the *card* total may be `23.47` but the *cash* total prints `23.45`. More acutely: a per-person proportional share of `7.823` should round to `7.80` or `7.85` for cash settlement, not `7.82`.

**Scenario:** Zürich lunch, 71.40 CHF cash, 3 people → engine yields 23.80 / 23.80 / 23.80 (clean here), but 71.35 / 3 = 23.783 → engine rounds to `23.78`, which **can't be paid in Swiss cash** (no 1-Rappen coin since 2007; smallest is 5 Rappen).

**V1 today:** no nickel-rounding anywhere (`grep` for `0.05`/`smallestDenomination`/`Rappen` → zero hits in math files). The cents grid produces unpayable cash amounts.

**Who's mis-billed:** nobody is *over*-billed in cents, but cash settlement is impossible at the displayed precision — a usability/trust break for CHF/AUD/NZD cash splits.

**Contract:** scales by proportion, but the *rounding grid* becomes a **per-currency, per-tender** concern (card = 0.01/0.05/1.0; cash = nickel for CHF/AUD/NZD). Not a new split mode; an extension of the `minorUnitScale` idea to a `cashRoundingIncrement`. Lower severity because card-settle (the common case) is fine.

### 8. Crypto / stablecoin tender (P3 — explicitly out of scope, flagging for completeness)
**Not in grounding.** A receipt settled in USDC/BTC (increasingly seen in crypto-friendly cafes) prints an 8-decimal (BTC) or 6-decimal (USDC) amount. The cents grid truncates BTC to 0.01 BTC (≈$600+ rounding error).

**V1 today:** no crypto currency code in the catalog; symbol map (`Currency.swift:52-98`) has no `₿`. Such a receipt falls through to USD-default or nil currency.

**Who's mis-billed:** N/A in practice — these receipts can't be ingested coherently today.

**Contract / verdict:** **Out of scope for V2.** Crypto is not in the supported-currency set and shouldn't be a splitter-V2 line item. Flag-and-skip; document as a non-goal so it doesn't reappear as a "missed dimension."

---

### Honesty pass — what's genuinely already covered, move on
- **Multi-currency / FX axis** (mixing JPY receipt into a USD trip): already a named dimension and there's real FX infra (ResplitFXScanProvider, currency-api). Not re-listing.
- **`discount`/`credit` extras being dropped at the bridge**: the *drop itself* (`:96-97`) is already in grounding ("dropped post-tax extras"). My **new** angle is narrow: those same kinds, when they represent **tender/redemption rather than a price reduction**, need *attribution* not just retention — that's cases #3/#5, not a restatement of the drop.
- **Inclusive-tax double-add, tax-on-tax, total!=balance_due**: covered. Note #3's `Balance Due` is a *different* `balance_due` — it's tender-reduced, not tax-reduced. Don't conflate.

**Severity roll-up:** P0 = #1 (zero-decimal cents poison, user-reachable today), #3 (gift-card tender over-bills the holder), #6 (`isMoney` rejects EU/zero-decimal). P1 = #2, #4. P2 = #5, #7. P3 = #8 (non-goal). The single highest-leverage structural gap: **#3/#4 prove `total` ≠ "what the table owes the payer" — the splitter needs a tender/settlement axis orthogonal to the proportion axis, and the contract's "proportion is truth" is necessary but not sufficient once stored-value or split tender enters.**

---

Confirmed. `amountOwed` is **purely derived** from the engine's consumption-proportion split — there is no stored, user-overridable per-person amount. The only two social levers in the entire system are (1) item assignment (proportion) and (2) the single `isPayer` flag. This is the decisive fact for the whole audit.

I now have everything needed. All code citations are verified against `/Users/leokwan/Development/resplit-ios`. Producing the markdown.

## split-mechanics-missed

**Framing — verified against `/Users/leokwan/Development/resplit-ios`.** The prework cataloged *what's on the receipt* (taxes, extras, currencies). It never cataloged *the social geometry of who actually pays whom*. V1's entire settlement model exposes exactly **two levers**, and nothing else:

1. **Consumption proportion** — item assignment (`ReceiptItemDTO.sharedEqually` / `participantIds`, `ReceiptSplitEngine.swift:26-41`). This is the "proportion is truth" axis. `amountOwed` is a **purely derived** value (`ReceiptSplitCalculator.amountOwed(by:)` → `cachedSplitResult` only, ReceiptSplitCalculator.swift:198-206). There is **no stored, user-overridable per-person amount field** anywhere in the model — I checked.
2. **A single payer flag** — `ReceiptParticipant.isPayer: Bool?` (ReceiptParticipant.swift:14). `SettlementService` resolves it with `receipt.participants.first(where: { $0.isPayer })` (SettlementService.swift:43) and credits that **one** person the **whole** `receiptTotal` (SettlementService.swift:324-325, 481-482).

Every "split mechanic" below is a real human payment arrangement that maps onto **neither** lever. The proportion contract ("proportion is truth, equal-split is default") governs *consumption*; it says nothing about *who is liable for whose consumption* or *who actually fronted the cash*. That is a second, orthogonal axis the prework never named. This is the structural gap.

---

### [P0] One person treats / covers another ("I've got you", grandma pays for the table)

- **Scenario:** Family dinner. Dad covers his two kids' meals. Or a date where one person insists on paying for the other's $24 entrée. The receipt is real; the *consumption* is correctly Kid-A's burger, but the *liability* belongs to Dad.
- **V1 today:** No "X covers Y" relation exists. The only workarounds are both lies: (a) re-assign Kid-A's items to Dad — which **corrupts the proportion** (Dad now shows as having "consumed" the burger; per-person stats, item history, and any future audit are wrong), or (b) leave items truthful and Kid-A appears in the debt graph owing the payer (SettlementService.swift:51-59), so Dad's gift never registers and the app tells a non-paying kid to Venmo someone.
- **Trust break:** The app contradicts what actually happened at the table — the single most corrosive failure for a bill-splitter. Either the proportion lies or the settlement lies.
- **Scales by proportion?** **No.** This is a *liability reassignment*, orthogonal to consumption. Needs a new model concept: a per-participant "covered by → personId" link applied *after* the proportional split, so the consumption proportion stays truthful while the debt is redirected. This is the single highest-leverage missing primitive — birthday-free and kids-share (below) are special cases of it.

### [P0] Multiple payers / split the actual payment (two cards, "we'll each put down $50")

- **Scenario:** Bill is $180. Two people each hand the server a card; server splits the *tender* $90/$90. Or three friends each throw in cash. The consumption split is unchanged, but **two+ people fronted money**.
- **V1 today:** `isPayer` is a single Bool and `SettlementService` takes `.first(where: { $0.isPayer })` (SettlementService.swift:43) and credits **one** person the full `receiptTotal`. A second payer's contribution is **structurally unrepresentable** — only one creditor can exist per receipt.
- **Who's mis-billed:** The second payer is silently turned into a *debtor* (they consumed, so they "owe" the first payer), even though they paid cash at the table. They get told to pay money they already paid.
- **Scales by proportion?** **No.** Needs `isPayer: Bool` → `amountPaid: Double` (or a payments array) per participant, so the debt graph nets *paid* against *owed*. The greedy netter (SettlementService.swift:495+) is already a multi-creditor algorithm; it's starved by the single-payer input upstream.

### [P0] Someone pays, then is reimbursed out-of-band (Venmo'd already / paid me back in cash)

- **Scenario:** Trip folder. Leo fronts the $400 hotel; mid-trip Nicole hands him $200 cash. The folder still shows Nicole owing $200 against that receipt.
- **V1 today:** No "mark settled / partial payment received" state. `isPayer`/`amountOwed` are the only inputs to `calculateNetBalances` (SettlementService.swift:470-491); an out-of-band repayment has nowhere to live. The debt graph keeps surfacing a debt that's already paid.
- **Trust break:** Trip settlement nags people for money already exchanged — the classic "the app is wrong, stop using it" moment for group trips (Resplit's actual differentiator).
- **Scales by proportion?** **No.** Needs a settlement-ledger concept (recorded payments / "mark as paid" that subtracts from the net balance) layered *on top of* the proportional engine. Orthogonal to the split math entirely.

### [P1] Uneven custom % split (60/40, "I'll take 70% since it was my idea")

- **Scenario:** Two roommates split a $200 grocery run 60/40 by prior agreement, not by who-ate-what. Or business partners splitting a client dinner by equity stake.
- **V1 today:** There is **no per-participant weight/percent field** (I grepped — `percent` exists only on `TipOption`, SummaryItemCalculator.swift:22). The *only* way to express 60/40 is to fabricate fake line items sized to hit those ratios, which destroys the item-level truth and any receipt-reconciliation invariant.
- **Who's mis-billed:** Nobody numerically if they hand-tune fake items, but the receipt becomes fiction and the ZERO_SUM/reconcile invariants (ReceiptSplitCalculator.swift:114+) now guard a lie.
- **Scales by proportion?** **Partially — this is the one that *fits* the contract.** A 60/40 split *is* a proportion (0.6/0.4). The contract says proportion is truth and equal-split is the *default* proportion — a custom-weight mode is just "let the user set the proportion directly instead of deriving it from items." This needs a **per-participant manual-weight override** that feeds `proportionByParticipant` directly, bypassing item derivation. It's the cleanest fit to the existing engine but the field doesn't exist yet.

### [P1] Birthday person eats free / guest of honor exempt

- **Scenario:** 6-person birthday dinner, $300. The birthday person pays nothing; the other 5 absorb their share, typically equally (+$10 each) or proportionally.
- **V1 today:** Setting the birthday person's items to "shared equally" still charges them; un-assigning their items makes those items **orphans** ("Won't count toward totals", ReceiptSplitEngine.swift:53-63), so their food *vanishes from the bill* and the table is **under-billed by their consumption** — the payer silently eats it. To do it right you'd have to redistribute their items onto the other 5 by hand.
- **Who's mis-billed:** Either the payer eats the birthday meal (orphan path) or the other 5 are under-distributed.
- **Scales by proportion?** **No, not natively** — it's the "cover" primitive again (the table collectively covers one person, proportion → 0 for them, redistributed to the rest). This is the **same edge the prework's flat-cover/proportion-0 case warned about, but from the opposite direction**: there, a 0-consumption person still *owes* a flat cover; here, a full-consumption person owes *nothing*. Both require the engine to handle a participant whose owed amount is decoupled from their consumption. Genuinely a new mode (exempt/redistribute), built on the same "covered-by" primitive as P0 #1.

### [P1] Tip-out to staff / cash left on table not on the receipt

- **Scenario:** Printed total is $100. The group leaves an extra **$20 cash tip** on the table that never appears on the receipt. Real money out of one person's pocket.
- **V1 today:** Tip is modeled only as a `TipOption` percent **of the printed subtotal/total** (SummaryItemCalculator.swift:22-23, "% of subtotal+tax"). An **off-receipt cash amount fronted by one person** has no field — it's neither a line item nor a TipOption value, and it inflates what one payer actually laid out vs. what the engine thinks the total is.
- **Who's mis-billed:** Whoever dropped the cash tip is under-credited by $20 in the settlement; the reconcile gate may also flag the receipt as mismatched.
- **Scales by proportion?** **The distribution does** (the $20 splits by proportion like any extra), **but the *funding* doesn't** — it's a payment one person made off-receipt, so it needs the same `amountPaid`/off-receipt-contribution concept as the multi-payer case (P0 #2). A flat-amount manual tip input would also cover the cash-on-table case.

### [P2] Round-up-for-charity / "just make it $100" overpayment

- **Scenario:** Bill is $94.50; the group rounds the payment to $100, the $5.50 goes to a charity round-up or is just a generous tip. Or everyone agrees to pay a round $20 each on a $94.50 check.
- **V1 today:** No round-up primitive. A charity round-up line would have to be a fake item; "everyone pays a round number" can't be expressed because shares are *derived* down to the cent (ReceiptSplitEngine.swift:73, remainder logic :78-81) — the user can't say "round my share up." The remainder-distribution logic even *fights* this by forcing exact-to-the-cent sums.
- **Who's mis-billed:** Low stakes (small amounts), but the derived-cents model can't represent a deliberately-rounded payment, so the settlement won't match the cash that changed hands.
- **Scales by proportion?** **No.** A round-up is an *additive flat extra* (splits fine by proportion) **plus** an optional per-person rounding-of-owed-amount. The first half fits the extra-taxonomy work already cataloged; the per-person rounding is new but minor. **P2 — lowest leverage of the set.**

### [P2] Kids share a parent's portion / shared plate among a subset

- **Scenario:** Two kids split one $12 kids' meal; or three people share one $40 appetizer platter while the 4th doesn't touch it.
- **V1 today:** **Subset-sharing is actually already expressible** via `item.participantIds` with `sharedEqually == false` (ReceiptSplitEngine.swift:32-39) — assign the platter to the 3 sharers, it splits 3 ways among them. **This case is largely covered by the existing item-level mechanic.** The genuine gap is only the *liability* layer: if the kids' shared meal should bill to a *parent* rather than the kids, that's P0 #1 (cover) again, not a splitting gap. And there's no *fractional quantity* (½ portion) concept — but equal-split-among-claimers already handles "share one item N ways," which is the common case.
- **Scales by proportion?** **Yes — already does.** Flag this as **mostly-covered**; only the parent-pays-for-kid liability redirect is missing, and that's the cover primitive, not a new split mode.

### [P2] A guest with no app account (one-off diner, the friend who'll never install Resplit)

- **Scenario:** 5 people at dinner, one is a random plus-one who won't get the app. They still consumed $30 and owe the payer.
- **V1 today:** **Partially covered** — participants exist as `ReceiptParticipant` (name + optional `cnContactId`, ReceiptParticipant.swift:9-15) without requiring a `Person`/account; the comment "Link to Person entity (only for new receipts)" (:27) confirms account-less participants are a supported shape. So the *split math* works. The gap is **collection/notification**: the debt graph (SettlementService.swift:51-59) emits a transaction "Guest owes Payer $30," but a no-account guest can't receive a payment-request push, can't be charged, and may never reconcile — so the trip settlement carries a permanently-open balance the payer can't action.
- **Who's mis-billed:** Nobody numerically — but the settlement *never closes* for that guest, and the payer has no in-app way to mark "they paid me in cash" (which loops back to the P0 #3 reimbursement gap).
- **Scales by proportion?** **Yes for the math** (already does). The gap is **settlement lifecycle / mark-as-paid for non-account participants**, not split mechanics. Flag as **mostly-covered; real gap is the reimbursement-ledger (P0 #3)**.

---

### The one missing axis (synthesis)

Six of these nine (the three P0s + birthday-free + tip-out + the liability half of kids-share) are **not** patchable by the proportion contract because they live on a **second axis the prework never modeled: payment & liability, separate from consumption.** Concretely, two model primitives are absent and would resolve most of them:

1. **`amountPaid` per participant** (replace the single `isPayer: Bool`) — unlocks multi-payer, off-receipt cash, tip-out funding, and feeds the already-multi-creditor greedy netter (SettlementService.swift:495+) properly.
2. **A "covered-by → personId" / liability-redirect** applied *after* the proportional split — unlocks treat/cover, birthday-free, and parent-pays-for-kid, while keeping the consumption proportion truthful (no fake-item corruption).

Only **custom-% (P1)** genuinely fits "proportion is truth" — it's a manual proportion override and belongs in the engine. **Kids-share, no-account-guest, and round-up's distribution half are mostly already covered** by existing item-level / participant mechanics; their residual gaps (liability redirect, mark-as-paid) collapse into the two primitives above. The honest verdict: the prework's "proportion is truth" contract is correct but **incomplete as a splitter spec** — it has no statement about *who is liable* or *who paid*, and that omission is where every P0 social mechanic falls through.

---

I have verified all the load-bearing code paths. `ReceiptItem.amount` is a non-optional `MultiSourceAmount` (Receipt nil-amount items resolve to 0 via `valueToUse`), folders aggregate receipts with no cross-receipt netting, and `resolvedTotalAmount` precedence is confirmed. I have enough to write the completeness critique.

## parse-data-modalities-missed

Verdict up front: of the 8 candidates in my blind spot, **3 are genuinely already covered** by the grounding (summary-only/EMPTY_ITEMS, voided-as-negative-line, itemized-but-no-prices partial), **1 is half-covered**, and **4 are NOT cataloged at all** and expose a class of failure the 102-case catalog never touched: *the receipt is not the unit of the meal*. The catalog assumes one scan == one bill == one split. Real meals routinely produce zero, two, or N receipts per settlement, and V1's per-receipt additive model has no concept of receipt-to-receipt relationships. That is the structural gap here.

---

### ALREADY COVERED (stating and moving on)

- **Summary-only receipt (total, zero items).** This IS the EMPTY_ITEMS case. Fully owned by `2026-05-31-proportion-is-truth-contract.md` (Claim 2) and catalog P2 line 378 — the `EMPTY_ITEMS_ALL_ZERO → EMPTY_ITEMS_EQUAL_SPLIT` flip. I verified the mechanism: `OCRSnapshotMapper.swift:57-58` returns `[]` when Azure has no items, `ReceiptSplitEngine.swift:47` skips the proportion block on `sumOfRawAmounts == 0`, and lines 83-89 zero everyone. Nothing new to add — except one wrinkle below (pre-auth) that the contract does NOT cover.

- **Voided item reprinted as a NEGATIVE line.** Covered by catalog P1 line 769-774 (negative-line / zero-split guard) and the deposit-credit work. The line-item-discount and void-credit shapes are the same negative-line. Move on.

- **Itemized-but-no-prices (line items, `amount == nil`).** Partially covered: catalog P1 line 854 (Fuzí timeout → 0 items) and the qty/parse-fidelity dimension touch dropped/null lines. I verified the coercion path: `ScannedLineItem.amount` is `Double?` (ScannedReceipt.swift:77), but on the engine side `ReceiptItem.amount` is non-optional `MultiSourceAmount` (ReceiptItem.swift:80), so a nil-price item resolves to **0** via `valueToUse` in `ReceiptTotalCalculator.swift:7`. **What's NOT cataloged:** a receipt where items have *names but no prices* and there IS a scanned total (common on thermal receipts where the price column smears). Today every named item contributes 0, `calculatedTotal` = tax+tip only, and `resolvedTotalAmount` (Receipt.swift:271) returns that **under-counted** calculated total *in preference to the larger scanned total* (line 274 only reached when calculated == 0). So a $200 dinner with 8 priced-but-unreadable items + a clean scanned $200 total bills the table ~$0 + tax. This is a distinct, severe sub-case of the parse-fidelity dimension worth pinning. **[P1]**, scales by proportion once you fall back to scanned-total-over-equal-split (it becomes the summary-only case).

---

### NOT COVERED — the 4 real gaps

#### 1. TWO receipts for one meal (bar tab + dinner check) — no cross-receipt identity or netting
**Scenario:** Table opens a bar tab ($88, 4 people drinking), then moves to a table and the dinner check ($240) is rung separately. Two scans, same 4 (or overlapping) people, same meal. Or: the classic "we paid the bar, they paid dinner, net it out."

**V1 today:** A `Folder` holds `receipts: [Receipt]?` via `@Relationship` (Folder.swift:23-24) and settles by **summing each receipt's `resolvedTotalAmount` independently** — there is no model of "these two receipts are one economic event," no per-person rollup that knows person A was on the bar tab but not dinner, and no netting. Each receipt runs the engine in isolation; the folder concatenates settlement transactions. If the same person is a participant on both, they correctly owe the sum — *but only if they were manually added to both receipts*. There is no de-dup, no "carry participants from receipt 1 to receipt 2," and no awareness that one card paid both (or that different cards paid each).

**Who gets mis-billed / trust break:** The drinker who left before dinner gets billed for dinner if the user lazily copies participants; the dinner-only arrival gets billed for the bar tab. More subtly: when receipt A was paid by Alice's card and receipt B by Bob's, the folder settlement should net (Alice owes Bob the delta), but V1 produces **two separate greedy settlements** that don't net against each other — phantom cross-transactions, the exact inverse-rounding residue problem the catalog flagged for FX (line 280) but here from un-netted same-currency receipts.

**Severity: [P1].** Real, frequent (every bar-then-dinner outing), silent.
**Scale by proportion?** No — this needs a **new mode**: a receipt-group / "one meal, many checks" abstraction with a shared participant roster and a cross-receipt settlement net. Proportion is correct *within* each receipt; the missing layer is *between* receipts.

#### 2. Pre-auth / open-tab total vs final total — stale total split before tip/close-out
**Scenario:** User scans the receipt at the table before the server closes out. The printed total is the **pre-authorization** (subtotal + tax, no tip) or an **open-tab** snapshot. The actual charged total (with tip, or with a corrected item) is higher. Bars print a "pre-auth $50.00" line; many POS print the check *before* tip is added.

**V1 today:** This breaks the EMPTY_ITEMS contract's safety assumption in a way the proportion-is-truth doc does NOT address. `resolvedTotalAmount` (Receipt.swift:265-280) precedence is **user-override > computed-from-items > scanned**. On a pre-auth scan, `calculatedTotal` = itemSum + tax (no tip line exists yet, OCRSnapshotMapper.swift:50 reads `fields.tip` which is nil pre-tip), so the group splits the **pre-tip total** and the card-payer eats the entire tip — *identical outcome to the handwritten-tip case (catalog line 871) but from a different root*: there the tip is ink Azure can't read; here the tip doesn't exist on paper yet because the receipt is temporally premature. The catalog frames handwritten-tip as a *parse* miss; pre-auth is a *receipt-lifecycle* miss. No `.warn` fires because nothing is mismatched — the pre-auth receipt is internally self-consistent (subtotal+tax == printed pre-auth total, Reconciler.swift:67-81 sees `delta ≈ 0`, severity `.clean`).

**Who / trust:** Card-payer silently absorbs 18-22% tip on every pre-tip scan. With equal-split-on-empty now landing (the contract), a *summary-only pre-auth* will confidently split the pre-tip number `total/N` and look correct.

**Severity: [P1].** Common (people scan at the table), silent, and it survives the new equal-split contract clean.
**Scale by proportion?** The split math scales fine — the problem is the *total is wrong/stale*. Needs a **detection signal**, not a new apportionment: a "this looks like a pre-auth / no-tip-yet receipt" heuristic (tip field nil + merchant is bar/restaurant + round-ish total) that prompts "add tip before splitting." Cheap to add as a Reconciler finding kind; today there is no such finding (Reconciler.swift:3-8 has only 4 cases).

#### 3. Merged group check — one receipt that is actually two tables / two parties
**Scenario:** Server merges two reservations onto one check (12-top printed as one bill), or a work dinner where two departments share one receipt but settle separately. One scan, but the *correct* settlement is **two independent splits over disjoint participant subsets**, not one split over 12.

**V1 today:** The engine (ReceiptSplitEngine.swift) takes one `participantIds` array and one item set. It can do `sharedEqually` across ALL participants or individually-claimed subsets — but there's no concept of "sub-table A pays for items 1-8, sub-table B pays for items 9-15, and the shared apps split only within each sub-table." The closest V1 primitive is per-item `participantIds`, which would require the user to hand-assign all 15 lines and all shared apps with no grouping help, and a *single* settlement still nets A against B as if they're one party (one greedy settlement, A may "owe" B).

**Who / trust:** Two parties that should never have a payment edge between them get a phantom A→B transfer. The settlement suggests strangers pay each other.

**Severity: [P2].** Less frequent than bar-tab but real for events/work dinners, and produces *socially wrong* settlement edges (the trust break is "why does it say I owe someone at the other table").

**Scale by proportion?** Partially — proportion is right *within* each sub-table. Needs a **new mode**: receipt partitioning / sub-group settlement boundaries so greedy settlement never crosses a partition. Adjacent to gap #1 (both are "the receipt boundary ≠ the settlement boundary").

#### 4. Voided + REPRINTED whole receipt — duplicate scan, double-billed table
**Scenario:** Server voids the first check (wrong item) and reprints. Customer photographs *both* the voided "** VOID **" copy and the corrected reprint, or scans the reprint into a folder that already has the original. Two near-identical receipts in one folder.

**V1 today:** I confirmed there is **no duplicate/void/reprint detection anywhere** — `ReconciliationFinding` (Reconciler.swift:3-8) has no `duplicate` or `void` case; the Reconciler operates on a *single* `ScannedReceipt` in isolation and never compares two receipts in a folder. A folder with [original $240, reprint $240] sums to **$480** via the independent `resolvedTotalAmount` aggregation — the table is billed **double**. A "** VOID **" banner is OCR'd as merchant noise; the void copy still carries a full total and splits like a live receipt. Nothing flags two receipts with identical merchant + total + timestamp.

**Who / trust:** Entire table double-billed, or billed for a voided amount that was never charged. This is the single highest *magnitude* error in this set — a clean 2× over-bill with zero warning.

**Severity: [P0].** Silent, large-magnitude, money-real, and trivially triggered (user scans both copies because they're unsure which is real).
**Scale by proportion?** No — proportion is irrelevant; the *count of receipts* is wrong. Needs a **new cross-receipt guard**: a folder-level near-duplicate detector (same merchant + total within threshold + close timestamp) → `.warn` "possible duplicate receipt," and void-banner recognition. This is the cross-receipt sibling of the existing single-receipt Reconciler and does not exist today.

#### 5 (bonus, in-scope of "handwritten additions"). Handwritten *item / total* additions, not just tip
The catalog covers handwritten **tip** (line 871) thoroughly. NOT covered: handwritten **split instructions on the receipt itself** ("Sarah's = circled items," "÷3" written across the bill, a handwritten line-item the server added in pen, or a handwritten corrected total over a struck-through printed one). Azure reads the *printed* total (OCRSnapshotMapper.swift:51); a pen-corrected total is invisible, so `resolvedTotalAmount` uses the struck-through printed value — over- or under-billing the whole table. **[P2]**, no new mode needed (it's a parse-fidelity + "prefer corrected total" detection), but it's a distinct data-shape from handwritten-tip and the catalog conflates the two under one entry.

---

### The one-line takeaway for V2 planning
The catalog's 12 dimensions are all **intra-receipt** (everything inside one bill). This blind spot surfaces a missing **13th dimension: receipt cardinality / receipt-to-meal mapping** — zero receipts (summary-only, covered), one premature receipt (pre-auth, P1), one over-merged receipt (group check, P2), N receipts for one meal (bar+dinner, P1), and duplicate receipts (void+reprint, **P0**). Three of these (#1, #3, #4) require a folder/receipt-group settlement layer that does cross-receipt netting, partitioning, and de-duplication — none of which exists; folders today are dumb additive sums of independent per-receipt splits (Folder.swift:23-24 + per-receipt `resolvedTotalAmount`). Proportion-is-truth governs *within* a receipt; it says nothing about *which receipts, how many, and whether they net* — and that is where the next class of silent money errors lives.

---

I now have everything confirmed against the real iOS files. Confirmed facts:
- `mapLineItems` keeps a line item even when `obj.totalPrice` is nil → `amount: nil` (a null-price phantom passes through, named "Item").
- `Reconciler.sumOfItemsFinding` filters out null-amount items (line 56-57), so a null-price item is **invisible** to the subtotal check but still becomes a real `ReceiptItem` in the split.
- No dedup anywhere; no confidence gate; negatives `abs()`'d.
- Severity computed once at apply-time, persisted, chip only renders for warn/error (clean = no chip = implicit green).

Here is my completeness-critic output.

## reconciliation-trust-missed

The grounding nailed `.unknown`-disables-`totalFinding` (Reconciler.swift:69) and the additive/currency/inclusive-tax/balance-due axes. But the "totals verified" signal is a stored `reconciliationSeverity` string (ReceiptSnapshotApplying.swift:272-275) computed **once at scan-apply time** from four findings, and the chip (ReconciliationChip.swift) only renders for `warn`/`error` — `clean` is silent implicit-green. Below are the trust-corruptors that are **NOT** in the grounding. I verified each against `resplit-ios` (not a worktree).

---

### 1. Null-price line item — invisible to reconcile, real in the split [P0]
**Scenario:** Azure returns a line "Wagyu — MKT" with no `totalPrice` (market-price/handwritten items, faded thermal). Common on steakhouse and izakaya receipts.
**V1 today:** `OCRSnapshotMapper.mapLineItems` (OCRSnapshotMapper.swift:60-80) `compactMap` keeps the item with `amount: nil`, names it `"Item"`, and it becomes a real `ReceiptItem` (ReceiptSnapshotApplying.swift:499-512). But `Reconciler.sumOfItemsFinding` **filters null-amount items out** (Reconciler.swift:56-57: `filter { $0.amount != nil }`) before summing. So the item is invisible to the subtotal check → reconciles `clean` → no chip. Then the split engine assigns that $0/nil item a real **proportion** of the table. Whoever claims "Wagyu — MKT" is charged their proportional slice of the *rest* of the bill for a line that should have been the most expensive thing on it — and the trust chip is green.
**Who's mis-billed:** the diner who claimed the priceless item is under-billed; everyone else over-billed; payer eats nothing but the table doesn't reconcile to reality.
**Severity P0** — silent money error with a green signal, and it's the exact item most likely to be expensive.
**Contract:** Cannot scale by proportion as-is — a nil-amount line has no defensible proportion. Needs a new state: a null-price item must either (a) raise a `missingItemAmount` finding (new mode — surface before split) or (b) be excluded from proportion entirely, not silently absorbed.

### 2. Confidence never gates the chip — low-confidence scan reads "verified" [P0]
**Scenario:** Glare/crumple makes Azure return `0.41` confidence on the total and several line amounts, but the numbers it *guessed* happen to satisfy `subtotal + tax + tip == total` (Azure often back-solves a plausible total).
**V1 today:** `ScannedLineItem.confidence` and `ScannedExtra.confidence` exist and are populated (V3ReceiptReconciler.swift:67, OCRSnapshotMapper.swift:72) — but `Reconciler` reads **zero** confidence fields anywhere (grep-confirmed: Reconciler.swift has no `confidence` reference). Severity is purely arithmetic. A 0.41-confidence scan whose hallucinated numbers happen to add up reconciles `clean` → green chip → "totals verified."
**Who's mis-billed:** everyone, by an unknown amount — the arithmetic self-consistency of an OCR *guess* is being sold to the user as verification.
**Severity P0** — this is the deepest one: the chip's literal promise ("verified") is decoupled from whether the OCR was confident in what it read.
**Contract:** Orthogonal to proportion. Needs a new finding/mode (`lowConfidenceScan`) that forces `warn` regardless of arithmetic — the grounding's "verify before split confidence gate" exists as a *sequencing* idea but the catalog never states that **the chip itself ignores confidence today**, which is the concrete bug.

### 3. Duplicate line item — double-counts, reconciles clean if subtotal echoes it [P1]
**Scenario:** Azure emits the same "Margarita $14.00" twice (common when a line wraps across two OCR rows, or a modifier is parsed as its own line). If the printed subtotal already includes both (kitchen rang it twice) it reconciles fine; the dangerous case is when the duplicate is an OCR artifact but the subtotal *also* got mis-summed to match.
**V1 today:** No dedup exists anywhere in `mapLineItems`, the bridge, or the reconciler. Two identical `ReceiptItem`s enter the split. `sumOfItemsFinding` sums both (Reconciler.swift:58-61) — if the subtotal coincidentally equals the doubled sum (Azure's subtotal is itself a guess), it's `clean`.
**Who's mis-billed:** whoever claims that drink pays for two; or if "shared equally," the whole table over-pays by one phantom drink — green chip.
**Severity P1** — needs the subtotal to also be wrong to go fully silent, but the no-dedup gap is real and the split-side double-charge is certain.
**Contract:** Scales by proportion fine *once detected* — but detection needs a new heuristic (identical name+amount adjacency → `possibleDuplicateLine` warn). Proportion can't save you here because both copies are "real" to the engine.

### 4. Negative subtotal / negative total → arithmetic passes, BOUNDED breaks downstream [P1]
**Scenario:** A full refund/void receipt, or OCR reads a leading "-" or parses "($49.45)" accounting-negative. `subtotal = -49.45`, `total = -53.84`.
**V1 today:** `totalFinding` does `expected = subtotal + positives - negatives; delta = expected - total` (Reconciler.swift:78-79) — pure arithmetic, **no sign guard**. A self-consistent negative receipt reconciles `clean`. But the grounding itself notes `SplitEngineEdgeCaseTests` already proves the engine returns proportion 1.25 / −0.25 on a negative item — so a `clean` chip sits on top of a split that then violates BOUNDED. The reconciler blesses a receipt the engine can't safely divide.
**Who's mis-billed:** unbounded — negative proportions mean someone is *credited* and someone *over-charged* arbitrarily, under a green chip.
**Severity P1** — refund receipts are real but rarer than the P0s; the trust break is that `clean` and "engine BOUNDED-violates" coexist.
**Contract:** Cannot scale by proportion (negative proportion is the documented failure). Needs a `negativeTotal`/`refundReceipt` mode that blocks the proportional split path entirely. This is *adjacent to* the grounding's negative-extra note but distinct: the grounding is about a negative *extra* (deposit/credit line); this is a negative *subtotal/total* passing reconciliation, which the catalog doesn't cover.

### 5. Cash-rounding line ("CASH ROUNDING −0.02") — unmodeled, either drops or false-flags [P2]
**Scenario:** CHF/AUD/NZD/CAD receipts print a "Rounding −0.02" / "Rappen rounding" line so the cash total lands on a 0.05 increment.
**V1 today:** There is no `.rounding` case in `ScannedExtraKind` (ScannedReceipt.swift:118-128). Two failure modes: (a) V4 bridge path drops the line (OCRSnapshotBridge.swift:96-98 drops everything but tax/tip) → `total != subtotal+tax+tip` by 0.02–0.04 → that's **under** `matchThreshold 0.01`? No — 0.02–0.04 is *above* 0.01 and *below* `warnThreshold 0.05`, so it surfaces a `warn` chip on a *perfectly correct* receipt (false alarm, trust erosion). (b) V3 path forces it to `.unknown` → disables `totalFinding` entirely (Reconciler.swift:69) → green, but the 2¢ is then dropped from the split (payer eats it).
**Who's mis-billed:** case (b) the payer eats the rounding; case (a) nobody is mis-billed but the chip cries wolf on a clean bill.
**Severity P2** — small money, but it's a *systematic* false-positive/false-negative on an entire class of correct receipts, which trains users to ignore the chip.
**Contract:** Scales by proportion trivially once typed as a tiny `.rounding` extra apportioned proportionally (or assigned to payer). The fix is a taxonomy case + threshold awareness — but note this is a *different* class from the grounding's currency-threshold discussion: here the rounding line is an explicit receipt line item being mishandled, not a float artifact.

### 6. OCR-hallucinated phantom item with a price ("SVC FEE" read off the footer marketing) [P2]
**Scenario:** Azure invents a line from receipt chrome — a loyalty-points line "EARN 250 PTS", a survey URL with a number, or a printed "$5 OFF NEXT VISIT" coupon parsed as a $5.00 line item.
**V1 today:** Phantom enters as a real `ReceiptItem`. If its amount is small enough that `subtotal + tax + tip` still lands within `matchThreshold` of `total` (the phantom is in `items` but the subtotal check only fires when `sum-of-items ≠ subtotal` by >0.01 — and a hallucinated subtotal can echo the hallucinated item), it reconciles. Even when `sumOfItemsFinding` *does* fire (Reconciler.swift:54-65), it produces only a `warn` if delta ≤ 0.05 — a $5 coupon → `error`, but a phantom $0.50 "PTS" line → `warn` at most, and the phantom is still claimable in the split.
**Who's mis-billed:** whoever the phantom gets assigned/shared to pays for a line that doesn't exist.
**Severity P2** — usually caught as a `warn` if the amount is non-trivial, but never *removed*, so the split still includes it.
**Contract:** Can't scale by proportion (a phantom has no rightful owner). Needs the confidence gate (#2) to do double duty — low-confidence solo line near footer → flag for removal, not silent inclusion.

---

### Honest "already covered, moving on"
- **Inclusive-tax double-add, deposit/balance-due, multi-tax, FX/symbol, 3-decimal, fractional-minor-unit, proportion-0 flat cover, EMPTY_ITEMS_ALL_ZERO flip** — all in grounding; not re-listed.
- **`.unknown` disables `totalFinding`** (Reconciler.swift:69) — explicitly the grounding's stated starting point; I extended *past* it.
- The grounding's "verify-before-split confidence gate" exists as a *sequencing recommendation* — but it never states the concrete present-tense bug that **`Reconciler` reads no confidence field at all** (#2) and that the chip's `clean`/absent state is therefore an arithmetic-only claim. That gap is the throughline connecting #1, #2, and #6.

**The meta-finding:** every case above exploits the same structural weakness the grounding under-states — `reconciliationSeverity` is *pure arithmetic self-consistency over only the amounts that survived OCR*, computed once and frozen. It cannot see: items it dropped (#1), how sure OCR was (#2), repeated lines (#3), sign (#4), receipt-printed rounding (#5), or invented lines (#6). A receipt can be internally arithmetic-consistent and still be wrong in all six ways, and today every one of those reads as green.

**Code citations verified against `/Users/leokwan/Development/resplit-ios` (not worktrees):** Reconciler.swift:34-35 (thresholds), :56-57 (null-amount filter), :69 (.unknown bail), :70-81 (typed total check), :101-116 (severity), no `confidence` read; OCRSnapshotMapper.swift:60-80 (mapLineItems keeps null-price); OCRSnapshotBridge.swift:96-98 (drops non-tax/tip extras); ReceiptSnapshotApplying.swift:272-275 (severity persisted once at apply); ScannedReceipt.swift:118-128 (no `.rounding` kind); ReconciliationChip.swift:77-88 (renders only warn/error, no clean state).

---

I now have everything I need. The folder settlement has no per-cent rounding pass (unlike `ReceiptSplitEngine`), no folder roster, no off-app payment concept, and net balances are raw floats filtered at the 1-cent threshold. I have enough verified detail to write the catalog.

## settlement-folder-missed

These are multi-receipt SETTLEMENT cases not in the prework grounding (which is single-receipt apportionment focused: additive-total, proportional split, cents-money, FX-per-receipt, dropped extras, empty-items). All citations confirmed against `ReceiptSplitter/SettlementService.swift` and `ResplitCore/Extensions/Receipt+DTO.swift` on the real iOS tree.

---

### SF-1 — Phantom freeloader: a folder member who paid nothing and consumed nothing silently vanishes
**Scenario:** A 6-person Tahoe trip folder. On every one of the 5 receipts, Dana was added as a participant for completeness but each time her line items were left unassigned (orphans) or she was marked shared-equally on a $0 item — net she owes $0 and never paid. Group expects the settlement screen to show "Dana: settled / owes nothing" as a trust signal that she was *accounted for*.
**What V1 does:** `calculateNetBalances` (`SettlementService.swift:470-492`) sums each person's balance, then `.filter { abs($0.value.balance) > minimumTransactionAmount }` (line 490, threshold `0.01`) drops anyone with a zero net. Dana produces **no `NetBalance`**, so she appears in **zero** settlement transactions. She is invisible on the settlement sheet.
**Who's mis-billed / trust break:** Nobody is mis-billed in dollars, but the trust signal "is everyone here accounted for?" silently fails. A member scanning the settlement list can't tell "Dana was included and nets to zero" from "we forgot Dana." In a friend group, an absent name reads as a bug. There is **no folder-level roster** (confirmed: no roster/attendees concept exists; `Folder.swift` only has `receipts`), so the engine literally cannot assert "all N members are represented."
**Severity:** P2 — correctness is fine; this is a confidence/completeness gap that erodes trust in the net-settlement claim.
**Scales by proportion?** No — proportion is irrelevant for a zero-balance person. Needs a presentation-layer change: settlement output should carry the **full folder member set** (zero-balance included as an explicit "settled" row), not just the non-zero `NetBalance` array.

---

### SF-2 — The payer who wasn't at the meal nets to a CREDITOR with no offsetting debt context
**Scenario:** Folder has receipts A, B, C. On receipt B (a $120 dinner), Marcus is set as `isPayer` because he fronted the card, but Marcus did *not eat* — his `amountOwed` on B is $0 (all items assigned to the 3 who ate). Marcus is also a normal eater on A and C.
**What V1 does:** In `calculateNetBalances` (lines 473-487): for receipt B, Marcus gets `newBalance -= 0` then, because `isPayer`, `newBalance += receiptTotal` (the full $120). Net across the folder, Marcus is a large creditor. The greedy `generateSettlementTransactions` (line 494) correctly produces "X pays Marcus $40, Y pays Marcus $40…". **The math is actually correct here** — paying-but-not-consuming is the canonical "I fronted it" case and proportional/net handles it.
**Trust break:** The math is right but the *explanation* is missing. The settlement row "Marcus is owed $120" has no provenance — a user who knows Marcus skipped dinner reads "owed $120" as "the app thinks Marcus ate $120," i.e. looks like the additive-total bug even though it isn't. `SettlementTransaction` (`SettlementTransaction.swift`) carries no per-receipt attribution.
**Severity:** P3 — output is correct; only the narrative/auditability is thin. Genuinely *mostly covered* by the net-settlement design; flagging it because the **per-receipt drill-down ("why does Marcus net +$120?") does not exist** and that's a real settlement-folder gap distinct from single-receipt apportionment.
**Scales by proportion?** Yes — already handled by net balances. No new mode; needs an audit/breakdown view only.

---

### SF-3 — Cross-receipt identity collision merges or splits the wrong people during netting
**Scenario:** Folder spans a 4-day trip. On receipt 1, "Alex" is a contact-linked participant (`person.stableId` present). On receipt 3, the same Alex was added as a quick manual guest (no contact, just typed name "alex"). On receipt 4 there are *two* people both displayed as "Sam" (Sam Lee, Sam Patel), one of whom has no contact link.
**What V1 does:** Netting keys on `ParticipantDTO.id`, which `Receipt+DTO.swift:12` sets to `participant.receiptDTOIdentityKey` → `person.stableId` if linked, else `canonicalIdentityKey` (`ReceiptParticipant.swift:5-13`). `canonicalIdentityKey` falls back to `"name-<lowercased name>"` (lines 27-38). So:
- Contact-Alex (`stableId`) and guest-alex (`"name-alex"`) net as **two different people** → Alex's true net is split across two ghost rows, both possibly below the `0.01` threshold and dropped, or shown as two separate debtors.
- Two distinct un-linked "Sam"s collapse to the **same** `"name-sam"` key → their balances merge; one Sam can end up paying the other Sam's debt.
**Who's mis-billed:** Real money moves wrong. Merged-Sam case over/under-bills both Sams. Split-Alex case can make Alex appear to owe twice or get dropped entirely.
**Severity:** P0 — this is silent wrong-money-to-wrong-person across receipts, the worst settlement failure class, and it only manifests at the *folder* level (single receipts never net cross-identity).
**Scales by proportion?** No — proportion can't fix identity. Needs an identity-reconciliation pass before netting (a folder-scoped person-merge UI, or a stricter key that refuses to net un-linked name-only matches and instead surfaces "is this the same Alex?").

---

### SF-4 — Mixed-currency folder where one receipt's net is a sub-cent residue gets dropped, leaving the FX total un-reconciled
**Scenario:** EUR + USD folder, base = USD. After converting each receipt at its own date's rate (`multiCurrencyFolderSettlement`, `SettlementService.swift:235`), one person's net balance lands at `$0.004` because FX multiplication of two near-equal opposing legs almost cancels.
**What V1 does:** Net balances are raw `Double`s. The folder path has **no cent-rounding/remainder-distribution pass** — unlike `ReceiptSplitEngine.calculateSplit` which does the `(x*100).rounded()/100` + remainder-to-first dance (`ReceiptSplitEngine.swift:73-81`). The folder filter `abs(balance) > 0.01` (line 340) drops the `$0.004` person, and the greedy matcher uses `min(creditor, debtor)` on un-rounded floats, leaving fractional-cent dust in `creditors[idx].balance` that's swept under `< minimumTransactionAmount` (lines 549-552). Result: **Σ(settlement transactions) ≠ Σ(converted receipt totals)** by up to a few cents, and `convertedTotal` (line 365) won't equal the sum of transaction amounts.
**Who's mis-billed:** Pennies, but the displayed `convertedTotal` vs. the sum of "pay X" rows won't tie out, which a careful user *will* notice on a multi-hundred-dollar trip. The sub-cent person also silently disappears (SF-1 compounded).
**Severity:** P2 — small money, but a visible reconciliation failure (total ≠ sum of transactions) on exactly the high-stakes multi-currency trip the folder feature is sold for.
**Scales by proportion?** Partially — needs the **same banker's-rounding + remainder-distribution discipline the single-receipt engine already has**, applied at folder net-balance time. This is a "port the rounding contract up to the folder layer" fix, not a new mode.

---

### SF-5 — Partial off-app reimbursement already settled in cash/Venmo has nowhere to go; the app double-counts it
**Scenario:** Mid-trip, Jordan Venmos Marcus $50 to "catch up" before the folder is finalized. Later the group opens the folder settlement: the app still shows "Jordan pays Marcus $130" (the full computed net), with no way to record the $50 already moved.
**What V1 does:** **Nothing — there is no concept of a recorded/off-app payment anywhere in the codebase.** Confirmed: grep for `markPaid`/`isPaid`/`reimburse`/`recordPayment`/`settledOffApp`/`paidOffApp` across `ReceiptSplitter` + `ResplitCore` returns **zero** hits. `SettlementTransaction` is a pure computed-suggestion struct with no `isSettled`/`paidAt` field. The settlement is recomputed from scratch every render from `amountOwed` + `isPayer`; any real-world payment that already happened is invisible to it.
**Who's mis-billed:** Jordan is told to pay $130 when he actually owes $80. If he follows the app literally he **overpays by $50**; if he doesn't, he can't trust the screen at all and the whole "who owes whom" feature loses its job-to-be-done for any group that pays incrementally (i.e., most real trips).
**Severity:** P1 — not silent-wrong-math, but a structural hole: the settlement screen is unusable as a running ledger because it can't acknowledge payments. For a multi-day folder this is the difference between "useful settle-up tool" and "one-shot snapshot."
**Scales by proportion?** No — fundamentally a **new mode**: a payment-ledger layer (`RecordedPayment { from, to, amount, currency, date }`) that the net-balance computation subtracts *before* running the greedy matcher. Proportion governs what's owed; it cannot represent what's been paid.

---

### SF-6 — Per-receipt FX date is correct, but a settlement that nets two legs at *different* rates produces a directionally-wrong "owed" sign
**Scenario:** Base USD folder, two JPY receipts. Receipt 1 (day 1, ¥10,000, Jordan paid, Marcus owes ¥5,000) converts at ¥150/$. Receipt 2 (day 4, ¥10,000, Marcus paid, Jordan owes ¥5,000) converts at ¥130/$ after a yen move. Intuitively the two ¥5,000 legs "cancel." In USD they don't: leg 1 = $33.33, leg 2 = $38.46.
**What V1 does:** Correctly — each receipt is converted at its own `requestedDate` rate (`multiCurrencyFolderSettlement` lines 253, 319-328). Marcus nets `-$33.33 + $38.46 = +$5.13` creditor. This is *arguably the right answer* (honor the rate on the day each debt was incurred).
**Trust break:** To the user, "we each owed the other ¥5,000, why does Marcus get $5.13?" looks like a bug. The `appliedRateEntries` audit data exists (`FolderSettlementResult.swift:57`) but there's no UI contract proven to surface "this $5.13 is an FX-timing artifact, not a miscount." Without that, FX-timing residue is indistinguishable from a real apportionment error.
**Severity:** P2 — math defensible, but the residue is *unexplained* and on a multi-currency trip will read as broken. This is a folder-only phenomenon (single receipt has one rate).
**Scales by proportion?** Yes for the math (already netted). Needs a disclosure mode: "FX timing added $5.13" so the artifact isn't mistaken for the additive-total class of bug. Borderline new-mode because it requires the engine to *attribute* a residue to FX vs. apportionment.

---

### Coverage notes (checked, deliberately NOT re-listed)
- **Multi-currency primary-currency selection / per-receipt FX rate** — already in grounding (`2026-05-31-international-regimes.md`, FX-date-per-receipt). SF-4/SF-6 are the *settlement-residue* consequences, which the apportionment-focused prework does not cover.
- **Paid-but-didn't-consume** (SF-2) — the *net* math is genuinely covered by the net-balance design; only the per-receipt audit drill-down is missing. Honestly half-covered, flagged for the narrative gap.
- **Sub-cent residue** — the *single-receipt* rounding contract is in grounding (`matchThreshold=0.01`, `ReceiptSplitEngine` remainder distribution). The **folder layer has no equivalent rounding pass** (SF-4) — that gap is new.

---

Confirmed. `extractRawAmount("1.234,56")` → strips the comma (it's not in `[\d.-]`) → `"1.234.56"` → `Double("1.234.56")` returns `nil` (two decimal points) → the charge is silently dropped. And `extractRawAmount("١٢,٥٠")` (Eastern-Arabic) → strips everything → `nil`. These are real, citable in-app failures distinct from the grounding's "parse layer is upstream" note.

I have everything I need. The grounding's comma-decimal note explicitly said "Parse layer is upstream of the cited files" — but `extractRawAmount`/`nonNumericRegex` IS the in-app parse layer, and it's a different, sharper failure than what's cataloged. Let me write the markdown.

## locale-display-missed

All citations below confirmed against `/Users/leokwan/Development/resplit-ios` (canonical repo, not a worktree).

---

### 1. `extractRawAmount` silently DROPS comma-decimal lines — a different, sharper bug than the cataloged "1000x misparse"

**Grounding overlap check:** The international-regimes evidence flags `1.234,56` as a "1000x undercount" risk but explicitly waves it off as "*Parse layer is upstream of the cited files*." That is wrong. The in-app text-line money parser is `ReceiptItemsFixer.extractRawAmount` (ReceiptItemsFixer.swift:374-389), and its behavior is the opposite of a 1000x error — it produces a **silent drop**, not a scaled number. This case is NOT in the grounding.

**Real scenario:** Any EU/LatAm receipt where Azure DI does not return a structured `valueCurrency.amount` for an extra (service charge, coperto, rounding line, a mis-keyed total) and the app falls back to scraping the OCR text line `Servizio   1.234,56`.

**What V1 does today:** `nonNumericRegex = "[^\\d.-]"` (ReceiptItemsFixer.swift:25) strips every char except ASCII digit, `.`, `-`. So `"1.234,56"` → the comma is stripped → `"1.234.56"` → `Double("1.234.56")` returns `nil` (two decimal points is not a valid Double) → `extractRawAmount` returns nil → the guard at line 242 `let currentLineAmount = extractRawAmount(...)` fails the `continue` → **the charge line is silently discarded**, never appended to `allCharges`.

**Who's mis-billed / trust break:** Nobody is over-charged; instead the extra (e.g. an Italian `Coperto 1.234,56` or a French `Service 12,50`) **vanishes from the split entirely** — the pool is silently *under*-counted, and every diner under-pays their share of a real charge. Worse, it's invisible: no error chip, the line just isn't there. This is the inverse failure mode from what the catalog assumed.

**Severity: P1.** It mis-counts the pool with zero user-facing signal, and it triggers on the single most common non-US format (comma-decimal, used across the entire Eurozone + LatAm).

**Proportion-or-new-mode:** Neither — it's a *parse-correctness* defect upstream of apportionment. The fix is a locale-aware numeric parse (NumberFormatter with the receipt's resolved locale, or "last separator is the decimal" heuristic) in `extractRawAmount` + the `nonNumericRegex` allowlist. No new split mode; the contract is fine, the number just never reaches it.

---

### 2. Eastern-Arabic / Devanagari / CJK numerals on the receipt → amount = nil (silent drop)

**Real scenario:** A Gulf (UAE/Saudi), Egyptian, or Iraqi receipt printing prices in Eastern-Arabic numerals (`١٢٫٥٠` = 12.50), or a Devanagari/Bengali-numeral Indian receipt (`१२.५०`), or a Japanese receipt using full-width digits (`１２３４`).

**What V1 does today:** `nonNumericRegex = "[^\\d.-]"` — `\d` in NSRegularExpression/ICU is Unicode-aware and *does* match some non-Latin digit categories, but `Double("١٢٫٥٠")` / `Double("１２.５０")` does **not** parse non-ASCII digit code points or the Arabic decimal separator `٫` (U+066B). `extractRawAmount` returns nil → charge dropped. The `isMoney` regex (Currency.swift:29) is `\\d*\\.\\d{2}` and keys on a literal ASCII `.` followed by exactly two ASCII-or-Unicode digits — an Arabic-decimal-separator amount (`١٢٫٥٠`) fails `isMoney` at the gate (no ASCII `.`), so it's never even recognized as money.

**Who's mis-billed / trust break:** Same silent-drop as case 1 — the line is invisible. In the GCC region (already in the catalog's 11 regions but only for 3-decimal BHD/KWD currency), the *numeral system* is an independent failure the currency-decimals analysis never touched.

**Severity: P2.** Real, but Azure DI's `valueCurrency.amount` (the primary path, OCRSnapshotMapper.swift:48-51,70) normalizes digits to a Double, so this only bites the text-line fallback path. Lower blast radius than case 1.

**Proportion-or-new-mode:** Neither — parse-layer fix (normalize Unicode digits + Arabic/locale decimal separator to ASCII before `Double()`).

---

### 3. Receipt `transactionDate` is parsed but NEVER feeds the FX rate date — every foreign receipt is converted at TODAY's rate

**Grounding overlap check:** The "fx" dimension is listed among the 12, and the international-regimes doc covers minor-units and symbol ambiguity. But the specific defect — **the FX rate is dated wrong** — is not cataloged. The DD/MM vs MM/DD ambiguity the brief asks about is a *subset* of a bigger latent bug: the date is captured and then thrown away.

**Real scenario:** Leo scans a Tokyo dinner receipt dated `03/04/2026` three weeks after the trip and settles it. JPY↔USD moved between the meal and settlement.

**What V1 does today:** `OCRSnapshotMapper` captures `transactionDate: fields.transactionDate?.valueDate ?? fields.transactionDate?.content` into `OCRSnapshot.transactionDate: String?` (OCRSnapshotMapper.swift:41-42, OCRSnapshot.swift:27). Grep confirms `transactionDate` has **zero downstream readers** outside the mapper/model. The FX converter signature *accepts* a date — `convert(_ amount: Double, _ from: String, _ to: String, _ date: Date)` (SettlementService.swift:10,33) — but every call site passes `Date()` (today) or the settlement's `effectiveDate` (SettlementService.swift:22,190; `conversionDate` is built from settlement events at :243,:316, never from the receipt). So the receipt's actual transaction date is dead data.

**Who's mis-billed / trust break:** Everyone on a multi-currency trip settled days/weeks later — the entire pool is converted at the wrong-day rate. For volatile pairs (ARS, TRY, EM currencies) a 3-week gap is a multi-percent error on the whole settlement. The DD/MM vs MM/DD parse ambiguity (`03/04` = Mar-4 or Apr-3) compounds it *if* the date were ever used — but today it's moot because the date is ignored entirely.

**Severity: P1** (wrong-day rate on the whole pool, silent). The DD/MM ambiguity itself is P3 — it only matters once the date is actually wired into FX, and even then Azure DI's `valueDate` returns ISO-8601 (unambiguous); the ambiguity only bites the `.content` string fallback.

**Proportion-or-new-mode:** Orthogonal to the proportion contract — proportions are unitless, so this doesn't touch apportionment. It needs the converter call sites to pass `receipt.transactionDate` (parsed to `Date`) as the rate date, with a fallback to `Date()` when absent. No new mode.

---

### 4. Zero RTL support — Arabic/Hebrew receipt rendering and bidi amount mangling

**Real scenario:** A Tel Aviv (Hebrew, ILS `₪`) or Dubai (Arabic, AED) receipt. Merchant name and item names are RTL script; amounts are LTR digits embedded in an RTL line.

**What V1 does today:** Grep for `layoutDirection`, `rightToLeft`, `isRTL` across all of `ReceiptSplitter/*.swift` returns **nothing** — there is no RTL handling anywhere in the receipt models or (by extension of this module) the formatting layer. `OCRLineItem.name` (OCRSnapshotMapper.swift:63-68) and `merchantName` are stored as raw strings with only `.cleaned()` (newline→space, String.swift:4) applied. When a SwiftUI `Text` renders a mixed Hebrew-label + `₪12.50`-amount string without an explicit bidi base direction, the Unicode bidi algorithm can reorder the visible amount (e.g. a minus sign or the symbol jumping sides), and a right-aligned price column visually collides with RTL item text.

**Who's mis-billed / trust break:** No money mis-billed (the underlying Double is correct), but the **receipt looks scrambled** — amounts appear on the wrong side, the merchant header reads backwards-feeling, and the user loses confidence the app "read" their receipt. For a product whose core trust signal is "I scanned it and it matches," a visibly mangled RTL receipt is a credibility hit that drives abandonment.

**Severity: P2.** Display-only, but it's a total-trust failure for two entire script families and the GCC/Israel regions already in scope.

**Proportion-or-new-mode:** N/A to the math contract — it's a SwiftUI presentation fix (set `.environment(\.layoutDirection)` per detected script, or wrap amounts in LTR isolates `\u{2066}…\u{2069}`). No engine change.

---

### 5. `isMoney` regex assumes period-decimal + exactly-2 fraction digits — misses comma-decimal and non-2-decimal currencies at the *recognition* gate

**Grounding overlap check:** The catalog covers JPY/KRW (0-decimal) and BHD/KWD (3-decimal) for the *money-math/rounding* layer (`*100/.../100`). It does NOT note that the **recognition** gate `Currency.isMoney` is hardcoded to `\\d*\\.\\d{2}` (Currency.swift:29) — a literal ASCII period and **exactly two** fraction digits.

**Real scenario:** (a) A French line `Service   12,50` (comma decimal). (b) A Bahraini line `1.234` (BHD, 3 decimals) or `12,500` (3-decimal with comma). (c) A Japanese line `¥1234` (0 decimals).

**What V1 does today:** `isMoney("12,50")` → false (no ASCII `.`) → the line is never treated as money → the whole `findAdditionalChargesOrFees` text-fallback path (ReceiptItemsFixer.swift:221,240-241) skips it. `isMoney("¥1234")` → false (no `.\d{2}`). `isMoney("1.234")` (BHD 3-decimal) → false (`\d{2}` wants exactly 2, sees 3). So comma-decimal, 0-decimal, and 3-decimal money lines all fail recognition.

**Who's mis-billed / trust break:** Same silent-drop family as cases 1-2 — extras in these formats are invisible to the text-fallback charge extractor, under-counting the pool. Because this is the *gate*, it compounds case 1: even a parser fix to `extractRawAmount` wouldn't help, because `isMoney` rejects the line before extraction is attempted.

**Severity: P2** (gated behind the text-fallback path; the structured Azure `valueCurrency.amount` path is unaffected).

**Proportion-or-new-mode:** Parse/recognition-layer fix — make `isMoney` locale-aware (accept comma decimal, 0/2/3 fraction digits per the resolved currency's minor unit). No split-mode change.

---

### 6. Very long merchant names + non-Latin item names — confirmed NOT a classifier bug (no classifier exists), but a real display-truncation gap

**Honest scope correction:** The brief asks about "non-Latin item names breaking the classifier." **There is no item classifier in this codebase** — grep for `classif`/`categor` returns only `ParticipantDisplayNameResolver.swift` (unrelated). Item names are pass-through strings (`OCRLineItem.name`, OCRSnapshotMapper.swift:68, defaulting to literal `"Item"` when empty). So there is no classifier to "break," and no category logic keyed on item-name language. **This specific concern is a non-issue — correcting the brief's premise.**

**What IS real:** (a) Long merchant names — `merchantName` is stored raw with no length cap (OCRSnapshotMapper.swift:37-38); a 60-char Thai/German compound merchant name has no `.lineLimit`/`.truncationMode` anywhere in this module (grep confirms none), so layout behavior is entirely at the call-site's mercy and can push amounts off-screen or wrap unboundedly. (b) The empty-name → `"Item"` default (OCRSnapshotMapper.swift:68) fires whenever a non-Latin item description comes back empty from Azure, collapsing several distinct dishes to indistinguishable `"Item"` / `"Item"` rows — which DOES degrade the user's ability to assign items, even though it doesn't break any classifier.

**Who's mis-billed / trust break:** No mis-bill; assignment friction (everyone sees three rows all labeled "Item" and can't tell which is theirs) + possible layout overflow on long names.

**Severity: P3.** Cosmetic/usability, not money.

**Proportion-or-new-mode:** N/A — display fix (`.lineLimit(1)` + `.truncationMode(.middle)` on merchant; better empty-name fallback). No engine change.

---

### Severity roll-up (locale/display, net-new vs grounding)

| # | Case | Sev | Net-new vs grounding | Fix layer |
|---|------|-----|----------------------|-----------|
| 1 | `extractRawAmount` drops comma-decimal lines (silent) | **P1** | Yes — corrects grounding's "upstream, 1000x" claim; it's an in-app silent *drop* | parse (`extractRawAmount`/`nonNumericRegex`) |
| 2 | Eastern-Arabic / Devanagari / CJK numerals → nil | P2 | Yes | parse (Unicode digit normalize) |
| 3 | `transactionDate` parsed but never feeds FX rate date | **P1** | Yes — date is dead data; FX always today | wire `transactionDate`→converter |
| 4 | Zero RTL support (Arabic/Hebrew render scramble) | P2 | Yes | SwiftUI bidi/layoutDirection |
| 5 | `isMoney` gate hardcodes `\.\d{2}` ASCII period | P2 | Yes — recognition gate, distinct from math layer | parse (`isMoney` locale-aware) |
| 6 | Long merchant / `"Item"` collapse (no classifier exists) | P3 | Partial — corrects premise; no classifier | display (`.lineLimit`/empty-name fallback) |

**None of the six requires a new apportionment mode** — the proportion-is-truth contract is untouched. Five are parse/display-layer defects upstream or downstream of the engine (#1, #2, #5 = numeric parse; #3 = FX date wiring; #4, #6 = SwiftUI presentation). The throughline missed by the prework: the catalog reasoned about *currency math and tax structure* but never audited the **in-app text-line parser** (`ReceiptItemsFixer.extractRawAmount` + `Currency.isMoney`), whose ASCII-period / 2-decimal / Latin-digit assumptions silently *drop* non-US-format money lines — under-counting the pool with no user-facing signal, the opposite of the "1000x over-count" the grounding assumed.

---

Now I have the complete picture and can assess cross-receipt stability precisely. `stableId` is a persisted `uniqueId` (UUID string), so a given person's stableId is stable across receipts within a folder. This is the crux. I have all citations verified against real files. Writing the analysis now.

## fairness-rounding-missed

All citations below are verified against the real iOS tree at `/Users/leokwan/Development/resplit-ios`. The prework's existing rounding/remainder coverage (catalog lines 107-111, 182-195, 287-289) is **entirely about currency granularity** — zero-decimal yen, three-decimal fils. It treats the remainder rule as correct-but-wrong-grain. **None of it examines whether the rule is _fair_ in the plain 2-decimal USD case it ships in every day.** That's this blind spot. Five cases follow; four are genuinely missed, one is partially covered and I say so.

---

### [P1] · Cumulative unfairness — the same friend eats the remainder on every receipt in a folder
**Scenario:** A friend group splits dinner 12 nights across a trip folder. Each night the bill doesn't divide evenly, so there's a 1-2¢ remainder. The whole remainder is added to `sortedIds.first` (`ReceiptSplitEngine.swift:79-81`). `sortedIds` is `proportionsByParticipant.keys.sorted()` — a lexicographic sort of `stableId`s (`:69`), and `stableId` is a **persisted UUID string** (`UniqueIdentifiable.swift:10-15`, stored in `uniqueId`) that is **stable for a given person across every receipt in the folder.** So whichever friend's UUID happens to sort lexicographically first absorbs the rounding penalty on *all 12 receipts*. Over a trip this is a real, accumulating overbill concentrated on one named person — not a wash.

**What V1 does today:** `amountOwedByEach[firstId, default: 0] += remainder` (`:80`). Deterministic by design and *locked* by `assertRemainderDeterministic` (`MathInvariants.swift:149-191`) and re-running stability. There is **no rotation, no cross-receipt memory, no folder-level fairness invariant** — I grepped every `assert*` in `MathInvariants.swift`; nothing addresses cumulative or cross-receipt fairness. The determinism invariant actively *enshrines* always-same-person as correct.

**Trust signal that breaks:** It's silent (sub-cent to 2¢ per receipt, invisible per-line) but a sharp friend who reconciles a trip notices "I always owe a penny more." The fairness story Resplit sells ("fair splits") is contradicted by a deterministic bias.

**Scale by proportion, or new mode?** Cannot be fixed by proportion — proportion is per-receipt and pure; this is an *inter-receipt allocation* problem. Needs a new mechanism: either (a) rotate the remainder recipient deterministically (e.g. seed the sort offset by receipt id so a different person sorts first each receipt), or (b) round half-up/half-down alternately so remainders cancel, or (c) split the remainder into 1¢ shares across the first-k participants instead of dumping the whole thing on one. Option (a) keeps referential transparency per-receipt while breaking the cross-receipt bias — but it would require *revising* `assertRemainderDeterministic`'s "always sortedIds.first" assumption, which the prework never flags as a fairness liability.

---

### [P2] · Two identical orders owe different cents
**Scenario:** Alice and Bob both order the exact same $14.33 entrée, share nothing else, no tax/tip wrinkle — a $43.00 bill split so each *should* owe identical money. If their two shares each round to, say, $21.49 but the distributable total is $43.00, the remainder $0.02 lands entirely on `sortedIds.first`. Alice (UUID sorts first) is shown **$21.51**, Bob **$21.49** — two people who ate identical food owe different amounts.

**What V1 does today:** The engine computes each share by `(proportion * distributableAmount * 100).rounded() / 100` (`:73`), then dumps the full leftover on one person (`:79-81`). It has no notion of "these two participants have equal proportion, keep them equal." `assertProportionBounded` (`MathInvariants.swift:77`) checks proportions sum to ~1 but not that equal proportions yield equal money.

**Trust signal that breaks:** This is the most *visible* fairness break — two friends literally compare phone screens and see different numbers for the same meal. Far more damaging to trust than the silent cumulative case, because it's legible at a glance.

**Scale by proportion, or new mode?** Proportion alone produces it (equal proportions, unequal post-remainder money). Needs a remainder-distribution rule that respects equivalence classes: when several participants tie on proportion, the 1¢ residues must be spread one-per-person, not stacked on the first. This is a *new remainder mode*, not a proportion change.

---

### [P3] · Tip computed on the unrounded base, then re-split — double rounding skew
**Scenario:** $100.00 subtotal, 18% tip. Tip = `100.00 * (18/100) = 18.00` clean here, but on a $99.99 subtotal tip = `17.9982`, a sub-cent value. That raw `Double` flows straight into `resolvedTotalAmount` via `ReceiptTotalCalculator.calculatedTotal` (`:11, :19`, `itemSum + tax + tip + customExtras`) with **no quantization at the tip boundary.** The engine then scales that fractional-cent-laden total across each head and rounds *once, at the very end* (`:73`).

**What V1 does today:** `SummaryItemCalculator.calculatedTip` returns `baseAmount * (percent / 100)` (`:21-23`) — no rounding to cents. The displayed tip line will format to `$18.00` while the value folded into everyone's owed amount carries `17.9982`. So the tip *shown* and the tip *billed* differ by a sub-cent, and that delta is then consumption-weighted across heads. `assertTipInvariant` (`MathInvariants.swift:117`) pins `tip == base * pct/100` exactly — meaning it **actively forbids** rounding the tip, so any fix here must re-express that invariant.

**Trust signal that breaks:** Mostly silent at 2-decimal granularity (the error is sub-cent and usually absorbed into the single end-rounding), but it means "tip on rounded base vs unrounded base" produces a per-head share that can be 1¢ off from a hand-computed `round(tip)/N`. Catalog line 124-126 names the fractional-*yen* version of this; the **2-decimal "tip-shown ≠ tip-billed" skew is not isolated as a fairness case** — it's folded into the zero-decimal story.

**Scale by proportion, or new mode?** Proportion handles the distribution fine; the fix is to **quantize the tip to the currency minor unit before it enters the total** (round at the `SummaryItem`/`ReceiptTotalCalculator` boundary), so the split engine scales a clean total. This is a boundary-rounding fix, compatible with proportion-is-truth — but it forces a revision of `assertTipInvariant` to `tip == round(base * pct/100)`.

---

### [P2] · The 0.005 boundary — remainder silently swallowed at exactly half a cent
**Scenario:** A 3-way split where the per-share rounding leaves a residue of *exactly* `$0.005` (e.g. distributable amount and proportions conspire so `distributableAmount - totalRounded == 0.005`). Real trigger: any total whose last-cent allocation sits on the half-cent boundary.

**What V1 does today:** `remainder = ((distributableAmount - totalRounded) * 100).rounded() / 100` then `if abs(remainder) >= 0.005 { ...add... }` (`:78-79`). Two boundary hazards: (1) **`.rounded()` uses round-half-*away-from-zero* (`.toNearestOrAwayFromZero`, Swift's default)**, so a true `0.005` residue rounds to `0.01` and *does* get added — but a residue of `0.0049999` from float accumulation rounds to `0.00` and the `>= 0.005` gate then drops it, so a near-half-cent leak can be **silently discarded**, leaving `Σ shares < total` by up to ~half a cent. (2) The `>=` (inclusive) gate plus away-from-zero rounding means the boundary behavior is asymmetric for positive vs negative residues. `assertZeroSum` (`MathInvariants.swift:27-43`) tolerates `< 0.01`, so this leak passes the safety net as "verified."

**Trust signal that breaks:** Σ of displayed per-head amounts can fail to equal the displayed total by a cent on boundary receipts, while the receipt still shows a green/verified chip. Quiet, but it's exactly the "the numbers don't add up" complaint that destroys confidence in a money app.

**Scale by proportion, or new mode?** Not a proportion issue — it's a rounding-mode + threshold correctness issue. Fix: make the residue computation and the trigger boundary explicit and symmetric (largest-remainder allocation rather than a single threshold-gated dump), so no fraction of a cent is ever discarded. The prework's currency-grain rewrite (line 187) *touches* the `0.005` literal but only to rescale it per-currency — it **never identifies the half-cent discard/boundary bug itself**, which exists in plain USD.

---

### [P3] · Negative remainder lands on first participant — partially covered, but the sign-direction fairness wrinkle is missed
**Scenario:** Per-share rounding *overshoots* (each share rounds up), so `distributableAmount - totalRounded` is **negative**. The code handles it: `abs(remainder) >= 0.005` triggers, and a negative `remainder` is *subtracted* from `sortedIds.first` (`:80`, `+= remainder` with negative value). So `sortedIds.first` can be billed *less* than their proportional share when rounding overshoots.

**Honest assessment — half-covered:** The *mechanics* of negative remainder are sound and the determinism is pinned. But it interacts with case [P1] in a way the prework never notes: because the recipient is **always the same person**, when remainders are systematically positive (under-allocation, the common case with round-half-up) that person is *always overbilled*, and on the rarer overshoot receipts they're *underbilled* — but there's no reason the two cancel for that specific person. The sign of the remainder correlates with the rounding direction of the *whole receipt*, not with any per-person property, so a folder of mostly-positive-remainder receipts produces a one-directional overbill on the lexicographically-first friend. This is the same root as [P1]; I'm flagging it because the catalog's determinism framing (`assertRemainderDeterministic`) treats "always same person, any sign" as a *feature*, and never asks whether the *expected value* of that person's rounding error is zero. It is not.

**Scale by proportion, or new mode?** Same fix as [P1] — rotate or spread the recipient. The negative-remainder path needs no separate handling; it's the *always-same-recipient* policy, across both signs, that's the bug.

---

**Net:** The prework cataloged this engine's remainder rule *thoroughly for non-USD granularity* and *not at all for fairness in its home currency.* The load-bearing miss is that `assertRemainderDeterministic` (`MathInvariants.swift:149-191`) and the `sortedIds.first` dump (`ReceiptSplitEngine.swift:79-81`) are cited everywhere as a *correctness anchor to preserve*, when they are simultaneously the *source of a deterministic, cumulative, always-same-friend overbill* (cases P1/P2/P3-negative). Any V2 that keeps "remainder → sortedIds.first" as an invariant ships the unfairness. The proportion-is-truth contract does not fix these — remainder fairness lives *below* proportion, in the quantization layer, and needs an explicit largest-remainder / rotated-recipient mode that the catalog has not specified.

---


# Contract Re-Audit (P9.8)

Confirmed: `currencyCode` exists but defaults to `"USD"` when nil (`ReceiptSplitCalculator.swift:90`: `receipt.currencyCode ?? "USD"`), and the pure `ReceiptSplitEngine.calculateSplit` carries no currency at all (operates on bare `Double` + `* 100` cents rounding). This is exactly the "currencyCode:nil / cents-hardcoded" money-model gap. matchThreshold lives in the Reconciler (already noted in the matrix as `Reconciler.swift:34`, P3-stage, not in the shipped split path). All citations confirmed. I have everything needed for the audit.

# P9.8 Contract Audit — Apportionment Directions vs. "Proportion Is Truth"

> Binding contract (2026-05-31): **proportion is the source of truth; equal-split is the DEFAULT proportion; the total scales proportions, it does not define shares.** A diner is proportion-0 only when line items exist and they were assigned none — never in the no-items case (there everyone is `1/N`).
> All code citations below re-verified against the real `/Users/leokwan/Development/resplit-ios` source (not worktrees). Engine: `proportion × distributableAmount` at `ReceiptSplitEngine.swift:73`; `distributableAmount = totalAmount − orphanAmount` at `:64`; empty-items → every participant `0.0` at `:83-89`; cents-hardcoded `* 100).rounded() / 100` at `:73,:78`.

## Audit table

| # | V2 direction | Scales money by proportion? | Obeys "proportion is truth"? | Obeys "equal-split is DEFAULT proportion"? | Breaks no-items case? | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Currency-aware money model** (replace `Double`+`*100` cents w/ currency-scaled minor units; `currencyCode` first-class instead of `?? "USD"` at `ReceiptSplitCalculator.swift:90`) | Indirectly — it changes the rounding *granularity* of `proportion × distributableAmount` (`:73`), not the share source | YES — proportions are unitless ratios; currency only re-scales the total. Multiply order is proportion-first, currency-quantize-last | YES — money model is orthogonal to where proportion comes from | NO — operates on the total, not the share basis. But the cents-hardcode (`*100`) at `:73/:78` must become currency-decimal-aware; the remainder rule at `:78-80` must quantize in the receipt's minor unit | **OBEYS** — with one caveat (quantize after proportioning, never derive shares from rounded money) |
| 2 | **Inclusive-tax fix** (stop double-adding VAT already baked into line `amount`; treat tax-inclusive prints as already-in-subtotal) | YES — corrects the *value* of `totalAmount`/line `amount` that proportions scale | YES — it fixes the **scalar** (the total), leaving the proportion vector intact. This is the contract's "total scales proportions" working exactly as intended | YES — does not touch the share basis; no-items bill has no inclusive-tax line to fix | NO — empty-items path returns $0 regardless of tax treatment (`:83-89`); equal-split-default flip is unaffected | **OBEYS** |
| 3 | **Extra-taxonomy apportionment — % service charge (proportional)** (matrix `mandatory-service-charge`, Option A) | YES — folds SC into `totalAmount`, spread via `:73` | YES — "everyone pays X% of their own order" IS proportion-as-truth; reuses `:73` verbatim, no new share math | YES — on a no-items bill SC = X% × 0 = $0, so equal-split-default's $0-from-empty still holds | NO — but the matrix already flags `grat-on-zero-items` must float to payer (orphan-like), not distribute. Under the **new** contract this is the no-items-equal-split case: SC is $0, everyone is `1/N` of $0 = $0. Consistent | **OBEYS** |
| 4 | **Extra-taxonomy — flat cover/min (equal-per-head)** (matrix `flat-cover-minimum`, Option B) | **NO — deliberately bypasses the proportion vector** (layers `fee/N` ON TOP, outside `:73`) | **PARTIAL / RECONCILE** — see Conflict 1. Equal-per-head is a *legitimate* proportion (`1/N`), but only if expressed AS a proportion, not as an out-of-band additive layer that re-introduces "the total defines a per-head share" | YES for the per-head layer (`1/N` IS the default proportion) — but the item-derived layer must stay separate | **YES (potential)** — a cover-only / zero-line-item bill forces `cover/N > 0` per head, which **collides with the old EMPTY_ITEMS_ALL_ZERO**. Under the **new** contract this collision *dissolves* (no-items → equal-split is now correct), but only if the cover is modeled as `proportion = 1/N`, not as a bolt-on additive | **OBEYS ONLY IF re-expressed as `1/N` proportion** (Conflict 1) |
| 5 | **Extra-taxonomy — deposit/credit** (matrix `deposit-prepayment`, Option A payer-attributed) | NO for the credit itself (post-split named-participant settlement, mirroring `assertPayerCredit` at `MathInvariants.swift:332`); YES for the gross split underneath | YES — gross split runs proportionally first (`:73`), credit applied after to one named participant. Proportion stays the truth; credit is a settlement adjustment, not a share redefinition | YES — credit doesn't touch the proportion basis | NO — but adds `TOTAL_VS_BALANCE_DUE`; must not mutate `assertZeroSum` (`:27`). No-items path untouched | **OBEYS** — with the known BOUNDED_LOWER hole (deposit > host's gross share drives `owed < -0.01`, `:57`) gated by a refund branch |
| 6 | **Extra-taxonomy — comp/discount/voucher** (matrix `comp-discount-voucher`, Option B targeted-first) | Targeted: NO (reduces the item `amount`, proportions recompute naturally); Table-wide: YES (proportional via `:73`) | YES — targeted comp lowers the comped owner's *raw amount*, so the proportion vector legitimately re-derives from item assignment (`:27-40`). This is the purest expression of "proportion is truth" | YES — table-wide voucher on a no-items bill floats to payer (orphan-like); under new contract, everyone `1/N` of the reduced total | **YES (potential)** — a credit larger than the distributable base makes `distributableAmount` (`:64`) negative → ZERO_SUM-with-BOUNDED_LOWER breach. Needs clamp-and-orphan | **OBEYS** — with the clamp-and-orphan guard the adversarial flagged |
| 7 | **Weighted/fractional item** (matrix `weighted-item`, Option A label-only now) | YES — splits `item.amount` (line total) by consumption via `:73`, unchanged | YES — Option A changes only the label + reconciler, never the proportion or the money. Money already correct | YES — orthogonal to no-items | NO | **OBEYS** (Option A). Option B's by-weight path needs a claimed-weight==line-weight guard before it's proportion-safe |

## Conflicts found

**Conflict 1 — `flat-cover-minimum` Option B is the ONE direction that structurally violates the contract as currently written.** The matrix specifies equal-per-head cover as a layer apportioned **"outside the consumption-proportion vector ... added on top of each person's food share"** and explicitly **"must NOT be injected into the proportion vector"** (`decision-matrix.md:63,68`). That phrasing makes the per-head fee an *additive layer derived from the total* (`fee/N`) — i.e., **"the total defines a per-head share,"** which is precisely the shape the binding contract forbids ("the total scales proportions, it does not define shares"). The fee/N is mathematically `1/N` of a sub-pool, so the fix is a *framing* change, not a math change:

- **Resolution:** model the flat cover as its own pool with an **explicit `1/N` proportion vector** (equal-split — the contract's DEFAULT proportion), then `proportion × cover_pool` through the same `:73` path, summed with the consumption pool's `proportion × food_pool`. Two proportion vectors, both truths, both scaled by their own sub-total. This keeps every share derived from a proportion (never from a raw `total/N` division) and makes the zero-line-item cover-only bill fall out naturally: it's the **no-items → equal-split-default** case, where `1/N` is exactly right.
- **Contract bonus:** the matrix's hand-wrung "Hard collision ... cover/N > 0 on a zero-line-item bill violates EMPTY_ITEMS_ALL_ZERO" **dissolves under the new contract.** EMPTY_ITEMS_ALL_ZERO is being inverted to `EMPTY_ITEMS_EQUAL_SPLIT` (contract §27, `MathInvariants.swift:381-413`). A cover-only bill is the canonical no-items case; `1/N` per head is now the *required* answer, not a canary violation. The matrix was written pre-contract and treats this as an unresolved hazard; the contract resolves it. **The matrix text must be updated** to say the cover layer is a `1/N` proportion pool, not an out-of-band additive — otherwise an implementer reading `decision-matrix.md:63,68` literally will reintroduce a total-defines-share path.

**Conflict 2 (latent, all proportional directions) — proportion-0 framing in worked examples.** Several worked examples and adversarial notes (e.g. `flat-cover` Cleo "proportion 0", `deposit` "proportion=0 diner untouched") reason about a proportion-0 diner. Per the contract these are all **line-items-exist** cases (Cleo ordered $0 *while others have items*), so proportion-0 is legitimate there. **No conflict in the math** — but every example that says "a true proportion=0 diner" must be read as *"line items exist and this diner was assigned none."* The contract explicitly forbids proportion-0 in the **no-items** case. None of the 6 directions' worked examples actually invoke proportion-0-on-empty-items, so this is a documentation-precision flag, not a behavioral break: the directions are safe as long as their proportion-0 reasoning is fenced to the items-exist case (which it is).

**No conflict for directions 1, 2, 3, 5, 6, 7** — each scales an *already-derived* proportion vector by a corrected/re-scaled total, or applies a post-split settlement to a named participant. None derives a share *from* the total. The money model (1) and inclusive-tax (2) touch only the scalar; the proportional extras (3) and the targeted/table-wide comp (6) re-derive proportions from item assignment via `ReceiptSplitEngine.swift:27-40,47-51` exactly as the contract requires; the deposit credit (5) is a post-`:73` adjustment; weighted-item Option A (7) is label-only over a money-correct engine. All obey "proportion is truth, total scales it."

**Net:** 6 of 7 directions OBEY the contract as-is (subject to their already-flagged invariant guards). **1 direction — flat-cover Option B — must be re-expressed from an out-of-band `fee/N` additive layer into an explicit `1/N` equal-split proportion pool** to obey the contract; doing so also auto-resolves its EMPTY_ITEMS collision because the new `EMPTY_ITEMS_EQUAL_SPLIT` contract makes `1/N`-on-empty the *correct* behavior rather than a canary violation.

---


# Second Opinion — the 2 riskiest recommendations

Now it's clear: `receipt` here is a DTO (`receiptDTOs`), and `participants` are `ParticipantDTO` with the stored `amountOwed` field (`ParticipantDTO.swift:9`), populated at DTO-build time via `Receipt+DTO.swift:17` → `calculator.amountOwed(by: participant)`. So settlement is a snapshot of the engine output at DTO-construction time. This confirms the propagation chain: engine → calculator → DTO → settlement.

I now have everything needed. The empty-items result feeds settlement through the DTO snapshot, so flipping the engine WILL propagate to settlement automatically (which is the dangerous part — real money). Let me write the verdict.

## empty-items-flip

**Adversarial second opinion on inverting `EMPTY_ITEMS_ALL_ZERO` (MathInvariants.swift:381) → `EMPTY_ITEMS_EQUAL_SPLIT`.** Read-only; all citations verified against `/Users/leokwan/Development/resplit-ios`.

### What the flip actually means in code

The "empty items" state is not a guarded special case — it is an emergent consequence of the engine's proportion math. In `ReceiptSplitEngine.calculateSplit` (ReceiptSplitEngine.swift:23-51): with `items == []`, `rawAmountsByEach` stays empty → `sumOfRawAmounts == 0` → the `if sumOfRawAmounts > 0` block is skipped → `proportionsByParticipant` is empty → step 4's `sortedIds` is empty → step 5 backfills every participant to `0.0`. Zero is the *fixed point of the proportion engine when there is no proportion signal*. `EMPTY_ITEMS_ALL_ZERO` (MathInvariants.swift:394-413) just pins that emergent behavior; the T8 hunt's "never shipped" finding is literally true — there was never a branch to ship, the zero falls out of the algebra.

So "flipping the invariant" is misleading. You cannot flip an assertion and change behavior; you must add a *new branch* to the engine (or upstream of it) that injects an equal proportion `1/N` when there is no proportion signal. That is the real change under discussion.

---

### STRONGEST CASE AGAINST flipping the engine

**1. Settlement reads a frozen snapshot, not the live engine — the blast radius is real money, not just a UI label.** This is the load-bearing finding. Settlement does *not* call the engine; it reads `participant.amountOwed` off a DTO:

- `TripSettlementFooter.swift:35` and `TripSettlementSheet.swift:53`: `receipt.participants.reduce(0.0) { $0 + $1.amountOwed }`
- `SettlementService.swift:56, 251, 448, 474`: same `participant.amountOwed`
- `PersonStatsCalculator.swift:15`: cross-receipt person rollup, same field

`ParticipantDTO.amountOwed` (ParticipantDTO.swift:9) is a stored value, populated once at DTO-build time from the engine via `Receipt+DTO.swift:17` (`calculator.amountOwed(by: participant)`). Meaning: an engine flip *does* propagate into settlement, person-rollup, and the settle-up transaction graph automatically — but only on whatever stale snapshot the settlement path happened to build. An empty-items receipt that previously contributed $0 to a trip settlement would, post-flip, start injecting `total/N` debt into the N-1 transaction minimization. The "never shipped → always $0" behavior is currently load-bearing for *every settled trip that contains an unscanned/empty receipt*. Flipping it silently rewrites historical settlement math the next time those DTOs rebuild. That is the exact failure shape of the 2026-04-22 SEV-0, but now in the direction of *manufacturing* debt instead of misallocating it.

**2. The orphan exclusion contract becomes self-contradictory for the empty case.** The orphan fix (ReceiptSplitEngine.swift:53-64, asc-receipt-detail-2026-04-22) established a hard contract: *line items present on the receipt but unassigned contribute to the total but are NOT redistributed* ("Won't count toward totals"). An empty-items receipt with a non-zero total is the **limit case of an all-orphan receipt** — there is a total, and zero proportion signal saying who owes it. Equal-split-on-empty says "redistribute the whole total `1/N`." All-orphan-with-one-$22-item says "redistribute nothing of the $22." These are the same epistemic situation (we have money, we have no claim signal) resolved in *opposite* directions. A user with [$22 unassigned item] sees Amir owe $0 for it; a user with [no items, $22 total] would see Amir owe $11. Same ignorance, opposite charge. That is a worse, less-defensible inconsistency than the current uniform-zero.

**3. `zeroSumInvariantHolds` will start firing false `.verified` on a now-non-zero pool — or break.** The gate in ReceiptSplitCalculator.swift:121-165 has two arms keyed on `anyRawAmount = items.contains { sharedEqually || !individualParticipants.isEmpty }`. With `items == []`, `anyRawAmount == false` → the **relaxed arm** (line 160-164) fires, which asserts `abs(participantSum) <= 0.01`. Post-flip, `participantSum == total`, so the relaxed arm now *fails* and the footer flips to `.hasErrors` / "Total may be incorrect" on every equal-split-empty receipt. So the naive engine flip doesn't just change the split — it lights up a red error banner on the exact receipts it was meant to fix, because the verification gate was written assuming empty ⇒ zero. You'd have to surgically re-thread the gate too. More surface, more SEV risk.

**4. `canStartLiveSplit` deliberately excludes empty-items receipts (Receipt.swift:290-293, pinned by ReceiptLiveSplitEligibilityTests.swift:5-9).** Live Split needs claimable items. An equal-split-empty receipt is exactly the receipt the product currently says "you can't live-split this." So the flip creates a receipt that *has* a meaningful per-person split but *cannot* enter the claim flow that would let a user correct it. The user is charged `total/N` with no in-app affordance to re-split — the only escape is adding items, which defeats the empty case. Equal-split-on-empty without a corresponding live-split/edit path is a charge with no override button.

**5. T8's archaeology verdict is being overruled by memory, not evidence.** The investigation that produced `EMPTY_ITEMS_ALL_ZERO` (T8-v1.8-regression-hunt) specifically chased Leo's recollection of a `total/N` fallback and proved it never existed in any examined commit. Leo's "it MUST be true" is a *product directive*, not a discovery that T8 was wrong. That's fine — but it means we are deliberately introducing new behavior the codebase has never had, in the money path, during the launch freeze. The burden of proof is on the change, and the change touches settlement.

---

### The SAFER framing (and why it's genuinely better)

**Synthesize one `sharedEqually` item equal to the total, upstream of the engine — do NOT touch `ReceiptSplitEngine`, the `EMPTY_ITEMS_ALL_ZERO` invariant, or the zero-sum gate.**

The engine already does perfect equal-split for a single `sharedEqually` item: ReceiptSplitEngine.swift:27-31 divides `item.amount / participantIds.count` across everyone, and `sharedEqually` is the model default (ReceiptItem.swift:101-104: `!(sharedByEveryone == false)`). So an "empty" receipt that should split equally is *definitionally* a receipt with one implicit whole-bill shared item.

Why this is strictly safer than an engine branch:
- **Zero-sum gate stays correct for free.** With a synthesized shared item, `anyRawAmount == true` (ReceiptSplitCalculator.swift:149-151), so the **strict** arm runs and `Σ participants == total` passes → footer correctly reads `.verified`, not the false `.hasErrors` the naive flip produces.
- **`canStartLiveSplit` becomes true automatically** (Receipt.swift:292 checks `!items.isEmpty`) — the user gets the claim/edit affordance, closing the "charged with no override" gap.
- **The orphan contract is untouched and stays consistent** — a synthesized *assigned-to-everyone* item is categorically not an orphan (orphan = `!sharedEqually && participantIds.isEmpty`), so it never hits the exclusion at lines 61-64. The "no items → all zero" invariant remains literally true and keeps guarding against accidental drift, because we never reach the empty branch.
- **Settlement propagation is the normal path**, not a special engine state — DTO build, person rollup, and the N-1 transaction graph all see a real shared item exactly like any equal-split receipt does today.

The cost/risk of the synth approach is the *decision boundary*: when do you synthesize? Auto-synthesizing on every empty receipt risks fabricating a bill from an OCR miss (receipt scanned, parse produced no line items, total=$50 → you'd manufacture a $50 equal-split the user never asked for). That is the one place this needs Leo: **equal-split-on-empty should be a user-triggered state (the existing "Share all" CTA / an explicit "split evenly" action), not an automatic engine behavior.** The product already has the `sharedByEveryone: true` toggle path (ItemParticipantRowViewModel.swift, the "Share all" CTA in the unassigned card). The right shape is "Share all" / "split evenly" creates the implicit whole-bill item — not "the engine guesses equal-split whenever items are empty."

---

### Net verdict: **REVISE → then NEEDS-LEO on one boundary**

**Do NOT flip `EMPTY_ITEMS_ALL_ZERO` or add an equal-split branch to `ReceiptSplitEngine`.** The engine's uniform-zero is correct *as an engine* — the engine should only ever distribute proportion signal it was given, and "no items" is genuinely "no signal." Keeping that invariant is what protects settlement, the zero-sum gate, and the orphan contract from silent money drift.

**The right implementation is the synthesized-shared-item framing**, driven by an explicit user action (extend/own the existing "Share all"/"split evenly" CTA), so equal-split flows through the *normal* shared-item path that the gate, live-split, settlement, and reconciler already handle correctly. This satisfies Leo's "equal-split MUST be true" without overruling T8 and without an engine money-path change during the freeze.

**The single NEEDS-LEO decision is the trigger boundary**, not the math: should equal-split-on-empty be (a) auto-applied to any empty receipt (risks fabricating splits from OCR parse failures — the dangerous one), or (b) gated behind an explicit user tap ("Share all" / "Split evenly"), which is safe and reuses existing UI. The investigations explicitly want the orphan/empty state to be *user-actionable*, not silently distributed — so (b) is the framing consistent with the prior contract, but the auto-vs-explicit call is a product decision Leo should make before any code lands. If forced to default: ship (b), explicit-trigger, never auto.

---

I have everything verified. The settlement layer works on signed balances (`balance > 0` = creditor, `< 0` = debtor) and handles a payer who is net-positive (over-paid) naturally — but `amountOwed` itself is gated by `BOUNDED_LOWER (owed >= -0.01)` at the engine/invariant layer. Now I have enough to write the adversarial stress-test.

## deposit-credit-default

**Verdict up front: REVISE — flip the default decision rule from "credit-to-payer by default" to a context-gated default (credit-to-payer for restaurant/catering checks, table-wide for event/trip pools), AND make the BOUNDED_LOWER refund branch a *blocking* prerequisite, not a footnote.** The current "A-default-with-B-toggle" is right that two modes exist and right about the engineering shape; it is *under-specified* on (a) when each is actually the common case and (b) the negative-owed breach it half-flags. Details below.

### The strongest case AGAINST "credit-to-payer by default"

**1. The "one host fronts it" model fits catering, not the dinners Resplit actually targets.** The entire A-default rests on one prose receipt — the Tripleseat catering check (`2026-05-30-what-v1-splitter-misses.md:20,25`), explicitly *not* in the scanned corpus (only 4 of 48 rows parsed; the deposit figures live in prose, per the matrix's own admission at `apportionment-decision-matrix.md:82`). Catering is the *least* representative Resplit transaction. Resplit's modal job is splitting a normal restaurant/bar tab among friends. On those checks, a "deposit" line is overwhelmingly **a table-wide reservation hold / pre-auth / group bottle-service minimum**, where the deposit reduces *the table's* balance due and was conceptually pooled — the Option B case. Defaulting every deposit to "return it all to the payer" mis-fits the high-frequency case to optimize the rare one.

**2. The mis-bill from a wrong A-default is silent and asymmetric.** If the truth is table-wide (B) but we apply A, the credited person (whoever happened to tap "I paid") gets the *entire* deposit refunded to them while everyone else pays full gross share — the payer is *under-billed* by `(N−1)/N × deposit` and the rest are collectively *over-billed* by the same. On a $262 deposit / 4-person table that's ~$196 mis-allocated. Critically, `assertZeroSum` (`MathInvariants.swift:27`) **still passes** — the sum reconciles to balance-due either way, so no test, no banner, no reconciler finding fires (`Reconciler.swift:78` only checks `subtotal + positives − negatives` against the printed total, not *who* the credit lands on). It is the same class of invisible misbill as the proportion-0 cover bug: arithmetically conserved, individually wrong.

**3. BOUNDED_LOWER is a hard breach under A, and it's not hypothetical.** I confirmed the threshold: `assertBounded` requires `owed >= -0.01` (`MathInvariants.swift:57`) — there is no over-credit/refund accommodation in the invariant. A-default models the deposit as a post-split credit on the named payer. The instant the deposit exceeds the payer's own gross consumption share — a light-eating host who fronted a large deposit (host consumes $131, fronted $262) — A drives that payer's `owed` to −$131 and **breaks the invariant outright**. The matrix calls this a "half-flag," but it is the load-bearing risk: shipping A-default *without* a refund/over-credit branch leaves exactly two outcomes, both bad: clamp `owed` to 0 and leak the excess $131 (breaks `assertZeroSum` against balance-due), or let it go negative (breaks `assertBounded`). B has no such failure mode — proportionally shrinking the pool keeps every share ≥ 0 because the deposit is bounded by the gross total. **So the *safer-by-construction* default is B, not A.** That's the strongest single point against the recommendation: A is the default that can violate a SEV-0-class invariant; B cannot.

**4. "Mirrors `assertPayerCredit`" oversells the safety.** I checked `assertPayerCredit` (`MathInvariants.swift:332-355`): it pins `payerBalance == receiptTotal − payer.amountOwed` and explicitly filters to `amountOwed > 0.01` non-payers. It is a *balance reconstruction* check, not a credit-injection mechanism — it assumes `amountOwed` is already non-negative. A deposit credit that pushes the payer's `amountOwed` negative isn't "the same tested shape"; it's a new state `assertPayerCredit` was never exercised against. The settlement layer downstream *can* represent a net-positive payer (the greedy loop at `SettlementService.swift:498-529` treats `balance > 0` as a creditor and settles fine), so the over-credit is survivable *at settlement* — but only if it's modeled as a settlement-graph credit, never as a negative `amountOwed` that trips the engine invariant first.

### Which default mis-bills *fewer people*?

This is the decisive frame and it cuts against A:
- **Wrong-A (truth was table-wide):** mis-bills **N−1 people** (everyone but the credited payer) plus over-credits the payer. Mis-bill count scales with table size.
- **Wrong-B (truth was one-host):** mis-bills **the host only** — the host eats `(N−1)/N` of their own deposit as a discount to others; the other N−1 are billed exactly their true consumption share. Mis-bill count is **1, regardless of table size.**

For a wrong default, **B mis-bills fewer people** (always 1) than A (always N−1). A only "wins" on *magnitude-to-one-person* in the catering case where one host is knowingly out-of-pocket and will notice. For the friend-dinner population Resplit targets — where nobody is tracking a weeks-old deposit and the bill is split casually — B's failure (host quietly loses a share of their own hold) is both rarer to occur *and* less broadly damaging when it does.

### Net verdict: REVISE (not keep, not pure needs-Leo)

Keep the matrix's strong parts: two genuine modes exist; model the credit at the SummaryItem→engine bridge as a named settlement credit, **never** as a negative `.custom` flowing through `customExtras` (I confirmed that would shrink `distributableAmount` at `ReceiptSplitEngine.swift:64`/`:73` and silently *become* Option B applied unconditionally — correct call); add `TOTAL_VS_BALANCE_DUE` without mutating `assertZeroSum`; keep tax/tip on gross subtotal.

Revise three things:
1. **Default by context, not globally to A.** A "credit-to-payer" default is only defensible when attribution is known. Since OCR cannot infer *who* fronted a deposit (the matrix admits A needs a `creditedTo` tap that OCR can't supply), a global A-default is a default that *requires manual input to even be correct* — that's a worse default than B, which is purely arithmetic from the two printed numbers. Make **B the zero-input default** (it's invariant-safe and OCR-derivable), and surface the credit-to-payer toggle as "one person prepaid this — credit it to them," prompting for the payer tap. This inverts the matrix's A-default/B-toggle into **B-default/A-toggle** for everything except a detected catering/event context.
2. **The BOUNDED_LOWER refund branch is a blocking prerequisite, not a "cons" bullet.** A-mode must not ship until `owed < 0` for a credited payer is explicitly modeled as a settlement-graph credit (payer becomes net creditor, surfaced as "owed back $X"), with the engine clamping `amountOwed ≥ 0` and routing the excess into the settlement balance — verified safe by the `SettlementService` creditor path. Without that branch, A-mode is an invariant violation waiting in TestFlight.
3. **needs-Leo on exactly one thing:** the *frequency claim*. My argument that table-wide is the common case for Resplit's population is reasoned, not data-backed — the corpus has zero scanned deposit rows. Leo owns whether the modal "deposit" on a friend-dinner check is a pooled reservation hold (→ B-default) or a one-host prepayment (→ A-default). Everything else above is engineering-decidable now.

**One-line bottom line:** the recommendation correctly identifies the two modes and the bridge shape, but defaults to the mode that (a) requires manual attribution to be correct, (b) can breach `BOUNDED_LOWER` (`MathInvariants.swift:57`), and (c) mis-bills N−1 people when wrong instead of 1 — so flip to a B-default / A-toggle, make the refund branch blocking, and let Leo rule the frequency assumption.

---

