# T-4 — Kitchen text ABC→FIRE implementation plan

**Date:** 2026-07-22  
**Authority:** `plans/abc-fire-control-plane/PLAN.md`  
**Status:** writing-plans only; **no app repo create**  
**Inputs:** Decision Log (two-brain, fire gate, Kitchen G1–G6); `design-spec-v0.md`; `ir-v0-schema-draft.md`; T-2b quality PROCEED

Standing veto: rewrite milestones/gates; hard rail on `gh repo create` stays paused until Leo opts in in plain language.

---

## 1. Vertical slice scope (Kitchen text only)

**Ship name:** Kitchen ABC→FIRE text loop  
**Surface:** standalone native iOS/SwiftUI (future repo). **No voice.** No car mode. No desktop chat port.

| In | Out |
|---|---|
| Blank intent → ≤3 outcome-class options (Nicole menu-depth) | Voice / STT / car hands-free |
| Pick + rider updates `constraints` on stack | Synonym chip spam (fail → freeform) |
| Editable `ChoicePathStack` pre-FIRE; resume from disk | Vidux writes every clarify turn |
| Fire gate: session confirm word + dry-run + abort | Confirmation-free fire (amp) |
| Sealed packet file on FIRE (G3) | Live Mac executor side effects beyond stub/mock for G4 |
| Clarify brain = cheap model, tools=none | Executor tools until after FIRE |
| Skeleton UI <200ms while options stream/fill | Hard sub-second complete turn (residual) |

**Dogfood intent (fixed for gates):** Nicole in the kitchen wants help turning a vague goal into a sealed handoff — e.g. "help me ship something for StrongYes this week" → three outcome classes → pick + rider → FIRE → packet on disk. Exact prompt fixture lives with golden dialogues; not a product copy freeze.

**Success of this slice:** G1–G6 green on device (or Simulator) with clarify live + executor **stubbed** so abort proves zero side effects. Real Mac executor HMAC/Tailscale is a later milestone after hard-rail repo exists — not required to close Kitchen G1–G6.

---

## 2. Module boundaries

Three hard walls. Crossing them is a bug, not a feature.

```text
┌───────────────────────────── iOS app (future repo) ─────────────────────────────┐
│  SwiftUI (KitchenSessionView)                                                    │
│       │                                                                          │
│       ▼                                                                          │
│  SessionStore  ←→  IR types (BeliefNode / ChoicePathStack)  ←→  DiskResume       │
│       │                                                                              │
│       ├── ClarifyBrainClient   tools=none, never mutates                           │
│       │         └── cheap model (Haiku / GLM / later local)                        │
│       │                                                                              │
│       └── FireGate             confirm word + blast tier + dry-run + abort         │
│                 │                                                                    │
│                 ▼ on commit only                                                     │
│           SealedPacketWriter → immutable JSON file                                 │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │ after FIRE ack (not in Kitchen stub)
                                      ▼
┌──────────────────────────── Mac executor (later) ───────────────────────────────────┐
│  Capability allow-list only: draft files / private draft PR / read plan+ledger      │
│  Denied: gh repo create, public push, external send, money, destructive git         │
│  Pattern lift: HMAC + Tailscale + Keychain OAuth (moussey), not glue copy           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

| Module | Owns | Must not |
|---|---|---|
| **Clarify brain** | Propose ≤3 options + optional narrow Q; fill `BeliefNode`; stream/skeleton UX | Call tools; write repos; send; spend; seal packet; talk to executor |
| **Fire gate** | Session confirm word; blast tier; dry-run JSON; undo/abort until executor start-ack | Run clarify; run executor tools; treat "FIRE" string as always-sufficient when blast high |
| **Executor** | Post-FIRE work under allow-list; ack start so abort window closes | Run before sealed packet; invent capabilities; create public repos |
| **Session / IR store** | Editable stack pre-FIRE; constraints from riders; disk resume | Persist to Vidux every turn; mutate stack after FIRE except abort |
| **Vidux** | Plan/proof/resume for *this design lane*; post-FIRE proof rows later | Be the product UI; own model routing |

**Boundary tests (cheap):**
- Clarify client binary / package has no network path to executor trigger URL.
- Fire gate unit: abort after dry-run → `SealedPacketWriter` never called; executor mock call count = 0.
- Executor stub refuses invoke if stack `status != fired`.

---

## 3. File / package sketch (FUTURE standalone iOS app)

**Not created in this task.** Sketch only for when Leo clears the hard rail. Suggested working name: `abc-fire` (final name Leo-owned at create time).

```text
abc-fire/                          # NEW REPO — paused until hard rail
├── README.md                      # product one-liner + hard rails
├── Package.swift                  # or Xcodeproj + SPM local packages
├── Apps/
│   └── KitchenApp/                # SwiftUI @main — Kitchen slice target
│       ├── KitchenApp.swift
│       └── Features/
│           └── Kitchen/
│               ├── KitchenSessionView.swift
│               ├── OptionCardView.swift
│               └── DryRunSheet.swift
├── Packages/
│   ├── ABCFireIR/                 # BeliefOption, BeliefNode, ChoicePathStack, FirePacket
│   │   └── Sources/ABCFireIR/
│   ├── ABCFireSession/            # SessionStore, DiskResume, stack edit/discard
│   │   └── Sources/ABCFireSession/
│   ├── ABCFireClarify/            # ClarifyBrainClient, prompts, distinctness check
│   │   └── Sources/ABCFireClarify/
│   ├── ABCFireGate/               # confirm word, blast tier, dry-run, abort window
│   │   └── Sources/ABCFireGate/
│   └── ABCFireExecutorStub/       # Kitchen: in-process mock; later: HMAC client
│       └── Sources/ABCFireExecutorStub/
├── Fixtures/
│   └── golden-kitchen/            # G1–G6 fixtures (lift from T-2b dialogues)
└── Tests/
    ├── ABCFireIRTests/
    ├── ABCFireGateTests/          # G4 abort, G6 dry-run ordering
    └── KitchenAcceptanceTests/    # G1–G5 integration (Simulator)
