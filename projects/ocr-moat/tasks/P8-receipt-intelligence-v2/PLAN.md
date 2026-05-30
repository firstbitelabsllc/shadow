# P8 — Receipt Intelligence V2 (catch what V1 misses)

> Parent: ../../PLAN.md

**Status:** [in_progress] — started 2026-05-30 (Leo: "our current structure is clearly MVP V1 ... not sophisticated enough to catch everything"). Builds on P7 (multi-model benchmark) with REAL ground truth now in hand.

## Purpose

We now have **32 real restaurant receipts** from Leo's Apple Photos (Apple ML-labeled "Receipt", classified to dining, ingested into the corpus). Use them — plus cloud models as an oracle — to (1) be **100% sure** the corpus holds only Resplit-scannable restaurant receipts (not grocery/gas/retail/invoices), (2) have Claude build rich tags + **a story of what Resplit's core splitter is missing** across edge cases, (3) audit the **latest Azure DI v4 prebuilt-receipt API** for capabilities we don't use (arbitrary key-value, query fields, full schema beyond tax/tip), and (4) wire **PostHog** observability. The deliverable is a concrete V1→V2 upgrade path for `ResplitCore` OCR + reconciliation, grounded in real receipts.

Leo verbatim 2026-05-30: *"have cloud models like CC create and build the tags and inspect and build a story on what our core splitter may be missing across diff receipts edge cases, also have multiple workflow run against latest azure v4 and see what api's or configs we're not using like arbitrary key value support post subtotal ... consider posthog."*

## Evidence

- [Source: live] 32 dining receipts ingested (ids in /tmp/dining-ids.txt): DYSTER BAR, Coqodaq, LENOIR, Pasquale Jones, Yasaiya Shabu-Shabu, MARBLE YAKINIKU (AU), Emirates Palace (AE), Taste Good Malaysian, The Clam Shack, Saigon Shack, Yamaguchi, A Zhong Taiwanese, Chayanne (Flushing), Maxis Noodle, Drift, Thursday Kitchen, Roxy Hotel, Grumpy Bagels (MY) … — a rich locale/format spread (US, AU, AE, MY; multi-currency; shabu/yakiniku/taqueria/bagel/fine-dining).
- [Source: classifier] 64 exported / 32 confident-dining / 32 UNSURE. UNSURE correctly caught NON-Resplit: Trader Joe's, Carrefour, Hannaford (grocery), Shell (gas), Sky Garage / Park Right (parking), Jurlique (cosmetics), TestFlight screenshots — AND a few real food places the heuristic under-scored (Qing Shu Hot Pot, Auntea Jenny, Al Ustad Kabab, shoshaku) needing an LLM second pass.
- [Source: P7 FINDING] Marathon Cafe: Azure prebuilt dropped a 3% CC processing fee; claude + qwen both caught it. → V1's `[tax,tip]`-only `extras` mapping under-extracts surcharges/fees/mandates.
- [Source: codebase] `ResplitCore/OCR/`: `ScannedReceipt` (extras bag supports 9 kinds), `OCRSnapshotMapper`, `V3ReceiptReconciler` (hardcodes `currencyCode: nil`!), `Reconciler.matchThreshold = 0.01` (wrong for JPY/no-decimal). `ReceiptSplitter/ReceiptScanner.swift` uses Azure DI v4 `prebuilt-receipt` but only maps a subset of fields.
- [Source: ocr-moat P4] PostHog telemetry was always the planned observability layer for OCR (events per scan: latency/confidence/unknown-extras).

## Constraints

- ALWAYS: only restaurant/dining receipts enter the corpus (Resplit scans dining bills, not grocery/retail/invoices). Multi-model agreement before a receipt is "confirmed dining". Real receipts are PII — keep them LAN-local; private/PII fields gitignored.
- ALWAYS: V2 changes to `ResplitCore` are evidence-backed (a real receipt that V1 mis-handles) + carry tests. Code-review every code change.
- NEVER: ship a V2 schema/reconciler change during the 2.0 freeze without Leo's sign-off — P8 produces the SPEC + evidence; the iOS code change is gated.
- NEVER: spend uncapped model budget — batch the cloud-model passes; local qwen for bulk where possible.

## Tasks (subplans — each gets actual work + tests + code review)

- [completed] P8.1 — **Classification hardening (100% sure)**: promote the Vision classifier to a real module (`receipts/classify.py`) with a dining/retail/invoice contract; LLM second-pass the 32 UNSURE to recover real food (Qing Shu, Auntea Jenny, Al Ustad, shoshaku) and reject retail/gas/parking; finalize the confirmed-dining set. Tests pin the dining-vs-retail boundary. [Workflow team: classify]
- [completed] P8.2 — **Tag enrichment**: Claude inspects each dining receipt → structured tags (locale, currency, multi-tax, service-charge, surcharge/fee, auto-gratuity, handwritten-tip, shared-items, foreign-language, long-itemization, comp/discount). Stored in `annotations.tags` + `known_issues`. [Workflow team: tagging]
- [completed] P8.3 — **"What the splitter misses" story**: across all 32, Claude builds the narrative + a structured findings report of edge cases V1's `ScannedReceipt`/`Reconciler`/`OCRSnapshotMapper` mishandles (fees beyond tax/tip, no currency in reconciler, no-decimal currencies, item-level shared/split hints, modifiers, voids, comps). Ranked by frequency × split-impact. → `evidence/`. [Workflow team: edge-case analysis]
- [completed] P8.4 — **Azure DI v4 capability audit**: research the LATEST `prebuilt-receipt` v4 (api-version, `features=keyValuePairs/queryFields`, the full receipt field schema incl. `TaxDetails[]`, `Tip`, `ArbitraryKeyValue`, currency, payment) vs our `ocr.py`/`ReceiptScanner.swift` usage. Output: gap list + concrete config/endpoint changes (e.g. enable key-value add-on, parse `TaxDetails[]` not just `TotalTax`). [Workflow team: azure-audit]
- [in_progress] P8.5 — **PostHog OCR observability**: plan + wire `ocr.scan.*` events (provider, latency, extras-kind distribution, prebuilt-vs-flagship divergence, unknown-extra count) so the aggregate "where Azure is weak" surfaces in a dashboard. [Source: ocr-moat P4]
- [in_progress] P8.6 — **V2 spec for ResplitCore**: synthesize P8.3 + P8.4 into a concrete spec (extras beyond tax/tip, currency-aware reconciler, key-value passthrough) — gated on Leo + the 2.0 freeze.

