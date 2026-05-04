> Parent: ../../PLAN.md

# P5 — Receipt Lab dev-app surface

**Status:** [in_progress] — Phase A recon shipped 2026-05-04T16:48Z by `claude-opus-4-7-rios-loop-c1777913113`. Slice plan written into `## Progress` below per cycle 1777906165's "encode redesign in PLAN body for two-cycle handoff" rule. **P5.1 [completed] — MERGED 2026-05-04T17:26Z via PR #597 squash `78c6d30e` by `claude-opus-4-7-rios-loop-c1777915611`.** All 3 bot checks SUCCESS (Graphite AI Reviews + Graphite mergeability_check + Sentry Seer Code Review) within 90s of `@graphite review` trigger; 0 inline comments; 0 unresolved threads; mergeStateStatus=CLEAN. 11min elapsed since last bot check satisfied the 5-min human-cognition gate. Worktree torn down. **P5.2 [in_review] via PR #598** — `claimed_by: claude-opus-4-7-rios-loop-c1777915611-subagent` `phaseBC_at: 2026-05-04T17:45Z`. Replaced placeholder Live Scan tab with real `LiveScanTab`: PhotosPicker -> Data -> provider (Azure Live | Fixture Replay segmented) -> ScannedReceipt card + `Reconciler.reconcile(_:)` chip + findings list. State machine pure-data enum (`idle | loading | success | failure`). 9 tests in `ResplitDevAppTests/LiveScanTabTests.swift` (all passing in 0.012s); MT-5 contrapositive on `LiveScanProviderKind` exhaustiveness. Build PASS, swiftlint 0 violations, cloudkit-lint clean. Branch head `fd33954b` on `claude/ocrmoat-P5-2-c1777915611`. PR #598 marked ready + `@graphite review` triggered. Phase D (bot verdict + merge) inherits to next cron tick. P5.3-P5.4 wire-ups remain `[pending]` per slice plan below.
**Priority:** P2 within ocr-moat (capstone — closes corpus-growth loop)
**Claim:** `claimed_by: claude-opus-4-7-rios-loop-c1777913113` `claimed_at: 2026-05-04T16:48Z` — Phase A only (recon + slice plan). Phase B+ defers to next cycle's P5.1 atomic-claim.
**Depends on:** P1 [completed], P2 [completed], P3 [completed]. P4 optional (telemetry events visible in dev-app if wired, harmless if not).
**Blocks:** none
**ETA:** 8h
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P5-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P5-<cycleid>/`

## Purpose

Close the corpus-growth loop. After P5, Leo (or any agent / contributor) can drop a new SF receipt JPEG into the dev-app, see the parsed `ScannedReceipt` side-by-side with the source, edit annotations, and save the result back to the repo's `corpus.jsonl` — all in <2 minutes.

This is what makes the moat self-sustaining. Without it, growing the corpus from 10 → 100 receipts requires hand-editing JSONL by reading raw Azure JSON. With it, you scan, you annotate, you save.

## What ships

### P5.1 — `ReceiptLab` view scaffold

New file `ResplitDevApp/Views/ReceiptLab/ReceiptLabView.swift`:

```swift
struct ReceiptLabView: View {
  @State private var selectedTab: ReceiptLabTab = .liveScan

