# Implementation plan v0 — Kitchen ABC→FIRE (text)

**Date:** 2026-07-22  
**Authority:** `PLAN.md` T-4  
**Hard rail:** do **not** `gh repo create` until Leo explicitly triggers that moment. Until then, stage in a private path or existing private repo only if already authorized; default = design continues in `vidux-main-active` evidence until create gate.

## Slice name

**Kitchen text ABC→FIRE** — Nicole menu-depth first; freeform rider; no voice v1.

## Work breakdown (parallelizable after create)

| ID | Work | Owner class | Proof |
|---|---|---|---|
| I1 | SwiftUI shell: Intent session screen + option cards | iOS codegen (GLM draft ok) | Preview + unit on stack reduce |
| I2 | Clarify client: JSON schema for BeliefNode; call cheap model | network + parse | golden D1–D5 fixtures offline |
| I3 | ChoicePathStack disk resume | local persistence | kill/relaunch restores |
| I4 | FIRE packet seal + dry-run sheet | product UX | packet snapshot golden |
| I5 | Blast-radius tiers + confirm word | product UX | high-blast requires dry-run |
| I6 | Mac executor stub (HMAC/Tailscale pattern later) | deferred post-FIRE | mock executor receipt |
| I7 | `/taste` pass on human-facing strings | taste | no synonym spam chips |

## Sequencing

1. **Pre-repo (now):** freeze IR + design-spec Decision Log ✅; golden fixtures ✅; implementation plan ✅
2. **Repo create gate (hard rail):** pause for Leo at `gh repo create`
3. **Post-create:** I1–I5 in order; I6 stub; I7 continuous
4. **Not v1:** voice car mode, public publish of app

## Latency strategy

- Show skeleton cards <200ms
- Fill from cheap model when ready (~10s remote GLM OK for v0 dogfood)
- Residual: local small model for sub-second

## Out of scope this plan

- Public app store
- Real iMessage send
- Moussey revive

## Exit

G1–G6 from design-spec-v0 green on device or Simulator; resume packet in plan.
