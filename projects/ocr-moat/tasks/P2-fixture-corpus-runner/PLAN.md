> Parent: ../../PLAN.md

# P2 — Fixture corpus + replay provider + corpus runner

**Status:** [in_progress] — **P2.0 SHIPPED 2026-05-04T02:30Z via PR #576 squash `ed40c7ae`** by subagent `claude-opus-4-7-rios-subagent-a1cc8dfcf78a8438e` (8 unit tests + CLI script + corpus README + .gitkeep dirs + .swiftlint.yml exclude; importer no-ops until Leo populates `Resplit OCR Fixtures` Photos album). Graphite mergeability_check + AI Reviews SUCCESS + Seer skipped (small infrastructure-only diff). P2.1-P2.5 pending pickup; next claimant should pick P2.1 (corpus directory + JSONL schema). KEY INSTALLATION NOTE for next claimant: Apple's Photos framework only exposes `PHAccessLevel.addOnly` and `.readWrite` (NOT `.readOnly` as the original spec said). The shipped script uses `.readWrite` and never writes — do NOT "fix" this back to `.readOnly` in future PRs; it doesn't exist on `PHAccessLevel`.
**Priority:** P0 within ocr-moat
**Claim:** `claimed_by: <unclaimed>` `claimed_at: <unclaimed>` — P2.3-slice-2 [in_review] via cron cycle 1777867383 (2026-05-04T04:20Z): `ReceiptFixtureCorpus` JSONL loader + `ReceiptFixtureLine` + `ReceiptFixtureAnnotations` types + 11 unit tests, branch `claude/ocr-moat-p2.3-slice-2-corpus-loader-2026-05-04`. Slice-1 [completed] via PR #578 squash `5ebb5c77` (2026-05-04T03:38Z). **Next available slice after slice-2 merges: P2.3-slice-3** (`FixtureReplayProvider` + `AzureDIv4Provider.mapToScannedReceipt(_:)` extraction). P2.0/P2.1 SHIPPED via #576 (`ed40c7ae`). P2.2 GATED on Leo populating `Resplit OCR Fixtures` Photos album.
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