  var body: some View {
    TabView(selection: $selectedTab) {
      LiveScanTab().tabItem { Label("Scan", systemImage: "camera.viewfinder") }
      AnnotateTab().tabItem { Label("Annotate", systemImage: "pencil.and.list.clipboard") }
      ReplayTab().tabItem { Label("Replay", systemImage: "play.rectangle") }
    }
  }
}
```

Wire into `ResplitDevApp` root navigation as a new top-level destination.

### P5.2 — Live Scan tab

`ResplitDevApp/Views/ReceiptLab/LiveScanTab.swift`:

- Photo picker (PhotosUI) → load receipt JPEG into `Data`
- Provider segmented control: `Azure Live` | `Fixture Replay` (toggles `Container.shared.receiptScanProvider`)
- Side-by-side layout (iPad-friendly, but iPhone-only target = stacked):
  - Top: source image
  - Bottom: parsed `ScannedReceipt` formatted as readable card (merchant, items, subtotal, tax, tip, extras list, total, provenance metadata in collapsible)
- Reconciliation report shown inline below the parsed card:
  - Severity chip (clean/warn/error)
  - Findings list (one row per finding)
- "Re-scan" button to retry without re-picking the image

### P5.3 — Annotate tab

`ResplitDevApp/Views/ReceiptLab/AnnotateTab.swift`:

- Fixture picker dropdown (lists every entry in `corpus.jsonl` by `id` + `name`)
- Editable form rendering current `expected` + `annotations`:
  - Line items list (label / amount / qty editable per row, "+" to add)
  - Subtotal / tax / tip / total fields (Money editable)
  - Extras list with kind picker (typed enum) per row
  - Annotations: tags multi-select, known_issues multi-line, leo_note free text
- "Diff vs cached" button → shows diff between current edits and what `corpus.jsonl` has on disk
- "Save" button → writes back to `corpus.jsonl` in the working tree (dev-app has write access via `FileManager` to repo path detected via env var `RESPLIT_REPO_ROOT` set in scheme launch args)

### P5.4 — Replay tab

`ResplitDevApp/Views/ReceiptLab/ReplayTab.swift`:

- Fixture picker (same as Annotate tab)
- "Run" button: loads cached `azure-v4-responses/<id>.json`, runs through `AzureDIv4Provider.mapToScannedReceipt(_:)`, displays parsed result alongside `expected`
- Field-by-field diff highlighting (green for match, red for mismatch, yellow for tolerance)
- "Run All" button: replays every fixture in corpus, shows pass/fail count + drill-down on failures
- Reconciliation severity badge per fixture

### P5.5 — Repo-write helper

`ResplitDevApp/Services/CorpusFileWriter.swift`:

```swift
struct CorpusFileWriter {
  static func saveLine(_ line: ReceiptFixtureLine) throws  // writes to corpus.jsonl
  static func loadCorpus() throws -> ReceiptFixtureCorpus
}
```

Detects repo root via `RESPLIT_REPO_ROOT` env var (set in `ResplitDevApp` scheme launch args). If not set, falls back to writing to a tmp file with an alert: "Set RESPLIT_REPO_ROOT in scheme to save back to repo."

### P5.6 — Documentation

Update `docs/guide/dev-app.md` (already exists per claudux docs refresh) with a Receipt Lab section:
- How to launch the dev-app with `RESPLIT_REPO_ROOT` set
- How to add a new fixture via the UI
- How "Replay" differs from production scanning

### P5.7 — Test coverage

`Tests/ResplitDevAppTests/ReceiptLabTests.swift`:
- Snapshot tests for the 3 tabs (per `/picasso` SwiftUI conventions)
- `CorpusFileWriter.saveLine` writes correctly-formatted JSONL line; round-trip parses back to identical struct
- Annotate tab edits don't corrupt `corpus.jsonl` if save is interrupted

## Files touched

**New:**
- `ResplitDevApp/Views/ReceiptLab/ReceiptLabView.swift`
- `ResplitDevApp/Views/ReceiptLab/LiveScanTab.swift`
- `ResplitDevApp/Views/ReceiptLab/AnnotateTab.swift`
- `ResplitDevApp/Views/ReceiptLab/ReplayTab.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/ScannedReceiptCard.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/AnnotationEditor.swift`
- `ResplitDevApp/Views/ReceiptLab/Components/FixtureDiffView.swift`
- `ResplitDevApp/Services/CorpusFileWriter.swift`
- `Tests/ResplitDevAppTests/ReceiptLabTests.swift`

**Modified:**
- `ResplitDevApp/ResplitDevAppApp.swift` (or root view) — add Receipt Lab destination
- `Project.swift` — add scheme launch arg `RESPLIT_REPO_ROOT=$(SRCROOT)` for `Resplit Dev App`
- `docs/guide/dev-app.md` — add Receipt Lab section
- `CLAUDE.md` Quick Commands — add `Receipt Lab` entry under Dev App scheme

## Tests required (CLAUDE.md §MT-5 + §Visual Proof)

UI is on revert-prone surfaces:

1. **Snapshot tests** — each tab renders correctly in `.clean`, `.warn`, `.error` reconciliation states.
2. **`CorpusFileWriter` round-trip test** — write a `ReceiptFixtureLine` to a tmp JSONL, parse back, deep-equal.
3. **Visual proof** — BEFORE = no Receipt Lab in dev-app; AFTER = Receipt Lab visible with all 3 tabs functional. Screenshots at `docs/autobot-evidence/2026-05-XX-receipt-lab-devapp/`.

## Gate (definition of done)

- [ ] `tuist generate --no-open` ✓
- [ ] `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] `tuist test "ResplitCore Corpus Tests"` ✓
- [ ] `tuist test "ResplitDevApp Unit Tests"` ✓ (new test target if not existing)
- [ ] `swiftlint lint` ✓
- [ ] **Visual proof committed:** `docs/autobot-evidence/2026-05-XX-receipt-lab-devapp/before.jpg` + `after.jpg`
- [ ] PR body includes BEFORE/AFTER table per CLAUDE.md §Visual Proof Merge Gate
- [ ] PR opened ready-for-review, threads resolved
- [ ] **Smoke test:** Leo (or claimer) drops a fresh SF receipt → annotated + saved to corpus in <2 min. Recorded as a Jam or QuickTime clip linked in PR body.
- [ ] `docs/guide/dev-app.md` updated with Receipt Lab section

