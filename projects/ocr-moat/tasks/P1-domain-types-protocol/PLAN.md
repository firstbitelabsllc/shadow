> Parent: ../../PLAN.md

# P1 — Domain types + provider protocol + Azure adapter

**Status:** [pending]
**Priority:** P0 within ocr-moat (foundation; gates P2-P5)
**Claim:** `claimed_by:` `claimed_at:` — first writer wins; pull → edit this line atomically → commit → push to claim.
**Hard gate:** Resplit 2.0 weekend-push (`../../../resplit-2-0-weekend-push/`) must ship before this PR opens. Verify by `gh pr list --state open --search "weekend-push"` returns empty AND `tag v2.0.0` exists on `firstbitelabsllc/resplit-ios`.
**Depends on:** none within ocr-moat.
**Blocks:** P2, P3, P4, P5.
**ETA:** 8h.
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P1-${RANDOM}` (export `RESPLIT_DD_PATH` per `/bigapple`).
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P1-<cycleid>/`.

## Purpose

Land the vendor-neutral contract. After this phase, no Azure-specific type leaks past the adapter layer. The rest of the app reads/writes `ScannedReceipt`, the protocol, and the error enum.

## What ships

3 sub-commits within one PR (or 3 stacked Graphite PRs, agent's call):

### P1.1 — Add domain types (no callers yet, no deletes)

New files in `ResplitCore/OCR/` (new directory):
- `ScannedReceipt.swift` — the struct per spec §3.1 (with `ScannedLineItem`, `ScannedExtra`, `ScannedExtraKind`, `ScanProvenance`).
- `ReceiptScanProvider.swift` — protocol + `ReceiptScanError` enum per spec §3.2.

`ScannedReceipt` is `Sendable, Codable, Equatable`. Convenience `.tax` and `.tip` fields are `let` initialized at construction time as `extras.filter { $0.kind == .tax }.map(\.amount).reduce(.zero, +)`.

Tests added in same commit (`Tests/ResplitCoreTests/OCR/ScannedReceiptTests.swift`):
- Round-trip `Codable` for fully-populated receipt.
- `tax` convenience computes correctly with mixed `.tax/.mandate/.surcharge` extras.
- Empty receipt → all-nil core + empty `extras` + empty `lineItems`.

Build green. No existing call sites changed.

### P1.2 — Add `AzureDIv4Provider` adapter (parallel path, not yet primary)

New file: `ReceiptSplitter/AzureDIv4Provider.swift` (next to existing `ReceiptScanner.swift`).

Conforms to `ReceiptScanProvider`. `scan(imageData:)` internally calls today's `ReceiptScanner.uploadReceiptV4` + `OCRSnapshotMapper.map(from:)` and converts the resulting `OCRSnapshot` into `ScannedReceipt`. Existing `OCRSnapshot` becomes `internal` (was `public`) — only the adapter and the CloudKit shim consume it.

**Key conversion mapping** (lives inside the adapter):
- `OCRSnapshot.tax` → `ScannedExtra(label: "Tax", amount:, kind: .tax, confidence: nil)` in `extras`.
- `OCRSnapshot.tip` → `ScannedExtra(label: "Tip", amount:, kind: .tip, confidence: nil)` in `extras`.
- For Azure v4 fields the existing mapper doesn't extract (Discount / Credit / ServiceCharge / Mandate per `asc-akig` Phase 2 finding): adapter does NOT yet add raw-text scanning — those gaps stay until P3 lands the Reconciler. Document the gap in a code comment with the asc-akig file path.
- `provenance.providerName = "azure-di"`, `providerVersion = "v4-2024-11-30"`, `latencyMs` measured around the `uploadReceiptV4` call, `retryCount` from existing retry loop counter.

Tests added: `Tests/ReceiptSplitterTests/AzureDIv4ProviderTests.swift` — feed cached `AnalyzeResultV4` JSON (extracted from existing inline test payloads), assert `ScannedReceipt` shape per fixture.

Build green. `AzureDIv4Provider` exists but no production caller yet.

### P1.3 — Migrate ViewModel layer to consume `ScannedReceipt`

`ReceiptOCRAnalyzer.analyze(status:)` is the orchestration call site. Today it consumes `ReceiptScanStatusV4` directly. Change:
- Parameter changes from `ReceiptScanStatusV4` to `ScannedReceipt`.
- Caller (`ReceiptOCRAnalyzer.uploadAndAnalyze` or equivalent) gets a `ReceiptScanProvider` (Factory-injected) and calls `provider.scan(imageData:)` returning `ScannedReceipt`.
- `Container+Database.swift` registers `AzureDIv4Provider()` as the default `ReceiptScanProvider`.

Persistence shim (`OCRSnapshot` → CloudKit data continuity):
- Add `ScannedReceipt.toOCRSnapshot()` extension and `OCRSnapshot.toScannedReceipt()` extension (in `ResplitCore/OCR/Compatibility/`). Used only by the persistence layer until a future cleanup phase deletes `OCRSnapshot` entirely.
- `Receipt.ocrSnapshotV4` field remains untouched — CloudKit data is preserved bit-for-bit. Reads convert via the extension.

Existing tests must continue to pass without rewriting (the migration is shape-preserving for persistence). New ViewModel-layer tests assert that the ViewModel correctly invokes the provider mock and consumes the returned `ScannedReceipt`.

## Files touched

**New:**
- `ResplitCore/OCR/ScannedReceipt.swift`
- `ResplitCore/OCR/ReceiptScanProvider.swift`
- `ResplitCore/OCR/Compatibility/OCRSnapshotBridge.swift`
- `ReceiptSplitter/AzureDIv4Provider.swift`
- `Tests/ResplitCoreTests/OCR/ScannedReceiptTests.swift`
- `Tests/ReceiptSplitterTests/AzureDIv4ProviderTests.swift`
- `Tests/ResplitCoreTests/OCR/OCRSnapshotBridgeTests.swift`

**Modified (minimum surface):**
- `ResplitCore/.../ReceiptOCRAnalyzer.swift` — parameter type change + provider injection
- `ResplitCore/.../Container+Database.swift` — register `ReceiptScanProvider` default
- `ResplitCore/.../OCRSnapshot.swift` — visibility from `public` to `internal`

**Untouched:**
- `OCRSnapshotMapper.swift` (still called by adapter internally)
- `ReceiptScanner.swift` (transport unchanged)
- All ViewModels that consume the OCR result downstream — they get `ScannedReceipt` from the analyzer; if they were reading `OCRSnapshot` properties, the bridge extension provides them.

## Tests required (per CLAUDE.md §MT-5)

OCR is on the revert-prone surfaces list. Same-PR regression tests:

1. `ScannedReceiptTests` — Codable round-trip, convenience field math, equality.
2. `AzureDIv4ProviderTests` — every `asc-akig` Phase 1 fixture (the 4 regression tests added 2026-04-13 in `ReceiptSnapshotApplyingTests.swift`) gets a parallel test feeding the same cached `AnalyzeResultV4` JSON through `AzureDIv4Provider`, asserting `ScannedReceipt` shape.
3. `OCRSnapshotBridgeTests` — `ScannedReceipt ↔ OCRSnapshot` is a bijection for the existing schema (no data loss in either direction).
4. ViewModel-layer test — `ReceiptOCRAnalyzer.analyze(status:)` invoked with mock `ReceiptScanProvider` returns expected `ScannedReceipt`.

## Gate (definition of done)

- [ ] `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-ocrmoat-P1-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] `tuist test "ReceiptSplitter Unit Tests"` ✓
- [ ] `tuist test "Resplit UI Tests"` ✓ (no UI surface changed; tests pass unchanged as smoke)
- [ ] `swiftlint lint` ✓
- [ ] `tools/lint/cloudkit-model-lint.sh` ✓ (no model changes; should pass unchanged)
- [ ] PR opened ready-for-review (not draft) — Graphite + Claude bots auto-review per CLAUDE.md §PR & Merge Discipline
- [ ] All review threads resolved via `gh api graphql` per CLAUDE.md §PR & Merge Discipline
- [ ] No user-facing change visible in dev-app or sim. Existing scan flow works identically. (Smoke check: scan a real receipt in sim, verify line items + tax + tip + total appear as before.)

**Not required for P1:** visual proof (no UI change). The §Visual Proof Merge Gate applies to user-visible bug fixes, not internal refactors.

## Out of scope (deferred to later phases)

- Reconciliation logic (P3).
- Telemetry events (P4).
- Dev-app testing surface (P5).
- Adding any new vendor adapter beyond Azure v4 (future spec).
- Deleting `OCRSnapshot` outright — kept as a CloudKit-persistence shim until a future cleanup pass (this prevents a CloudKit data migration in P1).
- Adding raw-OCR text scraping for credits/fees that Azure v4 doesn't extract — that goes in P3 with the Reconciler.

## Decision Log (P1-specific)

- [DIRECTION] 2026-05-01 — Three sub-commits (or stacked PRs) instead of one. Reason: P1.1 introduces types, P1.2 introduces adapter, P1.3 migrates callers. Sub-commits keep review surface small and bisectable. Stacked-PR alternative is fine if reviewer prefers.
- [DIRECTION] 2026-05-01 — Bridge `OCRSnapshot ↔ ScannedReceipt` rather than CloudKit migration. Reason: zero risk to user data. Cleanup is its own future phase.
- [DIRECTION] 2026-05-01 — Don't add raw-text scanning for missing extras here. Reason: that's the `Reconciler`'s job in P3. Mixing the responsibilities now would conflate "represent what the vendor returned" with "fix what the vendor missed".

## Progress

(empty — populated when claimed)
