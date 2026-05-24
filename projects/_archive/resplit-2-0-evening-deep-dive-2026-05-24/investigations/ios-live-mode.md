# Investigation: iOS live vs non-live mode UX divergence — necessary or relic?

## Reporter Says
"on ios i feel like the UX or the experience in live vs non live mode is limited different and im not 10000% certain its necessary whethre its a data safety / prevent write isue or just a relic" — Leo 2026-05-14

## Evidence

### Mode toggle predicate
The single source of truth is `LiveSessionPhase.isSessionAlive` (returns `true` for `creating | resuming | active | reconnecting | finalizing | reconciling | awaitingGuestDecisions`):
- `ResplitCore/UI/LiveSplit/LiveSessionModels.swift:49`
- Re-exposed as `LiveSessionViewModel.isLiveSessionLocked` at `ResplitCore/UI/LiveSplit/LiveSessionViewModel.swift:44`

### Lock state derivation (the cardinal divergence point)
`ResplitCore/ReceiptDetail/ReceiptDetailShellContent.swift:94-107` `lockState(for phase:)` decomposes the single phase into **three** independent flags. The block has an explicit regression contract comment (lines 87-93) warning that re-coupling these is an ASC-regression vector (ticket AHsK5pjy).
```
isEditingLocked: false                    // intentionally unlocked
isFooterLocked: sessionAlive               // settle/share button locked during live
isLiveSessionActive: sessionAlive          // informational badge flag
```

### Live-mode-only UI affordances (the divergence list)
1. **Footer settle/share locked** — `ReceiptActionFooterView.swift:49,75`; settle button replaced by "Add participant" while live.
2. **Merge-participant disabled** — `ReceiptDetailShellContent.swift:81` nulls `onMergeParticipant` when live.
3. **AddPeopleSheet "Done" button hidden** — `AddPeopleSheet.swift:116,552` gated on `!usesImmediateApply`; live mode fires `contactsManager.add*` on every tap.
4. **Tray chip non-removable** — `PeoplePickerViewModel.swift:850` `isRemovable: ... && !hasSession`. Removal still works via popover.
5. **Item-claim editing routed through `LiveSessionItemClaimBackend`** — `ItemParticipantRowView.swift:20`, `ReceiptLoadedListView.swift:422`. Chips network round-trip with debounce + offline queue.
6. **"Unassigned" label suppressed** — `ReceiptLoadedListView.swift:440` conditional on whether any guest mid-claimed the item.
7. **Popover copy swap** — `ParticipantPopoverActionPolicy.swift:16-47` "Remove" ↔ "Remove from Live Split" + alert titles.
8. **Header chrome compaction** — `ParticipantScrollView.swift:141,160` and `ReceiptParticipantHeader.swift:22-49` tighter spacing when `isSessionActive`.

### Git archeology — when the divergence shrank
The original implementation had a **blanket UI lock** on every participant edit during live mode. It was REMOVED on 2026-04-14:
- `9760abae` `fix(asc-ahsk-live-share): unlock participant editing + hide redundant Done button (#67)`
- Reporter: ASC AHsK5pjy — *"Backend needs to remove the lock on taken user."*
- Leo voice rant: *"you can't delete a user... you don't need to have a done button, additions/removals should be immediate."*
- Backend statement quoted in commit body: *"The backend already reconciles concurrent mutations via LiveSessionViewModel's pendingUpdate queue + offlineQueue + mutation observer, so the UI lock is belt-and-suspenders."*
- Investigation file: `resplit-ios/.cursor/plans/investigations/asc-ahsk-live-share-operations.md`

That commit split the formerly-monolithic `liveSessionPhase.isSessionAlive` lock into the three flags above, leaving only the footer locked + the informational badge. The current 8 divergences are the **residue** after that surgery.

