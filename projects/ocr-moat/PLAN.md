# OCR Moat — Vendor-Neutral Receipt Scanning Foundation

> Sibling of `../resplit-2-0-weekend-push/PLAN.md`. Post-launch foundation work.

**Status:** [in_progress] — THE single central goal for all receipt-scanning + splitter-V2 work (consolidated 2026-05-31 per Leo: "save this to one central vidux goal").
**Created:** 2026-05-01 (Leo: *"great keep working move on"*). **Authority spec (original):** `firstbitelabsllc/resplit-ios:docs/superpowers/specs/2026-05-01-ocr-moat-design.md`. **Authority spec (V2, current):** `tasks/P9-splitter-v2-prework/evidence/2026-05-31-V2-DESIGN-SPEC.md` (Rev 2, adversarially reviewed).

### Current state (read this first)

| Phase | What | Status |
|---|---|---|
| **P1–P5** | iOS FOUNDATION: vendor-neutral contract, fixture corpus, reconciler, telemetry, dev-app | **Largely SHIPPED May 2026** — P1 `[completed]` (PRs #562/#567), P3.1+P3.2 `[completed]` (#584/#585), P2/P4/P5 `[in_progress]` (slices shipped #576/#594). The V2 UPGRADE on top of this foundation is what's gated on the freeze. |
| **P6** | Receipt Corpus Lab (LAN web) — harvest/classify/extract/export | `[completed]` — built, 112 tests green, code-reviewed |
| **P7** | Multi-model extraction benchmark (Azure vs Claude/qwen) | `[completed]` — 48 receipts extracted, divergence aggregate captured |
| **P8** | Receipt Intelligence V2 — tags, "what V1 misses" story, Azure audit, PostHog | `[completed]` — 6 subplans, V1→V2 spec produced |
| **P9** | Splitter-core V2 prework + the V2 design spec | `[completed]` (prework) — 14 evidence docs, adversarially verified; **iOS impl gated on freeze** |

**The harness/research arc (P6–P9) is DONE.** What remains is the **iOS implementation (P1–P5), gated on the 2.0 freeze + Leo's sign-off + one open product decision (comp/voucher apportionment).** The P9 V2-DESIGN-SPEC is the authority for that implementation.

## Purpose

Make Resplit's receipt scanning **the moat** — robust, observable, vendor-portable. Today the Azure Document Intelligence v4 response types leak directly into ViewModel/domain code; swapping vendors requires changing three layers. This project lands a vendor-neutral contract (`ScannedReceipt` + `ReceiptScanProvider` protocol) plus the supporting infrastructure to prove the contract on real receipts (fixture corpus + reconciliation + telemetry + dev-app annotator).

Leo verbatim 2026-05-01:
> *"That's like the fucking moneymaker, that's like the mote of this fucking app. If people don't trust the scanning, then it doesn't work. It just does not work and it just does not work."*

## Evidence

- [Source: codebase] `ReceiptSplitter/ReceiptScanner.swift:267-329` — `uploadReceiptV4` POSTs Azure DI directly. `ReceiptScannerHTTPTransport` protocol abstracts only the HTTP layer, not response schema. No vendor abstraction.
- [Source: codebase] `OCRSnapshotMapper.map(from response: ReceiptScanStatusV4, ...)` — Azure types `AnalyzeResultV4`, `FieldsV4`, `ReceiptScanStatusV4` leak into the mapping layer.
- [Source: codebase] `OCRSnapshot.swift` (80 lines) — fixed-schema domain type. No dynamic key-value bag for SF mandates, surcharges, multi-tax, credits.
- [Source: investigation] `~/Development/resplit-ios/.cursor/plans/investigations/asc-akig-ocr-key-value-extraction.md` (268 lines). Phase 1 (regression tests) COMPLETE; Phase 2 (v4 fixer refactor + KV gap) parked in `[eng-design-backlog]`. **This project absorbs Phase 2 into P3.**
- [Source: codebase] `ReceiptItemsFixer.fixItemsIfNecessary()` — silent no-op on v4 path because v4 response lacks the `pages` field the fixer reads from. ~40-60 line refactor needed.
- [Source: codebase] No telemetry beyond Sentry breadcrumbs (`ReceiptOCRAnalyzer.swift:41-188`). Latency, confidence, retry-count, vendor cost, reconciliation severity not tracked.
- [Source: codebase] `Tests/ResplitCoreTests/...` — synthetic OCR payloads inlined in test files. No fixture corpus, no real-receipt JSONL, no replay provider.
- [Source: codebase] `ResplitDevApp.swift` exists, builds, but has zero OCR-testing surface.
- [Source: Leo direct 2026-05-01] *"I want to have all that code...extremely extremely robust and ensure that once the the client code receives that information, it is not aware of like the calling site...if we want to update to V5, V6, a different vendor, the contract for that the client sees is still clear and we can like conform to it."*
- [Source: Leo direct 2026-05-01] *"there's all these different types of like taxes and fees, especially in San Francisco, that are like arbitrary and need to be key-valued."*

## Constraints

### ALWAYS
- The vendor-neutral type `ScannedReceipt` is the only contract crossing from "vendor-land" to "app-land". Any Azure-specific type leaking past this is a contract violation; reject in code review.
- `ReceiptScanProvider` protocol is the only call path the app makes to vendors. UI/ViewModels NEVER construct or reference an Azure-specific scanner.
- `ReceiptScanError` enum is the only error shape the app handles. Vendor-specific errors map into this enum at the adapter layer.
- All UI-visible changes carry BEFORE/AFTER screenshots per CLAUDE.md `§Visual Proof Merge Gate`.
- Every phase ships regression tests in the same PR per CLAUDE.md `§MT-5` (OCR is on the revert-prone surfaces list alongside auth / Live-Split / FX).
- Each phase uses isolated DerivedData `/tmp/resplit-dd-ocrmoat-P<N>-${RANDOM}` per CLAUDE.md `§Build Isolation Mandatory`.
- All phases run their own worktree under `~/Development/resplit-ios-worktrees/ocrmoat-P<N>-<cycleid>/`.

### NEVER
- Introduce a new vendor-specific code path before completing P1 (would require redoing the abstraction).
- Land telemetry on top of an unstable contract — `ScannedReceipt` shape must be locked first.
- Defer P1's absorption of `asc-akig` Phase 2 — it's the architectural anchor.
- Open a P1 PR while Resplit 2.0 weekend-push (`../resplit-2-0-weekend-push/`) has Open ASC rows. This project starts AFTER Resplit 2.0 ships.
- Add new fixture annotations without a code PR — per `§MT-1`, plan/corpus updates ride with code changes.
- Skip the convenience `.tax` and `.tip` fields on `ScannedReceipt` — existing UI/totals code uses them; full migration to filtering `extras` is a separate later refactor.

## Tasks (Phases)

Status FSM per /vidux: `pending → in_progress → in_review → completed`. `[blocked]` is orthogonal.

### iOS FOUNDATION — largely shipped May 2026 (the contract the V2 upgrade extends)

These five landed the vendor-neutral foundation. The P9 V2-DESIGN-SPEC is the authority for the *next* layer on top (the V2 upgrade — extra-taxonomy apportionment, currency-aware money, inclusive-tax/balance_due), which is gated on the 2.0 freeze + Leo's comp/voucher ruling.

- `[completed]` **P1 — Domain types + provider protocol + Azure adapter** [Sub-plan: tasks/P1-domain-types-protocol/PLAN.md] — `ScannedReceipt` + `ReceiptScanProvider` + `AzureDIv4Provider` shipped (PRs #562/#567, May 2-3). **V2 next:** §1 extends `ScannedExtraKind` with the `(apportionment mode, base)` model; §2 adds the currency-aware minor-unit money type.
- `[in_progress]` **P2 — Fixture corpus + replay provider** [Sub-plan: tasks/P2-fixture-corpus-runner/PLAN.md] — P2.0 shipped (#576). The LAN corpus lab (P6) now grows the JSONL (48 real receipts ready to export to the iOS replay runner).
- `[in_progress]` **P3 — Reconciliation engine** [Sub-plan: tasks/P3-reconciliation-engine/PLAN.md] — P3.1+P3.2 shipped (#584/#585). **V2 next:** currency-scaled `matchThreshold`, the `.unknown`-doesn't-skip-the-total fix (spec §5), inclusive-tax/balance_due (§3), the negative-extra BOUNDED fix (prereq).
- `[in_progress]` **P4 — Telemetry pipeline** [Sub-plan: tasks/P4-telemetry/PLAN.md] — P4.1 shipped (#594). The harness `telemetry.py` (P8.5) is the reference for the `ocr.divergence` events.
- `[in_progress]` **P5 — Receipt Lab dev-app surface** [Sub-plan: tasks/P5-receipt-lab-devapp/PLAN.md] — Phase A recon shipped. The LAN web lab (P6) already covers the harvest loop.

### Harness / research — COMPLETE

- `[completed]` **P6 — Receipt Corpus Lab (LAN web surface)** [Sub-plan: tasks/P6-receipt-corpus-lab-web/PLAN.md] — vidux-browse `/receipts/` harvest/classify/extract/export. Built, durability + path-traversal hardened, **112 tests green, code-reviewed** (10 findings fixed). Hosts the `corpus.jsonl` (48 receipts) that everything downstream uses.
- `[completed]` **P7 — Multi-Model Receipt-Extraction Benchmark** [Sub-plan: tasks/P7-multi-model-ocr-benchmark/PLAN.md] — Azure prebuilt + Claude + qwen on all 48 receipts (44/44 new, 0 err). The aggregate divergence (Azure dropped serviceCharge on 9, tip on 14, …) is captured via P8.5 telemetry — the empirical "where Azure is weak" signal.
- `[completed]` **P8 — Receipt Intelligence V2** [Sub-plan: tasks/P8-receipt-intelligence-v2/PLAN.md] — tags, the "what V1 splitter misses" story, Azure DI v4 capability audit, PostHog observability. Produced the V1→V2 upgrade direction. 2 shipped harness deliverables (classify.py + telemetry.py), tested + reviewed.
- `[completed]` **P9 — Splitter-Core V2 Prework + Design Spec** [Sub-plan: tasks/P9-splitter-v2-prework/PLAN.md] — all-night, 20-engineer prework: code-state map, test audit, 102-case edge catalog, 11 international regimes, apportionment decision matrix, completeness sweep, Leo's proportion-is-truth contract, empirical extraction (31% of receipts carry an extra beyond tax+tip), and the **V2-DESIGN-SPEC (Rev 2, adversarially reviewed)**. 14 evidence docs, zero Swift. The authority for the gated P1–P5 iOS work. ONE open decision: comp/voucher apportionment.

**Done: P1 (foundation) + P3.1/P3.2 + P6–P9 (harness/research). In-progress slices: P2/P4/P5. Gated: the V2 UPGRADE (extra-taxonomy, currency-aware money, inclusive-tax/balance_due) on top of the foundation — on the 2.0 freeze + Leo's comp/voucher ruling.**

## Decision Log

- [DIRECTION] 2026-05-01 — Vendor-neutral protocol over inline Azure refactor. Reason: portability is the explicit user ask + once the protocol exists, A/B testing future vendors is a config change, not a refactor. Trade-off: one extra layer of indirection vs. open future. Worth it.
- [DIRECTION] 2026-05-01 — Typed `ScannedExtraKind` enum (`tax/tip/fee/serviceCharge/mandate/surcharge/discount/credit/unknown`) over raw `[String: Money]` for the dynamic KV bag. Reason: `.unknown` count in telemetry becomes a leading indicator of "vendor is finding a fee type we haven't categorized yet". Counter: schema migration when new fee types appear. Mitigation: `.unknown` fallback + telemetry alert.
- [DIRECTION] 2026-05-01 — Absorb `asc-akig` Phase 2 into THIS project's P3. Reason: the v4 reconciler refactor is the same architectural call as the new contract design; sequential would burn the contract design twice.
- [DIRECTION] 2026-05-01 — Phase ordering: domain → corpus → reconcile → telemetry → dev-app. Reason: corpus JSONL references the new types — pinning types early prevents annotation rework. Telemetry on an unstable contract gets thrown away when the contract changes.
- [DIRECTION] 2026-05-01 — Convenience `.tax` and `.tip` fields on `ScannedReceipt` alongside the `extras` bag. Reason: existing UI/totals code uses them directly. Computed at construction. Avoids forcing every consumer to filter `extras`.
- [DIRECTION] 2026-05-01 — Image storage: commit JPEGs to repo unless PII-bearing. PII-bearing images gitignored + listed with `image_path: null` and `private: true` in corpus. Reason: test reproducibility on fresh clone vs. PII safety. Replay provider works from cached Azure JSON anyway.
- [DEFER] 2026-05-01 — Vendor migration to v5 / Mindee / Google. Project ENABLES it; doesn't perform it. New spec when migration target is decided.
- [DEFER] 2026-05-01 — VisionKit offline production path. Per `asc-akig` Phase 2 note. Replay provider is offline but for tests only.
- [DEFER] 2026-05-01 — A/B test framework for vendor comparison. Future spec, builds on this contract.
- [DEFER] 2026-05-01 — Last-mile reconciliation UX (auto-fix flows, "this doesn't add up" prompts). P3 ships the math + warning chip; the UX of how to RESOLVE mismatches is a future spec once we have prod data on what mismatches actually look like.
- [DIRECTION] 2026-05-31 — **CONSOLIDATION:** this is THE one central goal for receipt-scanning + splitter-V2 (per Leo). P6–P9 subplans cleaned up + flipped to terminal `[completed]`; P9 added to the parent (it was missing); P1–P5 statuses corrected to reflect the foundation that actually shipped in May (not the stale `[pending]`). The P9 V2-DESIGN-SPEC is the authority for the V2 UPGRADE that extends the shipped P1–P5 foundation.
- [DIRECTION] 2026-05-31 — **V2 splitter model (the keystone):** a receipt is a set of charges; each charge carries an apportionment `(mode, base)`; money is a currency-aware minor-unit type; **proportion is the source of truth, equal-split is the default proportion** (Leo's binding contract, verified vs shipped 1.8). Replaces V1's single additive proportional-by-gross total. ~80% of 102 cataloged edge cases fall out of the old shape. See `tasks/P9-splitter-v2-prework/evidence/`.
- [DIRECTION] 2026-05-31 — **Per-charge apportionment basis:** tax → taxable base (exempt items excluded), tip/% service charge → consumption, flat cover/fee → equal-per-head, item-fee → claimant, credit/deposit → context-gated. Each is a separate DOLLAR LAYER, never injected into the proportion vector (protects `PROPORTION_SUM`).
- [DIRECTION] 2026-05-31 — **EMPTY_ITEMS resolution:** do NOT invert the shipped `EMPTY_ITEMS_ALL_ZERO` invariant; synthesize a `sharedEqually` item = `balanceDue − Σ(typed extras)` upstream so Leo's equal-split holds and the guard stays. Settlement reads a frozen DTO snapshot, so the engine fixed-point must not be touched.
- [HARD MUST] 2026-05-31 — A credit/deposit is a **post-split named-participant settlement adjustment, NEVER a signed `customExtras` term** — the latter passes `ZERO_SUM` and still mis-bills (deposit paid twice). The #1 ship-bug the adversarial review caught.
- [ASK-LEO] 2026-05-31 — ONE open product decision: **comp/voucher apportionment** (spread vs targeted). Default if unruled: spread proportionally unless tagged to a line item. Gates the V2 extra-taxonomy.

## Progress

- [2026-05-01 21:30 EDT] Project created. Authority spec at `firstbitelabsllc/resplit-ios:docs/superpowers/specs/2026-05-01-ocr-moat-design.md`. 5 phase sub-plans seeded. No code touched yet — gate is Resplit 2.0 weekend-push shipping first.
- [2026-05-31] CONSOLIDATION (Leo: "save this to one central vidux goal, subplans cleaned up merged updated"). Reconciled all 9 subplans into this central goal. P6 (corpus lab), P7 (multi-model benchmark), P8 (receipt intelligence V2), P9 (splitter-V2 prework) → all flipped to `[completed]`; P9 added to the parent Tasks (it was missing). The harness/research arc is DONE: corpus lab built (112 tests, reviewed), 48 receipts multi-model extracted, the V2-DESIGN-SPEC (Rev 2, adversarially reviewed) produced across 14 evidence docs. Empirical proof: 31% of real receipts carry an extra V1 drops. CORRECTED a stale assumption mid-consolidation: P1–P5 are NOT untouched — the iOS foundation largely SHIPPED in May (P1 + P3.1/P3.2 completed; P2/P4/P5 slices merged, PRs #562–#594). It's the V2 UPGRADE on top (apportionment taxonomy, currency-aware money, inclusive-tax/balance_due) that's gated on the 2.0 freeze + Leo's comp/voucher ruling, now authored by the P9 V2 spec. Next: Leo rules on comp/voucher and/or the freeze lifts → the V2 upgrade extends the existing P1/P3 foundation per the spec.
