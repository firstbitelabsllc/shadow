# OCR Moat — Vendor-Neutral Receipt Scanning Foundation

> Sibling of `../resplit-2-0-weekend-push/PLAN.md`. Post-launch foundation work.

**Status:** [unblocked — ready-to-claim] (gate lifted 2026-05-01T15:17:49Z when weekend-push T9 shipped build 2363 / v2.2.0 to TestFlight; see `../resplit-2-0-weekend-push/PLAN.md` line 208)
**Estimated scope:** 5 phases, 32 AI-hours, ~6 calendar weeks
**Authority spec:** `firstbitelabsllc/resplit-ios:docs/superpowers/specs/2026-05-01-ocr-moat-design.md`
**Created:** 2026-05-01 (Leo verbatim approval: *"great keep working move on"*, scope D)

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

- `[pending]` **P1 — Domain types + provider protocol + Azure adapter** [Sub-plan: tasks/P1-domain-types-protocol/PLAN.md] [ETA: 8h] — Lock the contract. `ScannedReceipt`, `ReceiptScanProvider`, `AzureDIv4Provider`. Migrate ViewModel layer to consume `ScannedReceipt`. Existing `OCRSnapshot` shimmed for CloudKit data continuity. 0 user-facing change.
- `[pending]` **P2 — Fixture corpus + replay provider + corpus runner** [Sub-plan: tasks/P2-fixture-corpus-runner/PLAN.md] [ETA: 6h] [Depends: P1] — JSONL format frozen. ~10 of Leo's receipts annotated. `FixtureReplayProvider` for offline tests. CI runs `tuist test "ResplitCore Corpus Tests"`.
- `[pending]` **P3 — Reconciliation engine** [Sub-plan: tasks/P3-reconciliation-engine/PLAN.md] [ETA: 6h] [Depends: P1, P2] — Replaces v3-only `ReceiptItemsFixer` with v4-aware `Reconciler`. **Absorbs `asc-akig` Phase 2.** UI warning chip on receipt detail when `severity ≥ .warn`. Visual proof BEFORE/AFTER.
- `[pending]` **P4 — Telemetry pipeline** [Sub-plan: tasks/P4-telemetry/PLAN.md] [ETA: 4h] [Depends: P1] — PostHog events per scan (`ocr.scan.started/succeeded/failed/field_confidence`). Sentry breadcrumbs structured. PostHog dashboard for OCR p99 latency + unknown-extras alerting.
- `[pending]` **P5 — Receipt Lab dev-app surface** [Sub-plan: tasks/P5-receipt-lab-devapp/PLAN.md] [ETA: 8h] [Depends: P1, P2, P3] — Dev-app `ReceiptLab` view: drop-image / annotate / save-to-corpus / replay-fixture. Closes the corpus-growth loop.

**Total: 32 AI-hours = ~6 calendar weeks at 1-2 phases/week.**

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

## Progress

- [2026-05-01 21:30 EDT] Project created. Authority spec at `firstbitelabsllc/resplit-ios:docs/superpowers/specs/2026-05-01-ocr-moat-design.md` (uncommitted in working tree, will land bundled with P1's first code PR per CLAUDE.md `§MT-1`). 5 phase sub-plans seeded. No code touched yet — gate is Resplit 2.0 weekend-push shipping first. Next: agent picks up P1 once weekend-push closes.
