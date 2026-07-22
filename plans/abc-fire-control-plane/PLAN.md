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

- Status: designing (standalone B locked; Option A dead); T-2b quality PROCEED
- Priority: 90
- Outcome: Approved design spec for the standalone ABC→FIRE app; Vidux stays control plane.
- Next: T-2c IR v0 review + T-3 design spec (agent-owned). Cross-lane: `ai-leo/vidux/recognition-mission/PLAN.md`.
- Why: Repurpose conversation reopened; Nicole barrier + on-the-go agency is the wedge.
- Validation: Spike receipt + IR draft + design sections; first vertical slice named with gates.
- Cost: Planning + cheap GLM probes; no product app code until design draft lands.
- Evidence: evidence/feasibility-spike/SPIKE-RECEIPT.md + evidence/ir-v0-schema-draft.md
- Updated: 2026-07-22

## Outcome Scorecard

| Metric | Baseline | Current | Target | Status | Proof |
|---|---|---|---|---|---|
| Design draft from Claude/Fable | none | in flight | receipted draft folded here | unproven | evidence/fable-plan-draft.md |
| Leo-approved design sections | none | not started | approaches + architecture locked | unproven | Decision Log |
| First vertical slice named | none | not started | acceptance gates written | unproven | Tasks T-3 |

## Tasks

- [completed] T-1: Read-only planning draft for ABC→FIRE (approaches + architecture + slice) — Grok build/high; Fable blocked (credits + plan-advisor sandbox 127)
- [completed] T-2: Leo vetoed Option A — "standalone B is the plan" (standalone native iOS/SwiftUI; one adaptive loop for both users)
- [completed] T-2b: Feasibility spike (make-or-break #4) — quality PASS via glm-max/glm delegate (3 distinct + narrow); sub-second remote FAIL (~10–17s). PROCEED. [validation: evidence/feasibility-spike/SPIKE-RECEIPT.md]
- [in_progress] T-2c: IR v0 — lift moussey `lib/intent-router.ts` `RouterDecisionTrace`/`RouterDecisionOption` as the per-question belief node; editable choice-path stack + rider field [validation: evidence/ir-v0-schema-draft.md started]
- [pending] T-3: Write design spec after spike (bounded job-template IR, two-brain split + executor capability manifest, blast-radius-gated distinct confirm word + dry-run/undo; read why StrongYes cut the suggested-prompt chips before rebuilding pick+rider)
- [pending] T-4: Implementation plan (writing-plans) only after spec approval; app repo creation is the Leo-gated moment

## Decision Log

- [DIRECTION] [2026-07-21] Provisional home = Option A (Vidux *is* the product). Standing veto for Leo. Reason: Leo asked for "spirit of work that i want vidux to have" and opened `/pilot` `/vidux` planning.
- [DIRECTION] [2026-07-21] Voice-test harness + car mode are adjacent lessons, not v1. Reason: Leo clarified the Nicole A/B/C barrier is the load-bearing idea.
- [DIRECTION] [2026-07-21] Living authority for this design = this file inside `vidux-main-active` (Pilot requires repo-contained authority). External `~/Development/vidux-projects/abc-fire-control-plane/PLAN.md` is a tombstone redirect.
- [DIRECTION] [2026-07-21] Planner seat switched to Grok build/high after Fable credits exhausted and `plan-advisor` sandbox-exec exit 127 on copied `claude` wrapper. Reason: Leo steer "use grok build high".
- [DIRECTION] [2026-07-21] **Option A VETOED by Leo — "standalone B is the plan."** Standalone native iOS/SwiftUI app; one adaptive loop (Nicole menu-depth ↔ car-Leo freeform); Vidux 1.0.0 remains plan/proof control plane only. Supersedes the provisional-home entry above.
- [DIRECTION] [2026-07-21] Scout verdicts folded: (1) Class A voice harness ships under SmartLittleApps/local-stt-mcp MIT identity, built from moussey voice-audio-corpus scaffolding — not on local-stt-mcp's code; (2) /amp is ritual not engine — highest lift is moussey `RouterDecisionTrace`; (3) StrongYes premise correction — shipped bugs were seam bugs, harness splits Class A (voice I/O) / Class B (real-seam probes; owned by strongyes-web voice-debug-harness PLAN).
- [DIRECTION] [2026-07-21] Mac executor = clean new agent lifting moussey's HMAC + Tailscale + `claude -p` Keychain-OAuth pattern (`app/api/lan/trigger-claude/route.ts`, `lib/lan-trigger-auth.ts`). Fire gate = blast-radius-gated distinct confirm word + dry-run/undo (amp's confirmation-free fire replaced). Standing one-line veto each.
- [DIRECTION] [2026-07-22] T-2b verdict: **PROCEED on quality**. Cheap GLM (delegate `glm-max` / `glm`) produces ≤3 mutually-distinct outcome-class options AND narrows. Remote path is multi-second (~10–17s), not sub-second — treat sub-second as UX residual (local/small model or skeleton UI), not architecture kill.

## Progress

- [2026-07-21] Plan initialized; moved in-repo for Pilot authority; branch `vidux/abc-fire-control-plane-design`.
- [2026-07-21] Fable `plan-advisor` + direct Fable failed (sandbox 127 / usage credits). Receipts in `evidence/fable-plan.receipt.json`.
- [2026-07-21] Grok `--reasoning-effort high --permission-mode plan` draft OK (12.6KB). Evidence: `evidence/grok-build-high-plan-draft.md` + `evidence/grok-build-high-plan.receipt.json`. PONG probe green. Recommendation: Option A; first slice = Nicole text ABC→FIRE with G1–G6 gates.
- [2026-07-22] T-2b COMPLETE: golden dialogues + live GLM probes + SPIKE-RECEIPT. Quality PASS; latency sub-second FAIL on remote. IR v0 draft landed at `evidence/ir-v0-schema-draft.md`. Next: finish T-2c review + T-3 design spec.
