# Investigation: Wrap-up race — last-second host change → stale guest amount

## Reporter Says

"when wrapping up we show what to pay, but what if User owner decide to make a last second change, there is a step there in between we haven't accounted for right?" — Leo 2026-05-14

## Evidence

### Wrap-up entry point (iOS host)

- `resplit-ios/ResplitCore/UI/LiveSplit/LiveSessionControlSheet.swift:571-585` — "Wrap up" button calls `finalizeAndDismissIfSuccessful()` → `viewModel.finalize()`. Disabled only while `phase == .finalizing/.reconciling`. **No confirmation modal, no preview-the-final-totals step.** One tap, immediate API call.
- `resplit-ios/ResplitCore/UI/LiveSplit/LiveSessionViewModel.swift:473-575` — `finalize()` flushes pending edits, then calls `networkService.finalizeSession(code:hostKey:)`. Body sent to server = whatever the host had locally at tap-moment.

### Stale-share window (web guest)

- `resplit-web/src/hooks/useSession.ts:462-541` — Polling loop. **Line 463: `if (status !== 'active' || !participantId) return`.** The instant the poll returns `status === 'finalized'`, the polling effect short-circuits and tears down.
- `useSession.ts:511-514` — When poll observes finalized: `setStatus(s); return;` (no `schedulePoll()`). Post-finalize host edits CANNOT propagate — polling is dead.
- `resplit-web/src/views/ClaimingPage.tsx:262-263` — On `status === 'finalized'` the router replaces URL with `/s/{slug}/done`. SummaryPage mounts a fresh `useSession`, which bootstraps once via `lookupSession`, then never polls (same line 463 guard).
- **Worst-case staleness window: UNBOUNDED.** Once guest lands on `/done`, the share displayed = receipt at the server tick when finalize committed. Any later mutation never reaches the guest screen.
- Best case (still on `/claim`): `BASE_POLL_INTERVAL = 5000ms` (line 20). Guest sees `updatedByHost` toast within 5s and `totals.yourShare` auto-recalculates. So the race only bites AFTER guest reaches `/done`.

### Venmo CTA timing (web guest)

- `resplit-web/src/views/SummaryPage.tsx:139,146,152-160` — `totals = useRunningTotal(state, participantId)`. Venmo URL is `useMemo`'d on `[totals.yourShare, state?.receipt.title, …]`. **Memoized URL captures cents at render time → that's what `<a href=…>` ships to the Venmo deeplink.**
- `resplit-web/src/hooks/useRunningTotal.ts:23-56` — Recomputes only when `state` or `participantId` changes. Since polling is dead on `/done`, `state` never changes after finalize-time bootstrap. **Venmo URL is permanently frozen.**

### iOS receipt-lock semantics (different model)

- `LiveSessionViewModel.swift:44-46,54` — `isLiveSessionLocked: surfacePhase.isSessionAlive` AND `state.locked` → `.awaitingGuestDecisions(state)` phase. On iOS, `state.locked == true` flips host into "no more joins / reconcile temp guests" phase — NOT a hard receipt freeze.
- `resplit-ios/ResplitCore/Managers/LiveSessionNetworkService.swift:257` — `LiveSessionError.sessionLocked` thrown by server for **guest-join** attempts after lock. Host edits use `flushPendingUpdate` → `networkService.updateSession`, **no analogous lock check at this layer.**
- Mock parity: `resplit-web/src/mocks/sessionApi.ts:280,486` — finalize sets `state.locked = true`, and `joinSession` checks it. `claimItem` / `updateItemNote` do NOT check `state.locked`. The lock is a join-gate, not a write-gate.

## Root Cause

Three compounding failures:

1. **Web client stops polling the instant it observes `finalized`** (`useSession.ts:463`). Post-finalize host mutations never reach the guest screen. Combined with `/done` being a fresh mount, the guest sees a permanent frozen snapshot from finalize-moment.
2. **No "guest confirms my final amount" handshake.** Host Wrap Up is unilateral (`LiveSessionControlSheet.swift:571`) → immediate `finalizeSession` API call. No two-phase commit, no preview-totals step, no guest cooldown.
3. **Venmo CTA captures cents at memo time.** `SummaryPage.tsx:152-160` builds the deep link once per `totals.yourShare` change; since `state` is frozen, the URL is frozen. Tapping Pay = guaranteed to send the finalize-moment amount, even if the screen SHOULD have moved.

## Impact Map

**User paths that trigger it:**
- Host taps Wrap Up → guest sees `/done` w/ amount X → host re-opens receipt in iOS → host edits item → server mutates → guest screen does not update → guest taps Pay → under/over-pays.
- Host taps Wrap Up DURING guest's Pay-button interaction. Venmo deeplink fires with old amount even though host believes final number is different.

**Failure modes:**
- **Overpay**: host removed comped item post-wrap-up; guest pays pre-removal amount. Guest is owed money; iOS host has no UI to notify.
- **Underpay**: host added tip/added an item guest claimed; guest pays old (lower) amount. Host short, must chase.
- **Confusion**: guest screen `$12.50`; host folder `$14.00`. Manual Venmo memo reconciliation required.

**iOS vs web parity:** iOS host sees canonical truth (their folder). Resplit 2.0 keeps guests on web. Cross-fleet contract: web guest is read-only viewport — but goes **BLIND** after finalize. That's the contract gap.

## Fix Spec

(pending — three mitigation patterns to evaluate)

- **A. Continue polling after finalize on `/done`.** Cheapest: drop the `status !== 'active'` guard (or add a separate `finalized` polling loop at 15s cadence). Guest screen stays live; Venmo URL recomputes via `useMemo`. Add "host updated the receipt — refresh to see your new share" banner that disables Pay until guest acknowledges.
- **B. Server-side hard lock on `finalize`.** Make `finalizeSession` set a freeze flag that blocks all `updateItem` / `claimItem` host endpoints, not just `joinSession`. Force host into "re-open trip" flow (visible state transition) before edits resume. Iron-clad contract; biggest scope.
- **C. Two-phase wrap-up.** Host taps Wrap Up → "Confirm final totals?" sheet shows per-guest shares one last time → host confirms → 5s grace where guests see "Host is wrapping up, final amounts in 5s…" → commit. Cheap UX guard; doesn't fix late edits but eliminates 90%+ of race window.

## Tests

(pending)

## Gate

(pending)