## V2 spec — ResplitCore upgrade (gated on Leo + 2.0 freeze; harness side proven)

Grounded in the 44 real receipts + the Azure audit. Each item cites the proof.

### Free now (decode-only, no Azure spend — data already returned)
1. **TaxDetails[]** -> emit one `.tax` extra per tax line (sales + service tax). DONE in `extract.py` harness; iOS = add `TaxDetails` to `FieldsV4` + map in `OCRSnapshotMapper`. (Proof: service tax 6% alongside sales tax.)
2. **Payments[]** (method, amount) -> "who paid" reconciliation. (Proof: split-tender receipts.)
3. **Items.Price / QuantityUnit / ProductCode** -> repair `qty*price != line total`. (Proof: quantity-embedded-in-description.)
4. **CountryRegion** -> fix `V3ReceiptReconciler` `currencyCode: nil`; infer currency (RM/AED/AUD in corpus).

### Schema / reconciler (the core gap)
5. **Populate `extras` beyond `[tax,tip]`** — map service charge -> `.serviceCharge`, admin/CC/cover -> `.fee`/`.surcharge`, auto-gratuity -> `.serviceCharge` (NOT `.tip`), deposit -> `.credit` (negative). (Proof: admin $80.83, gratuity $339.47, deposit -$262, cover $70.)
6. **Currency-aware reconciler** — stop hardcoding `currencyCode: nil`; derive `matchThreshold` from minor-unit (0.01 USD/EUR, 1 JPY/KRW). (Proof: foreign + no-decimal receipts.)
7. **`total != balance_due`** awareness — when a deposit/prepayment is applied, split the right number. (Proof: $2180.26 total vs $1918.26 balance due.)
8. **Inclusive-tax flag** — GST-included-in-total must not be added again. (Proof: "GST included in total $90.68".)
9. **Shared-item hint + handwritten-tip capture** (split UX). (Proof: shared appetizers; $25/$6 pen tips.)

### Premium (gate on cost, validate vs corpus)
10. **`features=queryFields=ServiceCharge,Gratuity,Surcharge,Fee,Deposit`** — opt-in shipped in `ocr.py`; prototype vs corpus, measure recovery vs cost before iOS adoption.
11. `features=languages` (free) — drop hardcoded `locale=en` for the non-English receipts. `ocrHighResolution` only on truncated-item retry.

## P8.5 — PostHog OCR observability (plan)

Per ocr-moat P4. Events (provider-agnostic, fire from the analyze path / iOS `ReceiptOCRAnalyzer`):
- `ocr.scan.completed` { provider, latencyMs, itemCount, extrasKinds[], hasUnknownExtra, currencyCode, totalReconciles(bool) }
- `ocr.divergence` { field, azureValue, flagshipValue, agree(bool) } — the prebuilt-vs-flagship gap (the P7 oracle signal) as a queryable funnel.
- Dashboard: % receipts with extras beyond tax/tip, top dropped-extra kinds, reconcile-fail rate by currency, provider latency p95. This is where "Azure dropped the CC fee" becomes a ranked, trackable metric instead of an anecdote.
Wire via `posthog-python` from the harness first (LAN-local capture or a project key), iOS via the existing analytics manager. NOT during the 2.0 freeze for the app; the harness/corpus side can capture now.

## Decision Log

- [DIRECTION] 2026-05-30 — Corpus is dining-only. Apple's "Receipt" ML label is the harvest source (238 in library); a Vision+LLM classifier gates to restaurant receipts. Grocery/gas/parking/retail/invoices are explicitly OUT (Resplit doesn't split those).
- [DIRECTION] 2026-05-30 — Cloud models are the ORACLE + the ANALYST: they extract (P7), tag (P8.2), and write the edge-case story (P8.3). The output is a SPEC for the V1→V2 upgrade, not an LLM-in-the-app.
- [DIRECTION] 2026-05-30 — V2 north star: move past `[tax,tip]`-only extras. Real receipts already show CC fees, multi-tax, service charges, foreign currency, no-decimal — V1 silently drops these. Azure v4 likely exposes more (key-value, TaxDetails[]) that we don't parse.

## Progress

- [2026-05-30] FDA unblocked (cmux toggle, no restart). osxphotos: 238 Apple-labeled receipts; exported 64 (last 365d); Vision classifier → 32 confident dining (ingested) + 32 UNSURE. Real restaurant corpus is live (36 total). Wrote P8 with 6 subplans. Next: fire workflow teams for classify(UNSURE) + tagging + edge-case story + Azure v4 audit concurrently; synthesize → V2 spec; implement classify.py + PostHog with tests + code review.