```

**IR types (Swift, from IR v0):** `ClarifyMode`, `ChoiceStatus`, `BeliefOption`, `BeliefNode`, `ChoicePathStack`, plus `FirePacket` (sealed snapshot: `sessionId`, frozen `nodes`, `constraints`, `blastTier`, `confirmWordHash`, `sealedAt`). Rider attaches to **chosen** option only.

**Vidux stays here:** design authority + evidence under `vidux-main-active/plans/abc-fire-control-plane/`. App code never lands in Vidux as product home.

**Pre-repo spikes (allowed without `gh repo create`):** IR Swift types as a local SPM folder under `evidence/spikes/` or a throwaway path **outside** a new GitHub repo; clarify prompt fixture re-run; fire-gate pure logic tests. No App Store identity, no public remote.

---

## 4. Milestone order + proof gates G1–G6

Order is fixed: IR → clarify loop → persistence → fire gate → (optional) executor stub wire → acceptance. Do not jump to executor networking before G1–G5.

| Mile | Deliverable | Proof gate | Pass criterion |
|---|---|---|---|
| **M0** | Repo scaffold (after hard rail) or local SPM spike | — | Packages compile; Kitchen target launches blank session |
| **M1** | IR + SessionStore in memory | — | Stack edit/discard; rider on chosen |
| **M2** | ClarifyBrainClient + skeleton UI | **G1** | Blank intent → 3 mutually-distinct outcome-class options (Jaccard / golden rule from T-2b); if fail → freeform instead of synonym spam |
| **M3** | Pick + rider → constraints | **G2** | Chosen option + `riderText` appends to `constraints`; next turn sees them |
| **M4** | DiskResume | **G5** | Kill app mid-clarify; relaunch restores same `sessionId` + stack |
| **M5** | FireGate dry-run + confirm word | **G6** | High-blast path shows packet JSON **before** seal; wrong confirm word rejects |
| **M6** | Seal + abort | **G3**, **G4** | G3: FIRE writes immutable packet file; G4: abort after dry-run → no packet, executor stub invocations = 0 |
| **M7** | Kitchen acceptance suite | G1–G6 green | Single script/test plan receipt under app repo `Fixtures/` + link from Vidux Progress |

**Latency (non-blocking):** skeleton <200ms; p50 fill <2.5s acceptable (T-2b). Sub-second complete = residual, not M2 kill.

**Blast tiers for Kitchen v0:** start `draft-only` for dogfood packet; exercise G6 with a forced `mutate` fixture so dry-run path is proven without real mutate tools.

---

## 5. Hard rails (called out)

| Rail | Rule |
|---|---|
| **`gh repo create`** | **PAUSED.** Leo plain-language opt-in required. This plan is not that opt-in. |
| Publicize / public push | Denied by default in executor manifest |
| Clarify mutates | Never — tools=none |
| Confirmation-free fire | Never — confirm word + dry-run |
| External send / money / destructive git | Denied; need separate plan rows |
| Voice as v1 ship gate | Vetoed — Kitchen is text-only |
| Product home in Vidux | Vetoed — standalone B |
| Commit app code into `vidux-main-active` as product | No — Vidux = plan/proof only |

---

## 6. Exact next engineering step (after this plan lands)

**Do this next (no repo create):**

1. **Local IR + FireGate spike** (not a GitHub repo): add `plans/abc-fire-control-plane/evidence/spikes/kitchen-ir/` as a tiny SwiftPM package with `BeliefOption` / `BeliefNode` / `ChoicePathStack` / `FirePacket` + unit tests for rider-on-chosen, abort-before-seal (G4 logic), dry-run-before-seal ordering (G6 logic).
2. Reuse T-2b golden dialogue fixtures as JSON under that spike for G1 distinctness checks (offline; no new model spend required to start).
3. **Stop before** Xcode app target, signing, and `gh repo create`.

When Leo clears the hard rail in plain language: create private app repo from §3 sketch, move spike packages in, then execute M0→M7.

**Operator next (parallel OK):** wait on hard-rail for repo **or** continue this non-repo spike; either is valid. Confirm-word UX taste pass remains deferred until human-facing screens.

---

## Exit criteria for T-4

- [x] This file exists and names Kitchen scope, module walls, future package sketch, M0–M7 + G1–G6, hard rails, next step.
- [ ] App repo created — **not** part of T-4 (hard rail).
