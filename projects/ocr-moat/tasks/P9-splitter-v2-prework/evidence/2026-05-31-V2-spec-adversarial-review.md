# V2 Design-Spec — Adversarial Review (the gate before Leo acts)

> Source: workflow `wyjsbyecl`, 4 reviewers. Found real holes in the capstone; all folded back into `2026-05-31-V2-DESIGN-SPEC.md`. Below is the raw review for the record.

## Fixes applied to the spec from this review

1. **No-items + service-charge contradiction** → synthesize the equal item from `balanceDue − Σ(typed extras)`, not raw total; apportion typed extras as separate dollar layers (was: synthesize from total, which split the SC equal-per-head + poisoned the tip base).
2. **Credit-as-signed-customExtras = the #1 ship bug** → promoted a HARD MUST into the spec body: model credit/deposit as a post-split named-participant settlement adjustment, never a negative `customExtras` (passes ZERO_SUM, still mis-bills).
3. **`fee` 'per policy' coin-flip** → gave it a concrete default (flat-$ fee = equal-per-head; %-fee = proportional).
4. **Apportionment-as-dollar-layer** → flat/by-claim modes compute a separate dollar vector, MUST NOT be injected into `proportionByParticipant` (protects `PROPORTION_SUM`); equal-per-head computed on headcount, not 0/0 normalization.
5. **ZERO_SUM vs matchThreshold** → kept distinct: ZERO_SUM exact (0 residue), matchThreshold = 1 minor-unit slack.
6. **Negative path unguarded** → the existing negative test doesn't call `assertBounded`; prereq now requires wiring it.
7. **Payment & liability second axis** → added as an explicit scoped boundary (settlement follow-on), not silently dropped.
8. **`.unknown` framing corrected** → an unknown chip IS emitted; the real hole is the total-check skipping.

---

## internal-consistency

**Verdict: internally consistent on the three specific axes asked about, with two genuine under-specifications and one latent ordering gap. Details below.**

---

### A. Does any §1 apportionment (mode, base) conflict with the §4 proportion-is-truth contract?

**No direct conflict — but the bridge between them is asserted, not specified.**

The §4 contract is: *proportion is source of truth; equal-split is the default proportion; the total scales proportions.* Each §1 mode reduces to a proportion vector, so all are compatible in principle:
- `proportional` (tax, tip, service, surcharge, mandate) → consumption-share proportions. Native fit.
- `by-claim` (line item, item-attributed fee) → claimant gets proportion 1, others 0. Fit.
- `equal-per-head` (cover, flat fee) → 1/N proportions. Fit — and §1 explicitly notes it must "bill proportion-0 diners," which is the same edge §4's synthesize-upstream relies on.

**The under-specification:** §4's contract is described as a *single global proportion vector scaling one total* ("the total scales proportions"). §1 introduces *per-charge* proportion vectors — a diner can be proportion-0 on `cover` (equal-per-head) but proportion-0.4 on `tax` (consumption). The spec never states how N per-charge proportion vectors compose back into the single "proportion is truth" object that §4 and the frozen settlement DTO consume. §9-line summary says "per-charge apportionment," but §4's invariant language is still single-vector. This is the seam the whole model turns on and it is asserted ("the contract holds") rather than shown. Not a contradiction, but the load-bearing reconciliation is missing.

---

### B. Does §4 synthesize-upstream equal-split interact badly with §1 typed-extra apportionment — specifically a no-items receipt that ALSO has a service charge?

**Yes — this is the sharpest real gap. It is under-specified bordering on contradictory.**

Trace the stated rules on `{ no line items, total, + mandatory serviceCharge }`:
- §4: "synthesize a single `sharedEqually` item = total UPSTREAM when OCR returns no items." It says **total**, and `total` (§3) includes the service charge.
- §1: serviceCharge mode is `proportional` over **consumption (subtotal share)**.

