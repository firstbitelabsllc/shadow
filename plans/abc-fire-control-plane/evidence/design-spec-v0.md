# ABC→FIRE design spec v0 (agent-owned draft)

**Date:** 2026-07-22  
**Authority:** `plans/abc-fire-control-plane/PLAN.md`  
**Status:** folded into PLAN Decision Log (2026-07-22); T-3 completed  
**Inputs:** T-2b SPIKE-RECEIPT (quality PROCEED), IR v0 draft, Grok planning draft (Option A superseded by Leo standalone-B lock), scout lifts.

Standing veto: rewrite any section; soft "approval" is agent-owned + revertable.

## 1. Product one-liner

A **standalone native iOS/SwiftUI** app that turns blank-box anxiety into
**A/B/C clarifying choices** until the human says a blast-radius-gated **FIRE**
word — one adaptive loop for Nicole (menu-depth) and car-Leo (freeform).

Vidux 1.0.0 remains plan/proof/resume control plane only (not the product home).

## 2. Jobs

| Job | Who | Success |
|---|---|---|
| Escape blank box | Nicole | ≤3 concrete outcome-class options without authoring a prompt |
| Rider | Nicole | "A and also…" attaches constraint without losing the pick |
| Hands-busy clarify | car-Leo | 2–3 options or freeform rider; no accidental send/mutate |
| Sealed handoff | both | FIRE freezes choice-path stack into immutable packet for Mac executor |

## 3. Two-brain split

| Brain | Role | Model class | Tools |
|---|---|---|---|
| **Clarify** | Propose ≤3 options + optional narrow Q | Cheap (GLM / later local) | None |
| **Executor** | Runs only after FIRE | Host/Pilot-selected | Capability manifest only |

Clarify never mutates repos, never sends messages, never spends money.

## 4. Session + IR (from IR v0)

- `ChoicePathStack` + `BeliefNode` + `BeliefOption` (see `ir-v0-schema-draft.md`)
- Modes: `menu` | `freeform` | `hybrid`
- Rider field on chosen option
- Editable stack pre-FIRE; immutable after FIRE except abort

## 5. Latency budget (post-spike)

| Path | Target | Reality (2026-07-22) |
|---|---|---|
| Remote GLM clarify | aspirational <1s | ~10–17s via delegate+opencode |
| v0 ship | <2.5s p50 OR skeleton UI <200ms | skeleton + async fill acceptable |
| Residual | on-device / smaller local model | not blocking architecture |

## 6. Fire gate

- Distinct confirm word chosen per session (not always "FIRE" alone if blast high)
- Blast-radius tiers: read-only / draft-only / mutate / external-send / money
- Dry-run shows packet JSON before commit
- Undo/abort path until executor acks start

## 7. Mac executor capability manifest (v0)

Allowed after FIRE (explicit allow-list):
- Write draft files in claimed worktree paths
- Open draft PR on private repos
- Read plan/ledger

Denied by default (hard rails):
- `gh repo create` / publicize / public push
- External send (mail/iMessage/Slack) without second gate
- Real money
- Destructive git

Pattern lift (not copy-glue): moussey HMAC + Tailscale + Keychain OAuth trigger.

## 8. First vertical slice (text-only Nicole)

**Name:** Kitchen ABC→FIRE text loop  
**Surface:** iOS SwiftUI, no voice v1  
**Gates:**
- G1: blank intent → 3 distinct options
- G2: pick + rider updates stack constraints
- G3: FIRE produces sealed packet file
- G4: abort leaves no executor side effects
- G5: resume after kill restores stack from disk
- G6: dry-run before high blast-radius FIRE

## 9. Non-goals v1

- Voice car mode as ship gate
- Port desktop chat UX
- Revive moussey product
- Host model routing inside the app (Pilot/host owns after FIRE)
- Public app repo create (hard rail)

## 10. StrongYes lesson (chips)

StrongYes cut suggested-prompt chips when they became synonym spam / ignored.
Rule for us: options must be **outcome classes**, scored by golden dialogues;
if distinctness fails, show "say it your way" freeform instead of three essays.

## 11. Open residuals

- Local model timing for true sub-second
- Confirm-word UX copy (`/taste` pass before human-facing)
- App repo creation moment (Leo-gated hard rail)

## Exit → T-4

Defaults are in Decision Log. Write implementation plan only; do not create
the app repo until hard-rail pause. Residual taste pass (confirm-word UX copy)
before human-facing screens.
