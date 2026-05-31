# Apportionment Decision Matrix (FOR LEO) — P9.6

> Source: workflow `wzuiyidrz`, adversarially verified. **These are PRODUCT decisions — real people get mis-billed if wrong.** Each row: Option A vs B with worked dollar examples + a recommendation + the invariant it must preserve.

> **Binding contract (2026-05-31):** proportion is the source of truth; equal-split is the DEFAULT proportion; the total scales proportions, it does not define shares. A diner is only proportion-0 when line items exist and they were assigned none — never in the no-items case. See `2026-05-31-proportion-is-truth-contract.md`.

All citations verified against the real iOS files. The tip base at `SummaryItemCalculator.swift:21` (`baseAmount = subtotalValue` or `subtotalValue + taxValue`) has no service-charge term, confirming the double-tip trap. `MathInvariants.swift` confirms `assertZeroSum:27`, `assertBounded:50`, `assertTipInvariant:117`, `assertEmptyItemsAllZero:381`. Here is the matrix row.

## mandatory-service-charge

**Decision owner:** Leo. **Severity: P0 — real people get mis-billed, silently.** A mandatory % service charge / auto-gratuity is the most common non-US bill term V1 cannot represent (UK/EU/AU/MY/SG print 10–18% service post-subtotal as standard). Today V1 has *no* slot for it: `OCRSnapshotBridge.toOCRSnapshot` drops `.serviceCharge` outright (verified `OCRSnapshotBridge.swift:95-98` — the comment literally lists `.serviceCharge` among kinds "dropped"), and the only legal manual home is a `.custom` SummaryItem that rides proportional-by-consumption through `ReceiptTotalCalculator.swift:33` → `ReceiptSplitEngine.swift:73`.

**The real receipt that forces this:** the P8 catering check (`2026-05-30-what-v1-splitter-misses.md:15-16`, cataloged at `edge-case-catalog.md:304-311`): a printed **mandatory `gratuity $339.47`** explicitly flagged kind `.serviceCharge` NOT `.tip` (it is not discretionary), plus an **admin fee $80.83**, on a `subtotal + sales tax + admin fee + auto-grat − deposit` bill. Second instance: a Malaysian receipt with a **10% service charge (RM26 / $29.93)** *plus* a separate 6% service tax (RM3.84) (`catalog:331`). If dropped, `resolvedTotalAmount` prefers the smaller computed total (`Receipt.swift:270-272`) and the payer silently eats the entire $339.47.

This row rules ONLY on a **percentage-of-subtotal** mandatory charge (10–18% auto-grat). Flat per-head cover / $10 drink-minimum is a *different* apportionment row (`catalog:329`, equal-per-head) — do not collapse them.

**Worked table (both options use the same 3 diners, $100.00 subtotal, 18% mandatory service charge = $18.00, no separate tax):**
Ana ordered $60.00 (steak), Ben $30.00 (pasta), Cara $10.00 (salad). Subtotal $100.00. Bill total = $118.00.