## Out of scope (deferred)

- Camera capture (vs. photos library only). Deferred — corpus growth from existing photo library is the primary case.
- Multi-fixture batch editing. Future spec.
- Visual diff of side-by-side receipts (image-to-image diff). Future spec.
- Export corpus as a PR-ready commit from inside the dev-app. Future spec — for now, save to working tree, commit/push manually.

## Decision Log (P5-specific)

- [DIRECTION] 2026-05-01 — Dev-app integration over standalone CLI tool. Reason: Leo said either works; dev-app is more discoverable (Leo opens it on his iPhone or sim regularly) and reuses existing UI patterns. CLI tool would duplicate the diff/annotation logic.
- [DIRECTION] 2026-05-01 — Write directly to repo path via `RESPLIT_REPO_ROOT` env var. Reason: simplest path to corpus-on-disk. Alternative was a temp file + manual copy, which is friction.
- [DIRECTION] 2026-05-01 — Three tabs (Scan / Annotate / Replay) over a single unified view. Reason: each is a distinct workflow; tabs keep mental model clean. Unified view would have too many states.

## Progress

### Phase A recon — 2026-05-04T16:48Z by `claude-opus-4-7-rios-loop-c1777913113` (cycle 1777913113)

**Existing surface checked on `origin/main`:**

- `ResplitDevApp/DevAppRoot.swift` defines `enum DevFlow: String, CaseIterable, Identifiable, Hashable` with **15 existing cases** (`guestLanding`, `walkthrough`, `guestScanner`, `guestReceiptReview`, `guestSplit`, `guestSignupPrompt`, `liveSplit`, `tripSettlement`, `settings`, `currencyPicker`, `fxSimplification`, `fxSummaryStates`, `fxFooterStates`, `receiptDetail`, `designSystem`). Each case carries `title: String`, `icon: String` (SF symbol), and `@ViewBuilder var destination: some View` switch arms. Top-level navigation is a `List` of `NavigationLink` rows in `DevAppRoot`'s body, NOT a `TabView`. Routes are deep-linkable via `resplitdev://<rawValue>` URL scheme + `-flow <rawValue>` launch arg.
- `ResplitDevApp/Flows/` contains 24 `*FlowView.swift` files following the convention `<FeatureName>FlowView.swift`. New flows are added by: (a) appending one `DevFlow` case, (b) adding title/icon/destination switch arms, (c) creating one new `*FlowView.swift` file in `Flows/`.
- `ResplitDevAppTests/` contains 3 test files (`DevCoverageRouteTests`, `DevFlowTests`, `SummaryDetailSheetViewModelFactoryTests`) — the test target exists, no new target needed.
- `ResplitCore/OCR/Reconciler.swift` exposes `public enum Reconciler { static func reconcile(_ receipt: ScannedReceipt) -> ReconciliationReport }` plus `ReconciliationFinding`, `ReconciliationSeverity`, `ReconciliationReport`. **The original P5 spec referenced `V3ReceiptReconciler.report(for: Receipt)` — that is the V3 production-Receipt API, NOT the OCR-ScannedReceipt API needed by Live Scan.** Slice plan below uses `Reconciler.reconcile(_:)` directly.
- `ResplitCore/OCR/AzureDIv4Provider.swift` and `ResplitCore/OCR/FixtureReplayProvider.swift` both conform to `ReceiptScanProvider` (per `ReceiptScanProvider.swift`). Both expose `scan(imageData: Data) async throws -> ScannedReceipt` so Live Scan tab can swap providers via segmented control without branching call-sites.
- `ResplitCore/OCR/ReceiptFixtureCorpus.swift` (P2.3-slice-2) exposes `ReceiptFixtureCorpus.load(from:)` + `.loadDefault()` + `fixture(forImageHash:)` + per-line `ReceiptFixtureLine` struct (Decodable). Annotate + Replay tabs build on this.

