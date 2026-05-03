> Parent: ../../PLAN.md

# P2 — Fixture corpus + replay provider + corpus runner

**Status:** [pending]
**Priority:** P0 within ocr-moat
**Claim:** `claimed_by:` `claimed_at:`
**Depends on:** P1 [completed]
**Blocks:** P3, P5
**ETA:** 6h
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P2-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P2-<cycleid>/`

## Purpose

Stand up the fixture corpus and the replay infrastructure that feeds it through the contract. After P2, the regression test "does Azure v4's response for THIS receipt produce THIS `ScannedReceipt`?" runs deterministically in CI without hitting the live Azure API.

## What ships

### P2.0 — Apple Photos album importer (NEW 2026-05-03)

Per Leo verbatim 2026-05-03: *"i can help take like 50 photos and upload to apple photos album and u can use that improt and add to th eanalysis is that coool?"* + lane-lead reply: *"YES, please. Album name: `Resplit OCR Fixtures` (case-sensitive)."*

Build a one-shot CLI importer at `scripts/import-photos-album-fixtures.swift` (or `.sh` wrapping `osascript`/Photos framework) that:

1. Authorizes Photos access via `PHPhotoLibrary.requestAuthorization(for: .readOnly, handler:)` (one-time prompt; subsequent runs use cached authorization)
2. Fetches the album by exact title `Resplit OCR Fixtures` via `PHAssetCollection.fetchAssetCollections(with: .album, subtype: .albumRegular, options: PHFetchOptions where title == "Resplit OCR Fixtures")`
3. For each `PHAsset` in the album:
   - SHA256 the underlying JPEG bytes (via `PHAssetResource` → `PHAssetResourceManager.requestData`)
   - Filename: `<short-sha>-<asset-creation-date-yyyyMMdd>.jpg`
   - Write to `Tests/Fixtures/Receipts/images/<filename>`
   - Append a stub line to `corpus.jsonl` with `id=<short-sha>`, `image_path="Tests/Fixtures/Receipts/images/<filename>"`, `expected=null` (to be hand-edited per P2.2 workflow), `annotations.source="photos-album:Resplit OCR Fixtures"`, `annotations.imported_at=<ISO-Z>`
4. Skip photos already imported (idempotent — SHA256 dedup against existing `images/` content)
5. Output a one-line summary: `Imported N new fixtures from "Resplit OCR Fixtures" (M skipped as duplicates)`

After import, the **P2.2 workflow takes over**: claim agent picks each new stub line, runs `scripts/capture-azure-fixture.sh <image-path> <fixture-id>` to populate `azure-v4-responses/<id>.json`, hand-edits `expected` to match what the receipt actually says, fills `annotations.tags` + `known_issues` + `leo_note`.

**Why this exists**: the original P2.2 workflow assumed git-feed/AirDrop ingestion. Apple Photos album is faster (Leo can take + tag receipts in his pocket without thinking about repo state), survives across Macs (iCloud Photos sync), and gives the Photos library tools (date filter, location filter, "show similar") for free. Per Decision Log entry below.

**Hard NEVER**: do not upload Photos library data anywhere. Photos framework access is local-only on Leo's Mac. The importer reads + writes to local repo; no network calls outside the existing Azure DI capture step (which only touches the JPEG bytes, not Photos metadata).

### P2.1 — Corpus directory + JSONL schema

Create `Tests/Fixtures/Receipts/` in the iOS repo:

```
Tests/Fixtures/Receipts/
├── corpus.jsonl              # 1 line per receipt
├── azure-v4-responses/       # cached AnalyzeResultV4 JSON
├── images/                   # original JPEGs (or empty for PII-bearing)
└── README.md                 # how to add a new fixture
```

`corpus.jsonl` schema per spec §3.5. `README.md` documents:
- Per-line schema (with example line for the simple case AND multi-tax-mandate case).
- How to add a new fixture (drop image, capture Azure response, run a script to seed the line, hand-edit `expected` + `annotations`).
- PII policy: PII-bearing images stay gitignored, `image_path: null`, `private: true` in the line.

### P2.2 — Annotate ~10 of Leo's real receipts

Working set Leo provides via Apple Photos album `Resplit OCR Fixtures` (per P2.0 importer above; supersedes the older git-feed/AirDrop path per Decision Log 2026-05-03). Leo target: ~50 photos covering the categorical distribution. Goal: cover the surface, not exhaustive volume.

Target distribution (claim agent should pick from Leo's actual stack):
- 2 simple US receipts (one tax, one tax+tip)
- 2 SF restaurant receipts with multi-tax + mandate
- 1 multi-currency receipt (FX-converted)
- 1 receipt with discount/credit line
- 1 long-itemization receipt (10+ items)
- 1 hard case where Azure v4 misses a line (the test asserts the GAP)
- 1 quick-print thermal receipt with low scan quality
- 1 international receipt (non-USD)

For each: drop image → capture live Azure response (one-shot script `scripts/capture-azure-fixture.sh <image-path> <fixture-id>`) → hand-edit `expected` based on what the receipt actually says → fill `annotations.tags` + `annotations.known_issues` + `annotations.leo_note`.

The `capture-azure-fixture.sh` script is part of P2 deliverable. It uses the same Azure API key as production, calls `/documentintelligence/.../prebuilt-receipt:analyze`, polls, writes JSON to `azure-v4-responses/<fixture-id>.json`.

### P2.3 — `FixtureReplayProvider` implementation

`Tests/Fixtures/Receipts/Helpers/FixtureReplayProvider.swift`:

```swift
public final class FixtureReplayProvider: ReceiptScanProvider {
  public let providerName = "fixture-replay"
  public let providerVersion: String
  private let corpus: ReceiptFixtureCorpus

