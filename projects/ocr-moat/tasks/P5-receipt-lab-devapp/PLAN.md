> Parent: ../../PLAN.md

# P5 — Receipt Lab dev-app surface

**Status:** [pending]
**Priority:** P2 within ocr-moat (capstone — closes corpus-growth loop)
**Claim:** `claimed_by:` `claimed_at:`
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

(empty)
