> Parent: ../../PLAN.md

# P3 — Reconciliation engine (absorbs asc-akig Phase 2)

**Status:** [pending]
**Priority:** P0 within ocr-moat
**Claim:** `claimed_by:` `claimed_at:`
**Depends on:** P1 [completed], P2 [completed]
**Blocks:** P5 (dev-app surface depends on Reconciler being available to display)
**ETA:** 6h
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P3-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P3-<cycleid>/`

## Purpose

Replace the v3-only `ReceiptItemsFixer` with a v4-aware `Reconciler` that operates on `ScannedReceipt` (vendor-neutral input). Surfaces reconciliation findings as a structured report consumable by tests, telemetry, and UI. **This phase absorbs Phase 2 of `~/Development/resplit-ios/.cursor/plans/investigations/asc-akig-ocr-key-value-extraction.md`** (the 40-60 line refactor of the fixer).

## What ships

### P3.1 — `Reconciler` pure-function module

New file `ResplitCore/OCR/Reconciler.swift`:

```swift
public enum ReconciliationFinding: Sendable, Equatable {
  case sumOfItemsMismatchSubtotal(delta: Money)
  case totalMismatch(delta: Money, expected: Money, actual: Money)
  case missingExpectedField(name: String)
  case unknownExtraKind(label: String)
}

public enum ReconciliationSeverity: String, Sendable, Codable {
  case clean   // no findings
  case warn    // findings ≤ $0.05 OR only `.unknownExtraKind`
  case error   // delta > $0.05 OR missing critical field (e.g., subtotal AND total both nil)
}

public struct ReconciliationReport: Sendable, Equatable {
  public let findings: [ReconciliationFinding]
  public let severity: ReconciliationSeverity
}

