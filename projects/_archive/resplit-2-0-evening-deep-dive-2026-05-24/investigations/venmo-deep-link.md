# Investigation: Venmo deep-link web pre-population broken

## Reporter Says
"the deep link venmo on web doesnt propopulate venmo info even with query param" — Leo 2026-05-14

## Evidence

### Web composer — `lib/guestCopy.ts:49-58`
```ts
export function buildVenmoUrl(input: {
  shareCents: number
  receiptTitle?: string | null
  shareHeading?: string | null
}): string | null {
  if (input.shareCents <= 0) return null
  const amount = (input.shareCents / 100).toFixed(2)
  const note = composeVenmoNote({ receiptTitle: input.receiptTitle, shareHeading: input.shareHeading })
  return `https://venmo.com/?txn=pay&amount=${amount}&note=${encodeURIComponent(note)}`
}
```

### Web caller — `src/views/SummaryPage.tsx:152-160`
```tsx
const venmoUrl = useMemo(
  () => buildVenmoUrl({
    shareCents: totals.yourShare,
    receiptTitle: state?.receipt.title ?? null,
    shareHeading: participantName ? guestCopy.summary.shareHeading(participantName) : null,
  }),
  [...]
)
```

Rendered into `<a href={venmoUrl} target="_blank">` at `SummaryPage.tsx:104` (no `recipients`, no `txn=charge` fallback, no UA branch for iOS/Android).

### iOS composer — `ResplitCore/UI/Components/PaymentAppManager.swift:95-108`
```swift
func deepLink(to username: String, amount: Double, note: String) -> URL? {
  // venmo
  var components = URLComponents(string: "venmo://paycharge")
  components?.queryItems = [
    URLQueryItem(name: "txn", value: "pay"),
    URLQueryItem(name: "recipients", value: cleanedUsername),  // <-- KEY
    URLQueryItem(name: "amount", value: amountString),
    URLQueryItem(name: "note", value: note),
  ]
  return components?.url
}
```

iOS feeds in the host's saved Venmo username (`methods[app]`, `FolderShareMessageGenerator.swift:174`) and uses **scheme `venmo://paycharge`** with **four** params.

### Sample URLs

Web emits (Leo's share = $12.34, title = "Sushi Night", participant = "Sam"):
```
https://venmo.com/?txn=pay&amount=12.34&note=Sushi%20Night%20%E2%80%94%20Sam%E2%80%99s%20share
```

iOS emits (same scenario, host's saved handle `@leojkwan`):
```
venmo://paycharge?txn=pay&recipients=leojkwan&amount=12.34&note=Sushi%20Night%20%E2%80%94%20Sam%E2%80%99s%20share
```

### Recent git log
- `406c058 feat(done): 1:1 iOS-native port — summary + Venmo handoff + tests (#590)` (Leo 2026-05-08) — shipped the current `buildVenmoUrl`. Tests assert `https://venmo.com/?txn=pay&amount=&note=` shape but never tested live pre-population.
- `7a03cb1 fix(FA.7): wire navigator.language to guest-flow copy` — wired locale into note text only.

No regression — this surface was **born broken**: PR #590 shipped the universal-link form without `recipients`, and never produced visual proof of pre-fill.

## Root Cause

Two defects compound:

1. **Missing `recipients` param.** Venmo's web universal link `https://venmo.com/?txn=pay&...` requires a recipient identifier (`recipients=USERNAME` or path-encoded `/USERNAME?...`) to land in the composer. With only `amount` + `note`, Venmo redirects to the marketing homepage or signed-in feed — neither pre-fills anything. The web composer **never receives or threads** a host Venmo handle. Grep for `hostVenmoHandle | venmoUsername | recipients` across `lib/` and `src/` outside tests: **zero hits**. `state?.meta` exposes only `hostDisplayName` (`lib/types.ts:40,123`), not a payment handle.

2. **Wrong scheme for app-handoff.** Even if `recipients` were added, `https://venmo.com/?...` does not reliably hand off to the installed Venmo app composer on iOS Safari / Android Chrome — it opens the website. The iOS-native pre-fill scheme is `venmo://paycharge?txn=pay&recipients=...` (custom scheme), which on mobile web only works if the page either (a) uses that scheme directly with a fallback, or (b) uses Venmo's documented path-form universal link `https://venmo.com/USERNAME?txn=pay&amount=N&note=X` which iOS/Android associated-domains routing claims and opens in-app.

The web emits the query-only form with no recipient — the worst of both worlds: no app handoff, no pre-fill on web.

## Impact Map

- **Surface:** `/s/[slug]/done` (SummaryPage hero CTA + footer CTA, both bound to same `venmoUrl`). Stories surface `WebGuest.stories.tsx:231` mirrors the same broken shape.
- **User path:** every guest who completes claim → done and taps "Pay {host} on Venmo". 100% of paying guests on web hit this.
- **iOS share-sheet:** unaffected — uses `venmo://paycharge` scheme with `recipients` and pre-fills correctly (covered by `FolderShareMessageGeneratorTests` line 142-150).
- **Cross-fleet divergence:** the "1:1 with iOS `composeVenmoNote`" claim in `buildVenmoUrl` JSDoc is true for the **note** payload but false for the **URL envelope**.

## Fix Spec (pending)

Three candidate fixes, ranked:

1. **Path-form universal link + host handle plumbing (preferred).** Add `hostVenmoHandle: string | null` to `LiveSplitMeta` (`lib/types.ts`), populate it from finalize-route when the host has a saved handle, and change `buildVenmoUrl` to emit `https://venmo.com/${handle}?txn=pay&amount=${amount}&note=${note}`. Falls back to `null` (hide CTA) when no handle is set. **Requires iOS to start syncing host's Venmo username into the receipt meta** — currently it isn't sent over the wire. Largest scope, correct answer.

2. **UA-aware scheme branch.** On mobile UA, emit `venmo://paycharge?txn=pay&recipients=${handle}&amount=&note=`; on desktop fall back to path-form universal link. Same handle-plumbing prerequisite as (1).

3. **Display-name fallback as `recipients` (cheap hack).** Pass `recipients=${slugify(hostDisplayName)}` so the composer at least lands on a search result. **Will route to wrong Venmo user** in any name collision — unsafe, do not ship.

Recommended path: (1). Sub-tasks: schema migration, iOS-side meta emit, web `buildVenmoUrl` rewrite + tests, hide-when-null CTA logic.

## Tests (pending)

- Unit: `buildVenmoUrl` returns `null` when `hostVenmoHandle` is missing; emits path-form `https://venmo.com/HANDLE?txn=pay&...` when present.
- E2E: extend `e2e/done-1-1-port.spec.ts` to assert the `href` includes a handle segment, not just query params.
- Cross-fleet parity test: iOS `paymentLinks(for:recipientName:)` and web `buildVenmoUrl` produce URLs that point at the same Venmo user.

## Gate (pending)

Mobile-Safari screenshot of `/s/<slug>/done` → tap "Pay {host} on Venmo" → Venmo app opens to the composer with **recipient pre-selected**, **amount pre-filled**, **note pre-filled**. Side-by-side with iOS app handoff doing the same. Until that screenshot exists, the fix is not shipped.
