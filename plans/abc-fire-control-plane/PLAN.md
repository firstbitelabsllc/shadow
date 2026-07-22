# ABC → Fire Control Plane (standalone app design)

## Purpose

Design (then later ship) a **standalone native iOS/SwiftUI app**: LLM-driven
A/B/C clarifying choices until the human says **FIRE**, one adaptive loop that
slides between menu-depth (Nicole: "I don't know what to ask") and freeform
(car-Leo, hands-free). Vidux 1.0.0 stays the plan/proof control plane — it is
NOT the product home (Option A vetoed). Not a desktop typing port. Not a
moussey rebuild — moussey voice parts are salvage.

## Evidence

- [Source: Leo chat 2026-07-21] Spirit = SAT multiple-choice vs freeform; Nicole wedge; Paseo lessons for plumbing.
- [Source: memory moussey-killed-adopt-verdict] Adopt Claude iOS + Remote Control; Paseo second; no Pipecat/LiveKit rebuild.
- [Source: memory vidux-repurpose-intent-2026-07-20] Vidux 1.0.0 + claudux 2.0 cut done; repurpose direction Leo-gated.
- [Source: ~/Development/vidux-main-active @ d5e89a49] Clean 1.0.0 plan/proof/resume surface.

## Constraints

**ALWAYS:**
- New-repo rule: Leo explicitly opted in to a standalone app repo (fcp-workflow-style exception, "standalone B is the plan"); the actual `gh repo create` still pauses as a hard rail.
- Plan/proof/resume stay Vidux-owned; model routing stays Pilot/host-owned.
- Do not revive moussey glue; borrow patterns from Paseo / Remote Control only.
- FIRE is the only gate that starts mutating/expensive agent work.

**NEVER:**
- Port desktop chat UX to mobile as the product.
- Treat voice-test harness or car mode as v1 scope without a new plan row.
- Claim provider/delegate health without a live receipt.

## Operator Brief

- Status: designing (standalone B locked; Option A dead); T-4 implementation plan landed; app repo still hard-rail paused
- Priority: 90
- Outcome: Approved design spec for the standalone ABC→FIRE app; Vidux stays control plane.
- Next: Wait on hard-rail for `gh repo create` **or** continue non-repo spikes (`evidence/spikes/kitchen-ir/` IR + FireGate unit tests). Cross-lane: `ai-leo/vidux/recognition-mission/PLAN.md`.
- Why: Repurpose conversation reopened; Nicole barrier + on-the-go agency is the wedge.
- Validation: Spike receipt + golden dialogues + IR + design-spec + T-4 plan (Kitchen G1–G6 + M0–M7).
- Cost: Planning done through T-4; no product app repo until hard-rail; non-repo SPM spike OK.
- Evidence: evidence/T-4-implementation-plan.md (+ ir-v0, design-spec-v0, t2b receipts)
- Updated: 2026-07-22

## Outcome Scorecard

| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| Design draft from Claude/Fable | none | Grok draft + agent spec | receipted draft folded here | met | evidence/design-spec-v0.md |
| Design sections (agent-default) | none | IR + two-brain + fire gate locked | approaches + architecture locked | met | Decision Log |
| First vertical slice named | none | Kitchen text ABC→FIRE G1–G6 | acceptance gates written | met | Tasks T-3 / design-spec §8 |
| Implementation plan (writing-plans) | none | Kitchen M0–M7 + module walls | plan file + next step | met | evidence/T-4-implementation-plan.md |

## Tasks