public enum Reconciler {
  public static func reconcile(_ receipt: ScannedReceipt) -> ReconciliationReport
}
```

Logic:
1. If `receipt.lineItems` non-empty AND `receipt.subtotal` non-nil: compute `sum(lineItems.amount * (qty ?? 1))`; if `|sum - subtotal| > $0.01`, emit `.sumOfItemsMismatchSubtotal(delta:)`.
2. If `receipt.subtotal` AND `receipt.total` both non-nil: compute `expected = subtotal + sum(extras.tax) + sum(extras.tip) + sum(extras.fee) + sum(extras.serviceCharge) + sum(extras.mandate) + sum(extras.surcharge) - sum(extras.discount) - sum(extras.credit)`; if `|expected - total| > $0.01`, emit `.totalMismatch(...)`.
3. If `receipt.subtotal` is nil AND `receipt.total` is nil AND `receipt.lineItems` is empty: emit `.missingExpectedField(name: "subtotal-or-total-or-items")`.
4. For each `extra` with `kind == .unknown`: emit `.unknownExtraKind(label: extra.label)`.

Severity rule:
- `.clean` if `findings.isEmpty`
- `.warn` if all findings are `.unknownExtraKind` OR all delta findings have `|delta| ≤ $0.05`
- `.error` otherwise

### P3.2 — Delete or shim `ReceiptItemsFixer`

The legacy v3-only fixer becomes redundant. Two options, agent's call:
- **Option A — delete it.** No callers exist on the v4 path (it's already a no-op). Sweep `grep -rn "ReceiptItemsFixer"` to confirm no production callers; delete the class + its tests.
- **Option B — shim it.** Make `ReceiptItemsFixer.fixItemsIfNecessary()` call `Reconciler.reconcile()` internally and apply WARN-level fixes (auto-correct subtotal if `delta ≤ $0.01` rounding error). This preserves the v3 behavior for any caller that still references it.

Pick Option A unless P1's grep finds active v3 callers. Document the call in P3 Decision Log.

### P3.3 — Wire reconciliation into `Receipt` persistence

After `Receipt.applyV4Result(...)` (or whatever P1 renamed it to) runs, store the `ReconciliationReport.severity` on the `Receipt` model as a new field `reconciliationSeverity: String` (raw value of the enum).

CloudKit schema migration: add the new field with default `"clean"` for existing rows. CloudKit treats new fields as nullable by default, so this is non-breaking — but run `tools/lint/cloudkit-model-lint.sh` to confirm.

### P3.4 — UI warning chip on receipt detail

When `Receipt.reconciliationSeverity == .warn` or `.error`, surface a small chip on the receipt detail header reading:
- `.warn`: small yellow chip "Check totals" (5-word rule per `/brand-resplit`, but FROZEN per current brand-resplit status — so use existing chip patterns, no new tokens)
- `.error`: small red chip "Totals don't match"

Tap → opens an info sheet listing the findings in plain language ("Sum of items doesn't match subtotal by $0.32"). Sheet has a "Got it" dismiss; no auto-fix UI yet (deferred per spec §10).

Use existing chip components from `ResplitCore/UI/...` — do NOT introduce new design tokens. Per `brand-resplit FROZEN` until 2.0 ships.

CopyTokens additions per CLAUDE.md §Localization:
- `CopyTokens.OCR.warnChipLabel` — "Check totals"
- `CopyTokens.OCR.errorChipLabel` — "Totals don't match"
- `CopyTokens.OCR.findingItemsMismatch(_ delta: String)` — "Sum of items off by \(delta)"
- ... etc per finding case

Translate to all 9 supported languages.

### P3.5 — Visual proof per CLAUDE.md §Visual Proof Merge Gate

Before/after screenshots required. Pick a fixture from P2 with a known mismatch (the `asc-akig` SF mandate case):
- BEFORE = receipt detail without P3 changes (no chip)
- AFTER = receipt detail with the warn chip visible + the info sheet open

Save under `docs/autobot-evidence/2026-05-XX-ocr-reconciliation-chip/` with `before.jpg` and `after.jpg`.

PR body includes the visual proof table per CLAUDE.md §Visual Proof Merge Gate.

## Files touched

**New:**
- `ResplitCore/OCR/Reconciler.swift`
- `ResplitCore/UI/ReceiptDetail/ReconciliationChip.swift`
- `ResplitCore/UI/ReceiptDetail/ReconciliationFindingsSheet.swift`
- `Tests/ResplitCoreTests/OCR/ReconcilerTests.swift`
- `Tests/ResplitCoreTests/Corpus/CorpusReconciliationTests.swift`
- `docs/autobot-evidence/2026-05-XX-ocr-reconciliation-chip/before.jpg`
- `docs/autobot-evidence/2026-05-XX-ocr-reconciliation-chip/after.jpg`

**Modified:**
- `ReceiptSplitter/Models/Receipt.swift` — add `reconciliationSeverity: String` field
- `ResplitCore/Localization/CopyTokens.swift` — add `OCR` namespace entries
- `ResplitCore/Resources/Localizable.xcstrings` — translations for all new keys × 9 languages
- `ResplitCore/.../ReceiptOCRAnalyzer.swift` — call `Reconciler.reconcile(_:)` after `applyV4Result`, store severity
- `ResplitCore/UI/ReceiptDetail/ReceiptDetailHeader.swift` (or equivalent) — render chip when severity ≠ .clean

**Deleted (Option A):**
- `ResplitCore/.../ReceiptItemsFixer.swift`
- `Tests/ResplitCoreTests/.../ReceiptItemsFixerTests.swift`

## Tests required (CLAUDE.md §MT-5)

OCR + UI both on revert-prone surfaces — double regression coverage:

1. **`ReconcilerTests`** — every `ReconciliationFinding` case, every severity bucket, edge cases (empty receipt, all-nil, single line item, large multi-currency).
2. **`CorpusReconciliationTests`** — extends P2's `CorpusReplayTests` to also assert `Reconciler.reconcile(receipt).severity` matches `expected.reconciliation_severity` field added to `corpus.jsonl` schema.
3. **UI snapshot test** — `ReceiptDetailHeader` with each severity (`.clean`, `.warn`, `.error`) renders correctly. Saves snapshot per `/picasso` SwiftUI conventions.
4. **a11y test** — chip has correct accessibility identifier + label.

## Gate (definition of done)

- [ ] `tuist generate --no-open` ✓
- [ ] `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-ocrmoat-P3-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] `tuist test "ResplitCore Corpus Tests"` ✓ — every fixture matches expected severity
- [ ] `tuist test "Resplit UI Tests"` ✓ — chip snapshot tests pass
- [ ] `swiftlint lint` ✓
- [ ] `tools/lint/cloudkit-model-lint.sh` ✓ — `Receipt.reconciliationSeverity` field added cleanly
- [ ] `corpus.jsonl` has `expected.reconciliation_severity` field added to every line
- [ ] **Visual proof committed:** `docs/autobot-evidence/2026-05-XX-ocr-reconciliation-chip/before.jpg` + `after.jpg`
- [ ] PR body includes the BEFORE/AFTER table per CLAUDE.md §Visual Proof Merge Gate
- [ ] PR opened ready-for-review, threads resolved
- [ ] Translations for all 9 languages added to `Localizable.xcstrings`

## Out of scope (deferred)

- Auto-fix UI ("This doesn't add up — adjust to $X?"). Deferred to future spec per spec §10. P3 ships READ surface only.
- Telemetry on reconciliation severity (P4 wires the PostHog event).
- Reconciliation in the `ReceiptLab` dev-app surface (P5 surfaces this).

## Decision Log (P3-specific)

- [DIRECTION] 2026-05-01 — Pure function `Reconciler.reconcile(_:)` static method, not an injected service. Reason: zero state, zero dependencies, easier to test in isolation, no DI plumbing.
- [DIRECTION] 2026-05-01 — `$0.01` threshold for "match" + `$0.05` threshold for `.warn` vs `.error`. Reason: $0.01 is the smallest unit of USD; cumulative rounding from FX or Money math can hit $0.04. Above $0.05 means a real line is missing or wrong.
- [DIRECTION] 2026-05-01 — Surface in UI as warn/error chip on header, not blocking modal. Reason: scanning is the moneymaker — if reconciliation fails on a clean-looking receipt we don't want to block the user; we want to flag it for them to confirm. Modal UX adds friction.
- [PUNT] 2026-05-01 — Don't add raw-text scraping for missed Azure-extracted fees in P3. The Reconciler reports the GAP (via `.totalMismatch` when fees are missing) but doesn't try to recover them from raw OCR lines. That's a future spec when we have telemetry data on how often this matters.

## Progress

(empty)
