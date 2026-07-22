# Golden dialogues — ABC→FIRE feasibility

**Date:** 2026-07-22  
**Gate:** T-2b / mission R3 — cheap model produces ≤3 mutually-distinct options AND narrows.

## G1 — Nicole blank-box (menu-depth)

**User:** I don't know what to ask. I just want help with dinner tonight.

**Good clarify (≤3 distinct outcome classes):**
- A: Use what's already in the fridge (inventory-first)
- B: Order takeout under a budget
- C: Cook one simple 20-minute recipe with a short list

**Bad (synonyms / essay):**
- A: Help me decide dinner
- B: Figure out what to eat
- C: Meal ideas

**Narrow on pick A:** "Any dietary constraints or people counting?" → next options stay inventory-first.

## G2 — Nicole partial + rider

**User:** Something for me and Leo, not too heavy.

**Options:**
- A: Two light pasta bowls
- B: Big shared salad + protein
- C: Soup + bread night

**User pick:** A and also no dairy.

**Stack constraint:** `no dairy` rider on A; next turn offers dairy-free pasta variants only.

## G3 — Car-Leo freeform (hands-busy)

**User:** text Nicole I'll be 20 late and ask if she needs anything from the store

**Options (may be 2 + freeform):**
- A: Draft iMessage (edit before send) — HARD RAIL: no send without FIRE
- B: Add calendar note only
- C: Say it your way (dictation rider)

**FIRE:** only after explicit confirm word; dry-run shows packet.

## G4 — Ambiguous work ask

**User:** Can you fix the app?

**Options must force disambiguation of outcome class:**
- A: Crash / error right now (debug)
- B: Visual / polish change
- C: New feature request

Not: three ways of saying "help with the app".

## G5 — Already-clear intent (should narrow fast → ready)

**User:** Open a draft PR on resplit-web that renames the Trip Link sheet title to "Shared trip" and nothing else.

**Options:**
- A: FIRE with that exact scope
- B: Also update empty-state copy
- C: Clarify which screen first

**Pass criterion:** A is clearly distinct; model does not invent a 4th scope.

## Scoring rubric (mechanical)

| Check | Pass |
|---|---|
| Count | 2–3 options |
| Distinctness | different outcome class (not synonym labels) |
| Length | labels ≤8 words; no multi-paragraph essay |
| Narrow | after a pick, next options inherit constraints |
| Latency | p50 clarify turn <1000ms on cheap model (stretch); <2500ms acceptable for remote GLM |
