> Parent: ../../PLAN.md

# P1 — Domain types + provider protocol + Azure adapter

**Status:** [in_progress] — P1.1 MERGED 2026-05-02T21:22:45Z (PR #562, squash `33afa14e`). P1.2 (adapter) claimed by loop-1777761115 2026-05-02T22:32Z. P1.3 (ViewModel migration) still pending.
**Priority:** P0 within ocr-moat (foundation; gates P2-P5)
**Claim:** `claimed_by: claude-opus-4-7-rios-loop-1777761115` `claimed_at: 2026-05-02T22:32:00Z` — first writer wins; pull → edit this line atomically → commit → push to claim. (Re-claim from `claude-opus-4-7-rios-77d1ec` whose claim was 20h stale per loop staleness rule; P1.1 shipped under prior claim, P1.2 is contiguous next sub-task.)
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

- [2026-05-01 17:10 EDT] Claimed by `claude-opus-4-7-rios-77d1ec`. Worktree at `~/Development/resplit-ios-worktrees/ocrmoat-P1-77d1ec/`, branch `claude/ocrmoat-P1.1-domain-types`.
- [2026-05-01 17:10 EDT] **P1.1 shipped as PR #562** (https://github.com/firstbitelabsllc/resplit-ios/pull/562) — ready-for-review. Bundled the authority spec doc per CLAUDE.md `§MT-1`. 3 source files added (no existing files modified): `ResplitCore/OCR/ScannedReceipt.swift`, `ResplitCore/OCR/ReceiptScanProvider.swift`, `ResplitCoreTests/OCR/ScannedReceiptTests.swift`. Gates: build ✓, 9/9 new tests ✓, 1181/1181 ResplitCore unit tests (skip pre-existing FF flag) ✓, swiftlint ✓, cloudkit-lint ✓.
- [DESIGN PIVOT 2026-05-01] Simpler `ScannedReceipt` shape than the spec proposed: mirrored `OCRSnapshot` field-for-field (flat `merchantName: String?` + `merchantAddress: String?` instead of nested `Merchant` struct, `Double?` for amounts instead of `Money` type, `String?` for dates instead of `Date`). Reason: minimizes the bridge surface in P1.3, matches existing codebase conventions, and defers `Merchant` / `Money` / typed-Date refactors to a future cleanup phase. The vendor-neutrality contract is unchanged — typed-core fields + `extras` bag + `provenance` are the architectural anchor; whether the merchant is flat-string or nested-struct is a cosmetic detail.
- Next: P1.2 (Azure DI v4 adapter wrapping existing `ReceiptScanner` + `OCRSnapshotMapper`, returning `ScannedReceipt`). Sub-plan unchanged. Wait for PR #562 to merge before opening P1.2 to avoid base-branch race; OR P1.2 can stack on PR #562 via Graphite.
- [2026-05-02 16:35 EDT] **PR #562 spec-fix pushed by `claude-opus-4-7-rios-loop-1777753435`** (commit `693a0947` fast-forwarded onto `claude/ocrmoat-P1.1-domain-types`). Addresses both unresolved Graphite findings — both were real spec deviations vs `docs/superpowers/specs/2026-05-01-ocr-moat-design.md`: (1) `tax`/`tip` were stored vars, now computed from `extras.filter { $0.kind == .tax/.tip }` per spec line 80-95 + the [DIRECTION 2026-05-01] decision in the parent ocr-moat PLAN line 67 ("Computed at construction"); (2) `ScannedLineItem.quantity: Int = 1` was masking the "vendor didn't extract" case, now `Int? = nil` per spec line 81. Two MT-5 regression tests added (`testTaxAndTipAreComputedFromExtrasNotStored`, `testQuantityRemainsOptionalToDistinguishMissingFromExplicitOne`). 11/11 ScannedReceiptTests pass on iPhone 17 Pro sim. Both Graphite review threads resolved + replied to. `@graphite review` re-trigger comment posted (PR#562#issuecomment-4364666419). Phase D step-3 protocol gate (5-min minimum + 30-min wait) holds — next loop cycle will poll Graphite verdict and either merge if approved or surface BOTS-SILENT after 30min.
- [2026-05-02T21:22Z] **P1.1 MERGED** by `claude-opus-4-7-rios-loop-1777756816` via squash `33afa14e` (PR #562). Phase D gate satisfied: 2 reviewThreads RESOLVED, 4 REVIEW objects (sentry[bot], graphite-app[bot], 2× leojkwan COMMENTED-empty), 3 bot CheckRuns SUCCESS (Graphite/AI Reviews, Graphite/mergeability_check, Seer Code Review), `mergeStateStatus=CLEAN`, last `@graphite review` trigger 50min ago (within 2h cooldown — no re-trigger per cycle 1777751926 PROPOSAL). Cleaned up worktrees `ocrmoat-P1-77d1ec` + `ocrmoat-P1.1-spec-fix-2026-05-02` + branches. P1.2 (Azure DI v4 adapter) is now unblocked from base-branch race; next ocr-moat agent can open it directly off `origin/main`.
- [2026-05-02T22:55Z] **P1.2 shipped as draft PR #567** by `claude-opus-4-7-rios-loop-1777761115` (https://github.com/firstbitelabsllc/resplit-ios/pull/567). Worktree at `~/Development/resplit-ios-worktrees/ocrmoat-P1.2-loop-1777761115/`, branch `claude/ocrmoat-P1.2-adapter`. Two new files (no existing files modified): `ResplitCore/OCR/AzureDIv4Provider.swift` (160 LOC) + `ResplitCoreTests/OCR/AzureDIv4ProviderTests.swift` (328 LOC). Gates: build ✓, 13/13 new tests pass in 0.029s on iPhone 17 Pro sim, swiftlint ✓ 0 violations, cloudkit-lint ✓. Three intentional spec deviations enumerated in PR body: (1) adapter file lives in `ResplitCore/OCR/` not `ReceiptSplitter/` because ResplitCore depends on ReceiptSplitter (circular dep otherwise — caught by SourceKit `No such module 'ResplitCore'` diagnostic on first write); (2) `OCRSnapshot` visibility tightening deferred to P1.3 (cross-module callers in ResplitCore + tests would break without the bridge extensions P1.3 introduces); (3) `ScanProvenance.retryCount = 0` because existing `pollForCompletionV4` retry counter is `private var` not externally exposed. PR opened as draft per loop Phase C protocol; next cycle picks up Phase D (`gh pr ready 567` + `@graphite review` trigger + min 5min wait + bot poll + thread resolution + merge OR `BOTS-SILENT 567` if no reviews after 30min).
- [2026-05-02T23:25Z] **PR #567 Phase D address-comments** by `claude-opus-4-7-rios-loop-1777763263`. Promoted draft → ready, `@graphite review` re-triggered (PR#567#issuecomment-4364917232). Three bot review threads landed within 3min of ready: (1) Sentry Seer LOW — `providerName`/`providerVersion` hardcoded duplicated as string literals in static `convert()` while also being class properties; (2) Codex P1 — `translate()` substring-matches `"HTTP 401"`/`"HTTP 429"` but `ReceiptScanner.swift:304` throws `Errors.customError(jsonString)` with raw Azure DI JSON body, so 401/403/429/5xx fall through to `.unknown`; (3) Codex P2 — `URLError.cancelled` mapped to `.providerUnavailable` instead of preserving cancellation semantic. All three confirmed real (verified line 304 throws raw JSON, no `HTTP X` prefix). Fixes shipped in commit `1bd3f4c4` (+148 LOC, -5): hoisted provenance constants to `static let providerNameValue`/`providerVersionValue` (both class props + `convert()` read from same source); `translate()` now also matches Azure JSON error codes (`AuthenticationFailed`/`TooManyRequests`/`InternalServerError`/`ServiceUnavailable`/`ServerBusy`/`subscription key`); extracted `static isCancellation(_ URLError) -> Bool` and re-throw `CancellationError()` from the URLError catch. +6 regression tests; full 19/19 AzureDIv4ProviderTests pass in 0.024s. swiftlint ✓, cloudkit-lint ✓. All 3 review threads replied to with sha + test names AND resolved via `resolveReviewThread` graphql. PR is non-draft; next cycle picks up Phase D merge after bots re-review the fix commit.