### Concurrency model
`LiveSessionViewModel` is **optimistic-write + server-version-reconcile**: 500ms debounce (`:13`), `pendingUpdate` (`:120`), `LiveSessionError.conflict` → `resolveConflict()` re-polls + re-queues (`:1134, :1150`). `LiveSessionOfflineQueue.swift:34-66` persists pending edits to UserDefaults with re-entrancy guard at `:52`. `mutationObserver` re-publishes SwiftData saves (`:114`). Last-write-wins with server reconciliation. Conflict path exists, is tested, ships today.

### Cross-platform parity
resplit-web has NO host-edit surface — it is the **guest claiming view only**. Search returns only guest files (`useSession.ts`, `ClaimingPage.tsx`, `LiveSessionStatusPanel.tsx`). The divergence is iOS-internal; nothing to compare across platforms.

## Root Cause
Per-lock analysis:

| # | Lock | Necessary? | Why |
|---|------|-----------|-----|
| 1 | **Footer settle/share locked** | NECESSARY | Settling closes the session. Doing so mid-live causes partial state on guest devices (claim view goes blank). This is product, not technical — the "Wrap Up" flow is the proper exit. |
| 2 | **Merge-participant disabled** | LIKELY RELIC | Merge produces participant-ID rewrites. The reconciler doesn't track ID swaps, so a guest's outstanding claim could orphan. Could be fixed server-side but isn't free. |
| 3 | **Done button hidden** | NECESSARY | Pure UX correctness — `usesImmediateApply=true` already fires every selection on tap, so "Done" was lying. |
| 4 | **Tray remove-chip hidden** | RELIC | Removal works fine via popover (which the AHsK commit unlocked). Hiding only the tray chip is inconsistent — the data path is identical. |
| 5 | **Live item-claim backend swap** | NECESSARY | Live chips MUST reach the server (they drive guest UI). Local-only chips would diverge from the session state. Correct routing. |
| 6 | **Unassigned label suppression** | NECESSARY | Live mode shows in-flight guest selections; "Unassigned" while a guest is mid-claim is misleading. |
| 7 | **Popover copy swap** | NECESSARY | This is purely copy / language — "Remove from Live Split" reads correctly in context (ASC AGxZDM2 fix). |
| 8 | **Header chrome compaction** | RELIC-ADJACENT | A density choice (live bar takes vertical space). Cosmetic, low risk to revisit. |

**Headline:** Of 8 divergences, **3 are removable relics** (#2 merge, #4 tray-remove, #8 chrome density). The other 5 are product-correctness, not data safety. The original "data safety" justification was already cashed in 2026-04-14: blanket lock gone, reconciler handles conflicts, offline queue handles disconnects.

The "different feel" Leo reports is residual asymmetry from the partial unlock — UI tells a different story per affordance even though the data model is uniform.

## Impact Map
- **Mid-session merge** — cannot consolidate a duplicate guest while live; must wrap up first (#2). Bites the "Nicole appears twice" pattern partially fixed by dedup in PR #628.
- **Tray-chip remove** — must close AddPeopleSheet and use popover to remove a participant (#4). Two-tap when it should be one.
- **Visual rhythm** — receipt header pads tighter while live (#8); subtle but reinforces the "feels different" sensation.

Cross-fleet: web has no host editor, so divergence is iOS-internal.

## Fix Spec
(pending — for each relic, propose removal path; for each necessary lock, propose better UX disclosure)

Sketch:
- **#2 merge**: spike a server-side ID-rewrite on `POST /sessions/:code/merge`; until then, swap the disabled state for an inline "Wrap up to merge" link.
- **#4 tray-remove**: drop the `&& !hasSession` clause on `PeoplePickerViewModel.swift:850`; identical confirmation alert path already handles live mode.
- **#8 chrome density**: A/B remove the `isSessionActive`-conditional spacing in `ParticipantScrollView` + `ReceiptParticipantHeader`; pick the looser default.

## Tests
(pending)

## Gate
(pending — Leo decision on whether to ship #2/#4/#8 as a "consolidate UX" PR or wait until post-2.0)
