# Foundational Contract — "Proportion is the source of truth" (Leo, 2026-05-31)

> Leo, verbatim: *"if the total isn't calculated and we only have line items and proportions, that is all that matters... the proportion is all we care about. And in the same vein if we have no line items but we have somehow a scanned subtotal or total, each person's total isn't 0 because we're not tallying by line item, we're tallying by proportion, and proportion is equal split by default at least that's what 1.8.0 prod does."* + *"see if that conflicts with any new logic we introduced it MUST be true."*

This is a load-bearing invariant for V2. I checked both halves against the **actual shipped 1.8 code**. One half matches; one half **conflicts with a shipped, test-locked behavior** — and it's a conflict the team already investigated once (T8).

## Claim 1 — "proportion is all that matters; total just scales it" → ✅ MATCHES the code

`ReceiptSplitEngine.calculateSplit` (ReceiptSplitEngine.swift:11-95):
- Derives each participant's **proportion** from line-item assignment (sharedEqually → split N ways :28; individually claimed → split among claimers :34).
- Final share = `proportion × distributableAmount` (:73), where `distributableAmount = totalAmount − orphanAmount` (:64).
- So the **proportions are the invariant**; the receipt total only scales them. If the total isn't reliably calculated, the calculator passes `resolvedTotalAmount` (falls back to items+tax+tip), and each person still gets their proportion of whatever that is. **Consistent with Leo.**

## Claim 2 — "no line items + scanned total → equal split (total/N), NOT zero" → ⛔ CONFLICTS

**The pure engine returns $0 for everyone when `items` is empty.** Verified:
- No items → `rawAmountsByEach` stays empty → `sumOfRawAmounts == 0` → the `if sumOfRawAmounts > 0` block is **skipped** (ReceiptSplitEngine.swift:47) → `proportionsByParticipant` stays empty.
- The final "ensure all participants have an entry" loop sets **every participant to 0.0** (ReceiptSplitEngine.swift:83-89).
- No synthetic item is created upstream: `OCRSnapshotMapper.mapLineItems` returns `[]` when Azure has no items (OCRSnapshotMapper.swift:57-58); no fallback exists anywhere.

**And a test invariant explicitly LOCKS the $0 behavior:** `EMPTY_ITEMS_ALL_ZERO` (MathInvariants.swift:381-412). Its own comment is the smoking gun:

> *"This is the **v1.8 canary case** invariant. Leo recalled v1.8 having a fallback that, on empty items + non-zero total, distributed the total equally as `total / participantCount`. The T8 v1.8-regression-hunt **proved that fallback never shipped** — `ReceiptSplitEngine.calculateSplit` has always returned $0 for every participant when `items.isEmpty`. This invariant locks that behavior so any future drift toward half/half-on-empty fails loudly here."*

So this is a **known divergence between Leo's memory and the shipped code**, already chased down once. The equal-split-on-empty fallback Leo remembers **never shipped**; zeros did; and a test now actively prevents equal-split-on-empty.

## The decision (Leo says it MUST be true → this is path A)

Leo is now asserting the equal-split-default **MUST** hold for V2. That makes it a **new V2 requirement that directly contradicts a currently-shipped, test-protected behavior.** To honor it:

1. **Invert `EMPTY_ITEMS_ALL_ZERO`** → the new contract is `EMPTY_ITEMS_EQUAL_SPLIT`: no items + non-zero total + N participants → each owes `total / N` (with deterministic remainder), proportion `1/N`. This is a real, observable behavior change — flipping a pinned invariant.
2. **Implement the default proportion = equal** when there is no line-item basis: either in the engine (when `sumOfRawAmounts == 0 && totalAmount > 0 && !participantIds.isEmpty`, set every proportion to `1/N`) or by synthesizing a single `sharedEqually` item = total upstream. Engine-level is cleaner and keeps one source of truth.
3. **Re-pin** with the new invariant so future drift toward zeros fails loudly.

## Reframes the catalog's "proportion = 0 diner" concern

With equal-split as the DEFAULT proportion, a participant is only proportion-0 when **line items exist and they were assigned none** (e.g. a flat cover on a non-drinker at an AYCE). In the no-items case everyone is `1/N` — nobody is 0. The decision-matrix worked examples must use **default proportion = equal**, and the flat-cover/per-head apportionment (P9.6) must still handle the genuine line-item proportion-0 case separately.

## Catalog audit (does any proposed V2 direction conflict with the contract?)

- None of the 102 catalog directions touched the empty-items path, so **no proposed direction currently contradicts** Claim 1 or the new Claim 2 — BUT every direction that scales by proportion (the currency-aware money model, the inclusive-tax fix, the extra-taxonomy apportionment) must be (re)stated against this now-explicit contract: **proportion is the source of truth; equal-split is the default proportion; the total scales proportions, it does not define shares.** Logged as P9.8.