**Spec drift discovered (audit dimensions per cycle 1777905169 + 1777902839 + 1777911481 rules):**

1. **(parallel-protocol redundancy)** Spec proposed `TabView { LiveScanTab + AnnotateTab + ReplayTab }` as the top-level Receipt Lab surface. Existing DevApp pattern is `DevFlow case + List + NavigationLink → destination`. Resolution: ONE new `DevFlow.receiptLab` case whose `destination` is a `ReceiptLabFlowView` containing the internal `TabView`. Internal `TabView` is fine — only the **root-level** parallel pattern is rejected.
2. **(API throw-away)** Spec referenced `V3ReceiptReconciler.report(for:)` — an API that doesn't exist (the V3 shim path lives in `ReceiptDetail/Managers/ReceiptSnapshotApplying.swift` and operates on production `Receipt`, not OCR `ScannedReceipt`). Resolution: Live Scan tab calls `Reconciler.reconcile(scannedReceipt) -> ReconciliationReport` directly — no shim, no `Receipt`-model dependency.
3. **(string-identifier propagation, audit dim 4 added cycle 1777911481)** Tab labels use SF Symbol systemImage strings (`"camera.viewfinder"`, `"pencil.and.list.clipboard"`, `"play.rectangle"`). These are external identifiers passed to SF Symbols — a typo silently degrades to a missing-glyph cell. P5.1 slice's snapshot test should assert `Image(systemName: <symbol>)` doesn't render the placeholder fallback (or, simpler: a unit test enumerates the 3 strings + asserts each is in `UIImage(systemName:)`'s known set).
4. **(visual-proof carve-out applicability)** Spec listed BEFORE/AFTER screenshots as mandatory. Per CLAUDE.md §Visual Proof Merge Gate: "**New feature (not a bug fix): rule doesn't apply; one screenshot of the new surface + description is the norm.**" Each P5.1-P5.4 slice ships ONE screenshot of the new surface. The full smoke-test gate ("Leo records Jam clip of <2min annotation flow") is the FINAL P5-capstone gate, not a per-slice gate.

**Redesigned slice plan (transcription guide for the next 4-5 cycles):**

#### P5.1 — DevFlow scaffold + empty Receipt Lab tabs

**Shape:** pure-additive, ~50-80 LOC, single-cycle B+C (~12min wall predicted).

- `ResplitDevApp/DevAppRoot.swift`: append one case `case receiptLab` (after `designSystem`), add `"Receipt Lab"` title, `"flask"` SF Symbol icon, `ReceiptLabFlowView()` destination arm.
- `ResplitDevApp/Flows/ReceiptLabFlowView.swift` NEW: SwiftUI `View` with internal `TabView` containing 3 placeholder tab views (`LiveScanTab`, `AnnotateTab`, `ReplayTab` as private structs returning `Text("...")` + an "Coming in P5.N" label). Tab item labels via `.tabItem { Label("Scan", systemImage: "camera.viewfinder") }` etc.
- `ResplitDevAppTests/DevFlowTests.swift`: ONE new test `testReceiptLabFlowAvailable()` asserting `DevFlow.receiptLab` is in `DevFlow.allCases` and its `destination` builds without crashing. ONE new test `testReceiptLabSystemImagesValid()` asserting the 3 tab SF Symbol strings resolve via `UIImage(systemName:)` (covers audit dim 3).
- Visual proof: ONE screenshot of the empty Receipt Lab with 3 tab bar items visible. Saved to `docs/autobot-evidence/2026-05-04-receipt-lab-scaffold/after.jpg`.
- Gate: `tuist generate --no-open` + `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-1-c<cycleid>` + `tuist test "Resplit Dev App Tests"` (or whatever the test scheme is named — verify via `Project.swift` line 493).

**Dependencies satisfied:** none external; uses only `SwiftUI` + `ResplitCore` stable surface.

#### P5.2 — Live Scan tab (photo picker → provider → ScannedReceipt + ReconciliationReport display)

**Shape:** wire-up + new view, ~150-200 LOC, single-cycle B+C + Phase D fix-up wave likely (per cycle 1777907480 wire-up budget rule).

- `ResplitDevApp/Flows/ReceiptLab/LiveScanTab.swift` NEW (or inline in `ReceiptLabFlowView.swift` — decide based on file-size readability): SwiftUI `View` with:
  - `PhotosPicker` (PhotosUI) → loads selected JPEG into `Data?`
  - Segmented control: `Azure Live` | `Fixture Replay`. Toggles a `@State private var provider: ReceiptScanProvider` instance constructed lazily.
  - "Scan" button: kicks off `provider.scan(imageData:)` in a `Task`, displays loading spinner, then renders the `ScannedReceipt` as a card.
  - Calls `Reconciler.reconcile(scannedReceipt)` after success, renders chip + findings list inline below the card.
- New helper view `ScannedReceiptCard.swift` (or inline private struct): renders merchant / items / subtotal / tax / tip / extras / total / provenance metadata.
- Tests: `LiveScanTabTests.swift` with snapshot tests for `.loading`, `.success(scannedReceipt)`, `.failure(error)`, `.reconciliation(.warn)`, `.reconciliation(.error)` states. Uses `FixtureReplayProvider` + corpus fixtures from P2.
- Visual proof: ONE screenshot of a successfully-scanned fixture receipt with reconciliation chip visible.
- Gate: same as P5.1.

**Dependencies satisfied:** `ReceiptScanProvider` protocol (P1), `Reconciler.reconcile(_:)` (P3), `FixtureReplayProvider` (P2.3-slice-3b), `ReceiptFixtureCorpus.loadDefault()` (P2.3-slice-2), Apple `PhotosUI`.

**Phase D budget reminder:** wire-up surfaces consistently surface bot-review fix-up waves (cycle 1777907480 + 1777909518). Budget 28-30min Phase B+C + 30min Phase D (1-2 fix-up commits) = ~1h total wall vs. P5.1's 12min.

#### P5.3 — Annotate tab + CorpusFileWriter (combined slice)

**Shape:** wire-up + new view + new service, ~250 LOC, two-cycle (B+C in cycle N, D in cycle N+1) per the wire-up budget rule.

- `ResplitDevApp/Flows/ReceiptLab/AnnotateTab.swift` NEW: fixture picker dropdown (lists every entry in `corpus.jsonl` by `id` + `name`), editable form rendering current `expected` + `annotations`, "Diff vs cached" + "Save" buttons.
- `ResplitDevApp/Services/CorpusFileWriter.swift` NEW (the spec's P5.5 — bundled into this slice per CLAUDE.md MT-1 no-bookkeeping-only-PRs):
  ```swift
  struct CorpusFileWriter {
    static func saveLine(_ line: ReceiptFixtureLine, repoRoot: URL) throws
    static func loadCorpus(repoRoot: URL) throws -> ReceiptFixtureCorpus
  }
  ```
- Repo-root detection: `ProcessInfo.processInfo.environment["RESPLIT_REPO_ROOT"]` from scheme launch args (`Project.swift` modification adds `.environmentVariables: ["RESPLIT_REPO_ROOT": "$(SRCROOT)"]` to the `Resplit Dev App` scheme runAction — verify this is the right key by checking Project.swift line ~480-490).
- Tests: `CorpusFileWriterTests.swift` with round-trip test (write `ReceiptFixtureLine` → re-load → deep-equal) using a tmp directory. Snapshot tests for AnnotateTab.
- Visual proof: ONE screenshot of an annotation form with edits in flight.
- MT-5 contrapositive: assert that an interrupted save (simulated via a writer that throws mid-write) leaves `corpus.jsonl` byte-identical to its pre-call state — the writer must use atomic-replace semantics, not partial-write.

**Dependencies:** `ReceiptFixtureCorpus` schema (P2.3-slice-2), Apple `Foundation.FileManager`.

#### P5.4 — Replay tab (capstone slice)

**Shape:** wire-up, ~200 LOC, single-cycle B+C + Phase D fix-up wave likely.

- `ResplitDevApp/Flows/ReceiptLab/ReplayTab.swift` NEW: fixture picker, "Run" button (loads cached `azure-v4-responses/<id>.json`, calls `AzureDIv4Provider.mapToScannedReceipt(_:)`, displays parsed result alongside `expected`), "Run All" button (replays every fixture in corpus, shows pass/fail count).
- Field-by-field diff highlighting via `ScannedReceipt+Diff.swift` (already exists per `grep` earlier).
- Tests: `ReplayTabTests.swift` with snapshot tests for the all-pass and partial-fail states.
- Visual proof: ONE screenshot of a "Run All" result with mixed pass/fail.

**Dependencies:** `AzureDIv4Provider.mapToScannedReceipt(_:)` (P2.3-slice-3a), `ScannedReceipt+Diff.swift` (P2 ride-along).

#### P5.5-P5.7 (absorbed)

- Spec's P5.5 (`CorpusFileWriter`) absorbed into P5.3 above per MT-1.
- Spec's P5.6 (docs/guide/dev-app.md update) rides with P5.1's PR (one-line "Receipt Lab now available" addition).
- Spec's P5.7 (test coverage) rides with each slice — no separate slice.

#### Capstone gate (after P5.1-P5.4 all merged)

The smoke-test gate from the spec ("Leo drops fresh SF receipt → annotated + saved to corpus in <2 min, recorded as Jam clip") fires ONCE after P5.4 ships. If Leo's smoke test passes, P5 flips from `[in_progress]` to `[completed]` and the corpus-growth loop is closed. If it fails, a P5.5 follow-up slice addresses the friction point.

**Cycle metric prediction (per cycle 1777909518's wire-up-vs-additive-budget rule):**

| Slice | Shape | B+C wall | D wall | Total |
|-------|-------|----------|--------|-------|
| P5.1 | pure-additive | ~12min | ~10min | ~22min |
| P5.2 | wire-up | ~28min | ~30min | ~1h |
| P5.3 | wire-up + service | ~35min | ~30min | ~1h 5min |
| P5.4 | wire-up | ~28min | ~30min | ~1h |

Aggregate predicted wall: ~3h 30min across 4-5 cron cycles. Original spec ETA was 8h — the slice budget halves this because each slice is independently shippable, no waiting on sim setup or fixture annotation.

#### Critical claim for next cycle (P5.1 transcription)

The next cycle should atomic-claim P5.1 by editing the `**Status:**` line above to add `**P5.1 [in_progress]**` and filling `claimed_by:` + `claimed_at:` with its own agent_id. P5.1's slice scope is fully transcribable from the section above — no further recon needed. Single new file + single enum case + 2 tests + 1 screenshot = single-cycle ship.

### Phase B+C P5.1 — 2026-05-04T17:12Z by `claude-opus-4-7-rios-loop-c1777914119` (cycle 1777914119)

**Shipped:** PR #597 — `feat(ocr-moat): P5.1 Receipt Lab DevFlow scaffold`. 3 files / +152 LOC:

- `ResplitDevApp/DevAppRoot.swift`: appended `case receiptLab` after `designSystem` + 3 switch arms (title `"Receipt Lab"`, icon `"flask"`, destination `ReceiptLabFlowView()`).
- `ResplitDevApp/Flows/ReceiptLabFlowView.swift` NEW: SwiftUI `View` with internal `TabView`. 3 private placeholder tab views (`ReceiptLabLiveScanTab`, `ReceiptLabAnnotateTab`, `ReceiptLabReplayTab`) each rendering a `ReceiptLabPlaceholder` card with SF Symbol + title + detail + "Coming in P5.N" tag. `ReceiptLabTab` enum (`liveScan`/`annotate`/`replay`) carries `title` + `icon` for `.tabItem` labels.
- `ResplitDevAppTests/DevFlowTests.swift`: +2 tests. `testReceiptLabFlowAvailable` pins receiptLab in `DevFlow.allCases` + asserts rawValue/title/icon stable. `testReceiptLabTabCasesAndSystemImagesValid` is the audit-dim-3 contrapositive — enumerates `ReceiptLabTab.allCases` + `DevFlow.receiptLab.icon` and asserts `UIImage(systemName: .)` is non-nil for each (a typo on `flask` / `camera.viewfinder` / `pencil.and.list.clipboard` / `play.rectangle` would fail the test rather than silently render a missing-glyph cell).

**Gate results:**

- `tuist generate --no-open` ✓ (25.350s)
- `tuist xcodebuild build -scheme 'Resplit Dev App' -derivedDataPath /tmp/resplit-dd-ocrmoat-P5-1-c1777914119 -destination 'generic/platform=iOS Simulator'` Build Succeeded
- `tuist xcodebuild test -scheme 'Resplit Dev App Tests' ... -only-testing:ResplitDevAppTests/DevFlowTests` 4/4 pass in 0.039s
- `swiftlint lint` 0 violations (after `.font(.system(size: 44, weight: .regular))` → `.font(designSystem.typography.display)` swap on the placeholder Image — the `no_direct_system_font_usage` rule blocks `.system(...)` font use)

**Phase D defers** to next cycle's 10-min cron tick per pure-additive-slice precedent (P4.4 cycle 1777911481, P3.4e cycle 1777902839). PR is non-draft, `@graphite review` triggered. The next cron fire inherits the bot-review wait + merge.

**Visual proof N/A this slice** per CLAUDE.md §Visual Proof Merge Gate **Special cases / New feature** rule + P3.4e PR #593 precedent. Each tab in this slice is a placeholder "Coming in P5.N" card — there is no functional surface to verify visually. The tab structure + SF Symbol glyphs are mechanically locked by `testReceiptLabTabCasesAndSystemImagesValid`. The meaningful AFTER screenshot ships in P5.2 once Live Scan parses real fixtures.

**Wall-time:** ~10min (claim 17:03Z → push 17:12Z + bookkeeping). Within the cycle 1777906165 prediction of ~12min for pure-additive single-cycle B+C — confirms the slice-shape budget rule continues to hold for new-flow scaffolds.

**Next claimable surface: P5.2** (Live Scan tab — `PhotosPicker` + `Azure Live | Fixture Replay` segmented control + `Reconciler.reconcile(_:)` chip + findings list inline below the parsed `ScannedReceipt` card). Wire-up shape per cycle 1777907480 budget rule: ~28min Phase B+C in subagent + 30min Phase D inheritance (1-2 fix-up commits expected). Slice plan above is fully transcribable; subagent dispatch should follow subagent-hygiene rules 1-4 (active-poll-with-timeout, commit-before-wait, git-evidence in report, 30min wall budget).

### Phase D P5.1 closeout — 2026-05-04T17:26Z by `claude-opus-4-7-rios-loop-c1777915611` (cycle 1777915611)

**Inherited PR #597** from prior cycle's deferred Phase D. State at cycle entry: non-draft, mergeStateStatus=CLEAN, mergeable=MERGEABLE, all 3 bot checks SUCCESS:

- Graphite AI Reviews — SUCCESS (completed 2026-05-04T17:14:01Z, ~3min after PR ready)
- Graphite mergeability_check — SUCCESS (completed 2026-05-04T17:13:47Z)
- Sentry Seer Code Review — SUCCESS (completed 2026-05-04T17:15:06Z)

Zero inline comments across all three reviewers. Zero unresolved review threads via `gh api graphql`. Only PR-level comment is the cron's own `@graphite review` trigger.

**Phase D gate evaluation:**
- ≥1 bot review exists ✓ (3 SUCCESS check_runs from configured AI reviewers)
- All comments addressed ✓ (none to address)
- All threads resolved ✓ (none open)
- 5-min human-cognition gate ✓ (11min elapsed: 17:15:06Z last check → 17:26Z merge decision)

**Squash-merged** to `origin/main` at `78c6d30e` via `gh pr merge 597 --squash --delete-branch`. Remote branch `claude/ocrmoat-P5-1-c1777914119` deleted. Worktree at `~/Development/resplit-ios-worktrees/ocrmoat-P5-1-c1777914119` removed. Local branch deleted (was `aea9729e`).

**Wall-time:** ~3min (cycle entry 17:23Z → push 17:26Z) for PR-state read + thread check + merge + worktree teardown + plan flip. Confirms cycle 1777911481's "single-cycle Phase D inheritance" pattern: when no fix-up waves are needed (the boring-is-good outcome of all 3 reviewers passing 0-comment), inherited Phase D fits in the cycle's read+verify+merge+cleanup envelope without re-claiming.

**Generalizable rule for /resplit-2-0-loop:** the asymmetric-cost-of-AI-review pattern (cycle 1777911481) extends to Phase D inheritance — pure-additive scaffolding with 0 inline comments needs no fix-up wave at all, so Phase D is just the merge + cleanup ceremony (3min wall). Compare to wire-up surfaces (cycles 1777909518 / 1777911481) where Phase D inherits 1-2 fix-up wave commits taking 25-33min wall. The cycle's pre-flight `gh pr view --json mergeStateStatus,reviews,statusCheckRollup` is the cheap test that decides which envelope you're in.