- [completed] T-1: Read-only planning draft for ABC→FIRE (approaches + architecture + slice) — Grok build/high; Fable blocked (credits + plan-advisor sandbox 127)
- [completed] T-2: Leo vetoed Option A — "standalone B is the plan" (standalone native iOS/SwiftUI; one adaptive loop for both users)
- [completed] T-2b: Feasibility spike (make-or-break #4) — quality PASS (≤3 mutually-distinct + narrow) on Haiku / gpt-5.3-chat / sibling glm-max; strict sub-second complete FAIL (~2–3s Haiku gen, ~10s GLM delegate); TTFT ~0.5s Haiku. PROCEED. [validation: evidence/t2b-feasibility-spike.receipt.md + evidence/golden-dialogues-t2b.md]
- [completed] T-2c: IR v0 — per-question belief node (`BeliefNode`/`BeliefOption`) + editable `ChoicePathStack` + rider-on-chosen; defaults folded to Decision Log. [validation: evidence/ir-v0-schema-draft.md]
- [completed] T-3: Design spec v0 — two-brain, fire gate (confirm word + dry-run/undo), executor allow-list, Kitchen slice G1–G6, StrongYes outcome-class rule; defaults folded to Decision Log. Deferred (not blocking): confirm-word UX taste pass; local sub-second model. [validation: evidence/design-spec-v0.md]
- [completed] T-4: Implementation plan (writing-plans) only — Kitchen text slice, module walls, future package sketch, M0–M7 + G1–G6, hard rails, next = non-repo IR/FireGate spike. App repo creation remains Leo-gated hard rail. [validation: evidence/T-4-implementation-plan.md]

## Decision Log

- [DIRECTION] [2026-07-21] Provisional home = Option A (Vidux *is* the product). Standing veto for Leo. Reason: Leo asked for "spirit of work that i want vidux to have" and opened `/pilot` `/vidux` planning.
- [DIRECTION] [2026-07-21] Voice-test harness + car mode are adjacent lessons, not v1. Reason: Leo clarified the Nicole A/B/C barrier is the load-bearing idea.
- [DIRECTION] [2026-07-21] Living authority for this design = this file inside `vidux-main-active` (Pilot requires repo-contained authority). External `~/Development/vidux-projects/abc-fire-control-plane/PLAN.md` is a tombstone redirect.
- [DIRECTION] [2026-07-21] Planner seat switched to Grok build/high after Fable credits exhausted and `plan-advisor` sandbox-exec exit 127 on copied `claude` wrapper. Reason: Leo steer "use grok build high".
- [DIRECTION] [2026-07-21] **Option A VETOED by Leo — "standalone B is the plan."** Standalone native iOS/SwiftUI app; one adaptive loop (Nicole menu-depth ↔ car-Leo freeform); Vidux 1.0.0 remains plan/proof control plane only. Supersedes the provisional-home entry above.
- [DIRECTION] [2026-07-21] Scout verdicts folded: (1) Class A voice harness ships under SmartLittleApps/local-stt-mcp MIT identity, built from moussey voice-audio-corpus scaffolding — not on local-stt-mcp's code; (2) /amp is ritual not engine — highest lift is moussey `RouterDecisionTrace`; (3) StrongYes premise correction — shipped bugs were seam bugs, harness splits Class A (voice I/O) / Class B (real-seam probes; owned by strongyes-web voice-debug-harness PLAN).
- [DIRECTION] [2026-07-21] Mac executor = clean new agent lifting moussey's HMAC + Tailscale + `claude -p` Keychain-OAuth pattern (`app/api/lan/trigger-claude/route.ts`, `lib/lan-trigger-auth.ts`). Fire gate = blast-radius-gated distinct confirm word + dry-run/undo (amp's confirmation-free fire replaced). Standing one-line veto each.
- [DIRECTION] [2026-07-22] T-2b verdict: **PROCEED on quality**. Cheap models produce ≤3 mutually-distinct options AND narrow (Haiku / gpt-5.3-chat live; sibling glm-max/glm via delegate). Strict sub-second **complete** turn is NO-GO (~2–3s Haiku wall, ~10s+ GLM delegate); Haiku TTFT ~0.5s supports streaming skeleton UX. Sub-second complete = residual, not architecture kill. Standing veto: Leo can veto PROCEED if hard sub-second complete options are required before design. Proof: `evidence/t2b-feasibility-spike.receipt.md` + `evidence/golden-dialogues-t2b.md`.
- [DIRECTION] [2026-07-22] **IR belief node shape (agent-owned).** One clarify turn = `BeliefNode` (prompt, mode menu|freeform|hybrid, ≤3 `BeliefOption`s, considered/discarded). Session = editable `ChoicePathStack` until FIRE freezes a sealed packet. Rider text attaches to the *chosen* option (not a 4th peer). Nicole menu starts with 3 outcome classes; car-Leo may return 2 + freeform. IR lives in app session store pre-FIRE; Vidux plan/proof only after FIRE. Options must differ by outcome class (StrongYes chip lesson: synonym spam → show freeform instead). Veto: "rider is peer" / "always 3" / "every turn in Vidux". Proof: `evidence/ir-v0-schema-draft.md`.
- [DIRECTION] [2026-07-22] **Two-brain split (agent-owned).** Clarify brain = cheap model, tools=none, never mutates/sends/spends. Executor brain = Host/Pilot-selected, runs only after FIRE, tools from an explicit capability allow-list (draft files in claimed worktree, private draft PR, read plan/ledger). Denied by default: public repo create/push, external send, real money, destructive git. Veto: "clarify may mutate". Proof: `evidence/design-spec-v0.md` §§3,7.
- [DIRECTION] [2026-07-22] **Fire gate (agent-owned).** Distinct confirm word per session (not always the word FIRE when blast is high); blast tiers read-only → draft-only → mutate → external-send → money; dry-run shows packet JSON before commit; undo/abort until executor acks start. Veto: "confirmation-free fire". Proof: `evidence/design-spec-v0.md` §6.
- [DIRECTION] [2026-07-22] **First vertical slice (agent-owned).** Kitchen text ABC→FIRE (iOS SwiftUI, no voice). Gates G1 blank→3 distinct options; G2 pick+rider updates constraints; G3 FIRE seals packet file; G4 abort = no executor side effects; G5 resume restores stack from disk; G6 dry-run before high-blast FIRE. Deferred: confirm-word UX taste copy; local sub-second model. Veto: "voice is ship gate for v1". Proof: `evidence/design-spec-v0.md` §8.
- [DIRECTION] [2026-07-22] **T-4 implementation plan (agent-owned).** Kitchen text only; clarify / fire-gate / executor walls; future `abc-fire` package sketch (no `gh repo create`); milestones M0–M7 mapped to G1–G6; next engineering = local SPM IR+FireGate spike under `evidence/spikes/kitchen-ir/`. Veto: treat plan as repo-create authorization. Proof: `evidence/T-4-implementation-plan.md`.

