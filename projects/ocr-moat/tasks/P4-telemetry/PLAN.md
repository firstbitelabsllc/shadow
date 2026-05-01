> Parent: ../../PLAN.md

# P4 — Telemetry pipeline

**Status:** [pending]
**Priority:** P1 within ocr-moat (depends on P1, parallel-safe with P3)
**Claim:** `claimed_by:` `claimed_at:`
**Depends on:** P1 [completed]. **Optional pairing:** P3 [completed] enables `reconciliation_severity` property on success event; can ship without P3 by emitting nil for that field.
**Blocks:** none
**ETA:** 4h
**DerivedData namespace:** `/tmp/resplit-dd-ocrmoat-P4-${RANDOM}`
**Worktree:** `~/Development/resplit-ios-worktrees/ocrmoat-P4-<cycleid>/`

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

(empty)