- 2026-05-03 — P2.0 Photos importer in flight via `claude-opus-4-7-rios-subagent-a1cc8dfcf78a8438e`. Files shipped: `scripts/import-photos-album-fixtures.swift`, `Tests/Fixtures/Receipts/{README.md,corpus.jsonl,images/.gitkeep,azure-v4-responses/.gitkeep}`, `ResplitCoreTests/Fixtures/PhotosAlbumImporterTests.swift` (8 unit tests, all green), `.swiftlint.yml` (added `scripts/` to excluded). Local gates: `tuist generate --no-open` PASS, `tuist xcodebuild build -scheme 'Resplit Debug' …` PASS, `tuist test "ResplitCore Unit Tests" …PhotosAlbumImporterTests` PASS (8/8), swiftlint PASS, cloudkit-model-lint PASS. Importer is gated on Leo populating the `Resplit OCR Fixtures` Photos album; until then, `swift scripts/import-photos-album-fixtures.swift` is a no-op (prints "album not found" with exit 0).
- [2026-05-04T03:11Z] (claude-opus-4-7-rios-loop-c1777863402, cycle 1777863402) — **P2.1 reconciled to [completed] via P2.0 ride-along** (no separate PR per CLAUDE.md MT-1): `Tests/Fixtures/Receipts/{corpus.jsonl,README.md,images/.gitkeep,azure-v4-responses/.gitkeep}` were verified live on `origin/main` at `ed40c7ae`. README has full per-line schema (table-format, with example), Path A/B for adding fixtures, and PII policy — meets every P2.1 spec requirement. **P2.3-slice-1 SHIPPED to draft-merge gate via PR #578** (`claude/ocr-moat-p2.3-slice-1-scanned-receipt-diff`): `ResplitCore/OCR/ScannedReceipt+Diff.swift` (88 LOC) + `ResplitCoreTests/OCR/ScannedReceiptDiffTests.swift` (170 LOC, 9 tests all green). Helper is pure `public extension ScannedReceipt { func diff(against:) -> String? }` — excludes `provenance` (vendor metadata) and `confidence` (signal quality, not content), aggregates every disagreement in declaration order. Local gates: `tuist test "ResplitCore Unit Tests" …ScannedReceiptDiffTests` PASS (9/9, 0.008s), `swiftlint` PASS (0 violations), `cloudkit-model-lint` PASS. PR opened non-draft, `@graphite review` triggered explicitly (per Phase D step 2 — auto-trigger has been observed silent on non-draft PRs). Phase D wait + merge defers to next cycle. P2.3-main (`FixtureReplayProvider` + `ReceiptFixtureCorpus`) + P2.4-P2.5 still available for fresh claim — P2.3-main can begin once this slice merges (it imports `ScannedReceipt.diff(against:)` for replay assertions).
- [2026-05-04T03:32Z] (claude-opus-4-7-rios-loop-c1777864926, cycle 1777864926) — **PR #578 Phase D bot-fix iteration**. Sentry Seer auto-reviewed within 90s of PR open and flagged a real LOW-severity contract violation: `diff(against:)` docstring promised "in declaration order" but compared `subtotal`/`total` BEFORE `lineItems`. `ScannedReceipt.swift` declares `lineItems` (line 19) before `subtotal` (line 20)/`total` (line 21). The `test_diff_aggregatesEveryMismatch_inDeclarationOrder` test was asserting the WRONG order, masking the bug — Seer caught both. Per CLAUDE.md MT-7 (subagent dispatch hygiene), verified Seer's claim against actual sources before applying fix; both Seer's claim and the proposed fix were correct. Shipped commit `9444fccf` to PR #578 branch (4 insertions, 3 deletions across 2 files): swapped subtotal/total comparisons to AFTER the lineItems block in `ScannedReceipt+Diff.swift`, updated test expectation. All 9 ScannedReceiptDiffTests still pass (0.050s wall), build green via isolated DD path. Replied to Sentry's thread `PRRT_kwDOKH5TFM5_PTPN` (resolved `isResolved: true`), re-triggered `@graphite review` for new commit. Phase D wait + merge defers to next cycle (~10 min) for bot re-review of `9444fccf`.
- [2026-05-04T03:38Z] (claude-opus-4-7-rios-loop-c1777865927, cycle 1777865927) — **P2.3-slice-1 [completed]: PR #578 merged via squash `5ebb5c77`**. Phase D verification: Graphite AI Reviews + Graphite mergeability_check + Seer Code Review all SUCCESS on commit `9444fccf` (gates green within ~12min of push, well past 5-min cognition-gate). Sentry's bug-prediction thread on `cef98269` confirmed self-resolved per its own footer (`*Resolved in 9444fcc*`), graphql `reviewThreads(first:50) | select(.isResolved == false)` returned empty → no unresolved threads. PR was already merged when squash attempted (Leo or peer agent merged the bot-clean PR independently); origin/main HEAD now `5ebb5c77` carries the slice. Worktree `~/Development/resplit-ios-worktrees/ocrmoat-p2-scanned-receipt-diff` removed `--force` (clean working tree, no uncommitted bytes), branch `claude/ocr-moat-p2.3-slice-1-scanned-receipt-diff` deleted locally. Claim line at top of P2 PLAN released (back to `<unclaimed>`). Continuous-drain doctrine evaluated next [pending] surface: P2.3-main is unblocked but exceeds single-cycle Phase A→D wall-time (60-90min per spec); P2.2 gated on Leo's Photos album population; P2.4/P2.5 depend on P2.3-main. Cycle exits OK; next cron fire (10min) picks P2.3-main as fresh atomic claim with slice-shaped scope per cycle-1777834188 orphan-shape lesson.
- [2026-05-04T04:20Z] (claude-opus-4-7-rios-loop-c1777867383, cycle 1777867383) — **P2.3-slice-2 [in_review]: PR #579 opened**. Pure additive `ReceiptFixtureCorpus` JSONL loader (`ResplitCore/OCR/ReceiptFixtureCorpus.swift`, 211 LOC) + 11 unit tests (`ResplitCoreTests/OCR/ReceiptFixtureCorpusTests.swift`). API: `parse(jsonl:)`, `load(from:)`, `fixture(forImageHash:)`, `all()`. Decodes `ReceiptFixtureLine` with snake_case ↔ camelCase mapping (`image_path`, `imported_at`, `known_issues`, `leo_note`, `private` → `isPrivate`); skips blank lines; rejects malformed lines with 0-based line index pinpoint via `CorpusParseError.invalidLine(index:underlying:)`. Local gates: `tuist generate --no-open` PASS, `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-cron-p2.3-slice-2-…` Build Succeeded, `tuist test "ResplitCore Unit Tests" -- -only-testing:ResplitCoreTests/ReceiptFixtureCorpusTests` 11/11 PASS in 0.048s, `swiftlint` clean, `cloudkit-model-lint` clean. PR opened non-draft as `firstbitelabsllc/resplit-ios#579`, `@graphite review` triggered explicitly (per Phase D step 2 — non-draft auto-trigger has been observed silent in this repo). Phase D 5-min cognition gate + bot-review wait defers to next cycle (~10 min) per "one phase per cycle" rule. **Slice-3 next** (`FixtureReplayProvider` + `AzureDIv4Provider.mapToScannedReceipt(_:)` extraction) — slice-3 imports `ReceiptFixtureCorpus` to look up cached vendor responses by image hash.
- [2026-05-04T04:31Z] (claude-opus-4-7-rios-loop-c1777868765, cycle 1777868765) — **PR #579 Phase D bot-fix iteration**. Both initial bot reviewers flagged real issues on commit `103f68f2`: (1) **Sentry HI** — `JSONDecoder` in `parse()` not configured for ISO-8601 dates; verified per MT-7 against `ScannedReceipt.swift:134` where `ScanProvenance.scannedAt: Date` confirms the failure mode for any annotated fixture P2.2 will land. (2) **Codex P2** — `parse()` silently accepted duplicate `id` despite `ReceiptFixtureLine.id` docstring calling it the dedup/lookup key and `fixture(forImageHash:)` using `.first { $0.id == hash }`. Both fixes shipped in commit `f0c42d73` to PR #579 branch (2 files, 63 insertions, 2 deletions): added `decoder.dateDecodingStrategy = .iso8601`; added `CorpusParseError.duplicateID(id:firstIndex:secondIndex:)` thrown after each successful decode if the id collides with a prior line, with both 0-based line indices preserved. Two new MT-5 regression tests in same PR: `test_parse_decodesISO8601Dates_inExpectedScanProvenance` (proves ISO-8601 round-trips through `.iso8601` strategy via inline annotated stub) and `test_parse_throwsDuplicateID_whenSameIdAppearsTwice` (proves dedup invariant + asserts both line indices). Local gates green: `tuist test ReceiptFixtureCorpusTests` 13/13 in 0.044s (both new + 11 prior), `swiftlint` 0 hits, `cloudkit-model-lint` 0 hits. Sentry's thread `PRRT_kwDOKH5TFM5_PsHL` auto-resolved when commit landed (per cycle 1777865927 documented self-resolve pattern); Codex thread `PRRT_kwDOKH5TFM5_PsH8` manually resolved via `gh api graphql resolveReviewThread` after posting fix-link comment. Seer Code Review currently `pending` re-running on `f0c42d73`. Phase D merge-wait defers to next cycle (~10 min) for fresh bot reviews of `f0c42d73` per cycle-1777864926 precedent + subagent-hygiene override (commit-Phase-D-before-wait satisfied: push landed, comment posted, threads resolved; merge is the only remaining step).
- [2026-05-04T04:51Z] (claude-opus-4-7-rios-loop-c1777869876, cycle 1777869876) — **PR #579 Phase D bot-fix iteration #2**. Sentry Seer's re-review of `f0c42d73` posted a NEW MED-severity bug-prediction thread `PRRT_kwDOKH5TFM5_PzRR` on `ReceiptFixtureCorpus.swift:92-104`: `ReceiptFixtureAnnotations` declares init defaults for `tags: [String] = []`, `knownIssues: [String] = []`, `leoNote: String = ""` but uses synthesized `Decodable` — synthesized impl ignores those defaults and throws `.keyNotFound` if JSON omits any of them. Mirrors EXACTLY the pattern just fixed for `ReceiptFixtureLine` last commit (custom `init(from:)` with `decodeIfPresent ?? defaultValue`). Per CLAUDE.md MT-7 verified Seer's claim against actual source (lines 73-113 confirm synthesized Decodable, no custom init; lines 62-70 of `ReceiptFixtureLine` confirm the existing pattern to mirror) BEFORE applying — both Seer and the fix shape are correct. Shipped commit `0e991cce` to PR #579 branch (2 files, 28 insertions): added 9-line custom `init(from:)` to `ReceiptFixtureAnnotations` mirroring `ReceiptFixtureLine` shape; added MT-5 regression test `test_parse_appliesAnnotationDefaults_whenOptionalFieldsMissing` asserting the contrapositive (JSONL with only `source`+`imported_at` decodes with `tags=[]`, `knownIssues=[]`, `leoNote=""`). Local gates green: `tuist test ReceiptFixtureCorpusTests` 14/14 in 0.039s on isolated DD `/tmp/resplit-dd-cron-${RANDOM}` (auto-build hook also confirmed source compile via `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-autobuild` succeeded), swiftlint + swiftformat clean via pre-commit hooks. `@graphite review` re-triggered. Sentry's thread `PRRT_kwDOKH5TFM5_PzRR` is a `BUG_PREDICTION` shape — per cycle-1777865927 documented pattern, will auto-resolve when this commit detected. Phase D merge-wait defers to next cycle (~10 min) for bot re-review of `0e991cce`. **Pattern observed:** PR #579 has now triggered 3 successive bot-fix iterations (Sentry HI dates → Codex P2 dedup → Sentry MED Decodable defaults), each surfacing a real latent bug missed in the original test design. The slice's loop count (3 fix commits beyond initial) is high but each iteration shipped a real fix with MT-5 regression coverage; the Phase D protocol scales cleanly with bot iteration count without any merge-without-review escapes.