## Progress

- [2026-07-21] Plan initialized; moved in-repo for Pilot authority; branch `vidux/abc-fire-control-plane-design`.
- [2026-07-21] Fable `plan-advisor` + direct Fable failed (sandbox 127 / usage credits). Receipts in `evidence/fable-plan.receipt.json`.
- [2026-07-21] Grok `--reasoning-effort high --permission-mode plan` draft OK (12.6KB). Evidence: `evidence/grok-build-high-plan-draft.md` + `evidence/grok-build-high-plan.receipt.json`. PONG probe green. Recommendation: Option A; first slice = Nicole text ABC→FIRE with G1–G6 gates.
- [2026-07-22] T-2b COMPLETE (Lane A): required receipts `evidence/t2b-feasibility-spike.receipt.md` + `evidence/golden-dialogues-t2b.md` (Nicole menu-depth + car-Leo freeform live samples, Jaccard distinctness, Haiku TTFT ~0.5s). Sibling GLM-delegate samples under `evidence/feasibility-spike/`. Quality GO; sub-second complete NO-GO; product PROCEED.
- [2026-07-22] design-spec-v0.md drafted (two-brain, fire gate, first slice G1–G6). Soft gate agent-owned.
- [2026-07-22] T-2c + T-3 COMPLETE: IR v0 + design-spec v0 folded into Decision Log (belief node, two-brain, fire gate, Kitchen G1–G6). Next = T-4 implementation plan only; app repo still hard-rail paused.
- [2026-07-22] T-4 COMPLETE: `evidence/T-4-implementation-plan.md` (Kitchen scope, module walls, future package sketch, M0–M7↔G1–G6, hard rails). Interim `implementation-plan-v0.md` superseded (tombstone). Next = wait hard-rail for app repo **or** non-repo `evidence/spikes/kitchen-ir/` spike.