  public init(corpus: ReceiptFixtureCorpus, version: String = "v1")

  public func scan(imageData: Data) async throws -> ScannedReceipt {
    // SHA256 imageData, look up matching fixture line by hash, load
    // azure-v4-responses/<id>.json, run through AzureDIv4Provider's
    // mapping logic (extracted into a pure function), return ScannedReceipt.
  }
}

public struct ReceiptFixtureCorpus {
  public static func loadDefault() throws -> Self  // reads corpus.jsonl
  public func fixture(forImageHash: String) -> ReceiptFixtureLine?
  public func all() -> [ReceiptFixtureLine]
}
```

`AzureDIv4Provider` from P1 has its mapping logic refactored into a `static func mapToScannedReceipt(_ azureResponse: AnalyzeResultV4) -> ScannedReceipt` so `FixtureReplayProvider` can call the same code path without going through HTTP.

### P2.4 — Corpus test runner

New test target / scheme: `ResplitCore Corpus Tests`. New file `Tests/ResplitCoreTests/Corpus/CorpusReplayTests.swift`:

```swift
final class CorpusReplayTests: XCTestCase {
  func testEveryFixtureMatchesExpected() async throws {
    let corpus = try ReceiptFixtureCorpus.loadDefault()
    let provider = FixtureReplayProvider(corpus: corpus)
    var failures: [String] = []
    for line in corpus.all() {
      let imageData = try line.loadImageData() // or synthetic if PII-private
      let scanned = try await provider.scan(imageData: imageData)
      if let diff = scanned.diff(against: line.expected) {
        failures.append("\(line.id) (\(line.name)): \(diff)")
      }
    }
    XCTAssertTrue(failures.isEmpty, "Corpus mismatches:\n\(failures.joined(separator: "\n"))")
  }
}
```

`ScannedReceipt.diff(against: ScannedReceipt) -> String?` is a small helper that returns nil on equality, otherwise a structured diff string identifying which field disagrees. (Helper added in P2; used by tests + dev-app in P5.)

### P2.5 — Project.swift wiring + CI hook

- Add the `ResplitCore Corpus Tests` scheme to `Project.swift` (per `/tuist`).
- `tuist generate --no-open` to regen.
- Document in `CLAUDE.md` "Standard commands" how to invoke: `tuist test "ResplitCore Corpus Tests"`.
- Add to the Cross-Platform Gate Matrix in `CLAUDE.md` so future PRs run it.

## Files touched

**New:**
- `Tests/Fixtures/Receipts/corpus.jsonl` (10 lines)
- `Tests/Fixtures/Receipts/README.md`
- `Tests/Fixtures/Receipts/azure-v4-responses/*.json` (10 files)
- `Tests/Fixtures/Receipts/images/*.jpg` (subset — PII-clean ones only; private ones gitignored)
- `Tests/Fixtures/Receipts/Helpers/FixtureReplayProvider.swift`
- `Tests/Fixtures/Receipts/Helpers/ReceiptFixtureCorpus.swift`
- `Tests/Fixtures/Receipts/Helpers/ScannedReceipt+Diff.swift`
- `Tests/ResplitCoreTests/Corpus/CorpusReplayTests.swift`
- `scripts/capture-azure-fixture.sh`

**Modified:**
- `ReceiptSplitter/AzureDIv4Provider.swift` — extract `mapToScannedReceipt(_:)` static func (was instance method, now pure)
- `Project.swift` — add new test scheme
- `CLAUDE.md` — document new gate command

## Tests required

P2 IS the test infrastructure. The deliverable itself is tests. No additional MT-5 regression tests beyond what the corpus runner asserts.

But: ensure the test runner ITSELF has a unit test (`ReceiptFixtureCorpusTests`) that asserts `loadDefault()` parses every line of `corpus.jsonl` without error and resolves all referenced files.

## Gate (definition of done)

- [ ] `tuist generate --no-open` ✓
- [ ] `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-ocrmoat-P2-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] **NEW:** `tuist test "ResplitCore Corpus Tests"` ✓ — every fixture matches expected
- [ ] `swiftlint lint` ✓
- [ ] `corpus.jsonl` has ≥ 10 lines covering the categorical distribution above
- [ ] `README.md` documents per-line schema + how to add a new fixture
- [ ] PR opened ready-for-review, threads resolved
- [ ] CLAUDE.md updated with the new gate command in §Standard commands and §Cross-Platform Gate Matrix

## Out of scope (deferred)

- Reconciliation findings (P3 — though P3 will add `severity` checks to the corpus runner).
- Dev-app annotator UI (P5).
- Auto-capture of images from device camera roll into corpus (future).
- A "regenerate fixtures from current Azure" script (future — useful when migrating to v5).

## Decision Log (P2-specific)

- [DIRECTION] 2026-05-01 — Image-hash-based fixture lookup, not file-path. Reason: tests pass `imageData: Data` per protocol, not paths; SHA256 of bytes is the deterministic key.
- [DIRECTION] 2026-05-01 — `ScannedReceipt.diff(against:)` helper returning a string. Reason: structured `assertEqual` per field would fail-fast; the diff helper enumerates ALL mismatches per fixture, so one corpus run reveals the full failure surface, not just the first.
- [DIRECTION] 2026-05-01 — Test scheme `ResplitCore Corpus Tests` separate from `ResplitCore Unit Tests`. Reason: corpus tests load JPEGs from disk (slower) and we want them in the gate matrix but separable for selective testing.
- [DIRECTION] 2026-05-03 — **Apple Photos album `Resplit OCR Fixtures` becomes the canonical ingestion path** (per Leo offer + lane-lead accept this session). Adds new sub-task P2.0 (Photos importer script) upstream of P2.1/P2.2. Supersedes the original "git feed or AirDrop" path (P2.2 prose updated to cite the album). Reason: faster + ergonomic for Leo (take photo in pocket, tag to album, importer pulls), iCloud-sync survives across both Macs, Photos library tools (date filter, similar-search) come for free. Local-only access via PHFetchOptions; no external upload. Per /vidux Course Correction — evidence changed (Leo's preferred ingestion path), plan updated accordingly.

## Progress

(empty)
