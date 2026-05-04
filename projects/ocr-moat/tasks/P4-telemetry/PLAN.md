> Parent: ../../PLAN.md

# P4 — Telemetry pipeline

**Status:** [in_progress] — Phase A recon shipped 2026-05-04T14:32Z by `claude-opus-4-7-rios-loop-c1777905169`. **P4.1 [in_review]** — Phase B+C shipped 2026-05-04T14:57Z by `claude-opus-4-7-rios-loop-c1777906165` as PR #594 (`feat(ocr-moat): P4.1 Event enum OCR cases + ScanTelemetryHandle`). Branch: `claude/ocrmoat-P4-1-c1777906165`. Commit: `25b842ba`. 8/8 EventOcrTests pass in 0.006s; build succeeds; swiftlint + cloudkit-lint clean. Graphite review triggered. **P4.2-P4.4 remain pending.** **Major spec drift discovered via cycle 1777902839's "throw-away-data audit" rule:** the spec assumed a brand-new `ReceiptScanTelemetry` protocol + `ScanTelemetryHandle` + `PostHogReceiptScanTelemetry` wrapper + `NoOpReceiptScanTelemetry` would be needed. Recon found Resplit-iOS **already has** the abstraction wired: `ResplitCore/Analytics/AnalyticsServiceType.swift` defines `AnalyticsServiceType` protocol with `track(_ event: some AnalyticsEvent)` + `AnalyticsService` multi-provider aggregator + `PostHogAnalyticsProvider` (production API key `phc_aAVDoPbOS9f1k9wOAKd5qVKHOeiKqaSAgfDgrjnj18e`, lifecycle + screen-view auto-capture disabled) + `AnalyticsEvent` protocol shape (`eventTitle: String` + `properties: [String: AnyHashable]?`) + `Event` enum with 40+ existing cases (e.g., `actionScanTapped(source:)`, `tripCompleted(receiptCount:participantCount:)`, `liveSessionFinalized(...)`). The `AnalyticsService.track(_:)` method also has a `captureForTesting` mode that records `capturedEventNames` for unit assertions — the test-shim is already built. **Redesigned slice plan (collapsed from 5 spec slices to 4 actual slices, parallel-protocol dropped):** **P4.1 (NEW)** — extend `Event` enum with OCR cases (`ocrScanStarted(provider:providerVersion:imageSizeBytes:)`, `ocrScanSucceeded(provider:providerVersion:latencyMs:retryCount:lineItemCount:extrasCount:unknownExtrasCount:reconciliationSeverity:)`, `ocrScanFailed(provider:providerVersion:errorKind:retryCount:latencyMs:)`) + introduce `ScanTelemetryHandle` value-type (`startedAt: Date`, `eventId: UUID`) for latency math + helpers `Event.ocrScanStarted(...) -> ScanTelemetryHandle` factory. Pure additive ~120 LOC + ~150 LOC tests. **P4.2 (NEW)** — wire `Event.ocrScan*` into `ReceiptOCRAnalyzing.swift:38-134 analyze(status:)` at the existing 4 breadcrumb call-sites (line 41, 92, 104, 118): inject `analyticsService` via Factory Container + call `analyticsService.track(.ocrScanStarted(provider:..., imageSizeBytes: imageData.count))` returning a `ScanTelemetryHandle`; on success/failure call `analyticsService.track(.ocrScanSucceeded(handle: ..., scanned: ..., reconciliationSeverity: receipt.reconciliationSeverity))`. Keep existing Sentry breadcrumbs (multi-provider redundancy is desirable). ~50 LOC modified. **P4.3 (RENAMED from P4.4)** — PostHog dashboard `Resplit OCR Health` with 4 tiles (p99 latency / failure rate / unknown-extras / reconciliation severity) — manual via PostHog UI or deferred to a doc-only follow-up; SKIP if PostHog MCP unavailable. **P4.4 (RENAMED from P4.5)** — Field-confidence histogram event `ocrScanFieldConfidence(provider:fieldName:confidenceBucket:)` for non-nil-confidence Azure DI fields, bucketed strings to keep cardinality manageable; ships as a separate slice after P4.2 because it changes the call-site loop in `AzureDIv4Provider.mapToScannedReceipt(_:)` not just the analyzer. **DROPPED:** The spec's P4.1 (parallel `ReceiptScanTelemetry` protocol + `PostHogReceiptScanTelemetry` + `NoOpReceiptScanTelemetry` wrappers) — redundant with existing `AnalyticsServiceType` + `PostHogAnalyticsProvider`. Saves ~200 LOC of duplicated abstraction. **Slice-scope contrapositive (per cycle 1777891887 lifecycle rule):** P4.1's regression test asserts that `Event.ocrScanStarted(provider: "azure", providerVersion: "v4", imageSizeBytes: 12345).eventTitle == "OCR scan started"` AND `properties == ["provider": "azure", "provider_version": "v4", "image_size_bytes": 12345]` — pinning the schema-contract from cycle 1 of P4. P4.2's regression test asserts that calling `analyzer.analyze(status: nil)` on an in-memory receipt with mock provider triggers exactly one `ocrScanStarted` capture followed by one `ocrScanSucceeded` capture (using `captureForTesting: true` mode). **Phase B starts next cycle** with P4.1 only (Event enum extension + ScanTelemetryHandle + tests).
**Priority:** P1 within ocr-moat (parallel-safe with P5)
**Claim:** `claimed_by: claude-opus-4-7-rios-loop-c1777905169` `claimed_at: 2026-05-04T14:32Z` — first writer wins; pull → edit this line atomically → commit → push to claim. Phase A only this cycle (recon + slice redesign + atomic-claim); Phase B (P4.1 code) starts next cycle.
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
