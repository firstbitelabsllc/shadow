> Parent: ../../PLAN.md

# P4 — Telemetry pipeline

**Status:** [in_progress] — **P4.1 [completed via PR #594 squash `c526b749`]**; merge completed 2026-05-04T15:10Z after Graphite + Seer green, empty review-thread audit, `mergeStateStatus=CLEAN`, and Claude-recorded local gates (build succeeds, 8/8 EventOcrTests pass, swiftlint + cloudkit-lint clean). **P4.2 [completed via PR #595 squash `28ddad01`]** shipped 2026-05-04T~15:30Z and merged 2026-05-04T16:03:47Z after a two-wave Sentry MEDIUM bot-review fix-up sequence on commits `58fe8512` (gate `ocrScanFailed` on `!isLegacyReceipt` to suppress orphan failed events for legacy receipts) and `7a4800ec` (cross-instance pairing contract test `testV4PollingTickThrowingEmitsOcrScanFailed` — pre-empts a future per-instance flag regression). All three terminal-bot checks green on `7a4800ec`: Seer SUCCESS (upgraded from NEUTRAL on `f4874452`), Graphite AI Reviews SUCCESS, Graphite mergeability_check SUCCESS. 0 unresolved threads at merge (4 total, all resolved). Phase D inherited + closed by `claude-opus-4-7-rios-loop-c1777909518`. **P4.4 [in_review] via PR #596** opened 2026-05-04T16:30Z by `claude-opus-4-7-rios-loop-c1777911481` on branch `claude/ocrmoat-P4-4-c1777911481`, head commit `1c5ad612` `feat(ocr-moat): P4.4 emit ocrFieldConfidence histogram per non-nil field`. Pure-additive shape: 5 files / +151 LOC across 3 surfaces (Event enum + ConfidenceBucket helper + 2-loop wire-up after `ocrScanSucceeded`). 18/18 tests pass in 0.120s (10 EventOcrTests + 8 ReceiptOCRAnalyzerTelemetryTests, includes 2 new schema tests + 1 MT-5 contrapositive `testV4SuccessEmitsFieldConfidencePerNonNilField` locking nil-skip + iteration order + bucket math). Build Succeeded on iPhone 17 sim with isolated `/tmp/resplit-dd-ocrmoat-P4-4-c1777911481`. swiftlint + cloudkit-lint clean. PR marked ready + `@graphite review` triggered. Phase D (bot-review wait + merge) defers to a later cycle per subagent-hygiene rule 2 (commit-before-wait). **P4.3 remains pending — deferrable per redesign (PostHog UI config, not code).**

**P4 redesign context:** Phase A recon shipped 2026-05-04T14:32Z by `claude-opus-4-7-rios-loop-c1777905169`; Phase B+C P4.1 shipped 2026-05-04T14:57Z by `claude-opus-4-7-rios-loop-c1777906165` as PR #594 (`feat(ocr-moat): P4.1 Event enum OCR cases + ScanTelemetryHandle`), branch `claude/ocrmoat-P4-1-c1777906165`, implementation commit `25b842ba`. Major spec drift discovered via cycle 1777902839's "throw-away-data audit" rule: Resplit-iOS already has `AnalyticsServiceType`, `AnalyticsService`, `PostHogAnalyticsProvider`, `AnalyticsEvent`, `Event`, and `captureForTesting`, so the parallel `ReceiptScanTelemetry` protocol/wrapper design was dropped. Redesigned slice plan: **P4.1 (done)** extends `Event` with OCR cases and adds `ScanTelemetryHandle`; **P4.2 (next)** wires `Event.ocrScan*` into `ReceiptOCRAnalyzing.swift:38-134 analyze(status:)` at the existing breadcrumb call-sites via `analyticsService.track(...)`; **P4.3** creates or documents the PostHog `Resplit OCR Health` dashboard; **P4.4** adds the field-confidence histogram event.
**Priority:** P1 within ocr-moat (parallel-safe with P5)
**Claim:** `claimed_by: claude-opus-4-7-rios-loop-c1777911481` `claimed_at: 2026-05-04T16:24Z` — P4.4 slice (field-confidence histogram) claimed; Phase A recon complete in this cycle (read `ScannedReceipt.swift` + `AnalyticsServiceType.swift` Event enum + `ReceiptOCRAnalyzing.swift` `.completed(scannedReceipt):` block on origin/main). Pure-additive shape (3-touch: enum case + bucket helper + post-success-event for-loops) — Phase B+C will be attempted in this same cycle per cycle 1777906165's single-cycle-additive precedent; if Phase B blocks, cycle exits with redesign written here for the next cycle to transcribe. Prior P4 claim history: P4.1 = `claude-opus-4-7-rios-loop-c1777905169` (recon) → `c1777906165` (Phase B+C PR #594) → `codex/night-watch-chat-updates` (Phase D squash `c526b749`); P4.2 = `c1777907480` (Phase B+C PR #595) → `c1777909518` (Phase D inherited squash `28ddad01`).

**P4.4 redesigned slice plan (transcription guide for any cycle inheriting Phase B):**

- **Surface 1 — Event enum extension** in `ResplitCore/Analytics/AnalyticsServiceType.swift`:
  - Add case after `ocrScanFailed` (~line 157):
    ```swift
    case ocrFieldConfidence(
      provider: String,
      providerVersion: String,
      fieldName: String,
      confidenceBucket: String
    )
    ```
  - Add `eventTitle` (~line 244 alongside other OCR titles):
    ```swift
    case .ocrFieldConfidence:
      "OCR field confidence"
    ```
  - Add `properties` case (~line 389 after `.ocrScanFailed` properties):
    ```swift
    case let .ocrFieldConfidence(provider, providerVersion, fieldName, confidenceBucket):
      [
        "provider": provider,
        "provider_version": providerVersion,
        "field_name": fieldName,
        "confidence_bucket": confidenceBucket
      ]
    ```

- **Surface 2 — Bucket helper.** Add a new top-level free function in `ResplitCore/Analytics/ScanTelemetryHandle.swift` (existing P4.1 file — keeps telemetry primitives co-located):
  ```swift
  public enum ConfidenceBucket {
    public static func label(for confidence: Double) -> String {
      switch confidence {
      case ..<0.5: return "0.0-0.5"
      case ..<0.7: return "0.5-0.7"
      case ..<0.9: return "0.7-0.9"
      default: return "0.9-1.0"
      }
    }
  }
  ```
  Boundaries match P4 PLAN line 70: `0.0-0.5 | 0.5-0.7 | 0.7-0.9 | 0.9-1.0`. Half-open intervals: `[0.0, 0.5) | [0.5, 0.7) | [0.7, 0.9) | [0.9, ∞)` — so 0.5 falls into "0.5-0.7", 0.7 into "0.7-0.9", 0.9 into "0.9-1.0". 1.0 included in top bucket (default).

- **Surface 3 — Wire-up** in `ReceiptOCRAnalyzing.swift` `case let .completed(scannedReceipt):` block (currently around line ~95-117 on origin/main, post-`ocrScanSucceeded` track call, before `return .success(.loaded(suggestion))`):
  ```swift
  for item in scannedReceipt.lineItems {
    guard let confidence = item.confidence else { continue }
    analyticsService.track(
      Event.ocrFieldConfidence(
        provider: provider.providerName,
        providerVersion: provider.providerVersion,
        fieldName: "line_item",
        confidenceBucket: ConfidenceBucket.label(for: confidence)
      )
    )
  }
  for extra in scannedReceipt.extras {
    guard let confidence = extra.confidence else { continue }
    analyticsService.track(
      Event.ocrFieldConfidence(
        provider: provider.providerName,
        providerVersion: provider.providerVersion,
        fieldName: "extra_\(extra.kind.rawValue)",
        confidenceBucket: ConfidenceBucket.label(for: confidence)
      )
    )
  }
  ```

- **Tests required (MT-5)**:
  - `Tests/ResplitCoreTests/EventOcrTests.swift` (extend the existing P4.1 file): bucket-boundary tests (`label(for: 0.0)` → "0.0-0.5", 0.49 → "0.0-0.5", 0.5 → "0.5-0.7", 0.69 → "0.5-0.7", 0.7 → "0.7-0.9", 0.89 → "0.7-0.9", 0.9 → "0.9-1.0", 1.0 → "0.9-1.0") + schema test asserting `Event.ocrFieldConfidence(provider: "azure-di", providerVersion: "v4", fieldName: "line_item", confidenceBucket: "0.7-0.9").eventTitle == "OCR field confidence"` + properties dict matches.
  - `Tests/ResplitCoreTests/ReceiptOCRAnalyzerTelemetryTests.swift` (extend the existing P4.2 file): contrapositive `testV4SuccessEmitsFieldConfidencePerNonNilField` — feed mock provider returning `ScannedReceipt` with 3 lineItems (confidences 0.4 / 0.7 / nil) + 2 extras (kind=.tax confidence 0.95 / kind=.fee confidence nil). Assert exactly 3 `ocrFieldConfidence` events emitted (NOT 5 — nil confidence skipped) with field_name values `["line_item", "line_item", "extra_tax"]` and confidence_bucket values `["0.0-0.5", "0.7-0.9", "0.9-1.0"]`. The contrapositive asserts that nil-confidence fields don't pollute the histogram.

- **Estimated LOC**: +25 production (5 enum case + 1 eventTitle + 7 properties + 9 bucket helper + 12 wire-up loops, minus 9 reuse) / +90 tests. Total <120 LOC, single-file-per-surface, no new dependencies, no DI changes (analyticsService already injected per P4.2). Pure-additive: no call-frequency change since for-loops fire in the same scan-success context as the existing `ocrScanSucceeded` track.

- **Why this is pure-additive** (single-cycle-ship safe, per cycle 1777909518's wire-up budget rule): the for-loops execute exactly once per `.completed(scannedReceipt)` arrival, which happens exactly once per scan (V4 polling resumption short-circuits at `receipt.hasV4Snapshot` before reaching the success block). No risk of poll-tick re-emission. No risk of legacy-path orphan events (the legacy short-circuit `analyzeLegacy` returns before reaching this block). No new instance-state to manage.
**Depends on:** P1 [completed], P2 [completed], P3 [completed via P3.4e PR #593 squash `bfa59831` — bookkeeping flip from `[in_review]` → `[completed]` rides with the next code PR per CLAUDE.md `§MT-1`]. **Throw-away-data audit confirms** `AnalyticsServiceType` + `PostHogAnalyticsProvider` already wired in `ResplitCore/Analytics/AnalyticsServiceType.swift` — no new SPM dep, no platform-decision ASK-LEO needed, no parallel protocol.
**Blocks:** none (P5 dev-app is parallel-safe — its OCR-event surface inspector can read whatever `Event` enum cases exist whenever they ship).
**ETA:** 4h total across 4 slices (P4.1 ~1h, P4.2 ~1h, P4.3 deferrable, P4.4 ~1h).
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P4-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P4-<slice>-<cycleid>/` (per-slice, not per-phase, to enable parallel slice ship if a later cycle has multi-agent capacity)

## Purpose

Wire OCR observability — every scan emits structured PostHog events; Sentry breadcrumbs become provider-tagged. Dashboards exist for p99 latency, failure rate, unknown-extras count, and (post-P3) reconciliation severity distribution. After P4, production OCR incidents are diagnosable from PostHog + Sentry without log access.

## What ships

### P4.1 — `ReceiptScanTelemetry` service

New file `ResplitCore/Telemetry/ReceiptScanTelemetry.swift`:

```swift
public protocol ReceiptScanTelemetry: Sendable {
  func scanStarted(provider: String, providerVersion: String, imageSizeBytes: Int) -> ScanTelemetryHandle
  func scanSucceeded(handle: ScanTelemetryHandle, scanned: ScannedReceipt, reconciliationSeverity: ReconciliationSeverity?)
  func scanFailed(handle: ScanTelemetryHandle, error: ReceiptScanError, retryCount: Int)
}

public struct ScanTelemetryHandle: Sendable {
  let startedAt: Date
  let eventId: UUID
}

public final class PostHogReceiptScanTelemetry: ReceiptScanTelemetry {
  // Wraps existing PostHog client (per /posthog-analytics)
}

public final class NoOpReceiptScanTelemetry: ReceiptScanTelemetry {
  // Used in tests + dev where PostHog is disabled
}
```

The handle pattern lets `scanStarted` return an opaque token that `scanSucceeded`/`scanFailed` use to compute latency without the caller tracking timing.

### P4.2 — Wire into `ReceiptOCRAnalyzer`

`ReceiptOCRAnalyzer.uploadAndAnalyze(...)` (or whatever P1 named it):
- Inject `ReceiptScanTelemetry` via Factory.
- Call `telemetry.scanStarted(provider:..., imageSizeBytes:...)` before `provider.scan(imageData:)`.
- On success: `telemetry.scanSucceeded(handle:, scanned:, reconciliationSeverity: P3-supplied)`.
- On failure: `telemetry.scanFailed(handle:, error:, retryCount:)`.

Sentry breadcrumb structure also updated:
- Existing `category: "ocr"` breadcrumbs gain `data: ["provider": providerName, "provider_version": providerVersion]`.
- New breadcrumb on retry: `category: "ocr.retry"`, `data: ["provider": ..., "attempt": Int, "error_kind": String]`.

### P4.3 — Event schema (PostHog)

Per `/posthog-analytics` event-prefix convention, `ocr.*` namespace:

| Event name | Properties |
|---|---|
| `ocr.scan.started` | `provider`, `provider_version`, `image_size_bytes` |
| `ocr.scan.succeeded` | `provider`, `provider_version`, `latency_ms`, `retry_count`, `line_item_count`, `extras_count`, `unknown_extras_count`, `reconciliation_severity` (nil pre-P3) |
| `ocr.scan.failed` | `provider`, `provider_version`, `error_kind`, `retry_count`, `latency_ms` |
| `ocr.scan.field_confidence` | `provider`, `provider_version`, `field_name`, `confidence_bucket` (e.g., "0.0-0.5", "0.5-0.7", "0.7-0.9", "0.9-1.0") |

The `field_confidence` event is a histogram event — emit one event per field with non-nil confidence. Bucketed strings keep PostHog cardinality manageable.

### P4.4 — PostHog dashboard tiles

Create dashboard `Resplit OCR Health` with 4 tiles via `posthog` MCP (or document the manual steps if MCP authentication is blocked):

1. **p99 scan latency** (last 24h) — timeseries on `ocr.scan.succeeded.latency_ms` p99, broken out by `provider`.
2. **Failure rate** — `count(ocr.scan.failed) / count(ocr.scan.started)` over rolling 1h, broken out by `error_kind`.
3. **Unknown extras** — sum of `unknown_extras_count` on `ocr.scan.succeeded`, last 7d. Alert: sustained >5/day = "vendor is finding fee types we haven't categorized".
4. **Reconciliation severity** (post-P3) — pie chart of `reconciliation_severity` distribution over last 24h.

### P4.5 — Test coverage

`Tests/ResplitCoreTests/Telemetry/ReceiptScanTelemetryTests.swift`:
- Mock telemetry recording — verify `scanStarted` → `scanSucceeded` emits the right event with the right properties.
- Latency math — handle's `startedAt` to `succeeded` time computes `latency_ms` correctly.
- `field_confidence` bucket boundary — confidence 0.499 → "0.0-0.5", 0.5 → "0.5-0.7", etc.

## Files touched

**New:**
- `ResplitCore/Telemetry/ReceiptScanTelemetry.swift`
- `ResplitCore/Telemetry/PostHogReceiptScanTelemetry.swift`
- `ResplitCore/Telemetry/NoOpReceiptScanTelemetry.swift`
- `Tests/ResplitCoreTests/Telemetry/ReceiptScanTelemetryTests.swift`

**Modified:**
- `ResplitCore/.../ReceiptOCRAnalyzer.swift` — wire telemetry calls
- `ResplitCore/.../Container+Database.swift` — register `ReceiptScanTelemetry` (PostHog in production, NoOp in tests)
- `ResplitCore/.../ReceiptScanner.swift` — pass `retry_count` out of the polling loop (currently internal counter; needs to surface)
- `ResplitCore/.../SentryBreadcrumbs.swift` (or wherever breadcrumbs are emitted) — add `provider` + `provider_version` to OCR breadcrumb data

## Tests required (CLAUDE.md §MT-5)

OCR is on revert-prone surfaces:

1. **`ReceiptScanTelemetryTests`** — schema correctness, handle math.
2. **`ReceiptOCRAnalyzerTelemetryTests`** — feed mock provider + mock telemetry, verify events fire in correct order with correct properties for success and failure paths.
3. **Sentry breadcrumb test** — assert `provider` tag is present on OCR breadcrumbs.

## Gate (definition of done)

- [ ] `tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-ocrmoat-P4-${RANDOM}` ✓
- [ ] `tuist test "ResplitCore Unit Tests"` ✓
- [ ] `tuist test "ResplitCore Corpus Tests"` ✓ (no regression on P2/P3 work)
- [ ] `swiftlint lint` ✓
- [ ] PR opened ready-for-review, threads resolved
- [ ] PostHog dashboard `Resplit OCR Health` exists with 4 tiles (or steps documented for manual creation)
- [ ] First 24h of beta data flowing post-merge — p99 latency tile populates non-empty
- [ ] Sentry breadcrumb sample (manually verified by triggering a scan in beta) shows `provider` tag

## Out of scope (deferred)

- Per-user OCR cost tracking (future spec; could layer on `provenance.cost_usd` if vendor exposes).
- A/B test framework for vendor comparison (future spec).
- Full distributed tracing (span IDs linking OCR request → applier → UI render). PostHog events get us 80% there.

## Decision Log (P4-specific)

- [DIRECTION] 2026-05-01 — Telemetry as a protocol with PostHog + NoOp implementations, not directly calling PostHog client. Reason: tests can verify event emission via mock; dev builds can opt out cheaply.
- [DIRECTION] 2026-05-01 — Bucketed confidence histograms over raw confidence values. Reason: PostHog property cardinality control. Raw 0.0-1.0 floats blow up the property index; 4 buckets keep it tractable.
- [DIRECTION] 2026-05-01 — Handle pattern (opaque token) over caller-managed start/end times. Reason: cleaner API surface, no shared mutable state, latency math is centralized.

## Progress

- [2026-05-04T14:32Z] (`claude-opus-4-7-rios-loop-c1777905169`, cycle 1777905169) — Phase A spec-drift recon + parallel-protocol redundancy check. Discovered `AnalyticsServiceType` + `PostHogAnalyticsProvider` + `Event` enum + `FakeAnalytics` already exist; dropped the spec's proposed parallel `ReceiptScanTelemetry` protocol. Redesigned slice plan from 5 spec slices to 4 actual slices (~200 LOC saved). Atomic-claim pushed.
- [2026-05-04T14:57Z] (`claude-opus-4-7-rios-loop-c1777906165`, cycle 1777906165) — Phase B+C P4.1 shipped as PR #594 (commit `25b842ba` on branch `claude/ocrmoat-P4-1-c1777906165`). Three OCR Event cases + `ScanTelemetryHandle` + 8 schema-contract tests (all pass in 0.006s). Build Succeeded on iPhone 17 sim with isolated `/tmp/resplit-dd-ocrmoat-P4-1-c1777906165`. swiftlint + cloudkit-lint clean. Graphite review explicitly triggered. Phase D (bot-review wait + merge) defers to a later cycle.
- [2026-05-04T15:10Z] (`codex/night-watch-chat-updates`) — PR #594 had Graphite + Seer green checks, `mergeStateStatus=CLEAN`, and zero review threads; merged by squash to `origin/main` as `c526b749`. Remote branch `claude/ocrmoat-P4-1-c1777906165` deleted. Open Resplit iOS PR queue is now empty.
- [2026-05-04T~15:30Z] (`claude-opus-4-7-rios-loop-c1777907480`, cycle 1777907480) — Phase B+C P4.2 shipped as PR #595 (head commit `3251ab7a` on branch `claude/ocrmoat-P4-2-c1777907480`). Three call-sites wired: `analyticsService.track(.ocrScanStarted(...))` at the post-short-circuit pre-dispatch point (so manual receipts emit zero events), `.ocrScanSucceeded(...)` alongside the existing `OCR analysis succeeded` Sentry breadcrumb, `.ocrScanFailed(...)` on both vendor `.failed` and outer-catch. `analyticsService: any AnalyticsServiceType` threaded into `ReceiptOCRAnalyzer.init` + both Container builders (`receiptOCRAnalyzingBuilder` + `receiptScanPollingService.analyzerBuilder`) with `?? AnalyticsService(posthog: nil)` fallback. `retryCount: 0` placeholder + `TODO(P4.4)` for the polling counter (P4.4 explicit follow-up). MT-5 regression suite `ReceiptOCRAnalyzerTelemetryTests.swift` (3 tests pass in 0.054s) pins event-emission shape: happy-path `["OCR scan started", "OCR scan succeeded"]`, vendor-failed `["OCR scan started", "OCR scan failed"]`, manual-receipt `[]`. Build Succeeded on isolated `/tmp/resplit-dd-ocrmoat-P4-2-c1777907480`. 31/31 selected tests pass (3 new + 8 EventOcr + 11 analyzer + 9 polling). swiftlint clean; cloudkit-lint exit 0. PR marked ready + `@graphite review` triggered. Phase D (bot-review wait + merge) defers to a later cycle.
- [2026-05-04T16:30Z] (`claude-opus-4-7-rios-loop-c1777911481`, cycle 1777911481) — Phase A recon + Phase B+C P4.4 shipped as PR #596 (head commit `1c5ad612` on branch `claude/ocrmoat-P4-4-c1777911481`). Atomic-claim won at 16:24Z; cycle 1777905169's "encode redesign in PLAN body" pattern + cycle 1777906165's single-cycle-additive precedent applied (Phase A's redesigned slice plan was already in the Claim line block from this cycle, so Phase B was transcription). Three surfaces: (1) Event enum extended with `ocrFieldConfidence(provider, providerVersion, fieldName, confidenceBucket)` case + matching eventTitle "OCR field confidence" + properties dict in `AnalyticsServiceType.swift`; (2) new `ConfidenceBucket.label(for: Double) -> String` enum in `ScanTelemetryHandle.swift` with half-open intervals `[0, 0.5) / [0.5, 0.7) / [0.7, 0.9) / [0.9, ∞)` per P4 PLAN line 70; (3) two for-loops in `ReceiptOCRAnalyzing.swift:.completed(scannedReceipt):` block iterating `scannedReceipt.lineItems` + `scannedReceipt.extras`, skipping nil-confidence, emitting one event per non-nil with `field_name="line_item"` or `"extra_<rawKind>"`. MT-5 coverage: `testOcrFieldConfidenceTitleAndProperties` (schema lock), `testConfidenceBucketLabelBoundaries` (8-point boundary sweep covering 0.0/0.49/0.5/0.69/0.7/0.89/0.9/1.0 closed/open edges), `testV4SuccessEmitsFieldConfidencePerNonNilField` (contrapositive: 3 lineItems conf 0.4/0.7/nil + 2 extras conf 0.95/nil → exactly 3 events with field_names `["line_item","line_item","extra_tax"]` and buckets `["0.0-0.5","0.7-0.9","0.9-1.0"]`, locking nil-skip + iteration order + bucket math + post-success emission position). Build Succeeded on iPhone 17 sim with isolated `/tmp/resplit-dd-ocrmoat-P4-4-c1777911481` (real stdout — auto-build reminders ignored per the cron's documented 4/4 false-positive pattern). 18/18 selected tests pass in 0.120s. swiftlint + cloudkit-lint clean (empty stdout = 0 violations). PR marked ready-for-review + `@graphite review` triggered. Phase D (bot-review wait + merge) defers per subagent-hygiene rule 2's commit-before-wait pattern — vidux PLAN flipped `[in_progress]` → `[in_review]` here so the work is durable even if the cron session is interrupted before bots reply.
- [2026-05-04T16:03Z] (`claude-opus-4-7-rios-loop-c1777909518`, cycle 1777909518) — Phase D inherited + closed. Two-wave Sentry MEDIUM bot-review fix-up sequence on PR #595: (1) commit `58fe8512` `fix(ocr-moat): P4.2 suppress orphan ocrScanFailed for legacy receipts` — hoisted `let isLegacyReceipt = receipt.analysisResult != nil && receipt.ocrSchemaVersion == nil` above the `do` block in `ReceiptOCRAnalyzing.swift:69` and gated the catch's `analyticsService.track(Event.ocrScanFailed(...))` on `if !isLegacyReceipt {}`. Legacy receipts skip `ocrScanStarted` (V4-first-call-only) so an unpaired failed event was an orphan funnel row. Added MT-5 contrapositive `testLegacyReceiptThrowingDoesNotEmitOcrScanFailed` injecting `URLError` into `fetchReceiptResult` and asserting `analytics.trackedEvents.isEmpty`. (2) commit `7a4800ec` `test(ocr-moat): P4.2 lock V4 polling-tick failure pairing across instances` — added MT-5 `testV4PollingTickThrowingEmitsOcrScanFailed` after a second Sentry MEDIUM proposed a per-instance `didEmitStartedEvent` flag that would BREAK legitimate poll-tick failures (each new analyzer instance via `ReceiptScanPollingService.swift:213 analyzerBuilder(receipt).analyze` starts with the flag false). Reply on the second thread documents that pairing is at the scan-operation level across instances, not per-instance — the test locks the contract so a future agent can't quietly revert. 7/7 telemetry tests pass in 0.091s (4 prior + 1 new failed-suppression + 2 cross-instance contract). Three terminal-bot checks green on `7a4800ec`: Seer SUCCESS (upgraded from NEUTRAL), Graphite AI SUCCESS, Graphite mergeability SUCCESS. 0 unresolved threads at merge. Squash-merged 16:03:47Z as `28ddad01`; remote branch deleted.