The collision: §4 synthesizes one equal item equal to the *whole total*. If the service charge is folded into that synthesized item, it is now apportioned **equal-per-head** (1/N, because it's inside the single sharedEqually item), directly violating §1's rule that serviceCharge is *proportional to consumption* and "not a tip, not in tip base." Conversely, if the engine first strips the service charge out as a typed extra and synthesizes the item from subtotal-only, then on a no-items receipt the consumption base for the proportional service charge is N identical synthesized shares — so proportional and equal-per-head coincide *numerically* (all diners equal), and the distinction is harmless **only in the degenerate equal case**. The spec never says which path executes, nor in what order synthesize-upstream (§4) runs relative to typed-extra extraction (§1). Sequencing (§87) orders the *features* (taxonomy is step 5, after money) but says nothing about per-receipt runtime ordering of synthesize-vs-apportion. Concrete contradiction risk: a no-items receipt where diners later claim unequal amounts (e.g. someone adds a manual item post-synthesis) would get the service charge split equal-per-head if it rode inside the synthesized item, contradicting §1.

**Tip base corollary (same root):** §3 says percent-tip base must be pre-tax subtotal; §1 says serviceCharge is "not in tip base." On a synthesized no-items receipt there is no real subtotal — the synthesized item IS the subtotal and it equals total (incl. service charge). So a percent-tip computed against that synthesized base would silently include the service charge in the tip base, contradicting both §1 and §3. Under-specified: §4 must say it synthesizes from **balance_due/total minus typed extras**, not raw total, or these two rules break together.

---

### C. Does currency-aware money (§2) conflict with the ZERO_SUM tolerance changes?

**No — consistent and mutually reinforcing, with one residual under-specification.**

§2 moves rounding/remainder into minor units and scales `matchThreshold`/`warnThreshold` to *1 minor unit*. §85 + the invariant list say to "currency-scale `ZERO_SUM`/`matchThreshold` tolerances to minor units" and adds `MINOR_UNIT_NO_SUBUNIT_RESIDUE`. These agree: ZERO_SUM is kept (§83) but its tolerance becomes currency-derived rather than the hardcoded `0.01` USD (`Reconciler.swift:34`). For JPY/KRW (scale 0) tolerance tightens to 1 yen and there is no sub-unit, so ZERO_SUM is exact; for BHD/KWD/OMR (scale 3) it loosens to 1 fils. No contradiction — the money type is precisely what makes the scaled tolerance well-defined.

**Residual under-specification:** "1 minor unit" as a *match* threshold and ZERO_SUM as an *exactness* invariant are subtly different guarantees. `MINOR_UNIT_NO_SUBUNIT_RESIDUE` implies remainder distribution leaves zero residue (exact), while a `matchThreshold` of 1 minor unit permits a 1-unit slack against the OCR-read total. The spec doesn't state whether ZERO_SUM (internal split sums to the split total — should be exact, 0 tolerance) and matchThreshold (split total vs scanned total — needs slack) are the *same* scaled number or two different ones. Using "1 minor unit" for both would weaken the internal ZERO_SUM exactness guarantee. Minor, but it's the one place §2 and the ZERO_SUM language are not pinned to the same meaning.

---

### Other internal note (not in the three asked axes, but a real ordering gap)

§1's `credit`/`discount`/`comp` rows depend on `NEGATIVE_EXTRA_BOUNDED_LOWER`, and Prereq #2 + §31 correctly mark the negative-BOUNDED engine fix as *blocking* before any negative extra ships. Consistent. But §1 lists `cover` as `equal-per-head` "incl. proportion-0 diners," and §4's synthesize-upstream produces 1/N — a proportion-0 diner (proportion exactly 0 on a flat charge) is exactly the divisor edge the Prereq #1 NaN/Inf guard exists to catch. The spec keeps `FLAT_CHARGE_EQUAL_PER_HEAD (incl. proportion-0)` and the NaN guard but never states that equal-per-head must bypass the proportion-normalization path (you cannot derive an equal-per-head share by normalizing a proportion vector that is all-zero for a flat charge — that's a 0/0). Under-specified: the equal-per-head mode needs an explicit "computed on headcount, not on normalized proportion" note, or it collides with PROPORTION_BOUNDED on a flat-charge-only receipt.

File reviewed: `/Users/leokwan/Development/vidux/projects/ocr-moat/tasks/P9-splitter-v2-prework/evidence/2026-05-31-V2-DESIGN-SPEC.md`

---

I have everything verified. The negative-amount test at `SplitEngineEdgeCaseTests.swift:38-69` confirms the engine produces `bob owes -10.0` and `proportion -0.25` today — but that test does NOT call `assertBounded`/`assertProportionBounded`, so those bounds are not enforced on that path. This is the crux. Here is the analysis.

## invariant-safety

**Scope:** V2-DESIGN-SPEC §1 (apportionment table, L17-29) + §6 ("Invariant changes", L82-86) vs the live suite at `resplit-ios/ReceiptSplitterTests/Invariants/`. Verdicts per proposed mode. STRICT read-only — no Swift touched.

### Invariants in force (verified at file:line)
- `ZERO_SUM` — `Σ owed + Σ orphan == total ±0.01` (`MathInvariants.swift:27`). Engine corpus uses it via `assertAllEngineInvariants:237`; property suite uses a **strict/relaxed split** by hand (`PropertyBasedEngineInvariantsTests.swift:169-191`).
- `BOUNDED` — `-0.01 ≤ owed ≤ total+0.01` (`MathInvariants.swift:50`; LOWER at `:57`).
- `PROPORTION_BOUNDED` — `0 ≤ p ≤ 1`, `Σp ~1.0 or ~0` (`MathInvariants.swift:77`).
- `REMAINDER_DETERMINISTIC` — `:149`. `EMPTY_ITEMS_ALL_ZERO` — `:381` (the v1.8 canary). Orphan/PR#397 contract = `ZERO_SUM` with orphans carried as a separate term (`assertPayerCredit:332` pins payer = `receiptTotal − payer.owed`, NOT `total − Σ non-payers`).

### 1. Cover charge → equal-per-head (incl. proportion-0 diner)
**Verdict: SAFE on ZERO_SUM/BOUNDED — but needs a NEW invariant + one structural guard. Will NOT silently break a green test if layered correctly; WILL break two if injected naively.**

- **ZERO_SUM holds** for a proportion-0 diner under equal-per-head. Worked example (decision-matrix L62-68): Cleo (ate $0) billed her flat $35; Σ = $225.00 = total. The mode raises a $0 share to a positive per-head slice — it can only *help* ZERO_SUM reconcile, never break it. `BOUNDED_LOWER` is not threatened (a positive flat fee never drives `owed` below 0; adversarial confirms L74).
- **The proportion-0 question, answered directly:** *Can equal-per-head on a proportion-0 diner still satisfy ZERO_SUM?* **Yes** — but only if the per-head pool is layered **ON TOP OF** the consumption-proportion vector, NOT injected into it. The catalog flags the hard collision (L68): if you add per-head weight into `proportionByParticipant`, `Σ proportions` is pushed off 1.0 → **`PROPORTION_BOUNDED` (PROPORTION_SUM, `MathInvariants.swift:99`) breaks a currently-green test.** The proportion-is-truth contract (L37) reinforces: a diner is only legitimately proportion-0 when line items exist and they claimed none — equal-per-head must add a separate dollar layer, leaving proportions untouched.
- **Second collision — the cover-only / zero-line-item bill:** a per-head cover on a receipt with **no items** forces `cover/N > 0` on every head, which **directly violates `EMPTY_ITEMS_ALL_ZERO` (`MathInvariants.swift:394`)** — a green, property-locked canary (`EmptyItemsInvariantsTests.swift`, 30 random pairs at `:52`). Spec §4/REFINEMENT 2 already routes around this (synthesize a `sharedEqually` item = total upstream, keep the guard intact) — but the cover-on-zero-items reconcile path must be explicitly decided, or this test goes red.
- **Needs:** `ADD FLAT_CHARGE_EQUAL_PER_HEAD` (spec §6 L84) — already on the spec's add-list. Must assert: each of N owes `fee/N ±0.01`, a zero-consumption diner owes the **full** per-head slice (never $0), remainder → `sortedIds.first`. **No existing invariant needs relaxing**, provided the layering discipline holds.

### 2. Item-attributed fee (CRV/corkage) → by-claim
**Verdict: SAFE. No invariant relaxed, no new invariant strictly required, no green test broken.**

- By-claim is structurally identical to the existing line-item path (`ReceiptSplitEngine.swift:73`, consumption proportion). The CRV/corkage rides on the claiming participant exactly as a `participantIds:["leo"]` individual item does today. ZERO_SUM, BOUNDED, PROPORTION_BOUNDED all hold unchanged — this is the V1-native path the corpus already exercises (`ReceiptSplitEngineInvariantsTests.swift` scenarios 1/3/7).
- Today these fees are **dropped** (`OCRSnapshotBridge.swift:92-98`), so the only risk is the *migration* clause (spec L98): don't silently re-apportion legacy `.custom`. Tagging it by-claim and routing through the existing path is the safest of all three modes. The spec lists no by-claim-specific invariant and none is needed.

### 3. Context-gated negative credit (deposit/discount, payer OR table-wide)
**Verdict: DANGER. This is the one mode that can SILENTLY BREAK a green test today AND requires a new invariant + a fix-FIRST prerequisite. Do not ship without it.**

- **Direct answer to "can a negative credit satisfy BOUNDED_LOWER?":** **Not unconditionally — and the engine already produces a BOUNDED_LOWER-violating result that no invariant currently catches.** `SplitEngineEdgeCaseTests.swift:38-69` proves the live engine returns `bob owes −10.0`, `proportion −0.25` for a negative line. That test asserts only the arithmetic (`:66-68`) — it **never calls `assertBounded` or `assertProportionBounded`**. So a negative extra routed through `customExtras`/the proportional path produces `owed < 0` (breaks `BOUNDED_LOWER:57`) and `proportion < 0` (breaks `PROPORTION_LOWER:84`) — and the green suite is blind to it because that path is untested against the shared lib. **This is the silent-break landmine:** the moment a V2 credit flows through the proportional engine and someone *does* wire `assertAllEngineInvariants` over it (as the corpus/property suites do for every other path), a previously-green-by-omission scenario turns red — or worse, ships a negative real-money owed.
- **Table-wide (Option B) overshoot:** a credit larger than the distributable base (e.g. −$262 catering deposit > residual balance) makes `distributableAmount` negative → ZERO_SUM-with-BOUNDED_LOWER breaks together (decision-matrix adversarial L181). Must clamp-and-route-residual-to-orphan.
- **Payer-credit (Option A) overshoot:** if the credited host's own gross share < deposit, the host goes negative → `BOUNDED_LOWER` breach (decision-matrix L95, L112). The spec correctly elevates this to a **blocking prerequisite** (§"Deposit/credit" L31; Prerequisites L78 — "Negative-amount BOUNDED… **Must fix before any negative extra ships**").
- **Needs:** `ADD NEGATIVE_EXTRA_BOUNDED_LOWER` + `BALANCE_DUE_SPLIT`/`TOTAL_VS_BALANCE_DUE` (spec §6 L84). Critically, `BOUNDED_LOWER` as written (`owed >= -0.01`) **must NOT be relaxed** to permit refunds — instead the credit belongs as a **post-split named-participant settlement credit** (decision-matrix L106), so a refund/negative-owed lives in the settlement layer where `SETTLEMENT_ZERO_SUM` governs it, NOT in `amountOwedByParticipant` where `BOUNDED_LOWER` governs it. A relaxed `BOUNDED_LOWER` on the engine output would weaken the SEV-0 sign-flip guard for *every* path.

### Summary table

| Mode | ZERO_SUM | BOUNDED_LOWER | PROPORTION_BOUNDED | EMPTY_ITEMS canary | Action |
|---|---|---|---|---|---|
| Cover → equal-per-head | ✅ holds (proportion-0 OK) | ✅ safe (positive only) | ⚠️ breaks if injected into proportion vector — layer ON TOP | ⚠️ breaks on cover-only/zero-item bill — synthesize upstream | ADD `FLAT_CHARGE_EQUAL_PER_HEAD`; no relax |
| Item-fee → by-claim | ✅ holds | ✅ safe | ✅ holds | ✅ unaffected | None required; honor migration gate |
| Negative credit (context-gated) | ⚠️ breaks on overshoot (clamp+orphan) | ❌ **engine already emits owed<0, untested → silent break** | ❌ engine already emits proportion<0, untested | ⚠️ table-wide voucher on zero-item must float to payer | ADD `NEGATIVE_EXTRA_BOUNDED_LOWER` + `BALANCE_DUE_SPLIT`; fix-FIRST prereq (L78); keep credit in settlement layer — **do NOT relax `BOUNDED_LOWER`** |

**Bottom line:** by-claim is free. Equal-per-head is safe but needs strict layering discipline (proportion vector + zero-item canary are the two tripwires) plus one new invariant. Context-gated negative credit is the only mode that (a) **already violates BOUNDED_LOWER/PROPORTION_LOWER in the live engine via an untested path** (`SplitEngineEdgeCaseTests.swift:38-69`), and (b) demands the negative-BOUNDED prerequisite ship first — the spec's blocking flag (L78) is correct and load-bearing. No invariant should be *relaxed*; three should be *added* exactly as §6 (L84) proposes.

---

I now have everything needed for a complete cross-doc consistency audit. Let me compile the findings.

## cross-doc-consistency

**Verdict: substantially FAITHFUL on the core model + the four canonical silent-money P0s + every decision-matrix recommendation, but the capstone DROPS an entire P0 class the completeness sweep (P9.8) surfaced — the "second axis: payment & liability" P0s — and silently demotes two tax/currency P0s the completeness critic raised. The headline numbers (31%, divergence counts, currency counts) carry through CONSISTENTLY with one minor internal-rounding caveat.**

---

### A. Decision-matrix recommendations → spec (P9.6 → capstone). FAITHFUL, all 5 carried.

| Matrix row | Matrix recommendation | Spec §1 row | Match |
|---|---|---|---|
| mandatory-service-charge | A proportional, no B-toggle; **not** taxable, **not** in tip base, no tip-on-top | "serviceCharge (mandatory %) → proportional / consumption; **not** a tip, **not** in tip base, **not** taxable" | ✅ exact, incl. all three negatives |
| flat-cover-minimum | B equal-per-head (proportion-0 fix) | "cover/minimum (flat) → **equal-per-head** / per seat … must bill proportion-0 diners" | ✅ |
| deposit-prepayment | A credit-to-payer default + B table-wide toggle; BOUNDED_LOWER refund branch is blocking | "credit/deposit → **context-gated** … BOUNDED_LOWER refund branch is a **blocking** prerequisite, not a footnote" | ✅ (spec frames default as context-gated per contract REFINEMENT 3, which the matrix's A-default predates — consistent, the contract refinement is the newer word and the spec honors it) |
| comp-discount-voucher | B targeted-first, A fallback, equal-per-head sub-mode needs-Leo | "discount/comp → **OPEN — Leo** … spread unless tagged to a line item" | ✅ correctly carried as THE one open decision |
| weighted-item | A now, B post-2.0 | "line item → by-claim / the item ✅ V1" + sequencing | ✅ (rolled into the by-claim line-item row; A-now is implicit in "no schema change," B-post-2.0 deferred) |

Spot-check the migration caveat: matrix "don't silently re-apportion existing `.custom` lines" → spec "Migration safety: Do **not** silently re-apportion existing `.custom` SummaryItems … untagged legacy `.custom` stays proportional." ✅ verbatim-equivalent.

---

### B. The four canonical silent-money P0s (SYNTHESIS / catalog) → spec. FAITHFUL, all 4 present.

1. Ambiguous currency symbol → wrong FX pair → spec §2 "never silently pick CNY for ¥ or USD for a bare $." ✅
2. CC/processing surcharge dropped by Azure (payer eats it) → spec §1 surcharge row + §5 "Flagship fallback for dropped extras." ✅
3. Inclusive GST/VAT double-added → spec §3 `taxInclusive` flag. ✅
4. Deposit credited to one payer not the table → spec §1 credit/deposit context-gated + §3 `balanceDue`. ✅

Plus the P9.8 keystone P0 (tax on taxable base, exempt-item buyer overpays) → spec §1 tax row "**taxable base** (exempt items excluded); needs per-item `isTaxable`" + new invariant `TAX_ON_TAXABLE_BASE`. ✅ This is the one completeness-sweep P0 that DID make the capstone.

---

### C. OMISSIONS — P0s that did NOT make the spec.

**C1 — DROPPED: the entire "payment & liability" second-axis P0 cluster (completeness-and-gaps `split-mechanics-missed`).** The P9.8 completeness sweep raised **three explicit [P0]s** that the capstone never mentions:
- **[P0] "One person treats/covers another"** (liability redirect / covered-by → personId).
- **[P0] "Multiple payers / split the actual payment"** (replace `isPayer: Bool` with `amountPaid` per participant).
- **[P0] "Someone pays, then is reimbursed out-of-band"** (settlement-ledger / mark-as-paid).

The completeness doc's own synthesis calls this *"a second axis the prework never modeled"* and concludes *"the 'proportion is truth' contract is correct but **incomplete as a splitter spec** — it has no statement about who is liable or who paid, and that omission is where every P0 social mechanic falls through."* The capstone's "model in one line" is purely about charges + apportionment + money type — it inherits exactly that incompleteness and **does not even flag these P0s as out-of-scope/deferred**. This is the single largest faithfulness gap: 3 P0s, explicitly labeled, silently absent. (Defensible as a scoping call — these are settlement-model, not splitter-apportionment — but the spec makes no such statement, so it reads as a drop, not a deferral.)

**C2 — DROPPED/demoted: two currency-side P0s from `currency-modalities-missed`.**
- **[P0] Gift-card / store-credit as TENDER** (over-bills the holder) — completeness doc calls this *"the biggest blind spot"* and a P0; the capstone has **no tender/balanceDue-from-tender concept** (its `balanceDue` is deposit/prepayment-driven only, §3). Same orthogonal "who already paid" axis as C1; absent.
- **[P0] `isMoney` rejects EU/zero-decimal amounts** (`\d*\.\d{2}` hardcode) — not in the capstone at all. Arguably parse-fidelity, not split, but flagged P0 and dropped without mention.
- **[P0] Zero-decimal cents-poison (HUF/ISK/CLP/VND user-reachable today)** — this one IS covered by the capstone's minor-unit money type (§2), so faithful; noting it so the C2 list isn't read as "all currency P0s dropped."

**C3 — DROPPED: receipt-cardinality P0s (`parse-data-modalities-missed`).** Completeness raised **[P0] duplicate receipts (void+reprint)** and **[P0] cross-receipt cross-identity netting at folder level** ("silent wrong-money-to-wrong-person across receipts, the worst settlement failure class"). Neither appears in the capstone. Again a folder/settlement-layer concern outside the splitter core — but flagged P0 and not carried, not deferred-with-a-note.

**Net on omissions:** every P0 that is *intra-receipt apportionment* is faithfully carried (the 4 canonical + tax-exempt keystone). Every P0 that lives on the *settlement / liability / tender / cross-receipt* axis (3 social P0s + gift-card tender + duplicate/cross-receipt netting) is **dropped from the capstone with no scope statement**, exactly the incompleteness the P9.8 critic predicted.

---

### D. NUMBER cross-checks. CONSISTENT (one rounding caveat).

- **31% / 15 of 48 / "nearly one in three"** — empirical-findings, PLAN P9.5, PLAN memory log, and spec line 3 + §empirical-grounding all agree on **31% / extra beyond tax+tip**. ✅ No disagreement.
- **serviceCharge counts** — empirical-findings: prevalence **6 receipts** ("any provider found it") vs Azure-missed-divergence **9**. Spec §1 serviceCharge row cites **"6 receipts."** ✅ Spec correctly uses the *prevalence* number (6), not the divergence number (9). PLAN log conflates them in one place ("serviceCharge on 6 … Azure dropped serviceCharge on 9") but states both correctly; spec picked the right one. No contradiction.
- **Divergence aggregate** — empirical-findings: **94 `ocr.divergence` events**, field-level **total on 21, currencyCode on 23, extras on 36, subtotal on 14**. Spec doesn't restate the 94/21/23 figures (cites them only obliquely via "the divergence data shows a flagship often caught the missing charge"). No number in the spec contradicts these. ✅
- **Non-USD count** — empirical-findings currency table: USD 44, MYR 4, AED 4, AUD 1 → **9 non-USD** (4+4+1). Spec §2: **"9 are non-USD."** ✅ Arithmetic checks.
- **Currency-disagreement count** — empirical-findings **"5 receipts the providers disagree on the currency."** Spec §2: **"5 receipts have provider currency-disagreement."** ✅
- **Caveat (not a disagreement):** empirical-findings reports `currencyCode` field-divergence on **23** receipts but provider currency *disagreement* on **5** — these are two different metrics (23 = any currencyCode field delta incl. null-vs-present; 5 = actual conflicting non-null codes). The spec uses **5** (the stricter, correct figure). Internally consistent; just flag that a careless reader could conflate 23 vs 5.

---

### E. Spot-checks of load-bearing file:line claims (spec vs catalog/matrix). All MATCH.

- `OCRSnapshotBridge.swift:92-98` drops post-tax extras — spec §1, catalog multiple, matrix all cite the same range. ✅
- `ReceiptSplitEngine.swift:73/78` cents-hardcoded — spec §2 vs SYNTHESIS vs catalog. ✅
- `V3ReceiptReconciler.swift:76` `currencyCode:nil` — spec §2 vs PLAN P9.1 vs SYNTHESIS. ✅
- `Reconciler.swift:69` `.unknown` early-return nil disables reconciliation — spec §5 vs empirical-findings ("the kind that silently disables reconciliation `Reconciler.swift:69`"). ✅
- `EMPTY_ITEMS_ALL_ZERO` at `MathInvariants.swift:381` — spec §4 "do NOT invert; synthesize upstream" exactly matches contract REFINEMENT 2 (the safer resolution that supersedes the matrix/early-pass "invert" framing). ✅ The spec correctly carries the *final* (pass-3 second-opinion) resolution, not the stale "invert the invariant" version — a faithfulness *win*, not a drop.

---

### F. Faithful-with-honest-caveat items.

- **`fee` row apportionment** — spec §1 lists `fee (admin/CC/delivery, flat) → equal-per-head OR proportional / per policy.` The matrix never adjudicated a standalone admin-fee row (the $80.83 admin fee rode along inside the service-charge row's forcing receipt). So the spec's "OR per policy" is an *under-specified* carry, not a contradiction — but it is the one row where the spec asserts a default-ish choice the decision matrix never actually ruled on. Worth a Leo flag alongside comp/voucher; the spec presents it as semi-settled when it's arguably a second open decision.
- **`mandate` row** — spec §1 "mandate → proportional / consumption (1 receipt)." Completeness-doc case 4 splits mandate into *percentage* (proportional) vs *flat resort/tourism fee* (equal-split). Spec collapses to proportional-only, dropping the flat-mandate sub-case. Minor (1 receipt, P1), but it IS a documented sub-case the spec flattens.

---

### Bottom line

- **Intra-receipt apportionment**: FAITHFUL. All 5 matrix recs + the 4 canonical P0s + the tax-exempt keystone P0 carried, with the *latest* (pass-3) resolutions correctly chosen over stale earlier framings. Numbers all reconcile.
- **The drop**: the capstone omits **3 explicit [P0] payment/liability social mechanics + [P0] gift-card tender + [P0] duplicate/cross-receipt netting** — every P0 on the "who paid / who is liable / which receipt" axis the P9.8 completeness sweep raised, with **no in-spec scope or deferral statement**. The completeness doc itself names this exact omission ("incomplete as a splitter spec"). If the intent is "splitter-core spec, settlement axis is a separate workstream," the spec should say so explicitly; as written, those P0s read as dropped.
- **Number disagreements**: none material. The only thing to watch is the 23-vs-5 currencyCode metric (spec correctly uses 5) and the 6-vs-9 serviceCharge metric (spec correctly uses 6) — no figure in the spec contradicts the empirical source.

---

This confirms the spec's core claims and exposes the real gaps. I found the critical fact: `totalFinding` does `if receipt.extras.contains(where: { $0.kind == .unknown }) { return nil }` — the silent-reconciliation hole at the line the spec cites. But notably, `unknownExtraKindFindings` IS already appended separately (line `findings.append(contentsOf: unknownExtraKindFindings(receipt))`), so the spec's framing that international receipts get a "hollow totals verified signal" is partially overstated — there IS an unknown-kind finding emitted. The hole is specifically that the *total* check silently skips.

I have enough verified ground truth. Writing the review.

## ship-skeptic

I read the spec as the dev who has to build this when the freeze lifts, and I cross-checked every load-bearing `file:line` against the real `ResplitCore` worktree (`resplit-ios-worktrees/ocr-i18n-currency-20260530`). The spec is well-researched, but there are concrete places where a careful, well-meaning implementation still ships a money bug — and one place where the spec is flat wrong about the current code.

### The single most likely way this ships a money bug

**The negative-extra path will be built, pass `assertZeroSum`, and still mis-bill — because `assertZeroSum` is exactly the invariant that *can't* catch it.** Every negative-extra row in the matrix (deposit, comp, discount, credit) reconciles to the right *total* while shifting the *wrong person's money*. The flat-cover worked example proves it: Option A sums to $225.00 and ZERO_SUM passes while silently moving the kid's $35 cover onto Ana. A dev who implements "negative extra → fold into `customExtras` → spread proportional" will get green tests and a happy reconciler and a host who pays the $262 deposit twice. The spec *says* "model the credit as a post-split named-participant settlement, NOT a negative `customExtras`" — but that sentence lives in a sibling matrix doc (`apportionment-decision-matrix.md:106`), **not in the V2-DESIGN-SPEC itself.** The spec's §1 table just says credit is "context-gated, payer OR table-wide," which a dev will most naturally implement as a signed `customExtras` term because that's the path of least resistance and it's what the existing `Reconciler` already models (`negativeKinds = [.discount, .credit]` subtracted via `abs()`). That is Option B applied unconditionally — the exact mis-bill. **The "don't route credits through `customExtras`" instruction must be promoted into the spec body as a hard MUST, or it gets lost.**

### Where "context-gated" / "per policy" hides a real, unmade decision

1. **`fee` (admin/CC/delivery, flat) — "equal-per-head OR proportional | per policy"** (§1 row). There is no policy. This is a naked coin-flip handed to the implementer. A $80.83 admin fee on the catering check bills very differently under the two modes, and the spec gives zero rule for which one fires. A dev will hardcode one (probably proportional, since it reuses the existing path) and silently mis-bill the other half of cases. **This needs the same A-vs-B worked-example ruling the cover row got — it doesn't have one.**

2. **`credit` / `deposit` — "context-gated | payer OR table-wide."** The gating signal is undefined *in the spec*. The matrix doc resolves it ("restaurant/catering → payer; event/trip pool → table-wide") but that heuristic is unimplementable from OCR alone — nothing on the receipt says "this is a trip pool." The matrix even admits Option A "requires capturing *who* fronted the deposit, which OCR cannot infer — needs a user tap." So "context-gated" is actually "requires a UI affordance that doesn't exist yet," and the spec doesn't list that UI as a prerequisite. A dev reading only the spec will pick a context heuristic, guess wrong, and rob the host.

3. **`comp` / `discount` — flagged "OPEN — Leo," good** — that one is honestly marked. But note the spec's stated default ("spread proportionally unless tagged to a line item") is the *more dangerous* default: proportional-on-a-targeted-comp is precisely the case that makes Ann pay $6.67 for a free steak. If Leo doesn't rule before the build, the default ships the bug.

### Where the spec is wrong about the current code (a dev will trust it and break things)

**§3 claims "`ReceiptTotalCalculator.swift:19` adds tax unconditionally → inclusive GST/VAT double-counts."** That is stale. The real `calculatedTotal` already has an inclusive branch: `if usesTaxInclusiveLineItemTotals(for: receipt) { return itemSum + tip + customExtras }` — it conditionally *omits* tax today. A dev who takes the spec at face value will add a *second* `taxInclusive: Bool` and now there are two competing inclusive-tax mechanisms (`usesTaxInclusiveLineItemTotals`'s 2-sig-fig heuristic vs. the new explicit flag) that can disagree on the same receipt. Best case wasted work; worst case the two paths fight and a VAT receipt double-counts *or* zero-counts depending on which wins. **The spec must be re-grounded against the current `ReceiptTotalCalculator`, not the version it was written against.** (Line numbers across §2/§3/§5 are also drifted from this worktree — `:19`, `:73`, `:69` don't land on the cited code here — so a dev grepping by line will land in the wrong place and patch the wrong thing.)

**§5 overstates the reconciliation hole.** The spec says a single `.unknown` extra makes "most international receipts get a hollow 'totals verified' signal." Reality: `totalFinding` does early-return nil on `.unknown` (`Reconciler.swift`, the `if receipt.extras.contains(where: { $0.kind == .unknown }) { return nil }` line — real and worth fixing), BUT `reconcile()` *separately* appends `unknownExtraKindFindings(receipt)`. So the receipt is NOT silently "verified" — it already surfaces an unknown-kind finding. The bug is narrower than stated (the *total-math* check is skipped, but the report is not hollow). A dev who believes the spec's framing might rip out the early-return entirely and start emitting false `totalMismatch` deltas on every international receipt with a genuinely-unknown charge — trading a real-but-bounded gap for noise.

### Is the sequencing safe? Mostly — but step 5 secretly depends on step 1, and the spec under-fences it.

The order (harden → money type → disambiguation → inclusive-tax → taxonomy → verify-gate) is directionally right, and Prereq #2 correctly makes `NEGATIVE_EXTRA_BOUNDED` a blocker before any credit/discount ships. **But:** step 5 (typed taxonomy) introduces `credit`/`discount`/`comp` — all negative — and the BOUNDED_LOWER refund branch is the gate. The spec calls the refund branch "a blocking prerequisite, not a footnote" (§1) — good — but it's listed nowhere in the numbered **Sequencing** list (step 1 only says "negative BOUNDED," which is the *clamp*, not the *refund path*). Clamping owed-to-zero when a deposit exceeds the host's share **breaks ZERO_SUM against balance-due** (the leaked credit has nowhere to go). So step 5 genuinely depends on a refund/over-credit mechanism that step 1 as-worded does not build. A dev will implement step 1's clamp, see green tests (no test exercises deposit > host-share yet), proceed to step 5, and ship the one scenario the adversarial notes flagged: light-eater host fronts a large deposit → either owed clamps to 0 and ZERO_SUM silently breaks, or BOUNDED_LOWER trips in prod. **The refund branch must be its own numbered, test-gated step between 1 and 5, not folded into "negative BOUNDED."**

### Other under-specified spots a dev will guess wrong on

- **Clamp-and-orphan for over-large credits is missing from the spec body.** The adversarial notes (comp row) require "an explicit clamp-and-orphan rule for credits that exceed the distributable base before either option is invariant-safe." The spec never states what happens when a credit exceeds the whole table's subtotal (distributable goes negative). Undefined → a dev produces negative `owed` or a NaN proportion. This is a MUST-specify, not a footnote.
- **§4 "synthesize a single `sharedEqually` item = total UPSTREAM"** — *upstream where?* If synthesized in the engine it's testable; if synthesized in a ViewModel/bridge it can race the persisted DTO snapshot that settlement reads (the spec itself warns settlement reads "a frozen DTO snapshot, real-money blast radius"). The exact injection point is the whole ballgame for whether this is safe, and it's named only as "UPSTREAM" in caps. A dev will pick a layer; if it's the wrong one, the synthesized item isn't in the frozen DTO and the no-items receipt settles at $0 forever.
- **Currency resolution (§2) "require CountryRegion or prompt"** — "prompt" is a UI surface with no spec. Until it exists, the disambiguation step (sequence #3) has no fallback, so a dev will reintroduce a silent default (`USD` for bare `$`) to keep the flow unblocked — re-creating the exact bug §2 exists to kill. The prompt UI is an unlisted prerequisite for step 3.
- **`MINOR_UNIT_NO_SUBUNIT_RESIDUE` + the existing `*100` cents math.** The current remainder routing is hardcoded `(x * 100).rounded() / 100` and `abs(remainder) >= 0.005` (verified in the engine). Switching to minor-unit scale touches the *remainder distribution*, which is the single most money-sensitive line in the engine. The spec lists the new invariant but gives no guidance on the JPY/KRW (`scale 0`) remainder case where the existing `>= 0.005` threshold is nonsensical. A dev who scales the multiply but forgets the threshold ships fractional-yen remainders to `sortedIds.first`.

### Bottom line

The research is real and the receipts are real. The spec's failure mode isn't bad analysis — it's that **the safety-critical instructions live in the sibling matrix docs and the adversarial blockquotes, not in the spec a dev will actually implement from.** The three things that will ship a money bug if built literally from this file: (1) credits/comps modeled as signed `customExtras` (mis-bills the host, passes ZERO_SUM); (2) the inclusive-tax flag layered on top of the *already-existing* `usesTaxInclusiveLineItemTotals` heuristic; (3) the deposit refund/over-credit branch absent from the numbered sequence so the clamp silently breaks ZERO_SUM-against-balance-due. Promote those into the spec body as hard MUSTs with worked failing examples, re-ground every `file:line` against current `ReceiptTotalCalculator`/`ReceiptSplitEngine`/`Reconciler`, define the `fee` "per policy" coin-flip, and pin the §4 "UPSTREAM" injection layer to an exact, testable location — before anyone writes Swift.

---