**Option A — Proportional-by-consumption** (service charge folds into `totalAmount`, spread by each diner's order share, exactly like tax/tip today):
- Shares: Ana 0.60, Ben 0.30, Cara 0.10.
- Service charge split: Ana $10.80, Ben $5.40, Cara $1.80 (= 18% of each person's own order).
- **Pays:** Ana $70.80, Ben $35.40, Cara $11.80. Sum = **$118.00**. ✓
- *Pros:* matches V1's tax/tip mental model and existing `ReceiptSplitEngine.swift:73` path — zero new engine math; "everyone pays 18% on what they ate" is intuitive and is the legally-correct treatment of a percent-of-subtotal charge.
- *Cons:* the big spender absorbs the most service charge; some groups feel a *mandatory* fee should be shared flat regardless of who ordered what.

**Option B — Equal-per-head** (service charge split evenly across the N participants, like a flat cover):
- $18.00 ÷ 3 = $6.00 each.
- **Pays:** Ana $66.00, Ben $36.00, Cara $16.00. Sum = **$118.00**. ✓
- *Pros:* "the table pays the fee equally" feels fair to some for a charge nobody chose; trivially explained.
- *Cons:* Cara (salad, $10) now pays a $6.00 fee = **60% of her food** while Ana's fee is 10% of hers — regressive and arguably wrong for a *percentage* charge, which by definition scales with consumption. Mathematically misrepresents a "% of subtotal" line as a flat fee.

**Recommendation: A (proportional-by-consumption) — A-default, no B-toggle for the percentage case.** A percentage service charge IS a percentage of subtotal by definition; apportioning it proportionally is the only treatment that preserves "each head pays X% of their own order," and it reuses the verified `ReceiptSplitEngine.swift:73` path with no new math. Reserve equal-per-head strictly for *flat* cover/minimum charges (separate matrix row). **Tippable-on-top: NO by default** — `SummaryItemCalculator.calculatedTip` (verified `SummaryItemCalculator.swift:21`) computes tip base as `subtotalValue` (or `subtotalValue+taxValue`) with **no service-charge term**; when a mandatory gratuity is present, suppress/warn the discretionary tip suggestion or a table pays ~36% gratuity (`catalog:354-360`). **Taxable: NO** — model it as post-tax (own term in `calculatedTotal`), not inside the tax base. **In the tip base: NO** — tip base must explicitly exclude the service charge.

**Invariant the rule must preserve (`MathInvariants.swift`, verified):**
- `assertZeroSum` (`:27`): Σ(amountOwedByEach) + Σ(orphans) == `resolvedTotalAmount` ±$0.01 — once `serviceCharge` is a first-class term in `calculatedTotal`, it must be inside this sum with **no silent-drop path**, and `resolvedTotalAmount` must stop preferring a computed total that omits a known scanned charge (`Receipt.swift:270-272`).
- `assertEmptyItemsAllZero` (`:381`, the v1.8 canary): a receipt with **zero line items** must keep every participant at $0. A percent-of-subtotal grat on a zero-item bill is $0, so this holds — but the spec must pin that grat-on-zero-items floats to the payer (orphan-like), never distributes. This is the `needs-revision` flag from `catalog:311`; reconcile before shipping.
- `assertBounded` (`:50`): 0 ≤ owed ≤ total must hold under the service-charge term.

> **Adversarial (mandatory-service-charge):** Both worked tables are arithmetically exact (A sums to $118.00 with shares 0.60/0.30/0.10; B to $118.00 at $6.00/head), and the recommendation is sound for the percentage case: routing the charge through the verified `ReceiptSplitEngine.swift:73` proportional path means a true proportion=0 diner (ordered $0) pays $0 of an 18%-of-subtotal charge — no misbill — and a zero-item bill yields SC = 18% × 0 = $0, so `assertEmptyItemsAllZero` holds as claimed. ZERO_SUM and BOUNDED_LOWER are not threatened by the charge itself because a mandatory % service charge is strictly positive (10–18%), so it can only raise `owed`, never drive it below 0. The one place the spec is doing real work and must not be hand-waved is the catering receipt it cites as the forcing case — that bill *also* carries a negative `−deposit`/credit term, and the BOUNDED_LOWER risk lives entirely in *that* separate row (a small-share diner could go negative if proportional credits exceed their positive charges), so the row is correct to explicitly fence "grat-on-zero-items floats to the payer (orphan-like)" and to keep flat cover charges in a different row rather than collapsing them.

---

Both invariants confirmed at the cited lines (ZERO_SUM at :27, EMPTY_ITEMS_ALL_ZERO at :394). All code citations verified. Writing the matrix row.

## flat-cover-minimum

**Question for Leo:** A FLAT per-head cover charge / table minimum / couvert (e.g. $35/head, RM10/pax, $10 drink minimum, AYCE "2 adult $49.90"). Should it apportion **proportional-by-consumption** (today's only behavior) or **equal-per-head** — and CRITICALLY, how do we bill a diner whose consumption proportion is **0** (the non-drinker at an AYCE, a kid who ordered nothing, someone whose food was on another's tab)? **The current engine literally cannot bill a proportion-0 person:** `ReceiptSplitEngine.swift:84-89` backfills any participant with no claimed items to `amountOwedByEach = 0.0`, and line 73 scales every share by a consumption proportion that is 0 for them. A flat cover is the canonical case where $0 is the *wrong* answer.

**The real receipt that forces this:** P8 V1-misses story (`/Users/leokwan/Development/vidux/projects/ocr-moat/tasks/P8-receipt-intelligence-v2/evidence/2026-05-30-what-v1-splitter-misses.md` line 18, table row "Cover / minimum charge") — **"2× $35 cover = $70", AYCE "2 adult" $49.90, and "drink minimum $10".** Cataloged as the **[P0]** "Flat per-head COVER / table charge spread proportionally instead of equal-per-head" row in `2026-05-30-edge-case-catalog.md:390`. V1 has no `.cover` kind: `SummaryItemType` is exactly `{custom, tip, tax, total, subtotal}` (`ReceiptItemsFixer.swift:444-450`), so a cover can only land as a `.custom` SummaryItem, get folded into `resolvedTotalAmount` via `ReceiptTotalCalculator.swift:19` (`itemSum + tax + tip + customExtras`, purely additive), then smeared by the consumption multiply at `ReceiptSplitEngine.swift:73`. Grep confirms zero per-head logic anywhere in `ReceiptSplitter/`.

**Worked setup (used by both options):** 3-person table, two adults. Food ordered: **Ana $90 steak, Ben $30 pasta, Cleo $0 (kid, drank tap water, ordered nothing).** Restaurant prints a **flat $35/head couvert ×3 = $105** cover line. Food subtotal = $120; total bill = $120 + $105 = $225. Correct real-world cover liability is unambiguous: **$35 each, three people, $105 — independent of what anyone ate.**

**Option A — Proportional-by-consumption (V1 behavior today):**
The $105 cover is folded into the $225 pool and scaled by food-consumption proportion (Ana 90/120 = 0.75, Ben 30/120 = 0.25, Cleo 0/120 = 0).
- Ana pays 0.75 × $225 = **$168.75** (her true liability: $90 food + $35 cover = $125 → **overcharged $43.75**)
- Ben pays 0.25 × $225 = **$56.25** (true: $30 + $35 = $65 → undercharged $8.75)
- Cleo pays 0.00 × $225 = **$0.00** (true: $0 food + $35 cover = $35 → **the kid's $35 cover silently vanishes onto Ana**)
- Sum = $225.00 ✓ (ZERO_SUM holds — that's exactly why the bug is invisible)
- **Pros:** Zero code change; ZERO_SUM (`MathInvariants.swift:27`) and the totals reconcile, so nothing trips a test or banner. **Cons:** Mis-bills real people — the heavy eater absorbs the light eaters' cover, and **a proportion-0 diner pays $0 of a charge they are personally, contractually liable for** (you occupied a seat / the AYCE counts your head). On $70 cover over a $130 food bill the catalog measures up to **~$14/person error** vs correct flat. A cover-only or pre-itemized event check (catering, AYCE before items are claimed) degenerates to **$0 for everyone** and the payer eats the entire mandatory charge.

**Option B — Equal-per-head (flat cover as its own pool):**
Tag the cover as an equal-per-head extra. Apportion it **outside** the consumption-proportion vector as a separate $105/3 = **$35/head** layer added on top of each person's food share. (Penny remainder, if headcount doesn't divide evenly, goes to `sortedIds.first` exactly like the engine's existing remainder rule at `ReceiptSplitEngine.swift:79`.)
- Ana: $90 food + $35 cover = **$125.00**
- Ben: $30 food + $35 cover = **$65.00**
- Cleo: $0 food + $35 cover = **$35.00** ← **the proportion-0 diner is correctly billed her flat cover**
- Sum = $225.00 ✓ (ZERO_SUM still holds)
- **Pros:** Matches reality — a cover/minimum/couvert is intrinsically per-seat; the kid and the non-drinker pay their cover and the steak-eater stops absorbing it. **Cons:** Requires (1) a new apportionment-mode tag on the extra and (2) it must NOT be injected into the proportion vector (proportions derive only from item raw-amounts per `assertProportionBounded`; adding per-head weight there pushes Σproportions off 1.0). **Hard collision to resolve:** a per-head cover on a **zero-line-item** receipt (cover-only / AYCE-before-itemizing) forces `cover/N > 0` on every head, which violates the **EMPTY_ITEMS_ALL_ZERO** canary (`MathInvariants.swift:394`, demands $0 when items are empty). The flat pool must be layered ON TOP of the consumption pool so the item-derived portion still satisfies EMPTY_ITEMS_ALL_ZERO, and the no-item all-cover case needs an explicit reconcile decision.

**Recommendation:** **B (equal-per-head), as the default for any extra typed cover/minimum/couvert — needs-Leo only on whether legacy `.custom`-entered charges silently inherit the new equal-per-head mode or stay proportional.** Why: a flat $X/head cover is a *fixed per-seat liability*, not a function of consumption; the entire reason this row is a P0 is that V1's single proportional path bills the proportion-0 diner $0 and that is a concrete, repeatable misbill of real people (the kid, the non-drinker, the pre-itemized event check). Proportional remains correct only for *percentage-of-subtotal* charges (a 10%/18% service charge) — those are a different matrix row and must keep the proportional path. The one genuinely Leo-level judgment is migration: do not silently re-apportion every existing `.custom` line as per-head (that would change historical splits); gate the new mode behind the new tag and leave untagged `.custom` proportional.

**Invariant the rule must preserve:** **ZERO_SUM** (`MathInvariants.swift:27`) — Σ(participant owed) + Σ(orphan amounts) == totalAmount must still hold after the flat per-head slice is added back (both worked examples sum to $225.00). Plus a **new FLAT_FEE_EQUAL_PER_HEAD** assertion: each of N participants owes `fee/N` within ±$0.01, **a zero-consumption participant still owes their full per-head slice** (Cleo = $35.00, never $0), and the penny remainder lands on `sortedIds.first`. And the fix must NOT break **EMPTY_ITEMS_ALL_ZERO** (`MathInvariants.swift:394`) for the item-derived portion — so the per-head cover is a layered pool, and the no-item/cover-only reconcile path is decided explicitly rather than left to collide with the v1.8 zero-items canary.

> **Adversarial (flat-cover-minimum):** Sound — I re-verified the arithmetic and the invariant logic holds. Option A's worked example sums to $225 (168.75 + 56.25 + 0 = 225) and Option B's also sums to $225 (125 + 65 + 35 = 225), so ZERO_SUM is preserved either way; the recommendation correctly identifies that A's pass is *deceptive* (it reconciles while silently shifting Cleo's $35 onto Ana, the textbook proportion-0 misbill). The candidate is also right that BOUNDED_LOWER is not at risk here (a positive flat cover never drives a share negative; the negatives/credit case is correctly punted to a separate row), and that Option B's only real hazard is the zero-line-item collision with EMPTY_ITEMS_ALL_ZERO — which it flags rather than glosses, requiring the flat pool to layer ON TOP of (not inside) the consumption-proportion vector so the item-derived portion still returns $0 when items are empty. One gap worth surfacing: the catalog claims "$35/head ×3 = $105" but the worked total ($225 = $120 food + $105 cover) is internally consistent, so the only unresolved real-money decision is the migration gate (legacy `.custom` charges must NOT silently flip to per-head, or historical splits change) — correctly escalated to Leo rather than auto-applied.

---

All citations confirmed against the real iOS files: `BOUNDED_LOWER` (owed >= -0.01) at MathInvariants.swift:57, `assertPayerCredit` (payer balance = receiptTotal − payer.amountOwed) at MathInvariants.swift:332-355, the purely-additive `ReceiptTotalCalculator.swift:19`, the proportional `ReceiptSplitEngine.swift:73`, and `OCRSnapshotBridge.swift:92-98` dropping `.credit`. The Reconciler at line 78 already computes `expected = subtotal + positives − negatives` via `.credit`. Here is the matrix row.

## deposit-prepayment

**The receipt that forces this decision.** P8 V1-misses corpus story (`vidux/projects/ocr-moat/tasks/P8-receipt-intelligence-v2/evidence/2026-05-30-what-v1-splitter-misses.md:20,25`): a real catering check where the printed **Total = $2180.26** but **Balance Due = $1918.26**, because a **`tripleseat deposit redeem −$262.00`** was prepaid. In real catering, ONE host put that $262 down weeks earlier — it is that host's money coming back, not a discount the merchant granted the table. (Note: the 48-row `corpus.jsonl` does NOT carry this — only 4 rows are scanned; the deposit figures live entirely in the P8 story prose. This is a prose-evidenced P0, not a corpus-native one.)

**Why V1 mis-bills today.** `ReceiptTotalCalculator.calculatedTotal = itemSum + tax + tip + customExtras` (`ReceiptTotalCalculator.swift:19`, purely additive) resolves to the GROSS $2180.26 and never the $1918.26 net. The engine then splits $2180.26 proportional-by-consumption (`ReceiptSplitEngine.swift:73`). A deposit line is silently dropped at ingestion (`OCRSnapshotBridge.swift:92-98` drops `.credit`). So the table is over-billed by the full $262 and the host pays it twice.

**Worked table for both options** — 3-person catering table, gross subtotal-driven proportions A:B:C = 50% / 30% / 20% of the $2180.26 gross (A is the host who fronted the $262 deposit). Gross proportional shares: A $1090.13, B $654.08, C $436.05 (sums to $2180.26).

### Option A — Deposit is ONE person's money returned (credit the payer)
The $262 is attributed to host A *after* the proportional split runs on the GROSS total. B and C are untouched; only A's net drops by $262.
- A net = $1090.13 − $262.00 = **$828.13**
- B net = **$654.08**
- C net = **$436.05**
- **Collection check:** A pays $828.13 + the $262 already prepaid = $1090.13 (A's true gross share). B+C = $1090.13. Cash collected at table = 828.13 + 654.08 + 436.05 = **$1918.26 = Balance Due.** ✓
- **Pros:** Matches the real-world fact (A's deposit was A's money). Mirrors the existing `assertPayerCredit` pattern (`MathInvariants.swift:332-355`) — a known, tested shape. B and C see identical numbers to a no-deposit split, which is what they actually owe.
- **Cons:** Requires capturing *who* fronted the deposit (a `creditedTo` attribution UI), which OCR cannot infer — needs a user tap. If A's own share is smaller than the deposit, A goes negative (owed change) and trips `BOUNDED_LOWER` (`owed >= -0.01`, `MathInvariants.swift:57`) unless an over-credit/refund path exists.

### Option B — Deposit is a TABLE-WIDE prepayment (reduce everyone proportionally)
The $262 shrinks the distributable pool to $1918.26; everyone's share drops by their consumption ratio.
- A net = 50% × $1918.26 = **$959.13**
- B net = 30% × $1918.26 = **$575.48**
- C net = 20% × $1918.26 = **$383.65**
- **Sums to $1918.26 = Balance Due.** ✓
- **Pros:** No attribution UI needed — purely arithmetic, OCR-derivable from the two printed numbers. Sums cleanly to balance-due. Correct *only* when the deposit was genuinely a group-pooled prepayment (rare for catering, common for a shared trip "we all chipped in a deposit").
- **Cons:** For the canonical catering case this is the **wrong-money transfer**: host A fronted $262 but recovers only their 50% share (~$131) — B and C pocket the other ~$131 of A's money as a discount on their own meals. The larger the table, the worse: at 8 diners the host loses ~$229 to the others (P8 story:485-486).

**Recommendation: A-default-with-B-toggle.** Default to payer-attributed credit (Option A) because the canonical evidence is catering where one host prepays — Option B silently robs that host. But the split pool must still reconcile to balance-due, so expose a per-deposit toggle "this deposit was shared by the table" that switches to B for the genuine group-pooled case. Engineering shape (plan-only): model the deposit as a post-split settlement credit on a named participant (mirroring `assertPayerCredit`), NOT as a negative `.custom` flowing through `customExtras` — a negative custom would shrink `distributableAmount` (`ReceiptSplitEngine.swift:64`) and spread the credit proportionally, which IS Option B applied unconditionally and is the exact mis-bill. The Reconciler already computes `expected = subtotal + positives − negatives` via `.credit` (`Reconciler.swift:78`), so the credit concept belongs at the SummaryItem→engine bridge, not a greenfield schema.

**Invariant the rule must preserve.** A new `TOTAL_VS_BALANCE_DUE`: the sum of all participant `amountOwed` must equal **balance_due (= gross total − deposit credits)**, never gross total — while `assertZeroSum` (Σ participants + Σ orphans == totalAmount, the PR #397 SEV-0 contract) stays intact against a deposit-aware total (ADD the new invariant, do not mutate the existing one). Plus `BOUNDED_LOWER` (`owed >= -0.01`, `MathInvariants.swift:57`) must hold under Option A: no participant — including the credited host — is driven below zero without an explicit over-credit/refund path; and tax/tip base stays computed on GROSS subtotal (a deposit reduces the distributable pool, not the tax actually owed).

> Both worked tables verify exactly. My adversarial findings:
> 
> **Adversarial (deposit-prepayment):** The arithmetic is sound — Option A nets (828.13 / 654.08 / 436.05) and Option B nets (959.13 / 575.48 / 383.65) both sum to the $1918.26 balance-due, and A's collected-plus-prepaid reconciles to the $1090.13 gross share, so the A-default recommendation correctly routes A's own money back to A rather than discounting B/C. The recommendation is well-guarded on the invariant front: it explicitly ADDs `TOTAL_VS_BALANCE_DUE` without mutating `assertZeroSum`, models the credit as a post-split named-participant settlement (not a negative `customExtras`, which would silently collapse to the Option-B mis-bill), and keeps tax/tip on the gross subtotal. The one real hole the candidate already half-flags but does not resolve: under Option A, BOUNDED_LOWER (`owed >= -0.01`) is only safe when the deposit ≤ the credited host's gross share — a light eater or large deposit (e.g., host A consumes $131 but fronted $262) drives A to −$131, which is a hard invariant breach unless the promised over-credit/refund path actually exists, so shipping A-default without that refund branch is the one scenario that mis-bills (it would either clamp A's owed to 0 and leak the excess credit, breaking ZERO_SUM against balance-due, or violate BOUNDED_LOWER). Also note the proportion=0 diner is untouched by either option (their 0% share stays $0 in both), so that invariant is not at risk here.

---

All citations are confirmed against the real iOS files. I have everything I need:

- **Real receipts:** catering check (deposit credit −$262.00, total $2180.26 ≠ balance due $1918.26) and the "comped items $0.00" / "10% service charge RM26" rows from the P8 what-V1-misses story (lines 16, 20, 23, 25); corpus row for "1 receipt with discount/credit line" (P2 PLAN.md:71).
- **Engine math:** proportional-by-consumption at ReceiptSplitEngine.swift:73, total = `itemSum + tax + tip + customExtras` at ReceiptTotalCalculator.swift:19.
- **Reconciler:** `negativeKinds = [.discount, .credit]` subtracts via `abs()` at Reconciler.swift:71,75-78; matchThreshold 0.01 at :34.
- **Invariants:** assertZeroSum (Σ participants + Σ orphans == total ±0.01), assertBounded/BOUNDED_LOWER (0 ≤ amountOwed, negative extras risk tripping it), assertEmptyItemsAllZero (zero items ⇒ everyone owes $0 — the canary a targeted-comp-on-cover-only bill could violate).

Here is the matrix row.

## comp-discount-voucher

**Decision owner:** Leo (P0 — real people get mis-billed; the corpus already contains a receipt this defect harms).

### The real receipt that forces this

Two real corpus receipts make this unavoidable:

1. **Catering check (P8 "what V1 misses," `2026-05-30-what-v1-splitter-misses.md:20,25`):** `tripleseat deposit redeem −$262.00`, classified `.credit`. The printed math is `total $2180.26 != balance due $1918.26` — the $262 gap **is** the credit. V1 has no concept of either the credit *or* the gap, so it splits the wrong number (`v1-misses:33`).
2. **Comped items (`2026-05-30-what-v1-splitter-misses.md:23`):** "ice water ×2, comped mushroom/pancake" — `$0.00` line items the splitter must keep visible. A *targeted* comp (one entrée removed, the rest of the table pays full) is structurally different from a table-wide deposit.
3. **Table-wide promo (`v1-misses:16`):** "10% service charge = RM26" is the inverse-sign sibling — a table-wide multiplier. The matrix promotion target for a discount/credit fixture is logged in `P2-fixture-corpus-runner/PLAN.md:71` ("1 receipt with discount/credit line") and `P6...PLAN.md:82` row #9 ("discount/credit negative").

The hinge question: **when a comp/voucher/discount reduces the bill, does the reduction land on everyone (proportional), on the comped item's owner only (targeted), or split flat (equal-per-head)? And does a table-wide deposit behave the same as a one-entrée comp?**

### Option A — One rule: ALL reductions are proportional-by-consumption (the V1-native path)

A negative extra (credit/discount/voucher) is a single receipt-level term folded into `resolvedTotalAmount` via `ReceiptTotalCalculator.calculatedTotal = itemSum + tax + tip + customExtras` (`ReceiptTotalCalculator.swift:19`), then the engine spreads it in each person's consumption ratio at `ReceiptSplitEngine.swift:73`. Matches the reconciler, which already subtracts `negativeKinds = [.discount, .credit]` via `abs()` from the expected total (`Reconciler.swift:71,75-78`).

**Worked example — $30 table-wide $9 voucher, 3 people:**
| Person | Ordered | Pre-comp subtotal | Proportion | After −$9 voucher |
|---|---|---|---|---|
| Ann | Steak | $20.00 | 0.6667 | $14.00 |
| Bob | Pasta | $7.00 | 0.2333 | $4.90 |
| Cara | Soup | $3.00 | 0.1000 | $2.10 |
| **Σ** | | **$30.00** | 1.000 | **$21.00** ✓ (= $30 − $9) |

Voucher pool = $30, distributable = $30 − $9 = $21, each share = proportion × $21.

**Pros:** zero new split-mode code; reconciler already agrees on the sign; `assertZeroSum` holds for free (Σ shares == $21). Correct for a **table-wide** promo/deposit where the whole table earned the discount (the catering deposit case).
**Cons:** **WRONG for a targeted comp.** If Ann's $20 steak is comped (not a table-wide voucher), Option A still drops the −$20 proportionally — Ann pays $6.67 for a steak that was free while Bob/Cara get a discount they didn't earn. It is also the path most likely to trip **BOUNDED_LOWER** (`assertBounded`, 0 ≤ amountOwed): a credit larger than a low-consumer's share drives `proportion × distributable` negative — the catalog flags negative extras as "completely untested" against this invariant (`code-state-map.md:58`).

### Option B — Targeted-first: the comp/voucher attaches to the line item(s) it applies to; only a table-wide promo is proportional

A targeted comp zeroes (or reduces) the specific `ReceiptItem.amount` it names — the comped owner's consumption drops, so the engine's proportions recompute naturally and **only that owner's share falls**. A table-wide voucher (no item named) still routes through Option A's proportional path.

**Worked example — same $30 table, Ann's $20 steak fully comped, 3 people:**
| Person | Ordered | Effective subtotal | New proportion | Pays |
|---|---|---|---|---|
| Ann | Steak (comped → $0) | $0.00 | 0.000 | $0.00 |
| Bob | Pasta | $7.00 | 0.700 | $7.00 |
| Cara | Soup | $3.00 | 0.300 | $3.00 |
| **Σ** | | **$10.00** | 1.000 | **$10.00** ✓ (= $30 − $20 comp) |

The −$20 lands entirely on Ann (she eats free); Bob and Cara pay exactly what they ordered. Bill drops from $30 to $10, which equals subtotal minus the comped line.

**Pros:** matches real-world intent — a comped entrée benefits the person who ordered it, not the table. Keeps comped items **visible as $0 lines** (the `v1-misses:23` requirement) instead of deleting them. Sidesteps BOUNDED_LOWER because reducing an item's amount can't push any share below 0.
**Cons:** requires a new first-class representation (a per-item comp flag or a `discount` that names target item IDs) — there is **no `isComped`/`isVoided` field today; a comp can only be modeled by deleting the line or zeroing `customAmount`** (`code-state-map.md:219`). Needs disambiguation logic: "is this credit targeted or table-wide?" A **cover-only / zero-line-items** bill with a table-wide voucher still falls to the proportional path and must NOT violate `assertEmptyItemsAllZero` (zero items ⇒ everyone owes $0, `MathInvariants.swift:394-413`) — the voucher floats to the payer, exactly like an orphan.

### Recommendation

**B (targeted-first) with A as the explicit fallback for un-attributable reductions — `needs-Leo` on one sub-question.** Targeted is the only rule that bills the right person for a one-entrée comp, and proportional is correct for the table-wide deposit; the two are genuinely different cases, so a single rule (Option A alone) mis-bills half the corpus. **The `needs-Leo` call:** for an *equal-per-head* voucher ("$30 off, split the savings evenly" — common with Groupon/gift-card promos), neither A nor B is right; that is a third mode and Leo must rule whether it's in-scope for V2 or deferred. Default to A's proportional behavior for any reduction that can't be attributed to specific items, and surface a comped item as a struck-through $0 line rather than deleting it.

### Invariant the rule MUST preserve

`assertZeroSum` — **Σ(participant shares) + Σ(orphan amounts) == resolvedTotalAmount ± $0.01** (`MathInvariants.swift:27-43`, ReceiptSplitCalculator.swift:159), with the post-comp `resolvedTotalAmount` now net of the reduction. Co-required: **`assertBounded` / BOUNDED_LOWER — 0 ≤ amountOwed** must hold even when a credit exceeds a low-consumer's share (the untested negative-extra under-flow, `code-state-map.md:58`); and **`assertEmptyItemsAllZero`** must not break when a table-wide voucher hits a zero-line-item (cover-only) bill — the reduction floats to the payer like an orphan, every participant still owes $0.

> **Adversarial (comp-discount-voucher):** The worked examples sum correctly (Option A: $14.00+$4.90+$2.10=$21.00=$30−$9; Option B: $0+$7+$3=$10=$30−$20), so the arithmetic holds, but Option A is unsound as a *single* rule precisely where the recommendation admits it: a targeted comp folded into `customExtras` and spread by consumption ratio mis-bills the comped diner (Ann pays $6.67 for a free steak) and can drive a low-consumer's `proportion × distributable` negative, tripping BOUNDED_LOWER (`assertBounded`, 0 ≤ amountOwed) on exactly the negative-extra path the catalog flags as untested (`code-state-map.md:58`). The candidate correctly identifies the proportion=0 / ZERO_SUM edges but understates one: a credit larger than the *whole* table's subtotal (e.g. the −$262 catering deposit exceeding a small residual balance) makes the distributable total negative, so even the table-wide path can violate ZERO_SUM-with-BOUNDED_LOWER unless reductions are clamped and any residual routed to orphans — neither worked example exercises that overshoot. Option B is the sound default for targeted comps but is incomplete: it has no answer for a table-wide credit on a *zero-line-item / cover-only* bill, where routing back to the proportional path with empty items must still satisfy `assertEmptyItemsAllZero` — so ship B for named-item comps, but require an explicit clamp-and-orphan rule for credits that exceed the distributable base before either option is invariant-safe.

---

Final confirmation found. `ReceiptItemViewModel.swift:29` renders `"\(item.quantity ?? 1) x \(title)"` — so the integer-coerced quantity becomes a **visible label** in the UI: a 1.45 lb seafood line displays as "1 x King Crab", and a 2.6 lb line displays as "3 x King Crab". The split math splits the line `amount` (total price) correctly regardless, but the **label lies** and the per-person mental check ("am I paying for the right weight?") breaks. I have everything verified.

## weighted-item

**Decision needed: how should a weighted, fractional-quantity shared item (e.g. seafood sold per-lb/kg) split?**

### The real receipt that forces this

Seafood/butcher/produce lines are priced as **weight × unit-price** and almost never land on a whole number: `KING CRAB 1.45 lb @ $39.99 = $57.99`, `SNOW CRAB 2.6 lb`, `HALIBUT 0.84 kg`. This is the **weighted-quantity / scale-priced row** named in the P9.3 edge-case catalog (`2026-05-30-edge-case-catalog.md`) and the i18n investigation's deli/wet-market evidence — the canonical "shared seafood platter, split among the table" story. The corpus is 47/48 un-scanned stubs (only Marathon Cafe is fully parsed), so the evidence here is the catalog + i18n doc naming real per-weight receipts in Leo's Photos, not a parsed corpus row.

**What V1 actually does (confirmed against the iOS source):**
- `OCRSnapshotMapper.swift:71` — `let quantity = max(1, Int((obj.quantity?.valueNumber ?? 1).rounded()))`. A `1.45` lb reading rounds to **1**; a `2.6` lb reading rounds to **3**. The fractional weight is destroyed at ingest.
- **Crucial:** the line `amount` is `obj.totalPrice?.valueCurrency?.amount` (`OCRSnapshotMapper.swift:69`) — the **whole-line total**, not unit price. `ReceiptSplitEngine.swift:27/33` splits `item.amount` directly (never amount×qty), so the **dollar split is correct regardless of the rounded quantity.** The money is right.
- The damage is **display and trust**, not dollars: `ReceiptItemViewModel.swift:29` renders `"\(item.quantity ?? 1) x \(title)"`, so `$57.99` of crab shows as **"1 x King Crab"** (and a 2.6 lb line shows **"3 x King Crab"**). The label contradicts the price; a diner sanity-checking "am I paying for 1 crab or 1.45 lb?" sees a lie. The integer coercion also silently mismatches the **reconciler**, which recomputes `sum += amount × Double(quantity ?? 1)` (`Reconciler.swift:59`) — a per-lb line whose `amount` is already the line total gets multiplied by the rounded qty, fabricating a phantom subtotal-mismatch finding (or hiding a real one) when qty ≠ 1.

So the product question is **not "who pays what"** (the engine already proportions by line total correctly) — it is **"what does the row say it is, and does the receipt still reconcile."** Both options below therefore split the same dollars; they differ in label fidelity and reconciler correctness.

---

### Option A — Keep integer quantity; show weight as a descriptor, never multiply

Stop coercing weight into the `quantity` Int. Treat a scale-priced row as **quantity = 1 line** (one crab order), preserve the raw weight as a display string baked into the title/subtitle (`"King Crab · 1.45 lb"`), and split the line total by consumption like any other shared item. Fix `Reconciler.swift:59` to **not** multiply when the line is weight-priced (its `amount` is already the line total).

**Worked example — shared crab platter, 3 people, $90.00 receipt:**

| Item | Line total | Who consumes | Per-person |
|---|---|---|---|
| King Crab · 1.45 lb (shared) | $57.99 | Ann, Bo, Cy (equal) | $19.33 each |
| Halibut · 0.84 kg (Ann only) | $18.01 | Ann | $18.01 |
| Tax + tip | $14.00 | by consumption proportion | see below |

Raw consumption: Ann = 19.33+18.01 = **$37.34**, Bo = **$19.33**, Cy = **$19.33** → proportions 0.492 / 0.254 / 0.254. Distribute the full **$90.00** by proportion:
- **Ann pays $44.27**, **Bo pays $22.86**, **Cy pays $22.87** (cent remainder lands on first sorted id per `ReceiptSplitEngine.swift:78`). **Sum = $90.00.** Rows read "King Crab · 1.45 lb", "Halibut · 0.84 kg" — honest labels.

**Pros:** Zero engine-math change (money already correct today). Smallest, safest diff. Kills the "3 x King Crab" lie and the phantom reconciler finding. No new data model. Preserves the existing `Σ(owed) + Σ(orphan) == total` invariant untouched.
**Cons:** Weight is "just a string" — you can't later let one diner claim "I only ate 0.5 of the 1.45 lb." Power-users who want true by-the-gram apportionment aren't served. The `quantity` field stays semantically wrong for non-weighted multi-packs (orthogonal problem).

---

### Option B — First-class fractional/decimal quantity (Decimal weight + unit price)

Promote `quantity` from `Int?` to a `Decimal` (or add `weight`+`unitPrice` fields), carry `1.45 lb @ $39.99`, render `"1.45 lb × $39.99 = $57.99"`, and let the split optionally apportion **by weight-share** when multiple diners split one weighted line unevenly.

**Worked example — same platter, but Ann ate more crab:**

| Item | 1.45 lb @ $39.99 = $57.99, split by claimed weight |
|---|---|
| Ann claims 0.80 lb | $31.99 |
| Bo claims 0.45 lb | $17.99 |
| Cy claims 0.20 lb | $8.00 |

Crab line: Ann **$31.99** + Bo **$17.99** + Cy **$8.00** = **$57.98** (1¢ rounding remainder → Ann = $32.00, sum **$57.99**). Add Halibut (Ann $18.01) + $14 tax/tip by proportion → Ann ≈ **$53.??**, etc., summing to **$90.00**. Rows read "1.45 lb × $39.99" — fully honest and itemizable.

**Pros:** Truthful to the receipt; enables real by-weight fairness for the one scenario where it matters (someone ate most of the crab). Fixes reconciler cleanly (`unitPrice × weight` is well-defined). Future-proof for deli/wet-market i18n receipts.
**Cons:** Schema migration on `ReceiptItem` (SwiftData), touches the mapper, engine, reconciler, three preview/test fixtures, and the row UI — a **large, multi-surface diff during a frozen launch window.** New UX (a weight-claim picker) to even use the unequal-split path. Risk of introducing a money-loss regression into a currently-correct engine, against the `SplitEngineMoneyLossTests` oracle.

---

**Recommendation: A-default-with-B-toggle (ship A now; defer B post-2.0).** A is a label-and-reconciler fix on top of math that is **already correct** — it removes the user-facing lie and the phantom reconciler finding with a near-zero-risk diff that fits the launch-window scope rule (P0 bug fix, not P3 polish). B is the "right" long-term model but it's a SwiftData migration across 6+ surfaces with real money-loss regression risk — wrong trade to make before 2.0 ships. The unequal-by-weight scenario B serves is rare enough to wait. **This is not `needs-Leo`** for A: it's a bug (a $57.99 line labeled "1 x" / "3 x"). B's schema change and the weight-claim UX *do* need Leo's product call post-launch.

**Invariant the rule must preserve:** `Σ(amountOwedByEach) + Σ(orphan amounts) == totalAmount` (the `ReceiptSplitEngine.swift:78` cents-exact remainder invariant guarded by `SplitEngineMoneyLossTests` / `PropertyBasedEngineInvariantsTests`) — splitting must remain **conservative to the penny regardless of quantity**, and additionally the displayed quantity/weight label must never alter the dollar split (today's `amount`-based engine guarantees this; the reconciler at `Reconciler.swift:59` must be fixed so it does not multiply an already-total line by a coerced quantity).

> Both worked examples are now verified. The arithmetic check exposes errors in the candidate's own Option A numbers.
> 
> **Adversarial (weighted-item):** The recommendation is directionally sound — both options split `item.amount` (the line total) by consumption, so neither contradicts ZERO_SUM, and Option A is correctly the smallest safe diff that keeps the V1 invariants untouched. **But the Option A worked example is wrong:** distributing $90.00 by the 0.491/0.254/0.254 proportions yields **Ann $44.22, Bo $22.89, Cy $22.89** (sum $90.00), not the candidate's "$44.27 / $22.86 / $22.87"; the candidate also mis-states the proportions as 0.492/0.254/0.254 and the remainder routing is fictional since the proportional split already lands exactly. Option B's crab math is fine (0.80/0.45/0.20 lb → $31.99/$18.00/$8.00, raw sum $57.99 within a rounding cent), but two correctness traps must be gated before it ships: (1) the by-weight path needs a **claimed-weight == line-weight** validation, since nothing forces the diner claims to sum to 1.45 lb — under-claim silently drops cents (a money-loss / ZERO_SUM break) and over-claim over-bills; and (2) a **proportion=0 / unclaimed-weight diner** must still be handled by the engine's existing consumption path, not the new weight path, or a zero-weight claimant gets a phantom $0 line while the remainder mis-distributes — so adopt Option A now and defer B behind both invariant tests plus the BOUNDED_LOWER check for any negative (credit) lines that this weight-multiply path would otherwise sign-flip.

---

